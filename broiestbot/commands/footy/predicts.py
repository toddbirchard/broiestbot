"""NMatch predictions for fixtures occurring today."""
from datetime import datetime
from typing import List, Optional
from datetime import datetime

import requests
from requests.exceptions import HTTPError
from emoji import emojize

from config import (
    FOOTY_FIXTURES_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    FOOTY_ODDS_ENDPOINT_2,
)
from logger import LOGGER

from .util import get_preferred_timezone, get_current_day, abbreviate_team_name, get_season_year


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
        for league_name, league_id in FOOTY_LEAGUES.items():
            league_fixtures = _fetch_today_fixtures_by_league(league_id, room, username)
            league_fixture_odds = fetch_today_fixture_odds_by_league(league_id, room, username)
            if not bool(league_fixture_odds):
                continue
            if league_fixtures is not None and i < 7:
                today_fixtures_odds += parse_fixture_odds(
                    league_name, league_fixtures, league_fixture_odds, room, username
                )
            i += 1
        if today_fixtures_odds != "\n\n\n":
            return today_fixtures_odds
        return emojize(
            f":soccer_ball: :cross_mark: sry no fixtures today :( :cross_mark: :soccer_ball:",
            language="en",
        )
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy predicts: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy predicts: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy predicts: {e}")


def _fetch_today_fixtures_by_league(league_id: int, room: str, username: str) -> List[Optional[dict]]:
    """
    Fetch all upcoming fixtures for the current date.

    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: List[Optional[dict]]
    """
    try:
        today = get_current_day(room)
        params = {
            "date": today.strftime("%Y-%m-%d"),
            "league": league_id,
            "season": get_season_year(league_id),
        }
        params.update(get_preferred_timezone(room, username))
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


def fetch_today_fixture_odds_by_league(league_id: int, room: str, username: str) -> Optional[dict]:
    """
    Get all fixtures scheduled for today's date.

    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

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
        }
        params.update(get_preferred_timezone(room, username))
        resp = requests.get(FOOTY_ODDS_ENDPOINT_2, params=params, headers=FOOTY_HTTP_HEADERS)
        return resp.json().get("response")
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching today's footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching today's footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching today's footy fixtures: {e}")


def parse_fixture_odds(league_name: str, fixtures: dict, fixtures_odds: dict, room: str, username: str) -> str:

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
        fixtures_odds_response = f"<b>{league_name}</b>\n"
        for i, fixture in enumerate(fixtures):
            fixture_start_time = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z").time()
            home_team = abbreviate_team_name(fixture["teams"]["home"]["name"])
            away_team = abbreviate_team_name(fixture["teams"]["away"]["name"])
            home_odds = fixtures_odds[i]["bookmakers"][0]["bets"][0]["values"][0]["odd"]
            draw_odds = fixtures_odds[i]["bookmakers"][0]["bets"][0]["values"][1]["odd"]
            away_odds = fixtures_odds[i]["bookmakers"][0]["bets"][0]["values"][2]["odd"]
            fixture_odds_summary = f"<b>{away_team} @ {home_team}</b> | <i>{fixture_start_time}</i>\n \
                {home_team}: {home_odds}\n \
                Draw: {draw_odds}\n \
                {away_team}: {away_odds}\n\n"
            fixtures_odds_response += fixture_odds_summary
        return emojize(fixtures_odds_response, language="en")
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing today's footy odds: {e}")
