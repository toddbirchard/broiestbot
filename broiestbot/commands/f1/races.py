"""Fetch F1 seasons, grands prix & circuits from the Hyprace API."""

from datetime import datetime, timedelta
from typing import List, Optional

import requests
from logger import LOGGER
from requests.exceptions import HTTPError

from config import (
    F1_CIRCUITS_ENDPOINT,
    F1_GRANDS_PRIX_ENDPOINT,
    F1_HTTP_HEADERS,
    F1_MAX_PAGES,
    F1_RACE_LIVE_WINDOW_HOURS,
    F1_SEASONS_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
)

from .util import parse_race_date

# Session type which represents the grand prix itself (as opposed to practice, qualifying & sprints).
MAIN_RACE_SESSION_TYPE = "MainRace"

# Grand prix statuses which mean a race will never be run again.
RACE_FINISHED_STATUSES = ("finished", "completed")
RACE_ABANDONED_STATUSES = ("cancelled", "canceled", "postponed", "abandoned")


def fetch_season_races(season: int) -> Optional[List[dict]]:
    """
    Fetch & normalize every grand prix scheduled for a given season.

    :param int season: Year of an F1 season, ie: `2026`.

    :returns: Optional[List[dict]]
    """
    season_id = resolve_season_id(season)
    if season_id is None:
        return None
    grands_prix = fetch_all_pages(F1_GRANDS_PRIX_ENDPOINT, {"seasonId": season_id})
    if grands_prix is None:
        return None
    return [normalize_race(grand_prix) for grand_prix in grands_prix]


def fetch_circuit(circuit_id: Optional[str]) -> Optional[dict]:
    """
    Fetch a circuit's name, host city & country (the source of a grand prix' flag).

    :param Optional[str] circuit_id: Hyprace ID of a circuit.

    :returns: Optional[dict]
    """
    if not circuit_id:
        return None
    data = _fetch_hyprace(f"{F1_CIRCUITS_ENDPOINT}/{circuit_id}", {})
    if not data:
        return None
    country = data.get("country") or {}
    return {
        "name": data.get("name"),
        "city": data.get("place"),
        "country": country.get("name"),
        "country_code": country.get("alphaTwoCode"),
    }


def normalize_race(grand_prix: dict) -> dict:
    """
    Flatten a Hyprace grand prix into the shape the rest of the F1 command consumes.

    The circuit is fetched separately (and only for the race being displayed), so it's
    left empty here to keep season lookups down to a single, quota-friendly request.

    :param dict grand_prix: Grand prix object returned by the Hyprace API.

    :returns: dict
    """
    season = grand_prix.get("season") or {}
    scheduled_distance = grand_prix.get("scheduledDistance")
    return {
        "id": grand_prix.get("id"),
        "name": grand_prix.get("name"),
        "official_name": grand_prix.get("officialName"),
        "round": grand_prix.get("round"),
        "season": season.get("year"),
        "circuit_id": grand_prix.get("circuitId"),
        "circuit": {},
        "date": _main_race_start(grand_prix),
        "status": grand_prix.get("status"),
        "laps": {"total": grand_prix.get("scheduledLaps"), "current": None},
        "distance": f"{scheduled_distance} km" if scheduled_distance else None,
        "weather": None,
    }


def _main_race_start(grand_prix: dict) -> Optional[str]:
    """
    ISO-8601 start time of a grand prix' race session (the lights-out time we care about).

    :param dict grand_prix: Grand prix object returned by the Hyprace API.

    :returns: Optional[str]
    """
    for session in grand_prix.get("schedule") or []:
        if session.get("type") == MAIN_RACE_SESSION_TYPE and session.get("startDate"):
            return session["startDate"]
    return grand_prix.get("startDate")


def resolve_season_id(season: int) -> Optional[str]:
    """
    Look up Hyprace's internal ID for a season, which its schedule & standings are keyed on.

    :param int season: Year of an F1 season, ie: `2026`.

    :returns: Optional[str]
    """
    data = _fetch_hyprace(F1_SEASONS_ENDPOINT, {"year": season})
    if not data:
        return None
    for item in data.get("items") or []:
        if item.get("year") == season and item.get("id"):
            return item["id"]
    return None


def fetch_all_pages(endpoint: str, base_params: dict) -> Optional[List[dict]]:
    """
    Fetch every item from a paginated Hyprace collection, following pages to the last one.

    Hyprace ignores any `pageSize` and serves 10 items a page, keyed on `pageNumber`; items
    are de-duplicated by ID so a season is never double-counted if the API ever repeats a page.

    :param str endpoint: Hyprace collection endpoint to page through.
    :param dict base_params: Query parameters shared across every page request.

    :returns: Optional[List[dict]]
    """
    items: List[dict] = []
    seen_ids = set()
    for page in range(1, F1_MAX_PAGES + 1):
        data = _fetch_hyprace(endpoint, {**base_params, "pageNumber": page})
        if data is None:
            # Surface a total failure, but keep whatever earlier pages we managed to gather.
            return None if page == 1 else items
        for item in data.get("items") or []:
            item_id = item.get("id")
            if item_id is not None and item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            items.append(item)
        total_pages = data.get("totalPages")
        if not data.get("hasNext") or (total_pages and page >= total_pages):
            break
    return items


def _fetch_hyprace(endpoint: str, params: dict) -> Optional[dict]:
    """
    Fetch & parse a JSON response from the Hyprace API.

    :param str endpoint: Hyprace API endpoint to be fetched.
    :param dict params: Query parameters to be passed to the endpoint.

    :returns: Optional[dict]
    """
    try:
        resp = requests.get(
            endpoint,
            headers=F1_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data if isinstance(data, dict) else None
        LOGGER.warning(f"Non-200 response from Hyprace `{endpoint}` {params}: {resp.status_code} {resp.text[:300]}")
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching F1 data from `{endpoint}`: {getattr(e.response, 'content', e)}")
    except ValueError as e:
        LOGGER.exception(f"Malformed JSON returned by Hyprace `{endpoint}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 data from `{endpoint}`: {e}")
    return None


def race_status(race: dict) -> str:
    """
    Normalized status of a race, ie: `finished`.

    :param dict race: Normalized race object.

    :returns: str
    """
    return (race.get("status") or "").strip().lower()


def is_race_finished(race: dict) -> bool:
    """
    Whether a race has been run to completion.

    :param dict race: Normalized race object.

    :returns: bool
    """
    return race_status(race) in RACE_FINISHED_STATUSES


def is_race_abandoned(race: dict) -> bool:
    """
    Whether a race has been called off, and as such should never be reported on.

    :param dict race: Normalized race object.

    :returns: bool
    """
    return race_status(race) in RACE_ABANDONED_STATUSES


def is_race_live(race: dict, now: datetime) -> bool:
    """
    Whether a race is currently being run.

    A race counts as live once its race session has started but hasn't been flagged as
    finished, up to a few hours later (red flags, rain delays and safety car parades all
    stretch a race well beyond its scheduled runtime). Hyprace's `Active` status marks the
    whole race weekend — practice & qualifying included — so the race session's start time,
    not the status, is what tells us the grand prix itself is underway.

    :param dict race: Normalized race object.
    :param datetime now: Current UTC time.

    :returns: bool
    """
    if is_race_finished(race) or is_race_abandoned(race):
        return False
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
