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
