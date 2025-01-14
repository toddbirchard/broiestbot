"""Get general fixture stats for live fixtures."""

from typing import Optional
import requests
from emoji import emojize
from chatango.ch import Room

from logger import LOGGER
from config import FOOTY_FIXTURE_STATS_ENDPOINT, FOOTY_HTTP_HEADERS, FOOTY_LIVE_STATS_LEAGUES, HTTP_REQUEST_TIMEOUT

from .live import fetch_live_fixtures
from .util import get_preferred_timezone


def footy_stats_for_live_fixtures(room: Room, username: str):
    """
    Fetch live fixture odds for EPL, LIGA, BUND, FA, UCL, EUROPA, etc.

    :param str username: Name of user who triggered the command.

    :returns: str
    """
    try:
        live_fixture_stats_response = "\n\n\n"
        tz_name = get_preferred_timezone(room, username)
        for league_name, league_id in FOOTY_LIVE_STATS_LEAGUES.items():
            live_league_fixtures = fetch_live_fixtures(league_id, tz_name)
            if live_league_fixtures and bool(live_league_fixtures) and live_league_fixtures != []:
                live_fixture_stats_response += f"<b>{league_name}</b>\n"
                for fixture in live_league_fixtures:
                    if fixture.get("fixture"):
                        fixture_id = fixture["fixture"]["id"]
                        live_fixture_stats = fetch_stats_per_live_fixture(fixture_id)
                        live_fixture_stats_response += parse_live_fixture_stats(live_fixture_stats)
        if live_fixture_stats_response != "\n\n\n":
            return emojize(live_fixture_stats_response, language="en")
        return emojize(f":warning: sry @{username} I couldn't find live fixtures bc im gay :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when serving live fixture stats: {e}")


def fetch_stats_per_live_fixture(fixture_id: int) -> Optional[str]:
    """
    Construct fixture stats for a single live fixture.

    :param int fixture_id: ID of a single live fixture.

    :returns: Optional[str]
    """
    try:
        params = {"fixture": fixture_id}
        resp = requests.get(
            FOOTY_FIXTURE_STATS_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        return resp.json()["response"]
    except requests.HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching live fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching live fixtures: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching live fixtures: {e}")


def parse_live_fixture_stats(fixture_stats: dict) -> str:
    """
    Parse live fixture stats aggregated by team.

    return: str
    """
    try:
        fixture_stats_response = "\n"
        for i, team_fixture_stats in enumerate(fixture_stats):
            team_stats = unpack_team_statistics(team_fixture_stats["statistics"])
            team_name = team_fixture_stats["team"]["name"]
            possession = team_stats.get("Ball Possession", 0)
            sog = team_stats.get("Shots on Goal", 0)
            total_shots = team_stats.get("Total Shots", 0)
            fouls = team_stats.get("Fouls", 0)
            yellow_cards = team_stats.get("Yellow Cards", 0)
            red_cards = team_stats.get("Red Cards", 0)
            pass_accuracy = team_stats.get("Passes %", 0)
            xg = team_stats.get("expected_goals")
            if team_fixture_stats and i < len(team_fixture_stats) - 1:
                fixture_stats_response += f"<b>{team_name}</b>\n \
                                                :bar_chart: Possession: {possession}\n \
                                                :bullseye: Shots: {sog} SOG of {total_shots} total \n \
                                                :counterclockwise_arrows_button: Pass accuracy: {pass_accuracy}\n \
                                                :no_entry: Fouls: {fouls} (:yellow_square: {yellow_cards}, :red_square: {red_cards})\n \
                                                :soccer_ball: xG: {xg} \n"
            if i % 2 == 0:
                fixture_stats_response += "\n-------------------\n\n"
        return fixture_stats_response
    except ValueError as e:
        LOGGER.exception(f"ValueError when parsing live fixture stats: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when parsing live fixture stats: {e}")


def unpack_team_statistics(team_stats_list: list) -> dict:
    """
    Normalize team stat data.

    :param list team_stats_list: List of team stats, where each stat is a "pair" of type and value.

    :returns: dict
    """
    team_stats = {}
    for stat in team_stats_list:
        team_stats[stat["type"]] = stat["value"] if stat["value"] else 0
    return team_stats
