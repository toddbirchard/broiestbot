"""Fetch lineups before kickoff or during the match."""

from datetime import datetime, timedelta
from typing import List, Optional
import pytz

import requests
from emoji import emojize
from requests.exceptions import HTTPError

from config import (
    FOOTY_HTTP_HEADERS,
    FOOTY_XI_LEAGUES,
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_XI_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
)

from logger import LOGGER

from .util import (
    get_current_day,
    get_preferred_timezone,
    get_season_year,
    check_fixture_start_date,
    get_preferred_time_format,
)


@LOGGER.catch
def footy_team_lineups(room: str, username: str) -> Optional[str]:
    """
    Fetch starting lineups by team for immediate or live fixtures.

    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: str
    """
    try:
        i = 0
        today_fixture_lineups = "\n\n\n"
        tz_name = get_preferred_timezone(room, username)
        for league_name, league_id in FOOTY_XI_LEAGUES.items():
            league_fixtures = get_today_live_or_upcoming_fixtures(league_id, room, tz_name)
            league_fixtures_with_lineups = filter_fixtures_with_lineups(league_fixtures, tz_name)
            if bool(league_fixtures_with_lineups) and i <= 3:
                i += 1
                today_fixture_lineups += emojize(f"<b>{league_name}</b>\n", language="en")
                for fixture_xi in league_fixtures_with_lineups:
                    if bool(fixture_xi):
                        fixture_id = fixture_xi["fixture"]["id"]
                        fixture_summary = build_fixture_summary(fixture_xi, room, username)
                        fixture_lineups = fetch_lineups_per_fixture(fixture_id)
                        if fixture_lineups == []:
                            today_fixture_lineups += f"{fixture_summary} \
                                <i>(Lineups not yet available)</i>\n\n"
                        else:
                            today_fixture_lineups += f"{fixture_summary} \n \
                                {get_fixture_xis(fixture_lineups)}\n\n"
                today_fixture_lineups += "\n\n----------------------\n\n"
        return today_fixture_lineups.rstrip("\n\n----------------------\n\n")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy XIs: {e}")


@LOGGER.catch
def fetch_lineups_per_fixture(fixture_id: int) -> Optional[List[dict]]:
    """
    Get team lineup for given fixture.

    :param int fixture_id: ID of an upcoming fixture.

    :returns: List[Optional[dict]
    """
    try:
        params = {"fixture": fixture_id}
        resp = requests.get(
            FOOTY_XI_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        return resp.json().get("response")
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching footy XIs: {e.response.content}")
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching footy XIs: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy XIs: {e}")


def get_fixture_xis(teams: dict) -> str:
    """
    Parse & format player lineups for an upcoming fixture.

    :param dict teams: JSON Response containing two lineups for a given fixture.

    :returns: str
    """
    try:
        lineups_response = ""
        for i, team in enumerate(teams):
            team_lineup = team.get("startXI")
            if team_lineup is None:
                continue
            team_name = team["team"]["name"]
            formation = team["formation"]
            coach = team["coach"]["name"]
            emoji = ":stadium:"
            players = "\n".join(
                [
                    f"<b>{player['player']['pos']}</b> {player['player']['name']} (#{player['player']['number']})"
                    for player in team_lineup
                ]
            )
            if i != 0:
                emoji = ":airplane:"
            lineups_response += emojize(f"<b>- {emoji} {team_name} {formation} ({coach})</b>\n", language="en")
            lineups_response += f"{players}\n"
        return lineups_response
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


@LOGGER.catch
def get_today_live_or_upcoming_fixtures(league_id: int, room: str, tz_name: str) -> Optional[List[dict]]:
    """
    Get fixtures for a league for the current day (live or upcoming).

    :param int league_id: ID of a footy league to fetch fixtures for.
    :param str room: Chatango room in which command was triggered.
    :param str tz_name: Chatango room in which command was triggered.

    :returns: Optional[List[dict]]
    """
    try:
        today = get_current_day(room)
        params = {
            "date": today.strftime("%Y-%m-%d"),
            "league": league_id,
            "season": get_season_year(league_id),
            "status": "NS-1H-2H",
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


@LOGGER.catch
def build_fixture_summary(fixture: dict, room: str, username: str) -> Optional[str]:
    """
    Summarize basic details about a fixture.

    :param dict fixture: JSON Response containing fixture details.

    :returns: str
    """
    try:
        home_team = fixture["teams"]["home"]["name"]
        away_team = fixture["teams"]["away"]["name"]
        status = fixture["fixture"]["status"]["short"]
        status_detail = fixture["fixture"]["status"]["long"]
        elapsed = fixture["fixture"]["status"]["elapsed"]
        date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
        display_date, tz = get_preferred_time_format(date, room, username)
        display_date = check_fixture_start_date(date, tz, display_date)
        if status == "FT":
            return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({status})</i>\n"
        if status == "NS":
            return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({display_date.replace('<b>Today</b>, ', '')})</i>\n"
        if status in ("1H", "2H"):
            return f'<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({elapsed}</i>")\n'
        return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({status_detail})</i>\n"
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing footy fixture summaries for footyXI: {e}")


@LOGGER.catch
def filter_fixtures_with_lineups(fixtures: List[dict], tz_name: str):
    """
    Filter fixtures lacking lineup data.

    :param List[dict] fixtures: List of fixtures for a given league.
    :param str tz_name: Timezone of user who triggered the command.

    :returns: List[Optional[dict]]
    """
    try:
        fixtures_with_lineups = []
        for fixture in fixtures:
            start_time = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z").now(
                pytz.timezone(tz_name)
            )
            now_time = datetime.now(pytz.timezone(tz_name))
            footy_xi_time = start_time - timedelta(hours=1)
            if now_time >= footy_xi_time:
                fixtures_with_lineups.append(fixture)
        return fixtures_with_lineups
    except Exception as e:
        LOGGER.error(f"Unexpected error when filtering fixtures with lineups: {e}")
