"""Shared fixtures for sumo command tests."""

import pytest

# ---------------------------------------------------------------------------
# Basho metadata (sumo-api.com /api/basho/<bashoId>)
# ---------------------------------------------------------------------------


@pytest.fixture
def basho_july_2026() -> dict:
    """July 2026 (Nagoya) basho metadata."""
    return {
        "date": "202607",
        "startDate": "2026-07-12T00:00:00Z",
        "endDate": "2026-07-26T00:00:00Z",
    }


@pytest.fixture
def basho_unscheduled() -> dict:
    """API response for a basho ID with no scheduled tournament (still HTTP 200)."""
    return {
        "date": "",
        "startDate": "0001-01-01T00:00:00Z",
        "endDate": "0001-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Torikumi (sumo-api.com /api/basho/<bashoId>/torikumi/<division>/<day>)
# ---------------------------------------------------------------------------


@pytest.fixture
def bout_completed() -> dict:
    """Bout that has been fought, with winner & kimarite populated."""
    return {
        "id": "202607-3-21-20-45",
        "bashoId": "202607",
        "division": "Makuuchi",
        "day": 3,
        "matchNo": 21,
        "eastId": 20,
        "eastShikona": "Hoshoryu",
        "eastRank": "Yokozuna 1 East",
        "westId": 45,
        "westShikona": "Onosato",
        "westRank": "Yokozuna 1 West",
        "kimarite": "yorikiri",
        "winnerId": 45,
        "winnerEn": "Onosato",
        "winnerJp": "",
    }


@pytest.fixture
def bout_upcoming() -> dict:
    """Scheduled bout that has not yet been fought."""
    return {
        "id": "202607-3-1-135-95",
        "bashoId": "202607",
        "division": "Makuuchi",
        "day": 3,
        "matchNo": 1,
        "eastId": 135,
        "eastShikona": "Dewanoryu",
        "eastRank": "Juryo 3 East",
        "westId": 95,
        "westShikona": "Oshoumi",
        "westRank": "Maegashira 15 West",
        "kimarite": "",
        "winnerId": 0,
        "winnerEn": "",
        "winnerJp": "",
    }


@pytest.fixture
def torikumi_day_3(basho_july_2026, bout_upcoming, bout_completed) -> dict:
    """Full torikumi response for day 3, lowest-ranked bout first."""
    return {**basho_july_2026, "torikumi": [bout_upcoming, bout_completed]}
