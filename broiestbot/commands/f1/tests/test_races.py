"""Tests for fetching & classifying F1 races."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from broiestbot.commands.f1.races import (
    current_lap,
    fetch_season_races,
    find_live_race,
    find_next_race,
    is_race_abandoned,
    is_race_finished,
    is_race_live,
)

RACE_START = datetime(2026, 3, 8, 15, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Race state
# ---------------------------------------------------------------------------


def test_race_is_live_once_it_starts(race_live):
    """A race which has started but isn't finished is live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 16, tzinfo=timezone.utc)) is True


def test_race_is_not_live_before_lights_out(race_live):
    """A race which hasn't started yet isn't live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 14, tzinfo=timezone.utc)) is False


def test_race_is_not_live_long_after_it_started(race_live):
    """A race which started well beyond its runtime is no longer considered live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 23, tzinfo=timezone.utc)) is False


def test_live_status_beats_the_clock(race_live):
    """An explicitly live status is honored regardless of the scheduled start time."""
    delayed_race = {**race_live, "status": "Live"}
    assert is_race_live(delayed_race, datetime(2026, 3, 9, 12, tzinfo=timezone.utc)) is True


def test_completed_and_cancelled_races_are_never_live(race_completed, race_cancelled):
    """Finished & abandoned races are never reported as live."""
    assert is_race_finished(race_completed) is True
    assert is_race_abandoned(race_cancelled) is True
    assert is_race_live(race_completed, datetime(2026, 3, 1, 6, tzinfo=timezone.utc)) is False
    assert is_race_live(race_cancelled, datetime(2026, 3, 22, 16, tzinfo=timezone.utc)) is False


def test_race_without_a_date_is_not_live(race_live):
    """A race with no start time can't be judged as live."""
    assert is_race_live({**race_live, "date": None}, RACE_START) is False


# ---------------------------------------------------------------------------
# Finding races within a season
# ---------------------------------------------------------------------------


def test_live_race_is_found_among_a_season(race_completed, race_live, race_cancelled):
    """The race underway is picked out of a full season of races."""
    races = [race_completed, race_live, race_cancelled]
    assert find_live_race(races, datetime(2026, 3, 8, 16, tzinfo=timezone.utc)) == race_live


def test_no_live_race_between_grand_prix(race_completed, race_upcoming):
    """No race is live during the week between grands prix."""
    assert find_live_race([race_completed, race_upcoming], datetime(2026, 3, 4, tzinfo=timezone.utc)) is None


def test_next_race_is_the_soonest_scheduled_race(race_completed, race_upcoming, race_cancelled):
    """The next race is the earliest unrun race, ignoring cancelled ones."""
    later_race = {**race_upcoming, "id": 1150, "date": "2026-04-05T15:00:00+00:00"}
    races = [later_race, race_completed, race_cancelled, race_upcoming]
    assert find_next_race(races, datetime(2026, 3, 4, tzinfo=timezone.utc)) == race_upcoming


def test_no_next_race_once_the_season_ends(race_completed):
    """A season of finished races has no next race."""
    assert find_next_race([race_completed], datetime(2026, 12, 20, tzinfo=timezone.utc)) is None


def test_current_lap(race_live, race_upcoming):
    """Laps are displayed as `current/total`, and omitted before a race starts."""
    assert current_lap(race_live) == "32/57"
    assert current_lap(race_upcoming) is None
    assert current_lap({"laps": {"current": 12, "total": None}}) == "12"
    assert current_lap({}) is None


# ---------------------------------------------------------------------------
# API requests
# ---------------------------------------------------------------------------


def test_season_races_are_unwrapped_from_response(race_upcoming):
    """A 200 response returns the `response` array of races."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"response": [race_upcoming]}
    with patch("broiestbot.commands.f1.races.requests.get", return_value=mock_resp) as mock_get:
        assert fetch_season_races(2026) == [race_upcoming]
    assert mock_get.call_args.kwargs["params"] == {"season": 2026, "type": "Race", "timezone": "UTC"}


def test_failed_race_request_returns_none():
    """Non-200 responses are logged & swallowed."""
    mock_resp = MagicMock(status_code=429, text="Too many requests")
    with patch("broiestbot.commands.f1.races.requests.get", return_value=mock_resp):
        assert fetch_season_races(2026) is None


def test_race_request_exception_returns_none():
    """Connection errors are logged & swallowed."""
    with patch("broiestbot.commands.f1.races.requests.get", side_effect=TimeoutError("timed out")):
        assert fetch_season_races(2026) is None
