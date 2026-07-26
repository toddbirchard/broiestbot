"""Fetch the F1 drivers' championship standings from the Hyprace API."""

from typing import List, Optional

from logger import LOGGER

from config import F1_DRIVER_STANDINGS_ENDPOINT

from .drivers import driver_roster
from .races import _fetch_hyprace, resolve_season_id


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
        roster = driver_roster(season_id)
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
