"""Fetch scheduled fixtures across leagues."""
import asyncio
from asyncio import Task
from datetime import datetime
from typing import List, Optional

import requests
from aiohttp import ClientError, ClientSession, InvalidURL
from emoji import emojize
from requests.exceptions import HTTPError

from config import (
    CHATANGO_OBI_ROOM,
    EPL_LEAGUE_ID,
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_LEAGUES,
    FOXES_TEAM_ID,
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
    upcoming_fixtures = "\n\n\n\n"
    fixtures = asyncio.run(create_tasks_and_fetch_upcoming_fixtures(room, username))
    if fixtures:
        upcoming_fixtures += "\n".join(fixtures[:5])
        return upcoming_fixtures
    return emojize(":warning: Couldn't find any upcoming fixtures :( :warning:", use_aliases=True)


async def create_tasks_and_fetch_upcoming_fixtures(room: str, username: str):
    headers = {
        "content-type": "application/json",
        "connection": "keep-alive",
        "accept": "*/*",
    }
    async with ClientSession(headers=headers) as session:
        tasks = await create_tasks(session, room, username)
        return await asyncio.gather(*tasks)


async def create_tasks(session: ClientSession, room: str, username: str) -> List[Task]:
    """
    Create asyncio tasks to execute the `footy_upcoming_fixtures_per_league` coroutine.

    :param ClientSession session: Async HTTP requests session.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: List[Task]
    """
    tasks = []
    for league_name, league_id in FOOTY_LEAGUES.items():
        task = asyncio.create_task(
            footy_upcoming_fixtures_per_league(session, league_name, league_id, room, username)
        )
        tasks.append(task)
    return tasks


async def footy_upcoming_fixtures_per_league(
    session: ClientSession, league_name, league_id: int, room: str, username: str
) -> Optional[str]:
    """
    Get this week's upcoming fixtures for a given league or tournament.

    :param ClientSession session: Async HTTP client session to fetch fixtures.
    :param str league_name: Name of the league/cup.
    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: Optional[str]
    """
    try:
        upcoming_fixtures = ""
        i = 0
        fixture_responses = await upcoming_fixture_fetcher(
            session, league_name, league_id, room, username
        )
        parse_upcoming_fixtures(fixture_responses, room, username)
        if bool(fixtures) is not False and i < 7:
            i += 1
            upcoming_fixtures += emojize(f"<b>{league_name}:</b>\n", use_aliases=True)
            for i, fixture in enumerate(fixtures):
                date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                upcoming_fixtures += add_upcoming_fixture(fixture, date, room, username)
            return upcoming_fixtures
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching footy fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


async def upcoming_fixture_fetcher(
    session: ClientSession, league_name: str, league_id: int, room: str, username: str
) -> list[str]:
    """
    Fetch next 3-6 upcoming fixtures for a given league.

    :param ClientSession session: Async HTTP client session to fetch fixtures.
    :param str league_name: Name of the league/cup.
    :param int league_id: ID of footy league/cup.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: Optional[List[dict]]
    """
    try:
        params = {
            "next": 6
            if "EPL" in league_name or "UCL" in league_name or "FA Cup" in league_name
            else 3,
            "league": league_id,
            "status": "NS",
        }
        params.update(get_preferred_timezone(room, username))
        async with session.get(FOOTY_FIXTURES_ENDPOINT, params=params) as resp:
            resp = await resp.json()
            fixtures = resp.get("response")
            if resp.status_code == 200 and fixtures:
                return fixtures
    except InvalidURL as e:
        LOGGER.error(f"InvalidURL while fetching footy fixtures: {e}")
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching footy fixtures: {e}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


async def parse_upcoming_fixtures(fixtures: dict, room: str, username: str):
    i = 0
    fixture_list = []
    for i, fixture in enumerate(fixtures):
        date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
        formatted_fixture = await add_upcoming_fixture(fixture, date, room, username)
        fixture_list.append(formatted_fixture)


async def add_upcoming_fixture(fixture: dict, date: datetime, room: str, username: str) -> str:
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
    return f"{away_team} @ {home_team} - {display_date}\n"


def fetch_fox_fixtures(room: str, username: str) -> str:
    """
    Fetch next 5 fixtures played by Foxes.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: str
    """
    try:
        upcoming_foxtures = "\n\n\n\n<b>:fox: FOXTURES:</b>\n"
        season = get_season_year(EPL_LEAGUE_ID)
        params = {"season": season, "team": FOXES_TEAM_ID, "next": "7"}
        params.update(get_preferred_timezone(room, username))
        req = requests.get(
            FOOTY_FIXTURES_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
        )
        fixtures = req.json().get("response")
        if bool(fixtures):
            for fixture in fixtures:
                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                display_date, tz = get_preferred_time_format(date, room, username)
                if room == CHATANGO_OBI_ROOM:
                    display_date, tz = get_preferred_time_format(date, room, username)
                upcoming_foxtures = (
                    upcoming_foxtures + f"{away_team} @ {home_team} - {display_date}\n"
                )
            return emojize(upcoming_foxtures, use_aliases=True)
        return emojize(
            f":warning: Couldn't find fixtures, has season started yet? :warning:",
            use_aliases=True,
        )
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching fox fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching fox fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching fox fixtures: {e}")
