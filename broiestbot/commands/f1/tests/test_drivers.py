"""Tests for resolving F1 drivers & their teams."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from broiestbot.commands.f1 import drivers as f1_drivers
from broiestbot.commands.f1.drivers import driver_roster, short_team_name


@pytest.fixture(autouse=True)
def clear_roster_cache():
    """Clear the cached driver roster between tests."""
    f1_drivers._DRIVER_ROSTERS.clear()
    yield
    f1_drivers._DRIVER_ROSTERS.clear()


def test_team_names_are_shortened():
    """Teams are shown by the names they go by, not their full entrant names."""
    assert short_team_name("Mercedes AMG F1 Team") == "Mercedes"
    assert short_team_name("McLaren F1 Team") == "McLaren"
    assert short_team_name("Racing Bulls") == "RB"
    assert short_team_name("Red Bull Racing") == "Red Bull"


def test_unknown_team_loses_its_boilerplate():
    """A team missing from the mapping is still trimmed down, or left as-is."""
    assert short_team_name("Andretti F1 Team") == "Andretti"
    assert short_team_name("Sauber") == "Sauber"
    assert short_team_name(None) is None


def test_roster_carries_short_team_names():
    """Drivers are resolved with their team's short name."""
    drivers = [
        {"id": "driver-rus", "firstName": "George", "lastName": "Russell", "tla": "RUS"},
        {"id": "driver-ver", "firstName": "Max", "lastName": "Verstappen", "tla": "VER"},
    ]
    drivers[0]["teams"] = [{"shortName": "Mercedes AMG F1 Team"}]
    drivers[1]["teams"] = [{"shortName": "Red Bull Racing"}]
    with patch("broiestbot.commands.f1.drivers.fetch_all_pages", new_callable=AsyncMock, return_value=drivers):
        roster = asyncio.run(driver_roster("season-2026"))

    assert roster["driver-rus"]["team"] == "Mercedes"
    assert roster["driver-ver"]["team"] == "Red Bull"
