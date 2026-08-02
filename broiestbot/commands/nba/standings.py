"""Fetch NBA team standings."""

from aiohttp import ClientError
from http_client import get_http_session
from logger import LOGGER

from config import NBA_API_KEY, NBA_BASE_URL, NBA_CONFERENCE_NAMES, NBA_SEASON_YEAR


async def nba_standings() -> str:
    """
    Fetch NBA team standings per conference for the regular season.

    :returns: str
    """
    try:
        standings = "\n\n\n"
        for conference in NBA_CONFERENCE_NAMES:
            params = {
                "league": "12",
                "season": NBA_SEASON_YEAR,
                "group": conference,
                "stage": "NBA - Regular Season",
            }
            endpoint = f"{NBA_BASE_URL}/standings"
            headers = {
                "x-rapidapi-host": "api-basketball.p.rapidapi.com",
                "x-rapidapi-key": NBA_API_KEY,
            }
            session = await get_http_session()
            async with session.get(endpoint, headers=headers, params=params) as resp:
                if resp.status != 200:
                    continue
                conference_standings = await resp.json(content_type=None)
            standings += f"{conference.upper()}\n"
            for team_info in conference_standings.get("response")[0]:
                team_standing = f"{team_info['position']}. {team_info['team']['name']} {team_info['games']['win']['total']}-{team_info['games']['lose']['total']} ({team_info['games']['win']['percentage']})\n"
                standings += team_standing
            standings += "\n"
        return standings
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching NBA standings: {e}")
    except LookupError as e:
        LOGGER.error(f"LookupError while fetching NBA standings: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching NBA standings: {e}")
