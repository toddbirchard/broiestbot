"""Tests for fetching the starting grid of a grand prix."""

from unittest.mock import patch

import pytest

from broiestbot.commands.f1 import drivers as f1_drivers
from broiestbot.commands.f1.qualifying import fetch_starting_grid, is_qualified

# Raw Hyprace qualifying sessions of a sprint weekend, which carries a sprint shootout too.
SPRINT_WEEKEND_SESSIONS = {
    "items": [
        {"id": "quali-sprint", "type": "Sprint", "startDate": "2026-07-03T15:30:00Z"},
        {"id": "quali-standard", "type": "Standard", "startDate": "2026-07-04T15:00:00Z"},
    ]
}

# Raw Hyprace qualifying results, deliberately out of order.
QUALIFYING_RESULTS = {
    "results": [
        {
            "driverId": "driver-ham",
            "q1": "1:18.730",
            "q2": "1:17.803",
            "q3": "1:17.219",
            "position": 2,
            "status": "Qualified",
        },
        {
            "driverId": "driver-ant",
            "q1": "1:18.277",
            "q2": "1:17.456",
            "q3": "1:17.207",
            "position": 1,
            "status": "Qualified",
        },
        {"driverId": "driver-rus", "q1": "1:21.322", "position": 3, "status": "Qualified"},
    ]
}

ROSTER = {
    "driver-ant": {"name": "Andrea Kimi Antonelli", "tla": "ANT", "team": "Mercedes AMG F1 Team"},
    "driver-ham": {"name": "Lewis Hamilton", "tla": "HAM", "team": "Scuderia Ferrari"},
    "driver-rus": {"name": "George Russell", "tla": "RUS", "team": "Mercedes AMG F1 Team"},
}


@pytest.fixture(autouse=True)
def clear_roster_cache():
    """Clear the cached driver roster between tests."""
    f1_drivers._DRIVER_ROSTERS.clear()
    yield
    f1_drivers._DRIVER_ROSTERS.clear()


def test_grid_is_resolved_to_names_and_sorted():
    """Grid rows are resolved to driver names & teams, pole first."""
    with (
        patch(
            "broiestbot.commands.f1.qualifying._fetch_hyprace",
            side_effect=[SPRINT_WEEKEND_SESSIONS, QUALIFYING_RESULTS],
        ),
        patch("broiestbot.commands.f1.qualifying.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.qualifying.driver_roster", return_value=ROSTER),
    ):
        grid = fetch_starting_grid("gp-hungary", 2026)

    assert [(entry["position"], entry["name"], entry["time"]) for entry in grid] == [
        (1, "Andrea Kimi Antonelli", "1:17.207"),
        (2, "Lewis Hamilton", "1:17.219"),
        (3, "George Russell", "1:21.322"),
    ]
    assert grid[0]["team"] == "Mercedes AMG F1 Team"


def test_sprint_qualifying_is_ignored():
    """The sprint shootout doesn't set the grand prix grid, so the standard session is used."""
    with (
        patch(
            "broiestbot.commands.f1.qualifying._fetch_hyprace",
            side_effect=[SPRINT_WEEKEND_SESSIONS, QUALIFYING_RESULTS],
        ) as mock_fetch,
        patch("broiestbot.commands.f1.qualifying.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.qualifying.driver_roster", return_value=ROSTER),
    ):
        fetch_starting_grid("gp-britain", 2026)

    assert "quali-standard" in mock_fetch.call_args_list[1].args[0]


def test_qualifying_yet_to_run_has_an_empty_grid():
    """A grand prix whose qualifying hasn't happened yet reports no grid at all."""
    with patch(
        "broiestbot.commands.f1.qualifying._fetch_hyprace",
        side_effect=[SPRINT_WEEKEND_SESSIONS, {"results": []}],
    ):
        assert fetch_starting_grid("gp-dutch", 2026) == []


def test_unresolved_driver_still_listed():
    """A grid row whose driver isn't in the roster is kept, just without a name."""
    with (
        patch(
            "broiestbot.commands.f1.qualifying._fetch_hyprace",
            side_effect=[SPRINT_WEEKEND_SESSIONS, QUALIFYING_RESULTS],
        ),
        patch("broiestbot.commands.f1.qualifying.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.qualifying.driver_roster", return_value={}),
    ):
        grid = fetch_starting_grid("gp-hungary", 2026)

    assert grid[0]["position"] == 1
    assert grid[0]["name"] is None


def test_missing_qualifying_session_returns_none():
    """A grand prix with no standard qualifying session yields no grid."""
    with patch("broiestbot.commands.f1.qualifying._fetch_hyprace", return_value={"items": []}):
        assert fetch_starting_grid("gp-hungary", 2026) is None


def test_failed_grid_request_returns_none():
    """A failed qualifying request is swallowed & reported as no data."""
    with patch("broiestbot.commands.f1.qualifying._fetch_hyprace", return_value=None):
        assert fetch_starting_grid("gp-hungary", 2026) is None


def test_race_without_an_id_has_no_grid():
    """A race we don't have an ID for can't have its grid looked up."""
    assert fetch_starting_grid(None, 2026) is None
    assert fetch_starting_grid("gp-hungary", None) is None


def test_unexpected_error_returns_none():
    """Unexpected errors are swallowed & reported as no data."""
    with patch("broiestbot.commands.f1.qualifying._fetch_hyprace", side_effect=ValueError("boom")):
        assert fetch_starting_grid("gp-hungary", 2026) is None


def test_penalized_driver_isnt_marked_as_qualified():
    """A driver who didn't simply qualify is flagged so their status can be shown."""
    assert is_qualified({"status": "Qualified"}) is True
    assert is_qualified({"status": "Disqualified"}) is False
    assert is_qualified({}) is False
