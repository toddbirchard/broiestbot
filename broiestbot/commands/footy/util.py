"""Helpers for footy commands."""

from datetime import datetime, timedelta, tzinfo
from typing import Collection, List, Optional, Tuple

import pytz
from pytz import BaseTzInfo
from sqlalchemy import Column, select

from config import (
    AFCON_CUP_ID,
    AFCON_QUALIFIERS_ID,
    CHATANGO_OBI_ROOM,
    CLUB_FRIENDLIES_LEAGUE_ID,
    CLUB_WORLD_CUP_LEAGUE_ID,
    CONCACAF_CHAMPIONS_LEAGUE_ID,
    CONCACAF_GOLD_CUP_ID,
    CONCACAF_NATIONS_LEAGUE_ID,
    COPA_DEL_REY,
    COUPE_DE_FRANCE_ID,
    ELITESERIEN_LEAGUE_ID,
    EPL_SUMMER_SERIES_LEAGUE_ID,
    EUROS_LEAGUE_ID,
    EUROS_QUALIFIERS_ID,
    FOOTY_LEAGUE_TEAM_FILTERS,
    INT_FRIENDLIES_LEAGUE_ID,
    METRIC_SYSTEM_USERS,
    MLS_LEAGUE_ID,
    OBOS_LIGAEN_ID,
    U20_ELITE_LEAGUE_ID,
    U20_WORLD_CUP_ID,
    UEFA_SUPER_CUP_ID,
    USL_LEAGUE_1_ID,
    USL_LEAGUE_2_ID,
    WC_QUALIFIERS_AFRICA_ID,
    WC_QUALIFIERS_CONCACAF_ID,
    WC_QUALIFIERS_EUROPE_ID,
    WC_QUALIFIERS_SOUTHAMERICA_ID,
    WEUROS_LEAGUE_ID,
    WOMENS_WORLD_CUP_ID,
    WORLD_CUP_ID,
)
from database import async_session
from database.models import ChatangoUser


async def lookup_user_preferred_timezone(username: str) -> Optional[Column[str]]:
    """
    Lookup user to determine preferred timezone.

    :param str username: Chatango username.

    :returns: Optional[Column[str]]
    """
    async with async_session() as db:
        result = await db.execute(
            select(ChatangoUser).where(ChatangoUser.username == username).where(ChatangoUser.ip.isnot(None))
        )
        user = result.scalars().first()
    if user and user.time_zone_name is not None:
        return user.time_zone_name


async def get_preferred_timezone(room: str, username: str) -> str:
    """
    Display fixture dates depending on preferred timezone of requesting user.

    :param str room: Chatango room which triggered the command.
    :param str username: Chatango user who triggered the command.

    :returns: str
    """
    if room == CHATANGO_OBI_ROOM or username in METRIC_SYSTEM_USERS:
        return "UTC"
    if "anon" not in username:
        tz_string = await lookup_user_preferred_timezone(username)
        if tz_string:
            return tz_string
    return "America/New_York"


async def get_preferred_time_format(
    start_time: datetime, room: str, username: str, tz_name: Optional[str] = None
) -> Tuple[str, BaseTzInfo]:
    """
    Display fixture times depending on preferred timezone of requesting user/room.

    A user's preferred timezone is the same for every fixture in a single command, so callers
    which format fixtures in a loop should resolve it once with `get_preferred_timezone` and
    pass it as `tz_name`. Omitting it costs a database round trip per fixture.

    :param datetime start_time: Fixture start time/date defaulted to UTC time.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.
    :param Optional[str] tz_name: Already-resolved preferred timezone, looked up when omitted.

    :returns: Tuple[str, BaseTzInfo]
    """
    timezone_name = tz_name if tz_name else await get_preferred_timezone(room, username)
    if "America" in timezone_name:
        return (
            start_time.strftime("%b %d, %l:%M%p").replace("AM", "am").replace("PM", "pm"),
            pytz.timezone(timezone_name),
        )
    if "anon" not in username and timezone_name:
        return start_time.strftime("%b %d, %H:%M"), pytz.timezone(timezone_name)
    if room == CHATANGO_OBI_ROOM or (METRIC_SYSTEM_USERS is not None and username in METRIC_SYSTEM_USERS):
        return start_time.strftime("%b %d, %H:%M"), pytz.timezone("Europe/London")
    return (
        start_time.strftime("%b %d, %l:%M%p").replace("AM", "am").replace("PM", "pm"),
        pytz.timezone(timezone_name),
    )


def get_current_day(room: str) -> datetime:
    """
    Get current date depending on Chatango room.

    :param room: Chatango room in which command was triggered.

    :returns: datetime
    """
    if room == CHATANGO_OBI_ROOM:
        return datetime.now(tz=pytz.timezone("Europe/London"))
    return datetime.now(pytz.timezone("America/New_York"))


def league_is_team_filtered(league_id: int) -> bool:
    """
    Determine whether a league only surfaces fixtures featuring specific clubs.

    :param int league_id: ID of footy league/cup.

    :returns: bool
    """
    return league_id in FOOTY_LEAGUE_TEAM_FILTERS


def fixture_features_team(fixture: dict, team_ids: Collection[int]) -> bool:
    """
    Determine whether either side of a fixture is a club we care about.

    :param dict fixture: Single fixture's data.
    :param Collection[int] team_ids: IDs of clubs worth surfacing a fixture for.

    :returns: bool
    """
    teams = fixture.get("teams") or {}
    home_team_id = (teams.get("home") or {}).get("id")
    away_team_id = (teams.get("away") or {}).get("id")
    return home_team_id in team_ids or away_team_id in team_ids


def filter_league_fixtures(fixtures: Optional[List[dict]], league_id: int) -> Optional[List[dict]]:
    """
    Discard fixtures of a team-filtered league which don't feature a club we care about.

    Some leagues are only interesting for a handful of clubs: club friendlies span every
    club on earth, and the Primeira Liga is only followed for Benfica. Fixtures of a league
    listed in `FOOTY_LEAGUE_TEAM_FILTERS` are kept only when either side is one of that
    league's clubs; fixtures of any other league pass through untouched.

    :param Optional[List[dict]] fixtures: Fixtures fetched for a single league/cup.
    :param int league_id: ID of footy league/cup the fixtures belong to.

    :returns: Optional[List[dict]]
    """
    team_ids = FOOTY_LEAGUE_TEAM_FILTERS.get(league_id)
    if not team_ids or not fixtures:
        return fixtures
    return [fixture for fixture in fixtures if fixture_features_team(fixture, team_ids)]


def abbreviate_team_name(team_name: str) -> str:
    """
    Abbreviate long team names to make schedules readable.

    :param str team_name: Full team name.

    :returns: str
    """
    return (
        team_name.replace("New England", "NE")
        .replace("Paris Saint Germain", "PSG")
        .replace("Manchester United", "Manu")
        .replace("Manchester City", "Man City")
        .replace("Liverpool", "LFC")
        .replace("Philadelphia", "Philly")
        .replace("Borussia Dortmund", "Dortmund")
        .replace("Nottingham Forest", "Nottingham")
        .replace("Club Brugge KV", "Club Brugge")
        .replace("PSV Eindhoven", "PSV")
        .replace("Olympiakos Piraeus", "Olympiakos")
        .replace("Sheriff Tiraspol", "Sheriff")
        .replace("Red Bull Salzburg", "RB Salzburg")
        .replace("Vikingur Reykjavik", "Reykjavik")
        .replace("Malmo FF", "Malmo")
        .replace("New England", "NE")
        .replace("Los Angeles FC", "LAFC")
        .replace("Los Angeles", "LA")
        .replace("New York City FC", "NYCFC")
        .replace("New York", "NY")
        .replace("Orlando City SC", "Orlando City")
        .replace("1. FC Heidenheim", "Heidenheim")
        .replace("SV Elversberg", "Elversberg")
    )


def check_fixture_start_date(fixture_start_date: datetime, tz: tzinfo, display_date: str) -> str:
    """
    Simplify fixture date if fixture occurs `Today` or `Tomorrow`.'

    :param datetime fixture_start_date: Datetime of fixture start time.
    :param tzinfo tz: Timezone of fixture start time.
    :param str display_date: Fallback string of fixture start time.

    :returns: str
    """
    if fixture_start_date.date() == datetime.date(datetime.now(tz)):
        return f"<b>Today</b>, {display_date.split(', ')[1]}"
    if fixture_start_date.date() == datetime.date(datetime.now(tz)) + timedelta(days=1):
        return f"Tomorrow, {display_date.split(', ')[1]}"
    return display_date


async def add_upcoming_fixture(
    fixture: dict, date: datetime, room: str, username: str, tz_name: Optional[str] = None
) -> str:
    """
    Construct upcoming fixture match-up.

    :param dict fixture: Scheduled fixture data.
    :param datetime date: Fixture start time/date displayed in preferred timezone.
    :param str room: Chatango room in which command was triggered.
    :param str username: Name of user who triggered the command.
    :param Optional[str] tz_name: Already-resolved preferred timezone of the requesting user.

    :returns: str
    """
    home_team = abbreviate_team_name(fixture["teams"]["home"]["name"])
    away_team = abbreviate_team_name(fixture["teams"]["away"]["name"])
    display_date, tz = await get_preferred_time_format(date, room, username, tz_name)
    display_date = check_fixture_start_date(date, tz, display_date)
    matchup = f"{away_team} @ {home_team}"
    return f"{matchup:<30} | <i>{display_date}</i>\n"


def get_season_year(league_id: int) -> int:
    """
    Determine `season` year — based on month for domestic leagues, or year for international leagues.

    :param int league_id: ID of league to determine season year for.

    :returns: int
    """
    current_year = datetime.now().year
    current_month = datetime.now().month
    # Exception for leagues that have a nonsensical `season` year: the Summer Series
    # labels each edition with the previous calendar year (`season` 2025 is played in
    # July 2026), so requesting the current year returns no fixtures.
    if league_id == EPL_SUMMER_SERIES_LEAGUE_ID:
        return current_year - 1
    # Leagues which have a season year that is the same as the current year.
    if league_id in (
        MLS_LEAGUE_ID,
        CONCACAF_CHAMPIONS_LEAGUE_ID,
        CONCACAF_GOLD_CUP_ID,
        COPA_DEL_REY,
        COUPE_DE_FRANCE_ID,
        WC_QUALIFIERS_CONCACAF_ID,
        WC_QUALIFIERS_EUROPE_ID,
        WC_QUALIFIERS_SOUTHAMERICA_ID,
        WC_QUALIFIERS_AFRICA_ID,
        AFCON_CUP_ID,
        AFCON_QUALIFIERS_ID,
        EUROS_LEAGUE_ID,
        EUROS_QUALIFIERS_ID,
        U20_WORLD_CUP_ID,
        WOMENS_WORLD_CUP_ID,
        CLUB_FRIENDLIES_LEAGUE_ID,
        INT_FRIENDLIES_LEAGUE_ID,
        USL_LEAGUE_1_ID,
        USL_LEAGUE_2_ID,
        UEFA_SUPER_CUP_ID,
        U20_ELITE_LEAGUE_ID,
        CONCACAF_NATIONS_LEAGUE_ID,
        OBOS_LIGAEN_ID,
        ELITESERIEN_LEAGUE_ID,
        CLUB_WORLD_CUP_LEAGUE_ID,
        WEUROS_LEAGUE_ID,
        WORLD_CUP_ID,
    ):
        return current_year
    # Exception for leagues that have a nonsensical `season` year.
    # if league_id == CONCACAF_NATIONS_LEAGUE_ID:
    # return current_year - 1
    # Domestic leagues that begin in the summer and end in the spring.
    if current_month >= 8:
        return current_year
    if current_month <= 6:
        return current_year - 1
    return current_year
