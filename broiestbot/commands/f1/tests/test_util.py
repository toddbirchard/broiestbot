"""Tests for Formula 1 formatting helpers."""

from datetime import datetime, timedelta, timezone

from broiestbot.commands.f1.util import (
    UNKNOWN_FLAG,
    country_code_to_flag,
    country_flag,
    driver_flag,
    driver_flag_from_name,
    format_countdown,
    format_odds,
    format_race_date,
    nationality_flag,
    normalize_name,
    parse_race_date,
)
from config import (
    F1_COUNTRY_CODES,
    F1_DRIVER_NATIONALITIES,
    F1_NATIONALITY_COUNTRY_CODES,
)

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def test_country_code_becomes_flag_emoji():
    """Two-letter country codes are converted to regional indicator pairs."""
    assert country_code_to_flag("NL") == "🇳🇱"
    assert country_code_to_flag("gb") == "🇬🇧"


def test_invalid_country_code_has_no_flag():
    """Garbage country codes yield an empty string rather than mojibake."""
    assert country_code_to_flag(None) == ""
    assert country_code_to_flag("") == ""
    assert country_code_to_flag("NLD") == ""
    assert country_code_to_flag("N1") == ""


def test_host_country_flag():
    """Grand prix host countries are matched case-insensitively."""
    assert country_flag("Bahrain") == "🇧🇭"
    assert country_flag("united states") == "🇺🇸"
    assert country_flag("Atlantis") == ""
    assert country_flag(None) == ""


def test_nationality_flag():
    """Driver nationalities map to their country's flag."""
    assert nationality_flag("Dutch") == "🇳🇱"
    assert nationality_flag("monegasque") == "🇲🇨"
    assert nationality_flag("Martian") == ""


def test_driver_flag_prefers_stated_nationality():
    """A driver's own nationality is used whenever the API provides one."""
    assert driver_flag({"name": "Max Verstappen", "nationality": "Dutch"}) == "🇳🇱"


def test_driver_flag_falls_back_to_surname():
    """Responses without a nationality fall back to a lookup by surname."""
    assert driver_flag({"name": "Charles Leclerc"}) == "🇲🇨"
    assert driver_flag_from_name("L. Hamilton") == "🇬🇧"


def test_driver_flag_ignores_accents():
    """Accented surnames still match their nationality."""
    assert driver_flag({"name": "Nico Hülkenberg"}) == "🇩🇪"
    assert driver_flag({"name": "Sergio Pérez"}) == "🇲🇽"


def test_unknown_driver_gets_placeholder_flag():
    """Drivers of unknown nationality get a placeholder rather than no flag at all."""
    assert driver_flag({"name": "Todd Birchard"}) == UNKNOWN_FLAG
    assert driver_flag({}) == UNKNOWN_FLAG


def test_configured_countries_all_have_valid_flags():
    """Every configured country code resolves to a flag emoji."""
    for country_code in {**F1_COUNTRY_CODES, **F1_NATIONALITY_COUNTRY_CODES}.values():
        assert country_code_to_flag(country_code) != ""


def test_configured_driver_nationalities_are_known():
    """Every driver's fallback nationality has a country code to match."""
    for nationality in F1_DRIVER_NATIONALITIES.values():
        assert nationality_flag(nationality) != ""


def test_names_are_normalized_for_comparison():
    """Accents & casing are stripped when comparing names across data sources."""
    assert normalize_name("Nico Hülkenberg") == "nico hulkenberg"
    assert normalize_name(None) == ""


# ---------------------------------------------------------------------------
# Dates & odds
# ---------------------------------------------------------------------------


def test_race_dates_are_parsed_as_utc():
    """ISO-8601 race dates are parsed, defaulting to UTC when no offset is given."""
    assert parse_race_date("2026-03-08T15:00:00+00:00") == datetime(2026, 3, 8, 15, tzinfo=timezone.utc)
    assert parse_race_date("2026-03-08T15:00:00Z") == datetime(2026, 3, 8, 15, tzinfo=timezone.utc)
    assert parse_race_date("2026-03-08T15:00:00") == datetime(2026, 3, 8, 15, tzinfo=timezone.utc)


def test_unparseable_race_dates_are_dropped():
    """Missing or malformed race dates return None instead of raising."""
    assert parse_race_date(None) is None
    assert parse_race_date("next sunday") is None


def test_race_dates_display_in_eastern_time():
    """Race start times are displayed in US eastern time."""
    assert format_race_date(datetime(2026, 3, 8, 15, tzinfo=timezone.utc)) == "Sun Mar 8, 11:00am ET"


def test_countdown_scales_with_time_remaining():
    """Countdowns are rounded to the largest sensible unit."""
    assert format_countdown(timedelta(days=3, hours=2)) == "in 3 days"
    assert format_countdown(timedelta(days=1)) == "in 1 day"
    assert format_countdown(timedelta(hours=5)) == "in 5 hours"
    assert format_countdown(timedelta(minutes=22)) == "in 22 minutes"
    assert format_countdown(timedelta(seconds=30)) == "in 1 minute"
    assert format_countdown(timedelta(seconds=-60)) == "any moment now"


def test_odds_formatting():
    """Decimal prices keep two decimals, including longshots."""
    assert format_odds(1.7) == "1.70"
    assert format_odds(26.0) == "26.00"
    assert format_odds(2500) == "2500.00"
    assert format_odds(-140) == "-140"
    assert format_odds(None) == ""
