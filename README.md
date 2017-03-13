# tap-freshdesk

This is a [Singer](https://singer.io) tap that produces JSON-formatted data following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

This tap:
- Pulls raw data from Clubhouse's [REST API](https://clubhouse.io/api/v1/)
- Extracts the following resources from Freshdesk:
  - [Stories](https://clubhouse.io/api/v1/#stories)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state


## Quick start

1. Install

    ```bash
    > pip install tap-clubhouse
    ```

2. Get your Clubhouse API Key

    Login to your Clubhouse account, navigate to Your Account > API Tokens
    page, and generate a new token. You'll need it for the next step.

3. Create the config file

    Create a JSON file called `config.json` containing the api token you just generated.

    ```json
    {"api_token": "your-api-token",
     "start_date": "2017-01-01T00:00:00Z"}
    ```

4. [Optional] Create the initial state file

    You can provide JSON file that contains a date for the API endpoints
    to force the application to only fetch data newer than those dates.
    If you omit the file it will fetch all Clubhouse data

    ```json
    {"stories": "2017-01-17T20:32:05Z"}
    ```

    If you optionally save state when you run this tap, the state file
    may look slightly different on subsequent runs. It'll be in the format
    that singer writes it out as.

    ```json
    {"value": {"stories": "2017-01-17T20:32:05Z"}, "type": "STATE"}
    ```

5. Run the application

    `tap-clubhouse` can be run with:

    ```bash
    tap-clubhouse --config config.json [--state state.json]
    ```

6. [Optional] Save state

    ```bash
    › tap-clubhouse --config config.json --state state.json >> state.json
    › tail -1 state.json > state.json.tmp && mv state.json.tmp state.json
    ```

---

Copyright &copy; 2017 Envoy
