"""Get team standings for a given league."""

from typing import Optional

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    AALESUND_TEAM_ID,
    ELITESERIEN_LEAGUE_ID,
    FOOTY_HTTP_HEADERS,
    FOOTY_STANDINGS_ENDPOINT,
    MLS_LEAGUE_ID,
    OBOS_LIGAEN_ID,
)

from .util import abbreviate_team_name, get_season_year


async def league_table_standings(league_id: int) -> Optional[str]:
    """
    Get table standings for a given league.

    :param int league_id: ID of league to get table standings for.

    :returns: Optional[str]
    """
    try:
        league_table_response = await fetch_league_table_standings(league_id)
        if league_table_response:
            standings_table = "\n\n\n\n"
            standings = league_table_response[0]["league"]["standings"][0]
            for standing in standings:
                rank = standing["rank"]
                team = standing["team"]["name"]
                points = standing["points"]
                wins = standing["all"]["win"]
                draws = standing["all"]["draw"]
                losses = standing["all"]["lose"]
                standings_table = (
                    standings_table + f"<b>{rank:5}. {team}</b>: {points}pts <i>({wins}W {draws}D {losses}L)</i>\n"
                )
            if standings_table != "\n\n\n\n":
                return standings_table
        return emojize(":warning: Couldn't fetch standings :warning:", language="en")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching {league_id} standings: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching {league_id} standings: {e}")


async def fetch_league_table_standings(league_id: int) -> Optional[dict]:
    """
    Fetch league table standings for a given league.

    :param int league_id: ID of league to get table standings for.

    :returns: Optional[dict]
    """
    try:
        params = {"league": league_id, "season": get_season_year(league_id)}
        session = await get_http_session()
        async with session.get(FOOTY_STANDINGS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            if resp.status == 200:
                standings = await resp.json(content_type=None)
                return standings.get("response")
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching {league_id} standings: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching {league_id} standings: {e}")


async def aafk_league_table_standings() -> Optional[str]:
    """
    Get table standings for whichever Norwegian league Aalesund currently play in.

    Aalesund yo-yo between Eliteserien and OBOS-Ligaen, so the league is resolved per
    request rather than hardcoded.

    :returns: Optional[str]
    """
    try:
        league_id = await fetch_team_current_league(AALESUND_TEAM_ID, (ELITESERIEN_LEAGUE_ID, OBOS_LIGAEN_ID))
        if league_id is None:
            return emojize(":warning: Couldn't determine which league AAFK are in :warning:", language="en")
        league_table_response = await fetch_league_table_standings(league_id)
        if league_table_response:
            league_name = league_table_response[0]["league"]["name"]
            standings_table = f"\n\n\n\n<b>:Norway: {league_name.upper()}</b>\n"
            standings = league_table_response[0]["league"]["standings"][0]
            for standing in standings:
                rank = standing["rank"]
                team = abbreviate_team_name(standing["team"]["name"])
                points = standing["points"]
                wins = standing["all"]["win"]
                draws = standing["all"]["draw"]
                losses = standing["all"]["lose"]
                goal_diff = standing["goalsDiff"]
                row = f"<b>{rank}. {team}</b> {points}pts <i>({wins}W {draws}D {losses}L, {goal_diff}GD)</i>"
                if standing["team"]["id"] == AALESUND_TEAM_ID:
                    row += " :fire:"
                standings_table += f"{row}\n"
            return emojize(standings_table, language="en")
        return emojize(":warning: Couldn't fetch standings :warning:", language="en")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching AAFK standings: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching AAFK standings: {e}")


async def fetch_team_current_league(team_id: int, eligible_league_ids: tuple) -> Optional[int]:
    """
    Determine which of a team's possible leagues they currently have a table position in.

    :param int team_id: ID of footy team to resolve the current league of.
    :param tuple eligible_league_ids: League IDs the team could plausibly be in, in order of preference.

    :returns: Optional[int]
    """
    try:
        params = {"team": team_id, "season": get_season_year(eligible_league_ids[0])}
        session = await get_http_session()
        async with session.get(FOOTY_STANDINGS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            if resp.status == 200:
                standings = await resp.json(content_type=None)
                league_ids = [league["league"]["id"] for league in standings.get("response", [])]
                for league_id in eligible_league_ids:
                    if league_id in league_ids:
                        return league_id
                LOGGER.warning(f"Team {team_id} not found in leagues {eligible_league_ids}; found {league_ids}")
    except ClientError as e:
        LOGGER.error(f"ClientError while resolving current league for team {team_id}: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when resolving current league for team {team_id}: {e}")


async def mls_standings() -> Optional[str]:
    """
    Fetch and parse standings for MLS (regular season).

    :returns: Optional[str]
    """
    try:
        mls_standings_response = await fetch_league_table_standings(MLS_LEAGUE_ID)
        if mls_standings_response:
            standings_table = "\n\n\n\n"
            for i, conference in enumerate(mls_standings_response[0]["league"]["standings"]):
                conference_table = mls_conference_standings(conference)
                if conference_table:
                    standings_table += conference_table
                if i == 0:
                    standings_table += "\n\n"
                elif standings_table != "\n\n\n\n":
                    return emojize(standings_table, language="en")
        return emojize(":warning: Couldn't fetch standings :warning:", language="en")
    except ClientError as e:
        LOGGER.error(f"ClientError while fetching {MLS_LEAGUE_ID} standings: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching {MLS_LEAGUE_ID} standings: {e}")


def mls_conference_standings(conference_standings: dict):
    """
    Parse standings for a given MLS conference.

    :param dict conference_standings: MLS standings for East OR West conference.

    :returns: str
    """
    try:
        conference_standings_table = ""
        conference_standings_table += f"<b>{conference_standings[0]['group'].upper()}</b>\n"
        for team_standing in conference_standings:
            rank = team_standing["rank"]
            name = abbreviate_team_name(team_standing["team"]["name"])
            points = team_standing["points"]
            wins = team_standing["all"]["win"]
            draws = team_standing["all"]["draw"]
            losses = team_standing["all"]["lose"]
            goalDiff = team_standing["goalsDiff"]
            form = (
                team_standing["form"]
                .replace("W", ":green_circle:")
                .replace("L", ":red_circle:")
                .replace("D", ":white_circle:")
            )
            conference_standings_table += (
                f"<b>{rank}. {name}</b> {points}pts <i>({wins}W {draws}D {losses}L, {goalDiff}GD)</i> {form}\n"
            )
        if conference_standings_table != "":
            return f"{conference_standings_table}\n"
    except KeyError as e:
        LOGGER.error(f"KeyError when parsing MLS conference standings: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing MLS conference standings: {e}")
