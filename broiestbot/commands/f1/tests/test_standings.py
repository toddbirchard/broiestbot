"""Tests for fetching the F1 drivers' championship standings."""

from unittest.mock import patch

import pytest

from broiestbot.commands.f1 import standings as f1_standings
from broiestbot.commands.f1.standings import fetch_driver_standings

# Raw Hyprace drivers-standings response (isLastStanding=true), deliberately out of order.
STANDINGS_RESPONSE = {
    "items": [
        {
            "raceId": "race-10",
            "standings": [
                {"position": 2, "points": 159, "driverId": "driver-ham"},
                {"position": 1, "points": 204, "driverId": "driver-ant"},
                {"position": 3, "points": 154, "driverId": "driver-rus"},
            ],
        }
    ]
}

# Raw Hyprace season roster, one page.
ROSTER_RESPONSE = {
    "items": [
        {
            "id": "driver-ant",
            "firstName": "Andrea Kimi",
            "lastName": "Antonelli",
            "tla": "ANT",
            "teams": [{"shortName": "Mercedes AMG F1 Team"}],
        },
        {
            "id": "driver-ham",
            "firstName": "Lewis",
            "lastName": "Hamilton",
            "tla": "HAM",
            "teams": [{"shortName": "Scuderia Ferrari"}],
        },
        {
            "id": "driver-rus",
            "firstName": "George",
            "lastName": "Russell",
            "tla": "RUS",
            "teams": [{"shortName": "Mercedes AMG F1 Team"}],
        },
    ],
    "hasNext": False,
    "totalPages": 1,
}


@pytest.fixture(autouse=True)
def clear_roster_cache():
    """Clear the cached driver roster between tests."""
    f1_standings._DRIVER_ROSTERS.clear()
    yield
    f1_standings._DRIVER_ROSTERS.clear()


def test_standings_are_resolved_to_names_and_sorted():
    """Championship rows are resolved to driver names & teams, leader first."""
    with (
        patch("broiestbot.commands.f1.standings.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.standings._fetch_hyprace", return_value=STANDINGS_RESPONSE),
        patch("broiestbot.commands.f1.standings.fetch_all_pages", return_value=ROSTER_RESPONSE["items"]),
    ):
        standings = fetch_driver_standings(2026)

    assert [(entry["position"], entry["name"], entry["points"]) for entry in standings] == [
        (1, "Andrea Kimi Antonelli", 204),
        (2, "Lewis Hamilton", 159),
        (3, "George Russell", 154),
    ]
    assert standings[0]["team"] == "Mercedes AMG F1 Team"


def test_driver_roster_is_cached():
    """The season roster is fetched once & reused across standings lookups."""
    with (
        patch("broiestbot.commands.f1.standings.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.standings._fetch_hyprace", return_value=STANDINGS_RESPONSE),
        patch("broiestbot.commands.f1.standings.fetch_all_pages", return_value=ROSTER_RESPONSE["items"]) as mock_roster,
    ):
        fetch_driver_standings(2026)
        fetch_driver_standings(2026)

    mock_roster.assert_called_once()


def test_unresolved_driver_still_listed():
    """A championship row whose driver isn't in the roster is kept, just without a name."""
    with (
        patch("broiestbot.commands.f1.standings.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.standings._fetch_hyprace", return_value=STANDINGS_RESPONSE),
        patch("broiestbot.commands.f1.standings.fetch_all_pages", return_value=[]),
    ):
        standings = fetch_driver_standings(2026)

    assert standings[0]["position"] == 1
    assert standings[0]["name"] is None


def test_unknown_season_has_no_standings():
    """A season with no resolvable ID yields no standings."""
    with patch("broiestbot.commands.f1.standings.resolve_season_id", return_value=None):
        assert fetch_driver_standings(2099) is None


def test_empty_standings_response_returns_none():
    """A standings response with no snapshots is swallowed."""
    with (
        patch("broiestbot.commands.f1.standings.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.standings._fetch_hyprace", return_value={"items": []}),
    ):
        assert fetch_driver_standings(2026) is None


def test_failed_standings_request_returns_none():
    """A failed standings request is swallowed & reported as no data."""
    with (
        patch("broiestbot.commands.f1.standings.resolve_season_id", return_value="season-2026"),
        patch("broiestbot.commands.f1.standings._fetch_hyprace", return_value=None),
    ):
        assert fetch_driver_standings(2026) is None
