"""Live betting odds for currently-active footy fixtures."""

from typing import Optional

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    FOOTY_HTTP_HEADERS,
    FOOTY_LIVE_ODDS_ENDPOINT,
    FOOTY_LIVE_ODDS_LEAGUES,
)

from .live import fetch_live_fixtures
from .util import abbreviate_team_name


async def footy_live_odds(username: str) -> str:
    """
    Fetch and display live betting odds for all active fixtures.

    :param str username: Name of user who triggered the command.

    :returns: str
    """
    all_odds = "\n\n\n"
    i = 0
    for league_name, league_id in FOOTY_LIVE_ODDS_LEAGUES.items():
        league_odds = await footy_live_odds_per_league(league_id, league_name, username)
        if league_odds is not None and i < 6:
            i += 1
            all_odds += league_odds + "\n"
    if all_odds == "\n\n\n":
        return emojize(":warning: No live odds available :warning:", language="en")
    return all_odds


async def footy_live_odds_per_league(league_id: int, league_name: str, username: str) -> Optional[str]:
    """
    Fetch and format live 1X2 odds for all active fixtures in a given league.

    :param int league_id: ID of footy league/cup.
    :param str league_name: Display name of the league.
    :param str username: Name of user who triggered the command.

    :returns: Optional[str]
    """
    try:
        fixtures = await fetch_live_fixtures(league_id, username)
        if not fixtures:
            return None

        odds_by_fixture = {}
        for fixture in fixtures:
            fixture_id = fixture["fixture"]["id"]
            fixture_odds = await fetch_live_odds_per_fixture(fixture_id)
            if not fixture_odds:
                continue
            for entry in fixture_odds:
                for bet in entry.get("odds", []):
                    if bet.get("name") == "Fulltime Result":
                        odds_by_fixture[fixture_id] = bet.get("values", [])
                        break

        if not odds_by_fixture:
            LOGGER.warning(f"No live odds found for any fixture in {league_name}")
            return None

        league_output = emojize(f"<b>{league_name}</b>\n", language="en")
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
                f"{home_team}: {home_odd} \n Draw: {draw_odd} \n {away_team}: {away_odd}\n\n"
            )

        if found:
            return league_output
        return None
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching live footy odds: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching live footy odds: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching live footy odds: {e}")


async def fetch_live_odds_per_fixture(fixture_id: int) -> Optional[list]:
    """
    Fetch live 1X2 odds for a specific fixture.

    :param int fixture_id: ID of a live fixture.

    :returns: Optional[list]
    """
    try:
        params = {"fixture": fixture_id}
        session = await get_http_session()
        async with session.get(FOOTY_LIVE_ODDS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            body = await resp.text()
            if resp.status == 200:
                data = (await resp.json(content_type=None)).get("response", [])
                if not data:
                    LOGGER.warning(f"Empty live odds response for fixture {fixture_id}: {body[:300]}")
                return data
            LOGGER.warning(f"Non-200 live odds response for fixture {fixture_id}: {resp.status} {body[:300]}")
    except ClientError as e:
        LOGGER.exception(f"ClientError fetching live odds for fixture {fixture_id}: {e}")
    except Exception as e:
        LOGGER.exception(f"Error fetching live odds for fixture {fixture_id}: {e}")
    return None
