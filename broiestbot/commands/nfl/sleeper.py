"""Commands related to Sleeper Fantasy Football."""

import requests

from config import SLEEPER_LEAGUE_ID


def fetch_sleeper_rosters():
    """Fetch and return Sleeper fantasy football rosters."""
    url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/rosters"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to fetch rosters"}


def fetch_sleeper_matchups(week: int = 7):
    """Fetch and return Sleeper fantasy football matchups."""

    url = f"https://api.sleeper.app/v1/league/{SLEEPER_LEAGUE_ID}/matchups/{week}"
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to fetch matchups"}
