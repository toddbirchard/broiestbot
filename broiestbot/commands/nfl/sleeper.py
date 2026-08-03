"""Commands related to Sleeper Fantasy Football."""

from typing import Optional

from http_client import get_http_session, request_timeout
from logger import LOGGER

from config import SLEEPER_LEAGUE_ID


async def get_sleeper_week_number() -> Optional[int]:
    """
    Get the current NFL week number from Sleeper API.

    :returns: Optional[int]
    """
    LOGGER.info("Fetching current NFL week number from Sleeper...")
    url = "https://api.sleeper.app/v1/state/nfl"
    session = await get_http_session()
    async with session.get(url, timeout=request_timeout(10)) as resp:
        if resp.status == 200:
            data = await resp.json(content_type=None)
            LOGGER.info(f"Sleeper NFL Week: {data['week']}")
            return data["week"]
    return None


async def get_sleeper_league_users() -> dict:
    """Fetch and return Sleeper fantasy football league users."""
    try:
        league_users = {}

        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/users"
        session = await get_http_session()
        async with session.get(url, timeout=request_timeout(10)) as resp:
            league_user_response = await resp.json(content_type=None) if resp.status == 200 else []
        for league_user in league_user_response:
            user = {
                league_user["user_id"]: {
                    "user_id": league_user["user_id"],
                    "username": league_user["display_name"],
                    "avatar": league_user["metadata"].get("avatar"),
                    "team_name": league_user["metadata"].get("team_name"),
                    "commish": league_user.get("is_owner", False),
                }
            }
            league_users.update(user)
        return league_users
    except Exception as e:
        LOGGER.error(f"Error fetching Sleeper league users: {e}")
        return {}


async def fetch_sleeper_rosters(users: dict):
    """Fetch and return Sleeper fantasy football rosters."""
    try:
        roster_users = []
        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/rosters"
        session = await get_http_session()
        async with session.get(url, timeout=request_timeout(10)) as resp:
            rosters = await resp.json(content_type=None) if resp.status == 200 else []
        for roster in rosters:
            users[roster["owner_id"]].update({"roster_id": roster["roster_id"]})
            roster_users.append(users[roster["owner_id"]])
        return roster_users
    except Exception as e:
        LOGGER.error(f"Error fetching Sleeper rosters: {e}")
        return {"error": "An error occurred while fetching rosters"}


async def fetch_sleeper_matchups(username: str) -> str:
    """Fetch and return Sleeper fantasy football matchups."""
    try:
        LOGGER.info("Fetching Sleeper matchups...")
        week_number = await get_sleeper_week_number()
        if week_number is None:
            return f"Sorry @{username}, NFL season is OVAH!!! MORAN!!!!"

        users = await get_sleeper_league_users()
        users = await fetch_sleeper_rosters(users)

        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/matchups/{week_number}"
        session = await get_http_session()
        async with session.get(url, timeout=request_timeout(10)) as resp:
            if resp.status != 200:
                return "Failed to fetch matchups"
            matchups = sorted(await resp.json(content_type=None), key=lambda m: m["matchup_id"])

        matchups_response = "\n\n\n"

        j = 0
        for i in range(0, len(matchups), 2):
            LOGGER.info("------------------------------")
            team1 = matchups[j]
            team2 = matchups[j + 1]
            LOGGER.info(f"Matchup #{j} | i = {i}")
            LOGGER.info(f"Team 1: {team1}")
            LOGGER.info(f"Player 1: {users[team1['roster_id']]}")
            LOGGER.info(f"Team 2: {team2}")
            LOGGER.info(f"Player 2: {users[team2['roster_id']]}")
            LOGGER.info("------------------------------")
            matchups_response += f"<b>{users[team1['roster_id']]['team_name']}</b> ({users[team1['roster_id']]['username']}) vs <b>{users[team2['roster_id']]['team_name']}</b> ({users[team2['roster_id']]['username']})\n WIP lol \n\n"
            j += 1
        LOGGER.info(f"MATCHUPS: {matchups_response}")
        return matchups_response
    except Exception as e:
        LOGGER.error(f"Error fetching Sleeper matchups: {e}")
        return "An error occurred while fetching matchups"
