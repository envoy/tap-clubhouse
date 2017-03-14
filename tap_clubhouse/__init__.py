#!/usr/bin/env python3

import sys
import time
import datetime
from operator import itemgetter

import requests
import singer

from tap_clubhouse import utils


REQUIRED_CONFIG_KEYS = ["api_token", "start_date"]
BASE_URL = "https://api.clubhouse.io"
CONFIG = {}
STATE = {}

ENDPOINTS = {
    "stories": "/api/v1/stories/search",
    "workflows": "/api/v1/workflows",
    "users": "/api/v1/users",
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
    rows = request(url, params, data).json()

    # fix clubhouse user not having created_at/updated_at
    if entity == "users":
        for row in rows:
            permission = row["permissions"][0]
            row["created_at"] = permission["created_at"]
            row["updated_at"] = permission["updated_at"]

    for row in sorted(rows, key=itemgetter("updated_at")):
        yield row


def sync_stories():
    singer.write_schema("stories", utils.load_schema("stories"), ["id"])

    start = get_start("stories")
    data = {
        "updated_at_start": start,
    }

    for _, row in enumerate(gen_request("stories", data=data)):
        LOGGER.info("Story {}: Syncing".format(row["id"]))
        utils.update_state(STATE, "stories", row["updated_at"])
        singer.write_record("stories", row)

    singer.write_state(STATE)


def sync_time_filtered(entity):
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

    sync_stories()
    sync_time_filtered("workflows")
    sync_time_filtered("users")

    LOGGER.info("Completed sync")


def main():
    config, state = utils.parse_args(REQUIRED_CONFIG_KEYS)
    CONFIG.update(config)
    STATE.update(state)
    do_sync()


if __name__ == "__main__":
    main()
