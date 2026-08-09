"""Tests for resolving which league a team currently has a table position in."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError

from broiestbot.commands.footy.standings import fetch_team_current_league
from config import AALESUND_TEAM_ID, ELITESERIEN_LEAGUE_ID, OBOS_LIGAEN_ID
from tests.aiohttp_mocks import FakeResponse, FakeSession, patch_http_session

NORWEGIAN_LEAGUES = (ELITESERIEN_LEAGUE_ID, OBOS_LIGAEN_ID)


def standings_by_team_response(*league_ids: int) -> dict:
    """
    Build a `/standings?team=<id>` payload listing a single row per league.

    :param league_ids: IDs of leagues the team holds a table position in.

    :returns: dict
    """
    return {
        "response": [
            {
                "league": {
                    "id": league_id,
                    "name": "Eliteserien" if league_id == ELITESERIEN_LEAGUE_ID else "OBOS-ligaen",
                    "standings": [[{"rank": 14, "team": {"id": AALESUND_TEAM_ID, "name": "Aalesund"}}]],
                }
            }
            for league_id in league_ids
        ]
    }


def test_fetch_team_current_league_returns_top_flight():
    """The Eliteserien ID is returned when AAFK hold a table position there."""
    with patch_http_session(
        "broiestbot.commands.footy.standings",
        FakeResponse(json_data=standings_by_team_response(ELITESERIEN_LEAGUE_ID)),
    ):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result == ELITESERIEN_LEAGUE_ID


def test_fetch_team_current_league_returns_second_tier():
    """The OBOS-Ligaen ID is returned after relegation, without any code change."""
    with patch_http_session(
        "broiestbot.commands.footy.standings",
        FakeResponse(json_data=standings_by_team_response(OBOS_LIGAEN_ID)),
    ):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result == OBOS_LIGAEN_ID


def test_fetch_team_current_league_prefers_earlier_eligible_league():
    """Eligible leagues are matched in the order given, regardless of API ordering."""
    with patch_http_session(
        "broiestbot.commands.footy.standings",
        FakeResponse(json_data=standings_by_team_response(OBOS_LIGAEN_ID, ELITESERIEN_LEAGUE_ID)),
    ):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result == ELITESERIEN_LEAGUE_ID


def test_fetch_team_current_league_ignores_ineligible_leagues():
    """A group-stage cup table the team appears in is not mistaken for their league."""
    with patch_http_session(
        "broiestbot.commands.footy.standings",
        FakeResponse(json_data=standings_by_team_response(667)),
    ):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result is None


def test_fetch_team_current_league_returns_none_on_empty_response():
    """An empty response (preseason, no table yet) resolves to None rather than raising."""
    with patch_http_session("broiestbot.commands.footy.standings", FakeResponse(json_data={"response": []})):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result is None


def test_fetch_team_current_league_returns_none_on_non_200():
    """Non-200 responses resolve to None."""
    with patch_http_session("broiestbot.commands.footy.standings", FakeResponse(status=403, text="Forbidden")):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result is None


def test_fetch_team_current_league_swallows_client_error():
    """A `ClientError` is logged and resolves to None."""
    with patch_http_session("broiestbot.commands.footy.standings", ClientError("boom")):
        result = asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert result is None


def test_fetch_team_current_league_queries_by_team_and_season():
    """The request filters standings by team, using the season year of the first eligible league."""
    session = FakeSession([FakeResponse(json_data=standings_by_team_response(ELITESERIEN_LEAGUE_ID))])
    with patch("broiestbot.commands.footy.standings.get_http_session", AsyncMock(return_value=session)):
        asyncio.run(fetch_team_current_league(AALESUND_TEAM_ID, NORWEGIAN_LEAGUES))

    assert len(session.calls) == 1
    assert session.calls[0][2]["params"] == {"team": AALESUND_TEAM_ID, "season": datetime.now().year}
