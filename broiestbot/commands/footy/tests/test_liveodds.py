"""Tests for live footy odds parsing logic."""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from broiestbot.commands.footy.liveodds import fetch_live_odds_per_fixture, footy_live_odds_per_league

# ---------------------------------------------------------------------------
# fetch_live_odds_per_fixture
# ---------------------------------------------------------------------------


def test_fetch_live_odds_per_fixture_returns_response(live_odds_response_fixture):
    """fetch_live_odds_per_fixture returns the response list on HTTP 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": live_odds_response_fixture}

    with patch("broiestbot.commands.footy.liveodds.requests.get", return_value=mock_resp):
        result = fetch_live_odds_per_fixture(1489392)

    assert result == live_odds_response_fixture


def test_fetch_live_odds_per_fixture_returns_none_on_non_200():
    """fetch_live_odds_per_fixture returns None for non-200 status codes."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Forbidden"

    with patch("broiestbot.commands.footy.liveodds.requests.get", return_value=mock_resp):
        result = fetch_live_odds_per_fixture(1489392)

    assert result is None


def test_fetch_live_odds_per_fixture_returns_empty_list_on_empty_response():
    """fetch_live_odds_per_fixture returns [] when the API reports 200 but no odds exist."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": []}
    mock_resp.text = '{"response": []}'

    with patch("broiestbot.commands.footy.liveodds.requests.get", return_value=mock_resp):
        result = fetch_live_odds_per_fixture(1489392)

    assert result == []


# ---------------------------------------------------------------------------
# bookmakers[].bets parsing — the key bug
# ---------------------------------------------------------------------------


def test_fulltime_result_is_parsed_from_top_level_odds(live_fixture, live_odds_response_fixture):
    """
    The live odds API returns bets in a top-level 'odds' array.
    'Fulltime Result' (id=59) is the live equivalent of 'Match Winner' — verify it parses correctly.
    """
    odds_by_fixture = {}
    fixture_id = live_fixture["fixture"]["id"]

    for entry in live_odds_response_fixture:
        for bet in entry.get("odds", []):
            if bet.get("name") == "Fulltime Result":
                odds_by_fixture[fixture_id] = bet.get("values", [])
                break

    assert fixture_id in odds_by_fixture
    values = odds_by_fixture[fixture_id]
    assert len(values) == 3
    home_odd = next((v["odd"] for v in values if v["value"] == "Home"), None)
    draw_odd = next((v["odd"] for v in values if v["value"] == "Draw"), None)
    away_odd = next((v["odd"] for v in values if v["value"] == "Away"), None)
    assert home_odd == "3.20"
    assert draw_odd == "3.10"
    assert away_odd == "2.25"


def test_missing_fulltime_result_yields_no_odds(live_fixture, live_odds_no_fulltime_result):
    """Response with no 'Fulltime Result' bet produces an empty odds_by_fixture dict."""
    odds_by_fixture = {}
    fixture_id = live_fixture["fixture"]["id"]

    for entry in live_odds_no_fulltime_result:
        for bet in entry.get("odds", []):
            if bet.get("name") == "Fulltime Result":
                odds_by_fixture[fixture_id] = bet.get("values", [])
                break

    assert fixture_id not in odds_by_fixture


# ---------------------------------------------------------------------------
# footy_live_odds_per_league — integration-style
# ---------------------------------------------------------------------------


def test_footy_live_odds_per_league_formats_output(live_fixture, live_odds_response_fixture):
    """footy_live_odds_per_league returns a formatted string with team names and odds."""
    with (
        patch(
            "broiestbot.commands.footy.liveodds.fetch_live_fixtures",
            return_value=[live_fixture],
        ),
        patch(
            "broiestbot.commands.footy.liveodds.fetch_live_odds_per_fixture",
            return_value=live_odds_response_fixture,
        ),
    ):
        result = footy_live_odds_per_league(1, "WORLD CUP", "testuser")

    assert result is not None
    assert "3.20" in result
    assert "3.10" in result
    assert "2.25" in result


def test_footy_live_odds_per_league_returns_none_when_no_fixtures():
    """footy_live_odds_per_league returns None when there are no live fixtures."""
    with patch("broiestbot.commands.footy.liveodds.fetch_live_fixtures", return_value=[]):
        result = footy_live_odds_per_league(1, "WORLD CUP", "testuser")

    assert result is None


def test_footy_live_odds_per_league_returns_none_when_no_odds(live_fixture):
    """footy_live_odds_per_league returns None when the odds API returns nothing."""
    with (
        patch(
            "broiestbot.commands.footy.liveodds.fetch_live_fixtures",
            return_value=[live_fixture],
        ),
        patch(
            "broiestbot.commands.footy.liveodds.fetch_live_odds_per_fixture",
            return_value=[],
        ),
    ):
        result = footy_live_odds_per_league(1, "WORLD CUP", "testuser")

    assert result is None
