"""Live betting odds for currently-active footy fixtures."""

from typing import Optional

import requests
from emoji import emojize
from logger import LOGGER
from requests.exceptions import HTTPError

from config import (
    FOOTY_HTTP_HEADERS,
    FOOTY_LIVE_ODDS_ENDPOINT,
    FOOTY_LIVE_ODDS_LEAGUES,
    HTTP_REQUEST_TIMEOUT,
)

from .live import fetch_live_fixtures
from .util import abbreviate_team_name


def footy_live_odds(username: str) -> str:
    """
    Fetch and display live betting odds for all active fixtures.

    :param str username: Name of user who triggered the command.

    :returns: str
    """
    all_odds = "\n\n\n"
    i = 0
    for league_name, league_id in FOOTY_LIVE_ODDS_LEAGUES.items():
        league_odds = footy_live_odds_per_league(league_id, league_name, username)
        if league_odds is not None and i < 6:
            i += 1
            all_odds += league_odds + "\n"
    if all_odds == "\n\n\n":
        return emojize(":warning: No live odds available :warning:", language="en")
    return all_odds


def footy_live_odds_per_league(league_id: int, league_name: str, username: str) -> Optional[str]:
    """
    Fetch and format live 1X2 odds for all active fixtures in a given league.

    :param int league_id: ID of footy league/cup.
    :param str league_name: Display name of the league.
    :param str username: Name of user who triggered the command.

    :returns: Optional[str]
    """
    try:
        fixtures = fetch_live_fixtures(league_id, username)
        if not fixtures:
            return None

        live_odds = fetch_live_odds_per_league(league_id)
        if not live_odds:
            return None

        odds_by_fixture = {}
        for entry in live_odds:
            fixture_id = entry["fixture"]["id"]
            for bet in entry.get("odds", []):
                if bet.get("name") == "Match Winner":
                    odds_by_fixture[fixture_id] = bet.get("values", [])

        league_output = emojize(f":soccer_ball: :moneybag: <b>{league_name}</b>\n", language="en")
        found = False
        for fixture in fixtures:
            fixture_id = fixture["fixture"]["id"]
            if fixture_id not in odds_by_fixture:
                continue
            found = True
            home_team = abbreviate_team_name(fixture["teams"]["home"].get("name", ""))
            away_team = abbreviate_team_name(fixture["teams"]["away"].get("name", ""))
            home_score = fixture["goals"].get("home", "")
            away_score = fixture["goals"].get("away", "")
            elapsed = fixture["fixture"]["status"].get("elapsed", "")
            values = odds_by_fixture[fixture_id]
            home_odd = next((v["odd"] for v in values if v["value"] == "Home"), "N/A")
            draw_odd = next((v["odd"] for v in values if v["value"] == "Draw"), "N/A")
            away_odd = next((v["odd"] for v in values if v["value"] == "Away"), "N/A")
            league_output += (
                f"<b>{away_team} {away_score} @ {home_team} {home_score}</b> <i>({elapsed}')</i>\n"
                f"{home_team}: {home_odd}  Draw: {draw_odd}  {away_team}: {away_odd}\n\n"
            )

        if found:
            return league_output
        return None
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching live footy odds: {e.response.content}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching live footy odds: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching live footy odds: {e}")


def fetch_live_odds_per_league(league_id: int) -> Optional[list]:
    """
    Fetch live 1X2 odds for all active fixtures in a given league.

    :param int league_id: ID of footy league/cup.

    :returns: Optional[list]
    """
    try:
        params = {"league": league_id, "bet": 1}
        resp = requests.get(
            FOOTY_LIVE_ODDS_ENDPOINT,
            headers=FOOTY_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("response")
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching live footy odds: {e.response.content}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching live footy odds: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching live footy odds: {e}")
