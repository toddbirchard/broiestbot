"""Fetch the F1 drivers' championship standings from the Hyprace API."""

from typing import Dict, List, Optional

from logger import LOGGER

from config import F1_DRIVER_STANDINGS_ENDPOINT, F1_SEASONS_ENDPOINT

from .races import _fetch_hyprace, fetch_all_pages, resolve_season_id

# Season driver rosters, cached by season ID (they change rarely over a season, and resolving
# every driver's name is otherwise several requests per `!f1`).
_DRIVER_ROSTERS: Dict[str, Dict[str, dict]] = {}


def fetch_driver_standings(season: int) -> Optional[List[dict]]:
    """
    Fetch the current drivers' championship standings, resolved to names & teams.

    :param int season: Year of an F1 season, ie: `2026`.

    :returns: Optional[List[dict]]
    """
    try:
        season_id = resolve_season_id(season)
        if season_id is None:
            return None
        data = _fetch_hyprace(F1_DRIVER_STANDINGS_ENDPOINT, {"seasonId": season_id, "isLastStanding": "true"})
        if not data:
            return None
        items = data.get("items") or []
        if not items:
            return None
        roster = _driver_roster(season_id)
        standings = []
        for row in items[0].get("standings") or []:
            position = row.get("position")
            if position is None:
                continue
            driver = roster.get(row.get("driverId")) or {}
            standings.append(
                {
                    "position": position,
                    "points": row.get("points"),
                    "name": driver.get("name"),
                    "tla": driver.get("tla"),
                    "team": driver.get("team"),
                }
            )
        return sorted(standings, key=lambda entry: entry["position"])
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 driver standings: {e}")
        return None


def _driver_roster(season_id: str) -> Dict[str, dict]:
    """
    Build (and cache) a map of driver ID to name, code & team for a season.

    :param str season_id: Hyprace ID of a season.

    :returns: Dict[str, dict]
    """
    if season_id in _DRIVER_ROSTERS:
        return _DRIVER_ROSTERS[season_id]
    drivers = fetch_all_pages(f"{F1_SEASONS_ENDPOINT}/{season_id}/drivers", {})
    if not drivers:
        return {}
    roster = {}
    for driver in drivers:
        driver_id = driver.get("id")
        if not driver_id:
            continue
        name = " ".join(part for part in (driver.get("firstName"), driver.get("lastName")) if part).strip()
        team = (driver.get("teams") or [{}])[0]
        roster[driver_id] = {
            "name": name or None,
            "tla": driver.get("tla"),
            "team": team.get("shortName"),
        }
    _DRIVER_ROSTERS[season_id] = roster
    return roster
