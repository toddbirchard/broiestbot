"""Top scorers for a given league."""

from typing import List, Tuple

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    EPL_LEAGUE_ID,
    FOOTY_HTTP_HEADERS,
    FOOTY_TOPSCORERS_ENDPOINT,
    GOLDEN_SHOE_LEAGUES,
)

from .util import get_season_year


async def epl_golden_boot() -> str:
    """
    Construct list of EPL top scorers.

    :return: str
    """
    try:
        top_scorers = []
        top_scorers.extend(await golden_boot_leaders(league=EPL_LEAGUE_ID))
        if bool(top_scorers):
            top_scorers.sort(key=lambda x: x[0], reverse=True)
            top_scorers = top_scorers[:20]
            top_scorers = [scorer[1] for scorer in top_scorers]
            top_scorers.insert(0, "\n\n\n\n")
            return "\n".join(top_scorers)
        return emojize(":warning: Couldn't find golden boot leaders; bot is shit tbh :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching golden boot leaders: {e}")
        return emojize(":warning: Couldn't find golden boot leaders; bot is shit tbh :warning:", language="en")


async def all_leagues_golden_boot() -> str:
    """
    Fetch list of top scorers per league.

    :return: str
    """
    try:
        top_scorers = []
        for league_id in GOLDEN_SHOE_LEAGUES.values():
            top_scorers.extend(await golden_boot_leaders(league=league_id))
        if bool(top_scorers):
            top_scorers.sort(key=lambda x: x[0], reverse=True)
            top_scorers = top_scorers[:20]
            top_scorers = [scorer[1] for scorer in top_scorers]
            top_scorers.insert(0, "\n\n\n\n")
            return "\n".join(top_scorers)
        return emojize(":warning: Couldn't find golden boot shoe; bot is shit tbh :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching golden shoe leaders: {e}")
        return emojize(":warning: Couldn't find golden boot shoe; bot is shit tbh :warning:", language="en")


async def golden_boot_leaders(league=EPL_LEAGUE_ID) -> List[Tuple[int, str]]:
    """
    Fetch list of top scorers per league.

    :return: str
    """
    try:
        goal_leaders_by_league = await fetch_golden_boot_leaders(league)
        if bool(goal_leaders_by_league):
            return parse_golden_boot_leaders(goal_leaders_by_league)
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching golden boot leaders: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching golden boot leaders: {e}")


async def fetch_golden_boot_leaders(league=EPL_LEAGUE_ID) -> List[Tuple[int, str]]:
    """
    Fetch list of top scorers per league via API.

    :return: List[str]
    """
    try:
        season = get_season_year(EPL_LEAGUE_ID)
        params = {"season": season, "league": league}
        session = await get_http_session()
        async with session.get(FOOTY_TOPSCORERS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            top_scorers = await resp.json(content_type=None)
            return top_scorers.get("response")
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching goal leaders for {league}: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching goal leaders for {league}: {e}")


def parse_golden_boot_leaders(players: dict) -> str:
    """
    Parse "golden boot" API response into readable chat.

    :params dict players: JSON response of players' goal (and other) statistics.

    :returns: str
    """
    try:
        top_scorers = []
        if players:
            for i, player in enumerate(players):
                name = player["player"]["name"]
                team = player["statistics"][0]["team"]["name"]
                goals = player["statistics"][0]["goals"]["total"]
                assists = player["statistics"][0]["goals"].get("assists")
                parsed_assists = f"{assists} assists, " if assists else ""
                shots_on = player["statistics"][0]["shots"].get("on", 0)
                shots_total = player["statistics"][0]["shots"].get("total", 0)
                top_scorers.append(
                    (
                        goals,
                        f"<b>{goals}. {name}</b>, {team} <i>({parsed_assists}{shots_on}/{shots_total} SOG)</i>",
                    )
                )
                if i > 9:
                    break
        return top_scorers
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching golden boot leaders: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching golden boot leaders: {e}")
