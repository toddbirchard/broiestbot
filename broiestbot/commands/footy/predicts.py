"""Match breakdown of all currently live fixtures."""
from datetime import datetime
from typing import List, Optional
from datetime import datetime

import requests
from requests.exceptions import HTTPError
from emoji import emojize

from config import (
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    FOOTY_PREDICTS_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
    FOOTY_XI_ENDPOINT,
    FOOTY_LIVE_LEAGUES_ODDS_IDS,
)
from logger import LOGGER

from .util import get_preferred_time_format, get_preferred_timezone, get_current_day


def footy_predicts_today(room: str, username: str) -> Optional[str]:
    """
    Fetch odds for fixtures being played today.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: Optional[str]
    """
    try:
        todays_predicts = "\n\n\n\n"
        fixture_ids = fetch_footy_fixtures_today(room, username)
        if bool(fixture_ids) is False:
            return emojize(":sad_but_relieved_face: No fixtures today :sad_but_relieved_face:", language="en")
        for fixture_id in fixture_ids:
            url = f"{FOOTY_PREDICTS_ENDPOINT}/{fixture_id}"
            resp = requests.get(url, headers=FOOTY_HTTP_HEADERS, timeout=HTTP_REQUEST_TIMEOUT)
            predictions = resp.json()["api"]["predictions"]
            for prediction in predictions:
                home_chance = prediction["winning_percent"]["home"]
                away_chance = prediction["winning_percent"]["away"]
                draw_chance = prediction["winning_percent"]["draws"]
                home_name = prediction["teams"]["home"]["team_name"]
                away_name = prediction["teams"]["away"]["team_name"]
                todays_predicts = (
                    todays_predicts + f"{away_name} {away_chance} @ {home_name} {home_chance} (draw {draw_chance})\n"
                )
        return todays_predicts
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy predicts: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy predicts: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy predicts: {e}")


def fetch_footy_fixtures_today(room: str, username: str) -> Optional[List[int]]:
    """
    Gets fixture IDs of fixtures being played today.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: Optional[List[int]]
    """
    try:
        today = datetime.now()
        display_date, tz = get_preferred_time_format(today, room, username)
        params = {"date": display_date}
        params.update(get_preferred_timezone(room, username))
        resp = requests.get(
            FOOTY_FIXTURES_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        fixtures_response = resp.json().get("response")
        if fixtures_response:
            return [
                fixture["fixture"]["id"]
                for fixture in fixtures_response
                if fixture["league"]["id"] in FOOTY_LEAGUES.values()
            ]
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy fixtures: {e}")


def fetch_live_odds_for_fixtures(room: str, username: str):
    """ """
    try:
        today = get_current_day(room)
        season = datetime.now().year
        params = {"season", season, ""}
        resp = requests.get(FOOTY_XI_ENDPOINT, params=params, headers=FOOTY_HTTP_HEADERS)
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy fixtures: {e}")
