"""Get general fixture stats for live fixtures."""
from typing import Optional
from collections import ChainMap


import requests

from .util import get_preferred_timezone
from logger import LOGGER
from .live import fetch_live_fixtures
from config import FOOTY_FIXTURE_STATS_ENDPOINT, FOOTY_HTTP_HEADERS, FOOTY_LIVE_STATS_LEAGUES, HTTP_REQUEST_TIMEOUT
from emoji import emojize
from chatango.ch import Room


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
                live_fixture_stats_response += f"<b>{league_name}<b>\n"
                for fixture in live_league_fixtures:
                    if fixture.get("fixture"):
                        fixture_id = fixture["fixture"]["id"]
                        live_fixture_stats = fetch_stats_per_live_fixture(fixture_id)
                        parsed_live_fixture_stats = parse_live_fixture_stats(live_fixture_stats)
                live_fixture_stats_response += parsed_live_fixture_stats
        if live_fixture_stats_response != "\n\n\n":
            return emojize(live_fixture_stats_response, language="en")
        return emojize(f":warning: sry @{username} I couldn't find live fixtures bc im gay :warning:", language="en")
    except Exception as e:
        LOGGER.error(f"Unexpected error when serving live fixture stats: {e}")


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
        return resp.json()
    except requests.HTTPError as e:
        LOGGER.error(f"HTTPError while fetching live fixtures: {e.response.content}")
    except KeyError as e:
        LOGGER.error(f"KeyError while fetching live fixtures: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching live fixtures: {e}")


def parse_live_fixture_stats(fixture_stats: dict) -> str:
    """
    Parse live fixture stats aggregated by team.

    return: str
    """
    try:
        fixture_stats_response = "\n\n"
        LOGGER.info(f"fixture_stats: {fixture_stats}")
        team_name = fixture_stats["response"]["team"]["name"]
        fixture_stats_response += f"<b>{team_name}</b>\n"
        for team_stats in fixture_stats["response"]:
            stat_dict = ChainMap(team_stats)
            LOGGER.info(f"stat_dict: {stat_dict}")
            """for stat in team_fixture_stats:
                    # if stat["type"] == "type":
                    LOGGER.info(f"stat: {stat}")
                    team_statistics = team_fixture_stats["statistics"]
                    possession = team_statistics.get("Ball Possession", 0)
                    sog = team_statistics.get("Shots on Goal", 0)
                    total_shots = team_statistics.get("Total Shots", 0)
                    fouls = team_statistics.get("Fouls", 0)
                    yellow_cards = team_statistics.get("Yellow Cards", 0)
                    red_cards = team_statistics.get("Red Cards", 0)
                    pass_accuracy = team_statistics.get("Passes %", 0)
                    xg = team_statistics.get("Expected Goals", 0.0)
                    fixture_stats_response += f"<b>{team_name}</b>\n \
                                            :soccer_ball: POSSESSION: {possession}\n \
                                            :bullseye: SOG: {sog} ({total_shots} TOTAL SHOTS) \n \
                                            :counterclockwise_arrows_button: PASS ACCURACY: {pass_accuracy}\n \
                                            :no_entry: FOULS: {fouls} (:yellow_square: {yellow_cards}, :red_square: {red_cards})\n \
                                            :soccer_ball: xG: {xg} \n"
                    if i == 0 and team_fixture_stats:
                        fixture_stats_response += "\n-------------------\n"
                    if i == len(fixture_stats - 1) and team_fixture_stats:
                        return fixture_stats_response"""
        return fixture_stats_response
    except ValueError as e:
        LOGGER.error(f"ValueError when parsing live fixture stats: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when parsing live fixture stats: {e}")
