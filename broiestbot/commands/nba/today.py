"""Fetch all (live & upcoming) NBA games for today."""

from datetime import datetime
from typing import List, Optional

import pytz
from aiohttp import ClientError
from http_client import get_http_session
from logger import LOGGER

from config import NBA_BASE_URL, NBA_SEASON_YEAR, RAPID_API_KEY


async def today_nba_games() -> Optional[List[dict]]:
    """
    Fetch all NBA games for the current date.

    :returns: Optional[List[dict]]
    """
    try:
        endpoint = f"{NBA_BASE_URL}/games"
        params = {
            "timezone": "America/New_York",
            "season": NBA_SEASON_YEAR,
            "league": "12",
            "date": datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d"),
        }
        headers = {
            "X-RapidAPI-Host": "api-basketball.p.rapidapi.com",
            "X-RapidAPI-Key": RAPID_API_KEY,
        }
        session = await get_http_session()
        async with session.get(endpoint, headers=headers, params=params) as resp:
            if resp.status == 200:
                games = await resp.json(content_type=None)
                return games.get("response")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching today's NBA games: {e}")
    except LookupError as e:
        LOGGER.exception(f"LookupError while fetching today's NBA games: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching today's NBA games: {e}")
    return None
