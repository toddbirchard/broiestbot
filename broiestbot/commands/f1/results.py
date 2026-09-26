"""Fetch the classified results of a grand prix from the Hyprace API."""

from typing import List, Optional

from logger import LOGGER

from config import F1_GRANDS_PRIX_ENDPOINT

from .drivers import driver_roster
from .races import MAIN_RACE_SESSION_TYPE, _fetch_hyprace, resolve_season_id

# Result status of a driver who took the chequered flag; anything else (`Dnf`, `Dsq`) is worth
# calling out next to their name.
FINISHED_RESULT_STATUS = "ok"


async def fetch_race_results(grand_prix_id: Optional[str], season: Optional[int]) -> Optional[List[dict]]:
    """
    Fetch the finishing order of a grand prix' race, resolved to driver names & teams.

    Returns an empty list when the race hasn't been classified yet (Hyprace serves the session
    with no participations until then), and `None` when the results couldn't be fetched at all.

    :param Optional[str] grand_prix_id: Hyprace ID of a grand prix.
    :param Optional[int] season: Year of the season the grand prix belongs to, ie: `2026`.

    :returns: Optional[List[dict]]
    """
    if not grand_prix_id or season is None:
        return None
    try:
        session_id = await _race_session_id(grand_prix_id)
        if session_id is None:
            return None
        data = await _fetch_hyprace(f"{F1_GRANDS_PRIX_ENDPOINT}/{grand_prix_id}/races/{session_id}/results", {})
        if data is None:
            return None
        participations = data.get("participations") or []
        if not participations:
            return []
        season_id = await resolve_season_id(season)
        roster = await driver_roster(season_id) if season_id else {}
        results = []
        for participation in participations:
            result = participation.get("result") or {}
            position = result.get("position")
            if position is None:
                continue
            driver = roster.get(participation.get("driverId")) or {}
            results.append(
                {
                    "position": position,
                    "name": driver.get("name"),
                    "tla": driver.get("tla"),
                    "team": driver.get("team"),
                    "time": result.get("time"),
                    "gap": result.get("gapToLeader"),
                    "laps_behind": result.get("lapsBehindLeader"),
                    "grid": result.get("grid"),
                    "points": result.get("points"),
                    "status": (result.get("resultStatus") or {}).get("status"),
                }
            )
        return sorted(results, key=lambda entry: entry["position"])
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 race results: {e}")
        return None


async def _race_session_id(grand_prix_id: str) -> Optional[str]:
    """
    ID of a grand prix' main race session (as opposed to its sprint).

    :param str grand_prix_id: Hyprace ID of a grand prix.

    :returns: Optional[str]
    """
    data = await _fetch_hyprace(f"{F1_GRANDS_PRIX_ENDPOINT}/{grand_prix_id}/races", {})
    if not data:
        return None
    for session in data.get("items") or []:
        if session.get("type") == MAIN_RACE_SESSION_TYPE and session.get("id"):
            return session["id"]
    return None


def is_finisher(entry: dict) -> bool:
    """
    Whether a driver took the chequered flag, as opposed to retiring or being disqualified.

    :param dict entry: Normalized race result entry.

    :returns: bool
    """
    return (entry.get("status") or "").strip().lower() == FINISHED_RESULT_STATUS
