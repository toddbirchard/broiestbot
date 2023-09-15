"""NFL games scheduled for today with scores & odds."""
from datetime import datetime, timedelta
from typing import Optional
import requests
import pytz
from emoji import emojize
from requests.exceptions import HTTPError

from config import NFL_GAMES_URL, NFL_HTTP_HEADERS, HTTP_REQUEST_TIMEOUT
from logger import LOGGER


def get_today_nfl_games() -> str:
    """
    Get summary of all live NFL games, scores and odds.

    :returns: str
    """
    try:
        games = fetch_today_nfl_games()
        if bool(games):
            game_summaries = "\n\n\n\n"
            for game in games:
                game_summaries += format_nfl_game(game)
            return game_summaries
        return emojize(
            ":prohibited: :american_football: bruh there's no NFL today MORAN!! :american_football: :prohibited:",
            language="en",
        )
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching live NFL games: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def fetch_today_nfl_games() -> Optional[dict]:
    """
    Get summary of NFL games scheduled today; includes scores and odds.

    :returns: str
    """
    try:
        todays_date = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")
        params = {"league": "NFL", "date": todays_date}
        resp = requests.get(NFL_GAMES_URL, headers=NFL_HTTP_HEADERS, params=params, timeout=HTTP_REQUEST_TIMEOUT)
        return resp.json().get("results")
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching NFL games: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching NFL games: {e}")


def format_nfl_game(game: dict) -> str:
    """
    Construct a summary of an NFL fixture.

    :params dict game: Dictionary summary of a single live NFL fixture.

    :returns: str
    """
    # fmt: off
    fixture_status = game["status"]
    away_team_score = ""
    home_team_score = ""
    fixture_start_time = datetime.strptime(game["schedule"]["date"], "%Y-%m-%dT%H:%M:%S.000Z")
    fixture_start_time = fixture_start_time - timedelta(hours=4)
    fixture_display_start_time = datetime.strftime(fixture_start_time, "%b %d, %l:%M%p")
    away_team_city = game["teams"]["away"]["abbreviation"]
    away_team_name = game["teams"]["away"]["mascot"]
    away_team_current_spread = game["odds"][0]["spread"]["current"]["away"]
    away_team_current_moneyline = game["odds"][0]["moneyline"]["current"]["awayOdds"]
    home_team_city = game["teams"]["home"]["abbreviation"]
    home_team_name = game["teams"]["home"]["mascot"]
    home_team_current_spread = game["odds"][0]["spread"]["current"]["home"]
    home_team_current_moneyline = game["odds"][0]["moneyline"]["current"]["homeOdds"]
    if fixture_status == "in progress":
        fixture_current_period = game["scoreboard"]["currentPeriod"]
        fixture_period_time_remaining = game["scoreboard"]["periodTimeRemaining"]
    if fixture_status != "scheduled":
        away_team_score = f"({game['scoreboard']['score']['away']})"
        home_team_score = f"({game['scoreboard']['score']['home']})"
    if away_team_current_spread > 0:
        away_team_current_spread = f"+{away_team_current_spread}"
        away_team_current_moneyline = f"+{away_team_current_moneyline}"
    if home_team_current_spread > 0:
        home_team_current_spread = f"+{home_team_current_spread}"
        home_team_current_moneyline = f"+{home_team_current_moneyline}"
    summary = f"<b>{away_team_city} {away_team_name} {away_team_score} @ {home_team_city} {home_team_name} {home_team_score}</b>\n"
    if fixture_status == "final":
        summary += ":chequered_flag: <i>FINAL</i>\n"
    if fixture_status == "scheduled":
        summary += f":calendar: {fixture_display_start_time}\n"
    if fixture_status == "in progress":
        summary += f":one-thirty: Period {fixture_current_period}, {fixture_period_time_remaining}\n"
    summary += f"<b>{away_team_city}</b> {away_team_current_spread} ({away_team_current_moneyline})\n \
                <b>{home_team_city}</b> {home_team_current_spread} ({home_team_current_moneyline})\n\n"
    # fmt: on
    return emojize(summary, language="en")
