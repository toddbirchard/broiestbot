"""Fetch F1 races, results & starting grids from the Formula 1 API."""

from datetime import datetime, timedelta
from typing import List, Optional

import requests
from logger import LOGGER
from requests.exceptions import HTTPError

from config import (
    F1_HTTP_HEADERS,
    F1_RACE_LIVE_WINDOW_HOURS,
    F1_RACE_RANKINGS_ENDPOINT,
    F1_RACES_ENDPOINT,
    F1_STARTING_GRID_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
)

from .util import parse_race_date

# Race statuses which mean a grand prix will never be run again.
RACE_FINISHED_STATUSES = ("completed", "finished")
RACE_ABANDONED_STATUSES = ("cancelled", "canceled", "postponed")
# Statuses which explicitly flag a grand prix as underway.
RACE_LIVE_STATUSES = ("live", "in progress", "started", "running")


def fetch_season_races(season: int) -> Optional[List[dict]]:
    """
    Fetch every grand prix (race sessions only) scheduled for a given season.

    :param int season: Year of an F1 season, ie: `2026`.

    :returns: Optional[List[dict]]
    """
    return _fetch_f1_data(F1_RACES_ENDPOINT, {"season": season, "type": "Race", "timezone": "UTC"})


def fetch_race_rankings(race_id: int) -> Optional[List[dict]]:
    """
    Fetch driver standings for a single race (live positions while a race is underway).

    :param int race_id: ID of a single grand prix.

    :returns: Optional[List[dict]]
    """
    return _fetch_f1_data(F1_RACE_RANKINGS_ENDPOINT, {"race": race_id})


def fetch_starting_grid(race_id: int) -> Optional[List[dict]]:
    """
    Fetch the starting grid of a single race, which only exists once qualifying is complete.

    :param int race_id: ID of a single grand prix.

    :returns: Optional[List[dict]]
    """
    return _fetch_f1_data(F1_STARTING_GRID_ENDPOINT, {"race": race_id})


def _fetch_f1_data(endpoint: str, params: dict) -> Optional[List[dict]]:
    """
    Fetch & unwrap a response from the Formula 1 API.

    :param str endpoint: Formula 1 API endpoint to be fetched.
    :param dict params: Query parameters to be passed to the endpoint.

    :returns: Optional[List[dict]]
    """
    try:
        resp = requests.get(
            endpoint,
            headers=F1_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("response")
        LOGGER.warning(f"Non-200 response from F1 API `{endpoint}` {params}: {resp.status_code} {resp.text[:300]}")
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching F1 data from `{endpoint}`: {getattr(e.response, 'content', e)}")
    except ValueError as e:
        LOGGER.exception(f"Malformed JSON returned by F1 API `{endpoint}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 data from `{endpoint}`: {e}")
    return None


def race_status(race: dict) -> str:
    """
    Normalized status of a race, ie: `completed`.

    :param dict race: Race object returned by the F1 API.

    :returns: str
    """
    return (race.get("status") or "").strip().lower()


def is_race_finished(race: dict) -> bool:
    """
    Whether a race has been run to completion.

    :param dict race: Race object returned by the F1 API.

    :returns: bool
    """
    return race_status(race) in RACE_FINISHED_STATUSES


def is_race_abandoned(race: dict) -> bool:
    """
    Whether a race has been called off, and as such should never be reported on.

    :param dict race: Race object returned by the F1 API.

    :returns: bool
    """
    return race_status(race) in RACE_ABANDONED_STATUSES


def is_race_live(race: dict, now: datetime) -> bool:
    """
    Whether a race is currently being run.

    A race counts as live when the API says so outright, or when it has started
    within the last few hours without being flagged as finished (red flags, rain
    delays and safety car parades all stretch a race well beyond its scheduled runtime).

    :param dict race: Race object returned by the F1 API.
    :param datetime now: Current UTC time.

    :returns: bool
    """
    if is_race_finished(race) or is_race_abandoned(race):
        return False
    if race_status(race) in RACE_LIVE_STATUSES:
        return True
    start_time = parse_race_date(race.get("date"))
    if start_time is None:
        return False
    return start_time <= now <= start_time + timedelta(hours=F1_RACE_LIVE_WINDOW_HOURS)


def find_live_race(races: List[dict], now: datetime) -> Optional[dict]:
    """
    Find the grand prix currently underway, if any.

    :param List[dict] races: All races in a season.
    :param datetime now: Current UTC time.

    :returns: Optional[dict]
    """
    live_races = [race for race in races if is_race_live(race, now)]
    if live_races:
        return sorted(live_races, key=lambda race: parse_race_date(race.get("date")) or now)[-1]
    return None


def find_next_race(races: List[dict], now: datetime) -> Optional[dict]:
    """
    Find the next grand prix yet to be run.

    :param List[dict] races: All races in a season.
    :param datetime now: Current UTC time.

    :returns: Optional[dict]
    """
    upcoming_races = []
    for race in races:
        if is_race_finished(race) or is_race_abandoned(race):
            continue
        start_time = parse_race_date(race.get("date"))
        if start_time and start_time > now:
            upcoming_races.append((start_time, race))
    if upcoming_races:
        return min(upcoming_races, key=lambda race: race[0])[1]
    return None


def current_lap(race: dict) -> Optional[str]:
    """
    Lap a live race is currently on, ie: `32/57`.

    :param dict race: Race object returned by the F1 API.

    :returns: Optional[str]
    """
    laps = race.get("laps") or {}
    lap = laps.get("current")
    total_laps = laps.get("total")
    if lap and total_laps:
        return f"{lap}/{total_laps}"
    if lap:
        return str(lap)
    return None
