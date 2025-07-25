"""Fetch scheduled fixtures across leagues."""

from datetime import datetime, timedelta
from typing import List, Optional

import requests
from emoji import emojize
from requests.exceptions import HTTPError

from config import (
    CHATANGO_OBI_ROOM,
    ENGLISH_CHAMPIONSHIP_LEAGUE_ID,
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    FOXES_TEAM_ID,
    HTTP_REQUEST_TIMEOUT,
)
from logger import LOGGER

from .util import (
    abbreviate_team_name,
    check_fixture_start_date,
    get_preferred_time_format,
    get_preferred_timezone,
    get_season_year,
)


def footy_upcoming_fixtures(room: str, username: str) -> str:
    """
    Fetch upcoming fixtures within 1 week for in order of priority.

    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    upcoming_fixtures = "\n\n\n"
    tz_name = get_preferred_timezone(room, username)
    i = 0
    for league_name, league_id in FOOTY_LEAGUES.items():
        league_fixtures = footy_upcoming_fixtures_per_league(league_name, league_id, room, username, tz_name)
        if bool(league_fixtures) is not False and i < 10:
            i += 1
            upcoming_fixtures += emojize(f"<b>{league_name}</b>\n", language="en")
            upcoming_fixtures += league_fixtures + "\n"
    if upcoming_fixtures != "\n\n\n":
        return upcoming_fixtures
    return emojize(":warning: Couldn't find any upcoming fixtures :warning:", language="en")


def footy_all_upcoming_fixtures(room: str, username: str) -> str:
    """
    Fetch upcoming fixtures within 1 week for ALL leagues.

    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    upcoming_fixtures = "\n\n\n"
    tz_name = get_preferred_timezone(room, username)
    for league_name, league_id in FOOTY_LEAGUES.items():
        league_fixtures = footy_upcoming_fixtures_per_league(league_name, league_id, room, username, tz_name)
        if bool(league_fixtures) is False:
            upcoming_fixtures += emojize(f"<b>{league_name}</b>\n", language="en")
            upcoming_fixtures += league_fixtures + "\n"
    if upcoming_fixtures != "\n\n\n":
        return upcoming_fixtures
    return emojize(":warning: Couldn't find upcoming fixtures for the next week :warning:", language="en")


def footy_upcoming_fixtures_per_league(
    league_name, league_id: int, room: str, username: str, tz_name: str
) -> Optional[str]:
    """
    Get this week's upcoming fixtures for a given league or tournament.

    :param str league_name: Name of the league/cup.
    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.
    :param str timezone_name: Name of user's preferred timezone (ie: `America/New_York`).

    :returns: Optional[str]
    """
    try:
        upcoming_fixtures = ""
        fixtures = upcoming_fixture_fetcher(league_name, league_id, tz_name)
        if bool(fixtures) is not False:
            for fixture in fixtures:
                fixture_date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                if fixture_date.date() <= datetime.now().date() + timedelta(days=8):
                    upcoming_fixture = add_upcoming_fixture(fixture, fixture_date, room, username)
                    if upcoming_fixture:
                        upcoming_fixtures += upcoming_fixture
            return upcoming_fixtures
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def upcoming_fixture_fetcher(league_name: str, league_id: int, tz_name: str) -> Optional[List[dict]]:
    """
    Fetch 6 upcoming fixtures for each top league, or 3 for each lower league.

    :param str league_name: Name of the league/cup.
    :param int league_id: ID of footy league/cup.
    :param str timezone_name: User's preferred timezone (ie: `America/New_York`).

    :returns: Optional[List[dict]]
    """
    try:
        params = {
            "next": 6 if "EPL" in league_name or "UCL" in league_name or "UEFA" in league_name else 3,
            "league": league_id,
            "status": "NS-1H-2H",
            "timezone": tz_name,
        }
        return fetch_upcoming_fixtures_by_league(params)
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def fetch_upcoming_fixtures_by_league(params: dict) -> Optional[List[dict]]:
    """
    Fetches upcoming fixtures for a single league.

    :param dict params: Request parameters for fetching fixtures for a given league or cup.py

    :returns: Optional[List[dict]]
    """
    try:
        resp = requests.get(
            FOOTY_FIXTURES_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("response")
    except HTTPError as e:
        LOGGER.error(f"HTTPError {resp.status_code} while fetching footy fixtures: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def add_upcoming_fixture(fixture: dict, date: datetime, room: str, username: str) -> str:
    """
    Construct upcoming fixture match-up.

    :param dict fixture: Scheduled fixture data.
    :param datetime date: Fixture start time/date displayed in preferred timezone.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    home_team = abbreviate_team_name(fixture["teams"]["home"]["name"])
    away_team = abbreviate_team_name(fixture["teams"]["away"]["name"])
    display_date, tz = get_preferred_time_format(date, room, username)
    display_date = check_fixture_start_date(date, tz, display_date)
    matchup = f"{away_team} @ {home_team}"
    return f"{matchup:<40} | <i>{display_date}</i>\n"


def fetch_fox_fixtures(room: str, username: str) -> str:
    """
    Fetch next 5 fixtures played by Lesta Foxes (now in EFL).

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: str
    """
    try:
        tz_name = get_preferred_timezone(room, username)
        upcoming_foxtures = "\n\n\n\n<b>:fox: FOXTURES</b>\n"
        season = get_season_year(ENGLISH_CHAMPIONSHIP_LEAGUE_ID)
        params = {"season": season, "team": FOXES_TEAM_ID, "next": "7", "timezone": tz_name}
        resp = requests.get(
            FOOTY_FIXTURES_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        fixtures = resp.json().get("response")
        if bool(fixtures):
            for fixture in fixtures:
                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                display_date, tz = get_preferred_time_format(date, room, username)
                display_date = check_fixture_start_date(date, tz, display_date)
                if room == CHATANGO_OBI_ROOM:
                    display_date, tz = get_preferred_time_format(date, room, username)
                upcoming_foxtures = upcoming_foxtures + f"{away_team} @ {home_team} | <i>{display_date}</i>\n"
            return emojize(upcoming_foxtures, language="en")
        return emojize(":warning: Couldn't find fixtures, has season started yet? :warning:", language="en")
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching fox fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching fox fixtures: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching fox fixtures: {e}")
