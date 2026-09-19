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


# ---------------------------------------------------------------------------
# Banzuke (sumo-api.com /api/basho/<bashoId>/banzuke/<division>)
# ---------------------------------------------------------------------------


@pytest.fixture
def banzuke_day_3() -> dict:
    """Top-division banzuke mid-basho. Dewanoryu (135) is a Juryo visitor, so he's absent."""
    return {
        "bashoId": "202607",
        "division": "Makuuchi",
        "east": [
            {
                "side": "East",
                "rikishiID": 20,
                "shikonaEn": "Hoshoryu",
                "rank": "Yokozuna 1 East",
                "wins": 5,
                "losses": 1,
                "absences": 0,
            },
        ],
        "west": [
            {
                "side": "West",
                "rikishiID": 45,
                "shikonaEn": "Onosato",
                "rank": "Yokozuna 1 West",
                "wins": 6,
                "losses": 0,
                "absences": 0,
            },
            {
                "side": "West",
                "rikishiID": 95,
                "shikonaEn": "Oshoumi",
                "rank": "Maegashira 15 West",
                "wins": 2,
                "losses": 3,
                "absences": 1,
            },
        ],
    }


@pytest.fixture
def basho_records() -> dict:
    """`fetch_basho_records` output matching `banzuke_day_3`."""
    return {
        20: {"wins": 5, "losses": 1, "absences": 0},
        45: {"wins": 6, "losses": 0, "absences": 0},
        95: {"wins": 2, "losses": 3, "absences": 1},
    }


# ---------------------------------------------------------------------------
# Head-to-head (sumo-api.com /api/rikishi/<rikishiId>/matches/<opponentId>)
# ---------------------------------------------------------------------------


@pytest.fixture
def head_to_head_hoshoryu_onosato() -> dict:
    """Series between Hoshoryu (east, 20) and Onosato (west, 45), from Hoshoryu's perspective."""
    return {
        "kimariteLosses": {"yorikiri": 3},
        "kimariteWins": {"uwatenage": 2, "yorikiri": 4},
        "opponentWins": 3,
        "rikishiWins": 6,
        "total": 9,
        "matches": [{"bashoId": "202605", "day": 15, "winnerEn": "Hoshoryu", "kimarite": "yorikiri"}],
    }


# ---------------------------------------------------------------------------
# Rikishi profile (sumo-api.com /api/rikishi/<rikishiId>)
# ---------------------------------------------------------------------------


@pytest.fixture
def rikishi_profile_hoshoryu() -> dict:
    """Full `/rikishi/{id}` payload for Hoshoryu (20)."""
    return {
        "id": 20,
        "shikonaEn": "Hoshoryu",
        "heya": "Tatsunami",
        "birthDate": "1999-05-22T00:00:00Z",
        "shusshin": "Mongolia, Ulaanbaatar",
        "height": 188,
        "weight": 148,
        "debut": "201711",
    }


# ---------------------------------------------------------------------------
# Previous-basho banzuke (sumo-api.com /api/basho/<bashoId>/banzuke/<division>)
# ---------------------------------------------------------------------------


@pytest.fixture
def last_basho_banzuke_makuuchi() -> dict:
    """Top-division banzuke for the basho preceding `banzuke_day_3` (202605)."""
    return {
        "bashoId": "202605",
        "division": "Makuuchi",
        "east": [
            {"side": "East", "rikishiID": 20, "shikonaEn": "Hoshoryu", "wins": 12, "losses": 3, "absences": 0},
        ],
        "west": [
            {"side": "West", "rikishiID": 45, "shikonaEn": "Onosato", "wins": 13, "losses": 2, "absences": 0},
        ],
    }


@pytest.fixture
def last_basho_banzuke_juryo() -> dict:
    """Juryo banzuke for the basho preceding `banzuke_day_3` (202605); empty division."""
    return {"bashoId": "202605", "division": "Juryo", "east": [], "west": []}
