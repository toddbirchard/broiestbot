"""Commands related to Sleeper Fantasy Football."""

from typing import Optional
import requests

from config import SLEEPER_LEAGUE_ID
from logger import LOGGER


def get_sleeper_week_number() -> Optional[int]:
    """
    Get the current NFL week number from Sleeper API.

    :returns: Optional[int]
    """
    LOGGER.info("Fetching current NFL week number from Sleeper...")
    url = "https://api.sleeper.app/v1/state/nfl"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        LOGGER.info(f"Sleeper NFL Week: {data['week']}")
        return data["week"]
    return None


def get_sleeper_league_users() -> dict:
    """Fetch and return Sleeper fantasy football league users."""
    try:
        league_users = {}

        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/users"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            for league_user in response.json():
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


def fetch_sleeper_rosters(users: dict):
    """Fetch and return Sleeper fantasy football rosters."""
    try:
        roster_users = []
        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/rosters"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            for roster in response.json():
                users[roster["owner_id"]].update({"roster_id": roster["roster_id"]})
                roster_users.append(users[roster["owner_id"]])
        return roster_users
    except Exception as e:
        LOGGER.error(f"Error fetching Sleeper rosters: {e}")
        return {"error": "An error occurred while fetching rosters"}


def fetch_sleeper_matchups(username: str) -> str:
    """Fetch and return Sleeper fantasy football matchups."""
    try:
        LOGGER.info("Fetching Sleeper matchups...")
        week_number = get_sleeper_week_number()
        if week_number is None:
            return f"Sorry @{username}, NFL season is OVAH!!! MORAN!!!!"

        users = get_sleeper_league_users()
        users = fetch_sleeper_rosters(users)

        url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/matchups/{week_number}"
        response = requests.get(url, timeout=10)

        matchups_response = "\n\n\n"

        if response.status_code == 200:
            matchups = sorted(response.json(), key=lambda m: m["matchup_id"])
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
        else:
            return "Failed to fetch matchups"
    except Exception as e:
        LOGGER.error(f"Error fetching Sleeper matchups: {e}")
        return "An error occurred while fetching matchups"
