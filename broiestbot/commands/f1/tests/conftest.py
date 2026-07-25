"""Shared fixtures for Formula 1 command tests."""

from typing import List

import pytest

# ---------------------------------------------------------------------------
# Races (api-formula-1 /races?season=<season>&type=Race)
# ---------------------------------------------------------------------------


@pytest.fixture
def race_upcoming() -> dict:
    """Scheduled grand prix which hasn't been run yet."""
    return {
        "id": 1141,
        "competition": {
            "id": 21,
            "name": "Bahrain",
            "location": {"country": "Bahrain", "city": "Sakhir"},
        },
        "circuit": {"id": 21, "name": "Bahrain International Circuit"},
        "season": 2026,
        "type": "Race",
        "laps": {"current": None, "total": 57},
        "fastest_lap": {"driver": {"id": None}, "time": None},
        "distance": "308.238 km",
        "timezone": "UTC",
        "date": "2026-03-08T15:00:00+00:00",
        "weather": None,
        "status": "Scheduled",
    }


@pytest.fixture
def race_live(race_upcoming) -> dict:
    """Grand prix currently being run, 32 laps in."""
    return {
        **race_upcoming,
        "id": 1142,
        "laps": {"current": 32, "total": 57},
        "date": "2026-03-08T15:00:00+00:00",
        "weather": "Sunny, 28°C",
        "status": "Scheduled",
    }


@pytest.fixture
def race_completed(race_upcoming) -> dict:
    """Grand prix which has already been run."""
    return {
        **race_upcoming,
        "id": 1140,
        "competition": {
            "id": 20,
            "name": "Australia",
            "location": {"country": "Australia", "city": "Melbourne"},
        },
        "laps": {"current": 58, "total": 58},
        "date": "2026-03-01T05:00:00+00:00",
        "status": "Completed",
    }


@pytest.fixture
def race_cancelled(race_upcoming) -> dict:
    """Grand prix which was called off."""
    return {**race_upcoming, "id": 1139, "date": "2026-03-22T15:00:00+00:00", "status": "Cancelled"}


# ---------------------------------------------------------------------------
# Driver rankings (api-formula-1 /rankings/races?race=<race>)
# ---------------------------------------------------------------------------


@pytest.fixture
def race_rankings() -> List[dict]:
    """Running order of a live race, deliberately out of order."""
    return [
        {
            "position": 3,
            "driver": {"id": 25, "name": "Lewis Hamilton", "abbr": "HAM", "number": 44},
            "team": {"id": 3, "name": "Ferrari"},
            "time": None,
            "gap": "+8.921",
            "laps": 32,
            "pits": 1,
        },
        {
            "position": 1,
            "driver": {"id": 20, "name": "Max Verstappen", "abbr": "VER", "number": 1},
            "team": {"id": 1, "name": "Red Bull Racing"},
            "time": "1:02:11.404",
            "gap": None,
            "laps": 32,
            "pits": 1,
        },
        {
            "position": 2,
            "driver": {"id": 22, "name": "Charles Leclerc", "abbr": "LEC", "number": 16},
            "team": {"id": 3, "name": "Ferrari"},
            "time": None,
            "gap": "+2.104",
            "laps": 32,
            "pits": 1,
        },
    ]


# ---------------------------------------------------------------------------
# Starting grid (api-formula-1 /rankings/startinggrid?race=<race>)
# ---------------------------------------------------------------------------


@pytest.fixture
def starting_grid() -> List[dict]:
    """Starting grid of a race whose qualifying is complete, deliberately out of order."""
    return [
        {
            "position": 2,
            "driver": {"id": 25, "name": "Nico Hulkenberg", "abbr": "HUL", "number": 27},
            "team": {"id": 6, "name": "Audi"},
            "time": "1:29.512",
        },
        {
            "position": 1,
            "driver": {"id": 20, "name": "Max Verstappen", "abbr": "VER", "number": 1},
            "team": {"id": 1, "name": "Red Bull Racing"},
            "time": "1:29.179",
        },
        {
            "position": 3,
            "driver": {"id": 30, "name": "Yuki Tsunoda", "abbr": "TSU", "number": 22},
            "team": {"id": 2, "name": "Racing Bulls"},
            "time": "1:29.740",
        },
    ]


# ---------------------------------------------------------------------------
# Bookmaker odds (pinnacle-odds /kit/v1/sports & /kit/v1/special-markets)
# ---------------------------------------------------------------------------


@pytest.fixture
def odds_sports() -> List[dict]:
    """Sports offered by the odds API."""
    return [
        {"id": 1, "name": "Soccer"},
        {"id": 3, "name": "Basketball"},
        {"id": 12, "name": "Formula 1"},
    ]


@pytest.fixture
def odds_race_winner_market() -> dict:
    """Race-winner market for the Bahrain Grand Prix."""
    return {
        "id": 1587215144,
        "sport_id": 12,
        "league_id": 3435,
        "league_name": "Formula 1",
        "category": "Race Winner",
        "name": "Bahrain Grand Prix - Winner",
        "starts": "2026-03-08T15:00:00Z",
        "lines": {
            "0": {"line_id": 1, "name": "Charles Leclerc", "price": 4.5},
            "1": {"line_id": 2, "name": "Max Verstappen", "price": 1.72},
            "2": {"line_id": 3, "name": "Lando Norris", "price": 3.25},
            "3": {"line_id": 4, "name": "Franco Colapinto", "price": None},
        },
    }


@pytest.fixture
def odds_specials(odds_race_winner_market) -> List[dict]:
    """Special (outright) markets offered for F1, including irrelevant ones."""
    return [
        {
            "id": 1587215100,
            "sport_id": 12,
            "league_name": "Formula 1",
            "category": "Drivers Championship",
            "name": "2026 Drivers Championship - Winner",
            "starts": "2026-03-08T15:00:00Z",
            "lines": {"0": {"line_id": 9, "name": "Max Verstappen", "price": 2.1}},
        },
        {
            "id": 1587215101,
            "sport_id": 12,
            "league_name": "Formula 1",
            "category": "Fastest Lap",
            "name": "Bahrain Grand Prix - Fastest Lap",
            "starts": "2026-03-08T15:00:00Z",
            "lines": {"0": {"line_id": 10, "name": "Lando Norris", "price": 3.0}},
        },
        odds_race_winner_market,
    ]
