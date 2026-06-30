"""Shared fixtures for footy command tests."""

from typing import List

import pytest

# ---------------------------------------------------------------------------
# Live fixture events (API-Football /v3/fixtures/events?fixture=<id>)
# ---------------------------------------------------------------------------


@pytest.fixture
def event_normal_goal() -> dict:
    """Normal goal event with all fields populated."""
    return {
        "time": {"elapsed": 23, "extra": None},
        "player": {"id": 1, "name": "Harry Kane"},
        "assist": {"id": 2, "name": "Bukayo Saka"},
        "type": "Goal",
        "detail": "Normal Goal",
        "comments": None,
    }


@pytest.fixture
def event_penalty_goal() -> dict:
    """Penalty goal event."""
    return {
        "time": {"elapsed": 45, "extra": None},
        "player": {"id": 3, "name": "Jude Bellingham"},
        "assist": {"id": None, "name": None},
        "type": "Goal",
        "detail": "Penalty",
        "comments": None,
    }


@pytest.fixture
def event_own_goal_with_assist() -> dict:
    """Own goal where the assist field has a player name."""
    return {
        "time": {"elapsed": 60, "extra": None},
        "player": {"id": 5, "name": "Virgil van Dijk"},
        "assist": {"id": 6, "name": "Trent Alexander-Arnold"},
        "type": "Goal",
        "detail": "Own Goal",
        "comments": None,
    }


@pytest.fixture
def event_own_goal_no_assist() -> dict:
    """Own goal where the assist field is entirely None/null."""
    return {
        "time": {"elapsed": 72, "extra": None},
        "player": {"id": 7, "name": "Sergio Ramos"},
        "assist": None,
        "type": "Goal",
        "detail": "Own Goal",
        "comments": None,
    }


@pytest.fixture
def event_yellow_card() -> dict:
    """Yellow card event with a comment."""
    return {
        "time": {"elapsed": 35, "extra": None},
        "player": {"id": 8, "name": "Declan Rice"},
        "assist": {"id": None, "name": None},
        "type": "Card",
        "detail": "Yellow Card",
        "comments": "Dangerous play",
    }


@pytest.fixture
def event_red_card() -> dict:
    """Red card event."""
    return {
        "time": {"elapsed": 80, "extra": None},
        "player": {"id": 9, "name": "Diego Costa"},
        "assist": None,
        "type": "Card",
        "detail": "Red Card",
        "comments": None,
    }


@pytest.fixture
def event_var_disallowed_goal() -> dict:
    """VAR disallowed goal event."""
    return {
        "time": {"elapsed": 55, "extra": None},
        "player": {"id": 10, "name": "Robert Lewandowski"},
        "assist": None,
        "type": "Var",
        "detail": "Goal Disallowed - offside",
        "comments": None,
    }


@pytest.fixture
def event_substitution() -> dict:
    """Substitution event where the assist field holds the player coming on."""
    return {
        "time": {"elapsed": 65, "extra": None},
        "player": {"id": 11, "name": "Marcus Rashford"},
        "assist": {"id": 12, "name": "Alejandro Garnacho"},
        "type": "subst",
        "detail": "Substitution 1",
        "comments": None,
    }


@pytest.fixture
def event_null_player() -> dict:
    """Event where the entire player object is null — seen in some API responses."""
    return {
        "time": {"elapsed": 40, "extra": None},
        "player": None,
        "assist": None,
        "type": "Goal",
        "detail": "Normal Goal",
        "comments": None,
    }


@pytest.fixture
def event_null_time() -> dict:
    """Event where the time object is null."""
    return {
        "time": None,
        "player": {"id": 13, "name": "Erling Haaland"},
        "assist": None,
        "type": "Goal",
        "detail": "Normal Goal",
        "comments": None,
    }


@pytest.fixture
def event_null_player_name() -> dict:
    """Event where player dict exists but name is null."""
    return {
        "time": {"elapsed": 50, "extra": None},
        "player": {"id": 14, "name": None},
        "assist": None,
        "type": "Goal",
        "detail": "Normal Goal",
        "comments": None,
    }


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
