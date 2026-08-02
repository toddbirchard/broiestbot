"""Fetch sports betting markets."""

from http_client import get_http_session, request_timeout
from logger import LOGGER

from config import ODDS_API_ENDPOINT, RAPID_API_KEY


async def get_odds(sport_id: str) -> str:
    """
    Get and format odds for games of a given sport.

    :param str sport_id: ID of sport for which to fetch odds.

    :returns: str
    """
    try:
        response = "\n\n\n\n"
        events = await fetch_odds_for_sport(sport_id)
        if events:
            for event in events:
                LOGGER.info(f"event: {event}")
                league_name = event["league_name"]
                start_time = event["starts"]
                home_team_name = event["home"]
                away_team_name = event["away"]
                status = event["event_type"]
                moneyline_first_half = event["periods"]["num_0"].get("money_line")
                moneyline_second_half = event["periods"]["num_1"].get("money_line")
                if league_name not in response:
                    response += f"<b>{league_name}<b>\n"
                response += (
                    f"{away_team_name} @ {home_team_name} <i>({status if status == 'live' else start_time})</i>\n"
                )
                if moneyline_first_half:
                    response += f"{home_team_name.upper()} {moneyline_first_half['home']}\n \
                        DRAW {moneyline_first_half['draw']}\n \
                        {away_team_name.upper()} {moneyline_first_half['away']}\n"
                if moneyline_second_half:
                    response += f"{home_team_name.upper()} {moneyline_second_half['home']}\n \
                        DRAW {moneyline_second_half['draw']}\n \
                        {away_team_name.upper()} {moneyline_second_half['away']}\n"
                response += "\n"
        return response
    except Exception as e:
        LOGGER.error(f"Error fetching odds: {e}")
        return "I couldn't fetch the odds at this time."


async def fetch_odds_for_sport(sport_id: str) -> dict:
    """
    Fetch raw odds data for a given sport.

    :param str sport_id: ID of sport for which to fetch odds.

    :returns: dict
    """
    url = ODDS_API_ENDPOINT
    params = {"sport_id": sport_id, "league_ids": "2635", "event_type": "live", "is_have_odds": "true"}
    headers = {"X-RapidAPI-Key": RAPID_API_KEY, "X-RapidAPI-Host": "pinnacle-odds.p.rapidapi.com"}
    session = await get_http_session()
    async with session.get(url, headers=headers, params=params, timeout=request_timeout(20)) as resp:
        body = await resp.text()
        LOGGER.info(f"Response from odds API: {resp.status} {resp.reason} {body}")
        events = await resp.json(content_type=None)
    return events.get("events")
