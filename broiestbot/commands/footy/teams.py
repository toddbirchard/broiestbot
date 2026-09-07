"""Fetch football data per team."""

from datetime import datetime
from typing import Optional

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    AALESUND_TEAM_ID,
    CHATANGO_OBI_ROOM,
    ENGLISH_CHAMPIONSHIP_LEAGUE_ID,
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOXES_TEAM_ID,
    OBOS_LIGAEN_ID,
)

from .upcoming import (
    check_fixture_start_date,
    get_preferred_time_format,
    get_preferred_timezone,
)
from .util import get_season_year


async def fetch_aafk_fixture_data(room: str, username: str) -> Optional[str]:
    """
    Return contextual information about the scheduled, imminent, or live fixture for AAFK

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: Optional[str]
    """
    try:
        tz_name = await get_preferred_timezone(room, username)
        season = get_season_year(OBOS_LIGAEN_ID)
        live_fixture = await fetch_live_fixture_for_team(AALESUND_TEAM_ID, tz_name)
        if bool(live_fixture):
            pass
            fixture_id = live_fixture[0]["fixture"]["id"]
        return await fetch_next_five_fixtures_per_team(
            room, username, AALESUND_TEAM_ID, OBOS_LIGAEN_ID, "🇳🇴 AALESUND F.K."
        )
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching AAFK data: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching AAFK data: {e}")


async def fetch_live_fixture_for_team(team_id: int, tz_name: str) -> Optional[dict]:
    """
    Fetch live footy fixture for provided team.

    :param int team_id: ID of footy team.
    :param str tz_name: Timezone of the user who triggered the command.
    :param int season: Season year.

    :returns: Optional[dict]
    """
    try:
        params = {"league": team_id, "live": "all", "timezone": tz_name}
        session = await get_http_session()
        async with session.get(FOOTY_FIXTURES_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            if resp.status == 200:
                fixtures = await resp.json(content_type=None)
                if fixtures.get("response"):
                    return fixtures.get("response")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching footy fixtures: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching footy fixtures: {e}")


async def fetch_next_five_fixtures_per_team(
    room: str, username: str, team_id: int, league_id: int, team_name: str
) -> Optional[str]:
    """
    Fetch next 5 fixtures scheduled for a given team.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.
    :param int team_id: ID of footy team.
    :param int league_id: ID of footy league.
    :param str team_name: Name of footy team.

    :returns: Optional[str]
    """
    try:
        tz_name = await get_preferred_timezone(room, username)
        upcoming_fixtures = f"\n\n\n\n<b>{team_name}</b>\n"
        season = get_season_year(league_id)
        params = {"season": season, "team": team_id, "next": "5", "timezone": tz_name}
        session = await get_http_session()
        async with session.get(FOOTY_FIXTURES_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            fixtures = (await resp.json(content_type=None)).get("response")
        if bool(fixtures):
            for fixture in fixtures:
                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                display_date, tz = await get_preferred_time_format(date, room, username, tz_name)
                # The OBI room shows the absolute date rather than the Today/Tomorrow shorthand,
                # which the second identical lookup used to achieve by overwriting it.
                if room != CHATANGO_OBI_ROOM:
                    display_date = check_fixture_start_date(date, tz, display_date)
                upcoming_fixtures = upcoming_fixtures + f"{away_team} @ {home_team} | <i>{display_date}</i>\n"
            return emojize(upcoming_fixtures, language="en")
        return emojize(":warning: Couldn't find fixtures, has season started yet? :warning:", language="en")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching fox fixtures: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching fox fixtures: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching fox fixtures: {e}")


async def fetch_fox_fixtures(room: str, username: str) -> Optional[str]:
    """
    Fetch next 5 fixtures played by Lesta Foxes (now in EFL).

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: Optional[str]
    """
    try:
        tz_name = await get_preferred_timezone(room, username)
        upcoming_foxtures = "\n\n\n\n<b>:fox: FOXTURES</b>\n"
        season = get_season_year(ENGLISH_CHAMPIONSHIP_LEAGUE_ID)
        params = {"season": season, "team": FOXES_TEAM_ID, "next": "7", "timezone": tz_name}
        session = await get_http_session()
        async with session.get(FOOTY_FIXTURES_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            fixtures = (await resp.json(content_type=None)).get("response")
        if bool(fixtures):
            for fixture in fixtures:
                home_team = fixture["teams"]["home"]["name"]
                away_team = fixture["teams"]["away"]["name"]
                date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                display_date, tz = await get_preferred_time_format(date, room, username, tz_name)
                # The OBI room shows the absolute date rather than the Today/Tomorrow shorthand,
                # which the second identical lookup used to achieve by overwriting it.
                if room != CHATANGO_OBI_ROOM:
                    display_date = check_fixture_start_date(date, tz, display_date)
                upcoming_foxtures = upcoming_foxtures + f"{away_team} @ {home_team} | <i>{display_date}</i>\n"
            return emojize(upcoming_foxtures, language="en")
        return emojize(":warning: Couldn't find fixtures, has season started yet? :warning:", language="en")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching fox fixtures: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching fox fixtures: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching fox fixtures: {e}")
