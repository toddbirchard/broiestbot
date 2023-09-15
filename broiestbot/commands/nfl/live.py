"""Live NFL game stats."""
from datetime import datetime
import requests
from config import NFL_LIVE_HTTP_HEADERS, NFL_LIVE_GAMES_URL
from emoji import emojize
from logger import LOGGER


def get_leaders_per_game():
    """Get passing and rushing leaders for live NFL game."""
    try:
        game_summaries = "\n\n\n"
        games = fetch_live_nfl_games()
        if bool(games):
            for game in games:
                game_summaries += parse_live_nfl_game(game)
        return game_summaries
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def fetch_live_nfl_games():
    """Fetch live NFL games."""
    try:
        current_year = datetime.now().year
        params = {"league": 1, "season": current_year, "live": "all"}
        resp = requests.get(NFL_LIVE_GAMES_URL, headers=NFL_LIVE_HTTP_HEADERS, params=params, timeout=30)
        LOGGER.info(f"NFL games: {resp.json()}")
        return resp.json().get("response")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def parse_live_nfl_game(game: dict) -> str:
    """
    Parse live NFL game.

    :params dict game: Dictionary summary of a single live NFL fixture.

    :returns: str
    """
    try:
        venue = game["game"]["venue"]["name"]
        quarter = game["game"]["status"]["short"]
        game_clock = game["game"]["status"]["timer"]
        home_team_name = game["teams"]["home_team"]
        away_team_name = game["teams"]["away_team"]
        return emojize(
            f"<b>{away_team_name} @ {home_team_name}</b>\n \
            :stadium: <i>{venue}</i>\n \
            :eight-thirty: {quarter} {game_clock}\n\n",
            language="en",
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing live NFL game: {e}")
