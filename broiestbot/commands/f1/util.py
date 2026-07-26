"""Helpers for formatting Formula 1 data."""

import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from emoji import emojize

from config import (
    F1_DRIVER_NATIONALITIES,
    F1_NATIONALITY_COUNTRY_CODES,
    TIMEZONE_US_EASTERN,
)

# Shown in place of a flag when a driver's nationality can't be determined.
UNKNOWN_FLAG = emojize(":globe_with_meridians:", language="en")


def country_code_to_flag(country_code: Optional[str]) -> str:
    """
    Build a flag emoji from an ISO 3166-1 alpha-2 country code.

    Flags are pairs of regional indicator symbols, which are offset from ASCII
    uppercase letters by a fixed amount (`A` -> `U+1F1E6`).

    :param Optional[str] country_code: Two-letter country code, ie: `NL`.

    :returns: str
    """
    code = (country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)


def nationality_flag(nationality: Optional[str]) -> str:
    """
    Flag emoji of a driver's nationality.

    :param Optional[str] nationality: Nationality of a driver, ie: `Dutch`.

    :returns: str
    """
    if not nationality:
        return ""
    return country_code_to_flag(F1_NATIONALITY_COUNTRY_CODES.get(nationality.strip().title()))


def normalize_name(name: Optional[str]) -> str:
    """
    Strip accents & casing from a name to make it comparable across data sources.

    :param Optional[str] name: Name of a driver, ie: `Nico Hülkenberg`.

    :returns: str
    """
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).strip().lower()


def driver_flag(driver: dict) -> str:
    """
    Flag emoji of a driver, either from their stated nationality or their surname.

    :param dict driver: Driver object returned by the F1 API.

    :returns: str
    """
    nationality = driver.get("nationality")
    if not nationality:
        surname = normalize_name(driver.get("name")).split(" ")[-1]
        nationality = F1_DRIVER_NATIONALITIES.get(surname)
    return nationality_flag(nationality) or UNKNOWN_FLAG


def driver_flag_from_name(name: Optional[str]) -> str:
    """
    Flag emoji of a driver known only by name (ie: as named by a bookmaker).

    :param Optional[str] name: Full or partial name of a driver.

    :returns: str
    """
    return driver_flag({"name": name})


def parse_race_date(race_date: Optional[str]) -> Optional[datetime]:
    """
    Parse a race's ISO-8601 start time into a timezone-aware datetime.

    Races are always fetched in UTC, so times which arrive without an offset are assumed to be UTC.

    :param Optional[str] race_date: Race start time, ie: `2026-03-08T15:00:00+00:00`.

    :returns: Optional[datetime]
    """
    if not race_date:
        return None
    try:
        parsed_date = datetime.fromisoformat(race_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed_date.tzinfo is None:
        return parsed_date.replace(tzinfo=timezone.utc)
    return parsed_date


def format_race_date(start_time: datetime) -> str:
    """
    Display a race's start time in US eastern time.

    :param datetime start_time: Start time of a race.

    :returns: str
    """
    local_start_time = start_time.astimezone(TIMEZONE_US_EASTERN)
    return local_start_time.strftime("%a %b %-d, %-I:%M%p").replace("AM", "am").replace("PM", "pm") + " ET"


def format_countdown(time_remaining: timedelta) -> str:
    """
    Human-readable countdown until a race starts, ie: `in 3 days`.

    :param timedelta time_remaining: Time between now and a race's start time.

    :returns: str
    """
    seconds_remaining = int(time_remaining.total_seconds())
    if seconds_remaining <= 0:
        return "any moment now"
    if seconds_remaining < 3600:
        minutes = max(seconds_remaining // 60, 1)
        return f"in {minutes} minute{'s' if minutes > 1 else ''}"
    if seconds_remaining < 86400:
        hours = seconds_remaining // 3600
        return f"in {hours} hour{'s' if hours > 1 else ''}"
    days = seconds_remaining // 86400
    return f"in {days} day{'s' if days > 1 else ''}"
