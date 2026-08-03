"""Resolve F1 driver IDs to names, codes & teams."""

from typing import Dict

from config import F1_SEASONS_ENDPOINT

from .races import fetch_all_pages

# Season driver rosters, cached by season ID (they change rarely over a season, and resolving
# every driver's name is otherwise several requests per `!f1`).
_DRIVER_ROSTERS: Dict[str, Dict[str, dict]] = {}


async def driver_roster(season_id: str) -> Dict[str, dict]:
    """
    Build (and cache) a map of driver ID to name, code & team for a season.

    :param str season_id: Hyprace ID of a season.

    :returns: Dict[str, dict]
    """
    if season_id in _DRIVER_ROSTERS:
        return _DRIVER_ROSTERS[season_id]
    drivers = await fetch_all_pages(f"{F1_SEASONS_ENDPOINT}/{season_id}/drivers", {})
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
