"""Tests that a command resolves the requesting user's timezone once, not per fixture.

`get_preferred_time_format` used to re-derive the timezone for every fixture it rendered,
costing a database round trip each time. Callers which format fixtures in a loop now pass
the already-resolved `tz_name` down.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from broiestbot.commands.footy.today import today_upcoming_fixtures
from broiestbot.commands.footy.upcoming import footy_upcoming_fixtures_per_league
from config import EPL_LEAGUE_ID
from tests.aiohttp_mocks import FakeResponse, patch_http_session

ROOM = "__pytest_room__"
USER = "__pytest__user1"
TZ = "America/New_York"

# Upcoming-fixture commands drop anything outside their forward window, so fixtures are dated
# relative to "now" rather than pinned to a date which would age out of the window.
FIXTURE_DATE = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S%z")


def build_fixture(fixture_id: int, home: str, away: str) -> dict:
    """
    Build a minimal upcoming fixture as returned by /v3/fixtures.

    :param int fixture_id: ID of the fixture.
    :param str home: Name of the home side.
    :param str away: Name of the away side.

    :returns: dict
    """
    return {
        "fixture": {
            "id": fixture_id,
            "date": FIXTURE_DATE,
            "status": {"short": "NS", "long": "Not Started", "elapsed": None},
            "venue": {"name": "Anfield"},
        },
        "league": {"id": EPL_LEAGUE_ID, "name": "EPL", "season": datetime.now().year},
        "teams": {"home": {"id": 40, "name": home}, "away": {"id": 42, "name": away}},
        "goals": {"home": None, "away": None},
    }


FIXTURES = [
    build_fixture(1, "Liverpool", "Arsenal"),
    build_fixture(2, "Everton", "Chelsea"),
    build_fixture(3, "Fulham", "Brentford"),
    build_fixture(4, "Burnley", "Wolves"),
]


def test_upcoming_fixtures_resolves_timezone_once():
    """One league's worth of fixtures costs a single timezone lookup, not one per fixture."""
    with patch(
        "broiestbot.commands.footy.util.lookup_user_preferred_timezone",
        new=AsyncMock(return_value=TZ),
    ) as lookup:
        with patch(
            "broiestbot.commands.footy.upcoming.upcoming_fixture_fetcher",
            new=AsyncMock(return_value=FIXTURES),
        ):
            result = asyncio.run(footy_upcoming_fixtures_per_league("EPL", EPL_LEAGUE_ID, ROOM, USER, TZ))

    assert result is not None
    # Every fixture was rendered (team names are abbreviated, so count lines rather than names)...
    assert len([line for line in result.splitlines() if line.strip()]) == len(FIXTURES)
    # ...and the caller's pre-resolved timezone meant zero further lookups.
    assert lookup.await_count == 0


def test_today_fixtures_resolves_timezone_once_across_leagues():
    """`!todayfixtures` resolves the timezone once for the whole command, not once per league."""
    response = FakeResponse(json_data={"response": FIXTURES})
    with patch(
        "broiestbot.commands.footy.util.lookup_user_preferred_timezone",
        new=AsyncMock(return_value=TZ),
    ) as lookup:
        with patch_http_session("broiestbot.commands.footy.today", response):
            result = asyncio.run(today_upcoming_fixtures(ROOM, USER))

    assert result is not None
    assert lookup.await_count == 1, f"expected a single timezone lookup, got {lookup.await_count}"


def test_timezone_is_still_resolved_when_not_passed():
    """Callers which don't pre-resolve a timezone keep working — the lookup just happens inline."""
    from broiestbot.commands.footy.util import get_preferred_time_format

    start = datetime.fromisoformat(FIXTURE_DATE)
    with patch(
        "broiestbot.commands.footy.util.lookup_user_preferred_timezone",
        new=AsyncMock(return_value="Europe/London"),
    ) as lookup:
        display_date, tz = asyncio.run(get_preferred_time_format(start, ROOM, USER))

    assert lookup.await_count == 1
    assert str(tz) == "Europe/London"
    assert display_date


def test_passed_timezone_is_the_one_used():
    """A pre-resolved timezone wins over whatever the database holds."""
    from broiestbot.commands.footy.util import get_preferred_time_format

    start = datetime.fromisoformat(FIXTURE_DATE)
    with patch(
        "broiestbot.commands.footy.util.lookup_user_preferred_timezone",
        new=AsyncMock(return_value="Europe/London"),
    ) as lookup:
        _, tz = asyncio.run(get_preferred_time_format(start, ROOM, USER, "Asia/Tokyo"))

    assert lookup.await_count == 0
    assert str(tz) == "Asia/Tokyo"
