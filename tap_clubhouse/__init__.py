#!/usr/bin/env python3

import sys
import time
import datetime
import urllib.parse
from operator import itemgetter

import requests
import singer

from tap_clubhouse import utils


REQUIRED_CONFIG_KEYS = ["api_token", "start_date"]
BASE_URL = "https://api.clubhouse.io"
CONFIG = {}
STATE = {}

ENDPOINTS = {
    "stories": "/api/v2/search/stories",
    "epics": "/api/v2/search/epics",
    "projects": "/api/v2/projects",
    "milestones": "/api/v2/milestones",
    "teams": "/api/v2/teams",
    "members": "/api/v2/members",
}

LOGGER = singer.get_logger()
SESSION = requests.Session()


def get_url(endpoint):
    return BASE_URL + ENDPOINTS[endpoint]


@utils.ratelimit(100, 60)
def request(url, params=None, data=None):
    params = params or {}

    if data:
        verb = "POST"
    else:
        verb = "GET"
        data = {}

    headers = {}
    if "user_agent" in CONFIG:
        headers["User-Agent"] = CONFIG["user_agent"]

    req = requests.Request(verb, url, params=params, data=data, headers=headers).prepare()
    LOGGER.info("{} {}".format(verb, req.url))
    resp = SESSION.send(req)

    if "Retry-After" in resp.headers:
        retry_after = int(resp.headers["Retry-After"])
        LOGGER.info("Rate limit reached. Sleeping for {} seconds".format(retry_after))
        time.sleep(retry_after)
        return request(url, params)

    elif resp.status_code >= 400:
        LOGGER.error("{} {} [{} - {}]".format(verb, req.url, resp.status_code, resp.content))
        sys.exit(1)

    return resp


def get_start(entity):
    if entity not in STATE:
        STATE[entity] = CONFIG["start_date"]

    else:
        # Munge the date in the state due to how Clubhouse behaves. Clubhouse keeps
        # returning the same record on subsequent runs because it treats
        # `updated_at_start` as inclusive
        start = utils.strptime(STATE[entity])
        STATE[entity] = utils.strftime(start + datetime.timedelta(seconds=1))

    return STATE[entity]


def gen_request(entity, params=None, data=None):
    url = get_url(entity)
    params = params or {}
    params["token"] = CONFIG["api_token"]
    data = data or {}
    next_params = None
    resp = request(url, params, data).json()

    if isinstance(resp, dict) and "data" in resp.keys():
        rows = resp["data"]
        if "next" in resp.keys() and resp["next"] != None:
            next_params = urllib.parse.parse_qs(urllib.parse.urlparse(resp["next"]).query)
    else:
        rows = resp

    for row in sorted(rows, key=itemgetter("updated_at")):
        yield row

    if next_params != None:
        yield from gen_request(entity, params=next_params)


def sync_search(entity):
    singer.write_schema(entity, utils.load_schema(entity), ["id"])

    start = get_start(entity)
    start_date = start.partition("T")[0]
    end_date = datetime.date.today().strftime("%Y-%m-%d")

    params = {
        "page_size": 25,
        "query": "updated:" + start_date + ".." + end_date,
    }

    LOGGER.info("Syncing {} from {}".format(entity, start))
    for _, row in enumerate(gen_request(entity, params=params)):
        if row["updated_at"] >= start:
            utils.update_state(STATE, entity, row["updated_at"])
            singer.write_record(entity, row)

    singer.write_state(STATE)


def sync_list(entity):
    singer.write_schema(entity, utils.load_schema(entity), ["id"])

    start = get_start(entity)

    LOGGER.info("Syncing {} from {}".format(entity, start))
    for row in gen_request(entity):
        if row["updated_at"] >= start:
            utils.update_state(STATE, entity, row["updated_at"])
            singer.write_record(entity, row)

    singer.write_state(STATE)


def do_sync():
    LOGGER.info("Starting Clubhouse sync")

    sync_search("stories")
    sync_search("epics")
    sync_list("projects")
    sync_list("milestones")
    sync_list("teams")
    sync_list("members")

    LOGGER.info("Completed sync")


def main():
    config, state = utils.parse_args(REQUIRED_CONFIG_KEYS)
    CONFIG.update(config)
    STATE.update(state)
    do_sync()


if __name__ == "__main__":
    main()
