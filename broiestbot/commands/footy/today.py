"""Fetch scheduled fixtures across leagues for today only."""
from datetime import datetime
from typing import List, Optional

import requests
from emoji import emojize
from requests.exceptions import HTTPError

from config import (
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    HTTP_REQUEST_TIMEOUT,
)
from logger import LOGGER

from .util import (
    abbreviate_team_name,
    check_fixture_start_date,
    get_current_day,
    get_preferred_time_format,
    get_preferred_timezone,
    get_season_year,
)


def today_upcoming_fixtures(room: str, username: str) -> str:
    """
    Fetch fixtures scheduled to occur today.

    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    i = 0
    upcoming_fixtures = "\n\n\n\n"
    for league_name, league_id in FOOTY_LEAGUES.items():
        league_fixtures = today_fixtures_per_league(league_name, league_id, room, username)
        if league_fixtures is not None and i < 7:
            i += 1
            upcoming_fixtures += f"{league_fixtures}\n"
    if upcoming_fixtures != "\n\n\n\n":
        return upcoming_fixtures
    return emojize(
        ":soccer_ball: :cross_mark: sry no fixtures today :( :cross_mark: :soccer_ball:",
        language="en",
    )


def today_fixtures_per_league(league_name: str, league_id: int, room: str, username: str) -> Optional[str]:
    """
    Get this week's upcoming fixtures for a given league or tournament.

    :param str league_name: Name of footy league/cup.
    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: Optional[str]
    """
    try:
        league_upcoming_fixtures = ""
        fixtures = fetch_today_fixtures_by_league(league_id, room, username)
        if fixtures:
            for i, fixture in enumerate(fixtures):
                fixture_start_time = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                if i == 0:
                    league_upcoming_fixtures += emojize(f"<b>{league_name}</b>\n", language="en")
                if i <= 7:
                    league_upcoming_fixtures += parse_today_fixture(fixture, fixture_start_time, room, username)
        if league_upcoming_fixtures is None:
            return None
        return league_upcoming_fixtures
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def fetch_today_fixtures_by_league(league_id: int, room: str, username: str) -> List[Optional[dict]]:
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
            "status": "NS-FT-1H-2H",
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
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


def parse_today_fixture(fixture: dict, fixture_start_time: datetime, room: str, username: str) -> str:
    """
    Construct fixture summary for upcoming, live, or finished games.

    :param dict fixture: Scheduled fixture data.
    :param datetime fixture_start_time: Fixture start time/date displayed in preferred timezone.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    try:
        fixture_status = fixture["fixture"]["status"]["short"]
        home_team = abbreviate_team_name(fixture["teams"]["home"]["name"])
        away_team = abbreviate_team_name(fixture["teams"]["away"]["name"])
        home_score = fixture["goals"].get("home")
        away_score = fixture["goals"].get("away")
        elapsed = fixture["fixture"]["status"]["elapsed"]
        display_date, tz = get_preferred_time_format(fixture_start_time, room, username)
        display_date = check_fixture_start_date(fixture_start_time, tz, display_date)
        display_date = display_date.replace("<b>Today</b>, ", "")
        if away_score and home_score:
            if fixture_status == "NS":
                return f"{away_team} @ {home_team} | <i>{display_date}</i>\n"
            if fixture_status == "FT":
                return f"{away_team} <b>({away_score})</b>  @ {home_team} <b>({home_score})</b> | <i>Final</i>\n"
            if fixture_status in ("1H", "2H"):
                return f'{away_team} ({away_score})  @ {home_team} ({home_score}) | <i>{elapsed}"</i>\n'
        matchup = f"{away_team} @ {home_team}"
        return f"{matchup:<30} | <i><b>{display_date}</b></i>\n"
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")
