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
                game_id = game["game"]["id"]
                game_summaries += parse_live_nfl_game_summary(game)
                game_events = fetch_live_nfl_game_events(game_id)
                game_summaries += parse_live_nfl_scoring_events(game_events)
        return game_summaries
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def fetch_live_nfl_games():
    """Fetch live NFL games."""
    try:
        current_year = datetime.now().year
        params = {"league": 1, "season": current_year, "live": "all"}
        resp = requests.get(NFL_LIVE_GAMES_URL, headers=NFL_LIVE_HTTP_HEADERS, params=params, timeout=30)
        return resp.json().get("response")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def parse_live_nfl_game_summary(game: dict) -> str:
    """
    Parse live NFL game.

    :params dict game: Dictionary summary of a single live NFL fixture.

    :returns: str
    """
    try:
        venue = game["game"]["venue"]["name"]
        quarter = game["game"]["status"]["short"]
        game_clock = game["game"]["status"]["timer"]
        home_team_name = game["teams"]["home"]["name"]
        home_team_score = game["scores"]["home"]["total"]
        away_team_name = game["teams"]["away"]["name"]
        away_team_score = game["scores"]["away"]["total"]
        return emojize(
            f"<b>{away_team_name} ({away_team_score}) @ {home_team_name} ({home_team_score})</b>\n \
            :stadium: {venue} | <i>({quarter} {game_clock})</i>\n",
            language="en",
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing live NFL game: {e}")


def fetch_live_nfl_game_events(game_id: int):
    """
    Get scoring events for a given live NFL game.

    :param int game_id: ID of live NFL game.

    :returns: dict
    """
    try:
        params = {"id": game_id}
        resp = requests.get(f"{NFL_LIVE_GAMES_URL}/events", headers=NFL_LIVE_HTTP_HEADERS, params=params, timeout=30)
        return resp.json().get("response")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live NFL games: {e}")


def parse_live_nfl_scoring_events(game_events: dict) -> str:
    """
    Parse live NFL scoring events.

    :params dict game_events: Dictionary of scoring events for a given live NFL game.

    :returns: str
    """
    try:
        game_event_summary = ""
        for event in game_events:
            game_event_type = f"<b>* {event['type']}</b>:"
            game_event_description = f"{event['comment']}\n"
            game_event_summary += f"{game_event_type} {game_event_description}"
        return emojize(game_event_summary, language="en")
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing live NFL scoring events: {e}")
