"""Shared fixtures for footy command tests."""

from typing import List

import pytest


@pytest.fixture
def live_fixture() -> dict:
    """Single live World Cup fixture as returned by /v3/fixtures?live=all."""
    return {
        "fixture": {
            "id": 1489392,
            "timezone": "UTC",
            "timestamp": 1750000000,
            "status": {"long": "Second Half", "short": "2H", "elapsed": 67},
            "venue": {"name": "Levi's Stadium", "city": "Santa Clara"},
        },
        "league": {"id": 1, "name": "World Cup", "country": "World", "season": 2026},
        "teams": {
            "home": {"id": 10, "name": "United States", "winner": None},
            "away": {"id": 24, "name": "Portugal", "winner": None},
        },
        "goals": {"home": 1, "away": 1},
        "score": {"halftime": {"home": 0, "away": 1}, "fulltime": {"home": None, "away": None}},
    }


@pytest.fixture
def live_odds_response_fixture(live_fixture) -> List[dict]:
    """
    Response from /v3/odds/live?fixture=1489392.
    Bets are in a top-level "odds" array; the live equivalent of "Match Winner"
    is "Fulltime Result" (id=59). "Match Winner" (id=1) does not appear in live odds.
    """
    return [
        {
            "fixture": {"id": live_fixture["fixture"]["id"]},
            "league": live_fixture["league"],
            "update": "2026-06-20T20:24:00+00:00",
            "odds": [
                {
                    "id": 59,
                    "name": "Fulltime Result",
                    "values": [
                        {"value": "Home", "odd": "3.20", "handicap": None, "main": None, "suspended": False},
                        {"value": "Draw", "odd": "3.10", "handicap": None, "main": None, "suspended": False},
                        {"value": "Away", "odd": "2.25", "handicap": None, "main": None, "suspended": False},
                    ],
                }
            ],
        }
    ]


@pytest.fixture
def today_fixture() -> dict:
    """Single upcoming World Cup fixture as returned by /v3/fixtures?date=..."""
    return {
        "fixture": {
            "id": 1489392,
            "date": "2026-06-25T19:00:00+00:00",
            "timezone": "UTC",
            "status": {"long": "Not Started", "short": "NS", "elapsed": None},
            "venue": {"name": "Levi's Stadium", "city": "Santa Clara"},
        },
        "league": {"id": 1, "name": "World Cup", "country": "World", "season": 2026},
        "teams": {
            "home": {"id": 10, "name": "United States", "winner": None},
            "away": {"id": 24, "name": "Portugal", "winner": None},
        },
        "goals": {"home": None, "away": None},
    }


def _match_winner_odds_entry(fixture_id: int, values: List[dict]) -> dict:
    """Build a single /v3/odds response entry for the 'Match Winner' bet (id=1)."""
    return {
        "fixture": {"id": fixture_id},
        "bookmakers": [
            {
                "id": 8,
                "name": "Bet365",
                "bets": [{"id": 1, "name": "Match Winner", "values": values}],
            }
        ],
    }


@pytest.fixture
def today_odds_response(today_fixture) -> List[dict]:
    """
    Response from /v3/odds with the 'Match Winner' values in canonical Home/Draw/Away order.
    """
    return [
        _match_winner_odds_entry(
            today_fixture["fixture"]["id"],
            [
                {"value": "Home", "odd": "3.20"},
                {"value": "Draw", "odd": "3.10"},
                {"value": "Away", "odd": "2.25"},
            ],
        )
    ]


@pytest.fixture
def today_odds_response_reversed(today_fixture) -> List[dict]:
    """
    Same odds as `today_odds_response`, but with the values returned in reverse
    (Away/Draw/Home) order — the API does not guarantee ordering. Home odds must
    still resolve to 3.20 and away to 2.25.
    """
    return [
        _match_winner_odds_entry(
            today_fixture["fixture"]["id"],
            [
                {"value": "Away", "odd": "2.25"},
                {"value": "Draw", "odd": "3.10"},
                {"value": "Home", "odd": "3.20"},
            ],
        )
    ]


@pytest.fixture
def live_odds_no_fulltime_result(live_fixture) -> List[dict]:
    """Response that contains odds but no 'Fulltime Result' bet — should yield no parsed output."""
    return [
        {
            "fixture": {"id": live_fixture["fixture"]["id"]},
            "league": live_fixture["league"],
            "update": "2026-06-20T20:24:00+00:00",
            "odds": [
                {
                    "id": 20,
                    "name": "Match Corners",
                    "values": [
                        {"value": "Over", "odd": "2.625", "handicap": "8"},
                        {"value": "Under", "odd": "1.833", "handicap": "8"},
                    ],
                }
            ],
        }
    ]
