"""Tests for today's footy odds parsing logic (the !footyodds command)."""

from broiestbot.commands.footy.predicts import (
    get_outcome_odds,
    map_odds_by_fixture_id,
    parse_fixture_odds,
)

# ---------------------------------------------------------------------------
# get_outcome_odds — the reverse-order bug
# ---------------------------------------------------------------------------


def test_get_outcome_odds_matches_by_value_name():
    """Odds are looked up by their 'value' name, not by list position."""
    values = [
        {"value": "Home", "odd": "3.20"},
        {"value": "Draw", "odd": "3.10"},
        {"value": "Away", "odd": "2.25"},
    ]
    assert get_outcome_odds(values, "Home") == "3.20"
    assert get_outcome_odds(values, "Draw") == "3.10"
    assert get_outcome_odds(values, "Away") == "2.25"


def test_get_outcome_odds_is_order_independent():
    """
    When the API returns outcomes in reverse (Away/Draw/Home) order, Home and Away
    odds must still resolve to the correct value rather than being swapped.
    """
    reversed_values = [
        {"value": "Away", "odd": "2.25"},
        {"value": "Draw", "odd": "3.10"},
        {"value": "Home", "odd": "3.20"},
    ]
    assert get_outcome_odds(reversed_values, "Home") == "3.20"
    assert get_outcome_odds(reversed_values, "Away") == "2.25"


def test_get_outcome_odds_returns_na_when_missing():
    """A missing outcome falls back to 'N/A' rather than raising."""
    assert get_outcome_odds([{"value": "Home", "odd": "3.20"}], "Away") == "N/A"
    assert get_outcome_odds([], "Home") == "N/A"


# ---------------------------------------------------------------------------
# map_odds_by_fixture_id — match odds to fixtures by ID
# ---------------------------------------------------------------------------


def test_map_odds_by_fixture_id_keys_on_fixture_id(today_odds_response):
    """Odds are keyed by fixture ID so they can be matched regardless of response order."""
    result = map_odds_by_fixture_id(today_odds_response)
    assert set(result.keys()) == {1489392}
    assert result[1489392][0]["value"] == "Home"


def test_map_odds_by_fixture_id_skips_entries_without_bookmakers():
    """Entries lacking bookmakers/bets are skipped instead of raising."""
    malformed = [
        {"fixture": {"id": 1}, "bookmakers": []},
        {"fixture": {"id": 2}, "bookmakers": [{"id": 8, "bets": []}]},
        {"bookmakers": [{"id": 8, "bets": [{"values": [{"value": "Home", "odd": "1.5"}]}]}]},
    ]
    assert map_odds_by_fixture_id(malformed) == {}


# ---------------------------------------------------------------------------
# parse_fixture_odds — integration-style
# ---------------------------------------------------------------------------


def test_parse_fixture_odds_associates_odds_with_correct_team(today_fixture, today_odds_response):
    """Home/draw/away odds are rendered against the correct team."""
    result = parse_fixture_odds("WORLD CUP", [today_fixture], today_odds_response, "room", "user")

    assert result is not None
    # United States is home (3.20), Portugal is away (2.25).
    assert "UNITED STATES: 3.20" in result
    assert "DRAW: 3.10" in result
    assert "PORTUGAL: 2.25" in result


def test_parse_fixture_odds_correct_when_outcomes_reversed(today_fixture, today_odds_response_reversed):
    """
    Regression test: when the odds API returns outcomes in Away/Draw/Home order,
    the home team must still be paired with the home odds (not the away odds).
    """
    result = parse_fixture_odds("WORLD CUP", [today_fixture], today_odds_response_reversed, "room", "user")

    assert result is not None
    assert "UNITED STATES: 3.20" in result
    assert "PORTUGAL: 2.25" in result


def test_parse_fixture_odds_matches_by_fixture_id_not_position(today_fixture, today_odds_response):
    """
    Odds for an unrelated fixture appearing earlier in the odds response must not be
    attributed to this fixture; matching is by ID, not list position.
    """
    unrelated = {
        "fixture": {"id": 999999},
        "bookmakers": [
            {
                "id": 8,
                "name": "Bet365",
                "bets": [
                    {
                        "id": 1,
                        "name": "Match Winner",
                        "values": [
                            {"value": "Home", "odd": "9.99"},
                            {"value": "Draw", "odd": "9.99"},
                            {"value": "Away", "odd": "9.99"},
                        ],
                    }
                ],
            }
        ],
    }
    odds_response = [unrelated] + today_odds_response

    result = parse_fixture_odds("WORLD CUP", [today_fixture], odds_response, "room", "user")

    assert result is not None
    assert "9.99" not in result
    assert "UNITED STATES: 3.20" in result
    assert "PORTUGAL: 2.25" in result
