"""Tests for parse_events_per_live_fixture in broiestbot/commands/footy/live.py."""

import pytest

from broiestbot.commands.footy.live import parse_events_per_live_fixture

# ---------------------------------------------------------------------------
# Happy-path: well-formed events
# ---------------------------------------------------------------------------


def test_normal_goal_included(event_normal_goal):
    """Normal goal event produces output containing the player name and elapsed time."""
    result = parse_events_per_live_fixture([event_normal_goal])
    assert result is not None
    assert "Harry Kane" in result
    assert '23"' in result


def test_penalty_goal_included(event_penalty_goal):
    """Penalty goal event produces output with PEN marker, player name, and elapsed time."""
    result = parse_events_per_live_fixture([event_penalty_goal])
    assert result is not None
    assert "PEN" in result
    assert "Jude Bellingham" in result
    assert '45"' in result


def test_own_goal_with_assist(event_own_goal_with_assist):
    """Own goal event includes both the scorer and the assisting player in output."""
    result = parse_events_per_live_fixture([event_own_goal_with_assist])
    assert result is not None
    assert "Virgil van Dijk" in result
    assert "Trent Alexander-Arnold" in result
    assert '60"' in result


def test_yellow_card_with_comment(event_yellow_card):
    """Yellow card event includes the player name and the referee's comment in output."""
    result = parse_events_per_live_fixture([event_yellow_card])
    assert result is not None
    assert "Declan Rice" in result
    assert "Dangerous play" in result
    assert '35"' in result


def test_red_card_included(event_red_card):
    """Red card event produces output containing the player name and elapsed time."""
    result = parse_events_per_live_fixture([event_red_card])
    assert result is not None
    assert "Diego Costa" in result
    assert '80"' in result


def test_var_disallowed_goal_included(event_var_disallowed_goal):
    """VAR disallowed goal event produces output containing the player name and elapsed time."""
    result = parse_events_per_live_fixture([event_var_disallowed_goal])
    assert result is not None
    assert "Robert Lewandowski" in result
    assert '55"' in result


def test_substitution_excluded_by_default(event_substitution):
    """Substitution events are omitted from output when subs=False (the default)."""
    result = parse_events_per_live_fixture([event_substitution], subs=False)
    assert result is not None
    assert "Marcus Rashford" not in result


def test_substitution_included_when_subs_true(event_substitution):
    """Substitution events include both the outgoing and incoming player when subs=True."""
    result = parse_events_per_live_fixture([event_substitution], subs=True)
    assert result is not None
    assert "Marcus Rashford" in result
    assert "Alejandro Garnacho" in result


# ---------------------------------------------------------------------------
# None-hardening: previously crashing edge cases
# ---------------------------------------------------------------------------


def test_null_player_object_does_not_raise(event_null_player):
    """If `player` is null in the API response, the event is silently skipped."""
    result = parse_events_per_live_fixture([event_null_player])
    assert result is not None


def test_null_time_object_does_not_raise(event_null_time):
    """If `time` is null in the API response, the event is silently skipped."""
    result = parse_events_per_live_fixture([event_null_time])
    assert result is not None
    assert "Erling Haaland" not in result


def test_null_player_name_does_not_raise(event_null_player_name):
    """If player dict exists but name is null, the event is silently skipped."""
    result = parse_events_per_live_fixture([event_null_player_name])
    assert result is not None


def test_own_goal_null_assist_does_not_raise(event_own_goal_no_assist):
    """Own goal with a null assist field must not raise TypeError on string concatenation."""
    result = parse_events_per_live_fixture([event_own_goal_no_assist])
    assert result is not None
    assert "Sergio Ramos" in result
    assert '72"' in result


def test_penalty_with_null_assist_name_does_not_raise(event_penalty_goal):
    """Penalty where assist dict has null name values must not crash."""
    result = parse_events_per_live_fixture([event_penalty_goal])
    assert result is not None
    assert "Jude Bellingham" in result


def test_empty_events_list_returns_newline():
    """An empty events list returns the base newline string without error."""
    result = parse_events_per_live_fixture([])
    assert result == "\n"


def test_mixed_events_with_nulls_does_not_raise(
    event_normal_goal,
    event_null_player,
    event_null_time,
    event_own_goal_no_assist,
    event_yellow_card,
):
    """A realistic mix of valid and null-field events must not raise."""
    events = [
        event_normal_goal,
        event_null_player,
        event_null_time,
        event_own_goal_no_assist,
        event_yellow_card,
    ]
    result = parse_events_per_live_fixture(events)
    assert result is not None
    assert "Harry Kane" in result
    assert "Sergio Ramos" in result
    assert "Declan Rice" in result
