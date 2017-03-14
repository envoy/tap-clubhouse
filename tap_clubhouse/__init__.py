#!/usr/bin/env python3

import sys
import time
import datetime

import requests
import singer

from tap_clubhouse import utils
from operator import itemgetter


REQUIRED_CONFIG_KEYS = ["api_token", "start_date"]
BASE_URL = "https://api.clubhouse.io"
CONFIG = {}
STATE = {}

ENDPOINTS = {
    "stories": "/api/v1/stories/search",
}

LOGGER = singer.get_logger()
SESSION = requests.Session()


def get_url(endpoint, **kwargs):
    return BASE_URL + ENDPOINTS[endpoint].format(**kwargs)


@utils.ratelimit(100, 60)
def request(url, params=None, data=None):
    params = params or {}
    data = data or {}
    headers = {}
    if "user_agent" in CONFIG:
        headers["User-Agent"] = CONFIG["user_agent"]

    req = requests.Request("POST", url, params=params, data=data, headers=headers).prepare()
    LOGGER.info("POST {}".format(req.url))
    resp = SESSION.send(req)

    if "Retry-After" in resp.headers:
        retry_after = int(resp.headers["Retry-After"])
        LOGGER.info("Rate limit reached. Sleeping for {} seconds".format(retry_after))
        time.sleep(retry_after)
        return request(url, params)

    elif resp.status_code >= 400:
        LOGGER.error("POST {} [{} - {}]".format(req.url, resp.status_code, resp.content))
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


def gen_request(url, params=None, data=None):
    params = params or {}
    params["token"] = CONFIG["api_token"]
    data = data or {}
    rows = request(url, params, data).json()
    for row in sorted(rows, key=itemgetter("updated_at")):
        yield row


def sync_stories():
    singer.write_schema("stories", utils.load_schema("stories"), ["id"])

    start = get_start("stories")
    data = {
        "updated_at_start": start,
    }

    for _, row in enumerate(gen_request(get_url("stories"), data=data)):
        LOGGER.info("Story {}: Syncing".format(row["id"]))
        utils.update_state(STATE, "stories", row["updated_at"])
        singer.write_record("stories", row)

    singer.write_state(STATE)


def do_sync():
    LOGGER.info("Starting Clubhouse sync")

    sync_stories()

    LOGGER.info("Completed sync")


def main():
    config, state = utils.parse_args(REQUIRED_CONFIG_KEYS)
    CONFIG.update(config)
    STATE.update(state)
    do_sync()


if __name__ == "__main__":
    main()
