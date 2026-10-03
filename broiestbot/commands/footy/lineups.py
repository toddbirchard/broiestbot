"""Fetch lineups before kickoff or during the match."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    CHATANGO_MESSAGE_MAX_LENGTH,
    FOOTY_FIXTURES_ENDPOINT,
    FOOTY_HTTP_HEADERS,
    FOOTY_XI_ENDPOINT,
    FOOTY_XI_LEAGUES,
    FOOTY_XI_LIVE_STATUSES,
    FOOTY_XI_MAX_LEAGUES,
    FOOTY_XI_UPCOMING_WINDOW,
)

from .util import (
    check_fixture_start_date,
    filter_league_fixtures,
    get_current_day,
    get_preferred_time_format,
    get_preferred_timezone,
    get_season_year,
)

LEAGUE_SEPARATOR = "\n----------------------\n\n"


@LOGGER.catch
async def footy_team_lineups(room: str, username: str) -> Optional[List[str]]:
    """
    Fetch starting lineups by team for immediate or live fixtures.

    A matchday's lineups easily outgrow a single Chatango message, so the reply is a list of
    messages split between fixtures (see `pack_lineup_messages`), each to be sent in turn.

    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.

    :returns: Optional[List[str]]
    """
    try:
        leagues = []
        tz_name = await get_preferred_timezone(room, username)
        for league_name, league_id in FOOTY_XI_LEAGUES.items():
            if len(leagues) >= FOOTY_XI_MAX_LEAGUES:
                break
            league_fixtures = await get_today_live_or_upcoming_fixtures(league_id, room, tz_name)
            league_fixtures_with_lineups = filter_fixtures_with_lineups(league_fixtures)
            if not league_fixtures_with_lineups:
                continue
            fixture_blocks = []
            for fixture_xi in league_fixtures_with_lineups:
                fixture_summary = await build_fixture_summary(fixture_xi, room, username, tz_name)
                fixture_lineups = await fetch_lineups_per_fixture(fixture_xi["fixture"]["id"])
                fixture_xis = get_fixture_xis(fixture_lineups) if fixture_lineups else None
                if fixture_xis:
                    fixture_blocks.append(f"{fixture_summary}{fixture_xis}\n")
                else:
                    fixture_blocks.append(f"{fixture_summary}<i>(Lineups not yet available)</i>\n\n")
            leagues.append((emojize(f"<b>{league_name}</b>\n", language="en"), fixture_blocks))
        return pack_lineup_messages(leagues)
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy XIs: {e}")


def pack_lineup_messages(
    leagues: List[Tuple[str, List[str]]], max_length: int = CHATANGO_MESSAGE_MAX_LENGTH
) -> List[str]:
    """
    Pack each league's fixture lineups into as few messages as fit under `max_length`.

    `chatango-lib` slices an over-long message at a fixed character count, which cuts a
    lineup (and its HTML tags) in half. Splitting only *between* fixtures keeps every
    lineup whole. A league whose fixtures spill into the next message has its header
    repeated there, so no message opens with an unlabelled fixture.

    :param List[Tuple[str, List[str]]] leagues: League header paired with its rendered fixture blocks.
    :param int max_length: Longest message to emit.

    :returns: List[str]
    """
    messages = []
    message = ""
    for league_header, fixture_blocks in leagues:
        for i, fixture_block in enumerate(fixture_blocks):
            if i == 0:
                prefix = f"{LEAGUE_SEPARATOR if message else ''}{league_header}"
            else:
                prefix = "" if message else league_header
            if message and len(message) + len(prefix) + len(fixture_block) > max_length:
                messages.append(message)
                message = ""
                prefix = league_header
            message += prefix + fixture_block
    if message:
        messages.append(message)
    return [message.rstrip("\n") for message in messages]


@LOGGER.catch
async def fetch_lineups_per_fixture(fixture_id: int) -> Optional[List[dict]]:
    """
    Get team lineup for given fixture.

    :param int fixture_id: ID of an upcoming fixture.

    :returns: List[Optional[dict]
    """
    try:
        params = {"fixture": fixture_id}
        session = await get_http_session()
        async with session.get(FOOTY_XI_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            lineups = await resp.json(content_type=None)
            return lineups.get("response")
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching footy XIs: {e}")
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching footy XIs: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy XIs: {e}")


def get_fixture_xis(teams: dict) -> Optional[str]:
    """
    Parse & format player lineups for an upcoming fixture.

    :param dict teams: JSON Response containing two lineups for a given fixture.

    :returns: Optional[str]
    """
    try:
        lineups_response = ""
        for i, team in enumerate(teams):
            team_lineup = team.get("startXI")
            if team_lineup is None:
                continue
            team_name = team["team"]["name"]
            formation = team["formation"]
            coach = f" ({team['coach']['name']})" if team["coach"].get("name") else ""
            emoji = ":stadium:"
            players = "\n".join(
                [
                    f"<b>{player['player']['pos']}</b> {player['player']['name']} (#{player['player']['number']})"
                    for player in team_lineup
                ]
            )
            if i != 0:
                emoji = ":airplane:"
            lineups_response += emojize(f"<b>- {emoji} {team_name} {formation}{coach}</b>\n", language="en")
            lineups_response += f"{players}\n"
        return lineups_response
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


@LOGGER.catch
async def get_today_live_or_upcoming_fixtures(league_id: int, room: str, tz_name: str) -> Optional[List[dict]]:
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
            "status": "-".join(("NS", *FOOTY_XI_LIVE_STATUSES)),
            "timezone": tz_name,
        }
        session = await get_http_session()
        async with session.get(FOOTY_FIXTURES_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            fixtures = await resp.json(content_type=None)
            return filter_league_fixtures(fixtures.get("response"), league_id)
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching footy fixtures: {e}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching footy fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching footy fixtures: {e}")


@LOGGER.catch
async def build_fixture_summary(
    fixture: dict, room: str, username: str, tz_name: Optional[str] = None
) -> Optional[str]:
    """
    Summarize basic details about a fixture.

    :param dict fixture: JSON Response containing fixture details.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.
    :param Optional[str] tz_name: Already-resolved preferred timezone of the requesting user.

    :returns: str
    """
    try:
        home_team = fixture["teams"]["home"]["name"]
        away_team = fixture["teams"]["away"]["name"]
        status = fixture["fixture"]["status"]["short"]
        status_detail = fixture["fixture"]["status"]["long"]
        elapsed = fixture["fixture"]["status"]["elapsed"]
        date = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
        display_date, tz = await get_preferred_time_format(date, room, username, tz_name)
        display_date = check_fixture_start_date(date, tz, display_date)
        if status == "FT":
            return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({status})</i>\n"
        if status == "NS":
            return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({display_date.replace('<b>Today</b>, ', '')})</i>\n"
        if status in ("1H", "2H"):
            return f'<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({elapsed}")</i>\n'
        return f"<b>{away_team.upper()} @ {home_team.upper()}</b> <i>({status_detail})</i>\n"
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing footy fixture summaries for footyXI: {e}")


@LOGGER.catch
def filter_fixtures_with_lineups(fixtures: Optional[List[dict]], now: Optional[datetime] = None) -> List[dict]:
    """
    Keep fixtures which are live, or yet to start but kicking off within `FOOTY_XI_UPCOMING_WINDOW`.

    Fixtures which have ended (or were postponed, cancelled, etc.) are dropped, as are
    upcoming fixtures further out than the window.

    :param Optional[List[dict]] fixtures: List of fixtures for a given league.
    :param Optional[datetime] now: Timezone-aware current time; defaults to the present.

    :returns: List[dict]
    """
    now = now or datetime.now(timezone.utc)
    fixtures_with_lineups = []
    for fixture in fixtures or []:
        try:
            status = fixture["fixture"]["status"]["short"]
            if status in FOOTY_XI_LIVE_STATUSES:
                fixtures_with_lineups.append(fixture)
            elif status == "NS":
                start_time = datetime.strptime(fixture["fixture"]["date"], "%Y-%m-%dT%H:%M:%S%z")
                if start_time - now <= FOOTY_XI_UPCOMING_WINDOW:
                    fixtures_with_lineups.append(fixture)
        except (KeyError, TypeError, ValueError) as e:
            LOGGER.error(f"Unexpected error when filtering fixtures with lineups: {e}")
    return fixtures_with_lineups
