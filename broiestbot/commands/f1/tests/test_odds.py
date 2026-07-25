"""Tests for fetching bookmaker odds of drivers winning a grand prix."""

from unittest.mock import MagicMock, patch

import pytest

from broiestbot.commands.f1 import odds as f1_odds
from broiestbot.commands.f1.odds import (
    _match_race_winner_market,
    _parse_odds_from_market,
    fetch_f1_sport_id,
    fetch_race_winner_odds,
)


@pytest.fixture(autouse=True)
def reset_cached_sport_id():
    """Clear the cached F1 sport ID between tests."""
    f1_odds._F1_SPORT_ID = None
    yield
    f1_odds._F1_SPORT_ID = None


# ---------------------------------------------------------------------------
# Sport ID lookup
# ---------------------------------------------------------------------------


def test_f1_sport_id_is_resolved_by_name(odds_sports):
    """F1's ID is looked up by name rather than hardcoded, then cached."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"sports": odds_sports}
    with patch("broiestbot.commands.f1.odds.requests.get", return_value=mock_resp) as mock_get:
        assert fetch_f1_sport_id() == 12
        assert fetch_f1_sport_id() == 12
    assert mock_get.call_count == 1


def test_missing_f1_sport_id_returns_none():
    """A bookmaker which doesn't offer F1 yields no sport ID."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"sports": [{"id": 1, "name": "Soccer"}]}
    with patch("broiestbot.commands.f1.odds.requests.get", return_value=mock_resp):
        assert fetch_f1_sport_id() is None


# ---------------------------------------------------------------------------
# Market matching & parsing
# ---------------------------------------------------------------------------


def test_race_winner_market_is_matched_to_the_grand_prix(odds_specials, odds_race_winner_market, race_upcoming):
    """The winner market naming the grand prix wins out over other outrights."""
    assert _match_race_winner_market(odds_specials, race_upcoming) == odds_race_winner_market


def test_unrelated_markets_are_ignored(race_upcoming):
    """Markets which aren't about a winner are never matched."""
    fastest_lap_market = {
        "category": "Fastest Lap",
        "name": "Bahrain Grand Prix - Fastest Lap",
        "starts": "2026-03-08T15:00:00Z",
        "lines": {"0": {"name": "Lando Norris", "price": 3.0}},
    }
    assert _match_race_winner_market([fastest_lap_market], race_upcoming) is None


def test_nearest_winner_market_matched_when_grand_prix_isnt_named(race_upcoming):
    """When no market names the grand prix, the one starting closest to it is used."""
    next_race_market = {
        "category": "Race Winner",
        "name": "Race Winner",
        "starts": "2026-03-22T15:00:00Z",
        "lines": {"0": {"name": "Lando Norris", "price": 2.5}},
    }
    this_race_market = {
        "category": "Race Winner",
        "name": "Race Winner",
        "starts": "2026-03-08T15:00:00Z",
        "lines": {"0": {"name": "Max Verstappen", "price": 1.9}},
    }
    assert _match_race_winner_market([next_race_market, this_race_market], race_upcoming) == this_race_market


def test_odds_are_sorted_by_favorite(odds_race_winner_market):
    """Drivers are returned favorite-first, dropping any without a price."""
    assert _parse_odds_from_market(odds_race_winner_market) == [
        ("Max Verstappen", 1.72),
        ("Lando Norris", 3.25),
        ("Charles Leclerc", 4.5),
    ]


def test_odds_lines_parsed_from_a_list():
    """Lines are parsed whether they arrive as a dict or a list."""
    market = {"lines": [{"name": "Max Verstappen", "price": "1.72"}, {"name": "Broiestbot", "price": "not a price"}]}
    assert _parse_odds_from_market(market) == [("Max Verstappen", 1.72)]


def test_market_without_lines_has_no_odds():
    """A market with no lines parses into no odds."""
    assert _parse_odds_from_market({}) == []


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


def test_race_winner_odds_are_fetched(odds_specials, race_upcoming):
    """Odds for a race are looked up via the bookmaker's prematch outrights."""
    with (
        patch("broiestbot.commands.f1.odds.fetch_f1_sport_id", return_value=12),
        patch("broiestbot.commands.f1.odds._fetch_odds_data", return_value=odds_specials) as mock_fetch,
    ):
        odds = fetch_race_winner_odds(race_upcoming)
    assert odds[0] == ("Max Verstappen", 1.72)
    assert mock_fetch.call_args.args[1]["event_type"] == "prematch"


def test_live_odds_are_used_when_no_prematch_market_exists(odds_specials, race_upcoming):
    """A live race falls back to the bookmaker's live outrights."""

    def fake_fetch(_endpoint, params, _response_key):
        return odds_specials if params["event_type"] == "live" else []

    with (
        patch("broiestbot.commands.f1.odds.fetch_f1_sport_id", return_value=12),
        patch("broiestbot.commands.f1.odds._fetch_odds_data", side_effect=fake_fetch) as mock_fetch,
    ):
        odds = fetch_race_winner_odds(race_upcoming)
    assert odds[0] == ("Max Verstappen", 1.72)
    assert mock_fetch.call_count == 2


def test_no_odds_without_a_sport_id(race_upcoming):
    """Odds are skipped entirely when F1 isn't offered by the bookmaker."""
    with patch("broiestbot.commands.f1.odds.fetch_f1_sport_id", return_value=None):
        assert fetch_race_winner_odds(race_upcoming) is None
