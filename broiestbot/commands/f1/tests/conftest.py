"""Shared fixtures for Formula 1 command tests."""

import pytest

# ---------------------------------------------------------------------------
# Circuits (Hyprace /v2/circuits/<id>)
# ---------------------------------------------------------------------------


@pytest.fixture
def circuit_bahrain() -> dict:
    """Circuit details as attached to a race for rendering."""
    return {
        "name": "Bahrain International Circuit",
        "city": "Sakhir",
        "country": "Bahrain",
        "country_code": "BH",
    }


# ---------------------------------------------------------------------------
# Races (normalized from Hyprace /v2/grands-prix?seasonId=<id>)
# ---------------------------------------------------------------------------


@pytest.fixture
def race_upcoming(circuit_bahrain) -> dict:
    """Scheduled grand prix which hasn't been run yet."""
    return {
        "id": "gp-bahrain",
        "name": "Bahrain Grand Prix",
        "official_name": "FORMULA 1 GULF AIR BAHRAIN GRAND PRIX 2026",
        "round": 1,
        "season": 2026,
        "circuit_id": "circuit-bahrain",
        "circuit": dict(circuit_bahrain),
        "date": "2026-03-08T15:00:00Z",
        "status": "Created",
        "laps": {"total": 57, "current": None},
        "distance": "308.238 km",
        "weather": None,
    }


@pytest.fixture
def race_live(race_upcoming) -> dict:
    """Grand prix whose race weekend is currently active."""
    return {**race_upcoming, "id": "gp-bahrain-live", "status": "Active"}


@pytest.fixture
def race_completed(race_upcoming) -> dict:
    """Grand prix which has already been run."""
    return {
        **race_upcoming,
        "id": "gp-australia",
        "name": "Australian Grand Prix",
        "round": 0,
        "circuit_id": "circuit-australia",
        "circuit": {
            "name": "Albert Park Circuit",
            "city": "Melbourne",
            "country": "Australia",
            "country_code": "AU",
        },
        "date": "2026-03-01T05:00:00Z",
        "status": "Finished",
    }


@pytest.fixture
def race_cancelled(race_upcoming) -> dict:
    """Grand prix which was called off."""
    return {**race_upcoming, "id": "gp-cancelled", "date": "2026-03-22T15:00:00Z", "status": "Cancelled"}
