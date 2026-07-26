"""Fetch the starting grid of a grand prix from the Hyprace API."""

from typing import List, Optional

from logger import LOGGER

from config import F1_GRANDS_PRIX_ENDPOINT

from .drivers import driver_roster
from .races import _fetch_hyprace, resolve_season_id

# Qualifying session which sets the grid for the grand prix itself. Sprint weekends also carry a
# `Sprint` session, but that one only decides the order of the sprint race.
GRAND_PRIX_QUALIFYING_TYPE = "Standard"

# Qualifying status of a driver who set a time & starts where they qualified; anything else
# (a penalty, a withdrawal) is worth calling out next to their name.
QUALIFIED_STATUS = "qualified"

# Qualifying segments, in the order a driver's best lap is most likely to have been set.
QUALIFYING_SEGMENTS = ("q3", "q2", "q1")


def fetch_starting_grid(grand_prix_id: Optional[str], season: Optional[int]) -> Optional[List[dict]]:
    """
    Fetch the starting grid of a grand prix, as set by its qualifying session.

    Returns an empty list when qualifying hasn't been run yet (Hyprace serves the session with
    no results until then), and `None` when the grid couldn't be fetched at all.

    :param Optional[str] grand_prix_id: Hyprace ID of a grand prix.
    :param Optional[int] season: Year of the season the grand prix belongs to, ie: `2026`.

    :returns: Optional[List[dict]]
    """
    if not grand_prix_id or season is None:
        return None
    try:
        session_id = _qualifying_session_id(grand_prix_id)
        if session_id is None:
            return None
        data = _fetch_hyprace(f"{F1_GRANDS_PRIX_ENDPOINT}/{grand_prix_id}/qualifying/{session_id}/results", {})
        if data is None:
            return None
        results = data.get("results") or []
        if not results:
            # Qualifying is still to come; the caller falls back to the championship standings.
            return []
        season_id = resolve_season_id(season)
        roster = driver_roster(season_id) if season_id else {}
        grid = []
        for result in results:
            position = result.get("position")
            if position is None:
                continue
            driver = roster.get(result.get("driverId")) or {}
            grid.append(
                {
                    "position": position,
                    "name": driver.get("name"),
                    "tla": driver.get("tla"),
                    "team": driver.get("team"),
                    "time": _best_lap(result),
                    "status": result.get("status"),
                }
            )
        return sorted(grid, key=lambda entry: entry["position"])
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 starting grid: {e}")
        return None


def _qualifying_session_id(grand_prix_id: str) -> Optional[str]:
    """
    ID of the qualifying session which sets a grand prix' grid.

    :param str grand_prix_id: Hyprace ID of a grand prix.

    :returns: Optional[str]
    """
    data = _fetch_hyprace(f"{F1_GRANDS_PRIX_ENDPOINT}/{grand_prix_id}/qualifying", {})
    if not data:
        return None
    sessions = data.get("items") or []
    for session in sessions:
        if session.get("type") == GRAND_PRIX_QUALIFYING_TYPE and session.get("id"):
            return session["id"]
    return None


def _best_lap(result: dict) -> Optional[str]:
    """
    A driver's best qualifying lap, from the last segment they took part in.

    :param dict result: Qualifying result row returned by the Hyprace API.

    :returns: Optional[str]
    """
    for segment in QUALIFYING_SEGMENTS:
        if result.get(segment):
            return result[segment]
    return None


def is_qualified(entry: dict) -> bool:
    """
    Whether a driver starts the race where they qualified, as opposed to being penalized or out.

    :param dict entry: Normalized starting grid entry.

    :returns: bool
    """
    return (entry.get("status") or "").strip().lower() == QUALIFIED_STATUS
