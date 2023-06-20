"""Fetch sports betting markets."""
from config import RAPID_API_KEY, ODDS_API_ENDPOINT
import requests
from logger import LOGGER


def get_odds(sport_id: str) -> dict:
    """
    Get and format odds for games of a given sport.

    :param str sport_id: ID of sport for which to fetch odds.

    :returns: str
    """
    response = "\n\n\n\n"
    events = fetch_odds_for_sport(sport_id)
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
            response += f"{away_team_name} @ {home_team_name} <i>({status if status == 'live' else start_time})</i>\n"
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


def fetch_odds_for_sport(sport_id: str) -> dict:
    """
    Fetch raw odds data for a given sport.

    :param str sport_id: ID of sport for which to fetch odds.

    :returns: dict
    """
    url = ODDS_API_ENDPOINT
    params = {"sport_id": sport_id, "league_ids": "2635", "event_type": "live", "is_have_odds": "true"}
    headers = {"X-RapidAPI-Key": RAPID_API_KEY, "X-RapidAPI-Host": "pinnacle-odds.p.rapidapi.com"}
    resp = requests.get(url, headers=headers, params=params)
    return resp.json().get("events")
