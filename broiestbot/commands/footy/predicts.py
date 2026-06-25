"""NMatch predictions for fixtures occurring today."""

from datetime import datetime
from typing import List, Optional

import requests
from emoji import emojize
from logger import LOGGER
from requests.exceptions import HTTPError

from config import (
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    FOOTY_ODDS_ENDPOINT_2,
    HTTP_REQUEST_TIMEOUT,
)

from .util import (
    abbreviate_team_name,
    get_current_day,
    get_preferred_timezone,
    get_season_year,
)


def footy_today_fixtures_odds(room: str, username: str) -> Optional[str]:
    """
    Fetch odds for fixtures being played today.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: Optional[str]
    """
    try:
        i = 0
        today_fixtures_odds = "\n\n\n"
        tz_name = get_preferred_timezone(room, username)
        for league_name, league_id in FOOTY_LEAGUES.items():
            league_fixtures = fetch_today_fixtures_by_league(league_id, room, tz_name)
            if league_fixtures:
                league_fixture_odds = fetch_today_fixture_odds_by_league(league_id, room, tz_name)
                if league_fixture_odds is not None and i < 5:
                    fixture_odds = parse_fixture_odds(league_name, league_fixtures, league_fixture_odds, room, username)
                    if fixture_odds:
                        if i > 0:
                            today_fixtures_odds += "---------------\n\n"
                        today_fixtures_odds += f"{fixture_odds}\n"
                i += 1
        if today_fixtures_odds != "\n\n\n":
            return today_fixtures_odds
        return emojize(
            ":soccer_ball: :cross_mark: sry no fixtures today :( :cross_mark: :soccer_ball:",
            language="en",
        )
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy predicts: {e.response.content}")
        return emojize(":yellow_square: trash API couldnt find footy odds smdh :yellow_square:", language="en")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy predicts: {e}")
        return emojize(":yellow_square: trash API couldnt find footy odds smdh :yellow_square:", language="en")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy predicts: {e}")
        return emojize(":yellow_square: trash API couldnt find footy odds smdh :yellow_square:", language="en")


def fetch_today_fixtures_by_league(league_id: int, room: str, tz_name: str) -> Optional[List[dict]]:
    """
    Fetch all upcoming fixtures for the current date.

    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str tz_name: Name of user who triggered the command.

    :returns: Optional[List[dict]]
    """
    try:
        today = get_current_day(room)
        params = {
            "date": today.strftime("%Y-%m-%d"),
            "league": league_id,
            "season": get_season_year(league_id),
            "timezone": tz_name,
        }
        resp = requests.get(
            FOOTY_FIXTURES_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        return resp.json().get("response")
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def fetch_today_fixture_odds_by_league(league_id: int, room: str, tz_name: str) -> Optional[dict]:
    """
    Get all fixtures scheduled for today's date.

    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str tz_name:

    :returns: Optional[dict]
    """
    try:
        today = get_current_day(room)
        params = {
            "date": today.strftime("%Y-%m-%d"),
            "league": league_id,
            "season": get_season_year(league_id),
            "bookmaker": 8,
            "bet": 1,
            "timezone": tz_name,
        }
        resp = requests.get(
            FOOTY_ODDS_ENDPOINT_2, params=params, headers=FOOTY_HTTP_HEADERS, timeout=HTTP_REQUEST_TIMEOUT
        )
        return resp.json().get("response")
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy fixtures: {e}")


def map_odds_by_fixture_id(fixtures_odds: List[dict]) -> dict:
    """
    Build a lookup of Match Winner odds keyed by fixture ID.

    The fixtures and odds endpoints are separate API calls whose responses are not
    guaranteed to be ordered identically, so odds must be matched to a fixture by ID
    rather than by list position.

    :param List[dict] fixtures_odds: Raw JSON response of today's fixtures' odds.

    :returns: dict
    """
    odds_by_fixture_id = {}
    for odds_entry in fixtures_odds:
        fixture_id = odds_entry.get("fixture", {}).get("id")
        bookmakers = odds_entry.get("bookmakers")
        if fixture_id is None or not bookmakers:
            continue
        bets = bookmakers[0].get("bets")
        if not bets:
            continue
        odds_by_fixture_id[fixture_id] = bets[0].get("values", [])
    return odds_by_fixture_id


def get_outcome_odds(values: List[dict], outcome: str) -> str:
    """
    Look up the odds for a single match outcome by its name.

    API-Football does not guarantee the ordering of the `values` array, so outcomes
    must be matched on the `value` field ("Home"/"Draw"/"Away") rather than by index;
    otherwise home and away odds can be silently swapped.

    :param List[dict] values: List of outcome/odd pairs for a fixture.
    :param str outcome: Name of the outcome to look up ("Home", "Draw", or "Away").

    :returns: str
    """
    return next((value["odd"] for value in values if value.get("value") == outcome), "N/A")


def parse_fixture_odds(
    league_name: str, fixtures: dict, fixtures_odds: dict, room: str, username: str
) -> Optional[str]:
    """
    Parse fixture details and odds.

    :param int league_name: Name of the footy league/cup.
    :param dict fixtures: Raw JSON response of today's fixtures.
    :param dict fixtures_odds: Raw JSON response of today's fixtures' odds.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    try:
        odds_by_fixture_id = map_odds_by_fixture_id(fixtures_odds)
        fixtures_odds_response = f"<b>{league_name}</b>\n"
        for i, fixture in enumerate(fixtures):
            values = odds_by_fixture_id.get(fixture["fixture"]["id"])
            if values and i < 7:
                fixture_start_time = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z").time()
                home_team = abbreviate_team_name(fixture["teams"]["home"]["name"])
                away_team = abbreviate_team_name(fixture["teams"]["away"]["name"])
                home_odds = get_outcome_odds(values, "Home")
                draw_odds = get_outcome_odds(values, "Draw")
                away_odds = get_outcome_odds(values, "Away")
                fixture_odds_summary = f"<b>{away_team} @ {home_team}</b> | <i>{fixture_start_time}</i>\n \
                    {home_team.upper()}: {home_odds}\n \
                    DRAW: {draw_odds}\n \
                    {away_team.upper()}: {away_odds}\n\n"
                fixtures_odds_response += fixture_odds_summary
        return emojize(fixtures_odds_response, language="en")
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing today's footy odds: {e}")
