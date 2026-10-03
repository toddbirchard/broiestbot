"""Tests for which fixtures `!footyxi` shows."""

from datetime import datetime, timedelta, timezone

import pytest

from broiestbot.commands.footy.lineups import filter_fixtures_with_lineups

NOW = datetime(2026, 10, 3, 15, 0, tzinfo=timezone.utc)


def _fixture(status: str, kickoff: datetime) -> dict:
    """Minimal API-Football fixture with the given status and kickoff time."""
    return {"fixture": {"id": 1, "date": kickoff.strftime("%Y-%m-%dT%H:%M:%S%z"), "status": {"short": status}}}


@pytest.mark.parametrize("status", ["1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"])
def test_live_fixtures_are_kept(status: str):
    fixture = _fixture(status, NOW - timedelta(minutes=50))
    assert filter_fixtures_with_lineups([fixture], NOW) == [fixture]


@pytest.mark.parametrize("status", ["FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"])
def test_ended_or_off_fixtures_are_dropped(status: str):
    fixture = _fixture(status, NOW - timedelta(hours=2))
    assert filter_fixtures_with_lineups([fixture], NOW) == []


@pytest.mark.parametrize("minutes_until_kickoff", [0, 30, 60])
def test_upcoming_fixture_within_the_hour_is_kept(minutes_until_kickoff: int):
    fixture = _fixture("NS", NOW + timedelta(minutes=minutes_until_kickoff))
    assert filter_fixtures_with_lineups([fixture], NOW) == [fixture]


@pytest.mark.parametrize("minutes_until_kickoff", [61, 180])
def test_upcoming_fixture_beyond_the_hour_is_dropped(minutes_until_kickoff: int):
    fixture = _fixture("NS", NOW + timedelta(minutes=minutes_until_kickoff))
    assert filter_fixtures_with_lineups([fixture], NOW) == []


def test_kickoff_compared_across_timezones():
    """A kickoff expressed in another UTC offset is compared by instant, not wall-clock time."""
    kickoff = (NOW + timedelta(minutes=30)).astimezone(timezone(timedelta(hours=-5)))
    fixture = _fixture("NS", kickoff)
    assert filter_fixtures_with_lineups([fixture], NOW) == [fixture]


def test_mixed_fixtures_keep_order():
    live = _fixture("2H", NOW - timedelta(minutes=70))
    finished = _fixture("FT", NOW - timedelta(hours=3))
    soon = _fixture("NS", NOW + timedelta(minutes=45))
    later = _fixture("NS", NOW + timedelta(hours=4))
    assert filter_fixtures_with_lineups([live, finished, soon, later], NOW) == [live, soon]


def test_missing_fixtures_yield_empty_list():
    assert filter_fixtures_with_lineups(None, NOW) == []


def test_malformed_fixture_is_skipped():
    good = _fixture("1H", NOW)
    assert filter_fixtures_with_lineups([{"fixture": {}}, good], NOW) == [good]
