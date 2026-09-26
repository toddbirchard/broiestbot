"""Tests for fetching the results of a grand prix."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from broiestbot.commands.f1 import drivers as f1_drivers
from broiestbot.commands.f1.results import fetch_race_results, is_finisher

# Raw Hyprace race sessions of a sprint weekend, which carries a sprint race too.
SPRINT_WEEKEND_RACES = {
    "items": [
        {"id": "race-sprint", "type": "SprintRace", "date": "2026-07-04T11:00:00Z"},
        {"id": "race-main", "type": "MainRace", "date": "2026-07-05T14:00:00Z"},
    ]
}

# Raw Hyprace race results, deliberately out of order.
RACE_RESULTS = {
    "participations": [
        {
            "driverId": "driver-ver",
            "result": {
                "position": 2,
                "grid": 8,
                "time": "1:38:02.339",
                "points": 18.0,
                "lapsBehindLeader": 0,
                "gapToLeader": "0.196",
                "resultStatus": {"status": "Ok", "positionStatus": "Classified"},
            },
        },
        {
            "driverId": "driver-rus",
            "result": {
                "position": 1,
                "grid": 1,
                "time": "1:38:02.143",
                "points": 25.0,
                "lapsBehindLeader": 0,
                "gapToLeader": "0",
                "resultStatus": {"status": "Ok", "positionStatus": "Classified"},
            },
        },
        {
            "driverId": "driver-ham",
            "result": {
                "position": 3,
                "grid": 7,
                "time": "1:07:36.051",
                "points": 0.0,
                "gapToLeader": "0",
                "resultStatus": {"status": "Dnf", "positionStatus": "NonClassified"},
            },
        },
    ]
}

ROSTER = {
    "driver-rus": {"name": "George Russell", "tla": "RUS", "team": "Mercedes AMG F1 Team"},
    "driver-ver": {"name": "Max Verstappen", "tla": "VER", "team": "Red Bull Racing"},
    "driver-ham": {"name": "Lewis Hamilton", "tla": "HAM", "team": "Scuderia Ferrari"},
}


@pytest.fixture(autouse=True)
def clear_roster_cache():
    """Clear the cached driver roster between tests."""
    f1_drivers._DRIVER_ROSTERS.clear()
    yield
    f1_drivers._DRIVER_ROSTERS.clear()


def test_results_are_resolved_to_names_and_sorted():
    """Result rows are resolved to driver names & teams, winner first."""
    with (
        patch(
            "broiestbot.commands.f1.results._fetch_hyprace",
            new_callable=AsyncMock,
            side_effect=[SPRINT_WEEKEND_RACES, RACE_RESULTS],
        ),
        patch("broiestbot.commands.f1.results.resolve_season_id", new_callable=AsyncMock, return_value="season-2026"),
        patch("broiestbot.commands.f1.results.driver_roster", new_callable=AsyncMock, return_value=ROSTER),
    ):
        results = asyncio.run(fetch_race_results("gp-baku", 2026))

    assert [(entry["position"], entry["name"], entry["gap"]) for entry in results] == [
        (1, "George Russell", "0"),
        (2, "Max Verstappen", "0.196"),
        (3, "Lewis Hamilton", "0"),
    ]
    assert results[0]["team"] == "Mercedes AMG F1 Team"
    assert results[0]["time"] == "1:38:02.143"
    assert results[2]["status"] == "Dnf"


def test_sprint_race_is_ignored():
    """The sprint isn't the grand prix, so the main race session is used."""
    with (
        patch(
            "broiestbot.commands.f1.results._fetch_hyprace",
            new_callable=AsyncMock,
            side_effect=[SPRINT_WEEKEND_RACES, RACE_RESULTS],
        ) as mock_fetch,
        patch("broiestbot.commands.f1.results.resolve_season_id", new_callable=AsyncMock, return_value="season-2026"),
        patch("broiestbot.commands.f1.results.driver_roster", new_callable=AsyncMock, return_value=ROSTER),
    ):
        asyncio.run(fetch_race_results("gp-britain", 2026))

    assert mock_fetch.call_args_list[1].args[0].endswith("/gp-britain/races/race-main/results")


def test_unclassified_race_has_no_results():
    """A race whose results haven't been published yet reports none at all."""
    with patch(
        "broiestbot.commands.f1.results._fetch_hyprace",
        new_callable=AsyncMock,
        side_effect=[SPRINT_WEEKEND_RACES, {"participations": []}],
    ):
        assert asyncio.run(fetch_race_results("gp-baku", 2026)) == []


def test_missing_race_session_returns_none():
    """A grand prix with no main race session yields no results."""
    with patch("broiestbot.commands.f1.results._fetch_hyprace", new_callable=AsyncMock, return_value={"items": []}):
        assert asyncio.run(fetch_race_results("gp-baku", 2026)) is None


def test_failed_results_request_returns_none():
    """A failed results request is swallowed & reported as no data."""
    with patch("broiestbot.commands.f1.results._fetch_hyprace", new_callable=AsyncMock, return_value=None):
        assert asyncio.run(fetch_race_results("gp-baku", 2026)) is None


def test_race_without_an_id_has_no_results():
    """A race we don't have an ID for can't have its results looked up."""
    assert asyncio.run(fetch_race_results(None, 2026)) is None
    assert asyncio.run(fetch_race_results("gp-baku", None)) is None


def test_unexpected_error_returns_none():
    """Unexpected errors are swallowed & reported as no data."""
    with patch("broiestbot.commands.f1.results._fetch_hyprace", new_callable=AsyncMock, side_effect=ValueError("boom")):
        assert asyncio.run(fetch_race_results("gp-baku", 2026)) is None


def test_retired_driver_isnt_a_finisher():
    """Only a driver who took the chequered flag counts as having finished."""
    assert is_finisher({"status": "Ok"}) is True
    assert is_finisher({"status": "Dnf"}) is False
    assert is_finisher({}) is False
