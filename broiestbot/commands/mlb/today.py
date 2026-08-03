"""Fetch Phillies MLB game summaries for the current date."""

from datetime import datetime
from typing import Optional

import pytz
from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import MLB_BASE_ENDPOINT, MLB_LEAGUE_ID, MLB_PHILLIES_ID, RAPID_API_KEY

from .util import parse_mlb_game


async def today_phillies_games() -> str:
    """
    Fetch live or upcoming Phillies games for the current date.

    :returns: str
    """
    today_games_response = "\n\n\n\n"
    today_games = await get_today_games()
    if bool(today_games):
        for game in today_games:
            mlb_game = await parse_mlb_game(game)
            if mlb_game is not None:
                today_games_response += mlb_game
                return today_games_response
    return emojize(":warning: Couldn't find any MLB games :warning:", language="en")


async def get_today_games() -> Optional[dict]:
    """
    Fetch Phillies games scheduled for the current date.

    :returns: Optional[dict]
    """
    try:
        url = f"{MLB_BASE_ENDPOINT}/games"
        today = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")
        params = {
            "league": MLB_LEAGUE_ID,
            "season": str(datetime.now().year),
            "team": MLB_PHILLIES_ID,
            "date": today,
            "timezone": "America/New_York",
        }
        headers = {
            "X-RapidAPI-Host": "api-baseball.p.rapidapi.com",
            "X-RapidAPI-Key": RAPID_API_KEY,
        }
        session = await get_http_session()
        async with session.get(url, headers=headers, params=params) as resp:
            games = await resp.json(content_type=None) if resp.status == 200 else None
            if games:
                return games.get("response")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching MLB games: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching MLB games: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching MLB games: {e}")
