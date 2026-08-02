"""Tests for weather condition -> emoji resolution."""

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from emoji import emojize

from broiestbot.commands.weather import get_weather_emoji

NIGHT_SKY = emojize(":night_with_stars:", language="en")


class _FakeResult:
    """Stand-in for a SQLAlchemy `Result` carrying a single (or no) `Weather` row."""

    def __init__(self, row):
        self._row = row

    def scalars(self):
        return self

    def one_or_none(self):
        return self._row


class _FakeSession:
    """Async session which serves one canned `Weather` row."""

    def __init__(self, row):
        self._row = row

    async def execute(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult(self._row)

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False


def _resolve(row, is_day: str) -> str:
    """Resolve the emoji for a weather code whose lookup returns `row`."""
    with patch("broiestbot.commands.weather.async_session", return_value=_FakeSession(row)):
        return asyncio.run(get_weather_emoji(113, is_day))


def test_known_condition_uses_its_icon():
    """A weather code present in the table renders that row's icon."""
    assert _resolve(SimpleNamespace(icon=":cloud_with_rain:", group="rain"), "yes") == ":cloud_with_rain:"


def test_unknown_weather_code_falls_back_to_the_sun():
    """
    Weatherstack serves codes the `weather` table has no row for. That must fall back
    to the default icon rather than dereferencing the missing row.
    """
    assert _resolve(None, "yes") == ":sun:"


def test_unknown_weather_code_at_night_also_falls_back():
    """The same fallback applies after dark, where the missing row used to be read."""
    assert _resolve(None, "no") == ":sun:"


def test_sun_group_is_swapped_for_a_night_sky_after_dark():
    """A clear-sky condition renders as a night sky rather than a sun once it's dark."""
    assert _resolve(SimpleNamespace(icon=":sun:", group="sun"), "no") == NIGHT_SKY


def test_sun_group_keeps_its_icon_during_the_day():
    """The same clear-sky condition keeps its sun during daylight."""
    assert _resolve(SimpleNamespace(icon=":sun:", group="sun"), "yes") == ":sun:"


def test_non_sun_conditions_keep_their_icon_after_dark():
    """Rain looks the same at night, so only sun-group conditions are swapped."""
    assert _resolve(SimpleNamespace(icon=":cloud_with_rain:", group="rain"), "no") == ":cloud_with_rain:"
