"""Tests for the `!f1` grand prix summary."""

from datetime import datetime, timezone
from unittest.mock import patch

from broiestbot.commands.f1.grandprix import API_ERROR_MESSAGE, f1_grand_prix_at

DRIVER_STANDINGS = [
    {"position": 1, "points": 204, "name": "Andrea Kimi Antonelli", "tla": "ANT", "team": "Mercedes AMG F1 Team"},
    {"position": 2, "points": 159, "name": "Lewis Hamilton", "tla": "HAM", "team": "Scuderia Ferrari"},
]


# ---------------------------------------------------------------------------
# Live grand prix
# ---------------------------------------------------------------------------


def test_live_race_reports_championship(race_live, circuit_bahrain):
    """A live race reports its circuit & the championship standings."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_live]),
        patch("broiestbot.commands.f1.grandprix.fetch_circuit", return_value=circuit_bahrain),
        patch("broiestbot.commands.f1.grandprix.fetch_driver_standings", return_value=DRIVER_STANDINGS),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 8, 16, tzinfo=timezone.utc))

    assert "LIVE NOW: BAHRAIN GRAND PRIX" in result
    assert "🇧🇭" in result
    assert "Bahrain International Circuit, Sakhir" in result
    assert "DRIVERS' CHAMPIONSHIP" in result
    assert "<b>1.</b> 🇮🇹 Andrea Kimi Antonelli <i>(Mercedes AMG F1 Team)</i> — 204 pts" in result


# ---------------------------------------------------------------------------
# Upcoming grand prix
# ---------------------------------------------------------------------------


def test_upcoming_race_reports_championship(race_completed, race_upcoming, circuit_bahrain):
    """A race which is still days out reports its details & the championship standings."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_completed, race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_circuit", return_value=circuit_bahrain),
        patch("broiestbot.commands.f1.grandprix.fetch_driver_standings", return_value=DRIVER_STANDINGS),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 4, 15, tzinfo=timezone.utc))

    assert "NEXT UP: BAHRAIN GRAND PRIX" in result
    assert "57 laps, 308.238 km" in result
    assert "Sun Mar 8, 11:00am ET <i>(in 4 days)</i>" in result
    assert "DRIVERS' CHAMPIONSHIP" in result
    assert result.index("Andrea Kimi Antonelli") < result.index("Lewis Hamilton")


def test_race_without_standings_says_so(race_upcoming, circuit_bahrain):
    """A race with no available standings still reports the grand prix itself."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_circuit", return_value=circuit_bahrain),
        patch("broiestbot.commands.f1.grandprix.fetch_driver_standings", return_value=None),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 4, 15, tzinfo=timezone.utc))

    assert "NEXT UP: BAHRAIN GRAND PRIX" in result
    assert "championship standings unavailable" in result


# ---------------------------------------------------------------------------
# Offseason
# ---------------------------------------------------------------------------


def test_finished_season_reports_next_season_opener(race_completed, race_upcoming):
    """Once every race has been run, the start of next season is reported."""
    next_season_opener = {
        **race_upcoming,
        "id": "gp-2027-opener",
        "name": "Australian Grand Prix",
        "season": 2027,
        "date": "2027-03-07T05:00:00Z",
    }
    with patch(
        "broiestbot.commands.f1.grandprix.fetch_season_races",
        side_effect=[[race_completed], [next_season_opener, {**next_season_opener, "date": "2027-03-21T15:00:00Z"}]],
    ):
        result = f1_grand_prix_at(datetime(2026, 12, 20, tzinfo=timezone.utc))

    assert "the 2026 F1 season is over" in result
    assert "Australian Grand Prix" in result
    assert "kicks off the 2027 season" in result
    assert "Sun Mar 7, 12:00am ET" in result


def test_finished_season_without_a_schedule(race_completed):
    """An unannounced schedule for next season is reported as such."""
    with patch(
        "broiestbot.commands.f1.grandprix.fetch_season_races",
        side_effect=[[race_completed], None],
    ):
        result = f1_grand_prix_at(datetime(2026, 12, 20, tzinfo=timezone.utc))

    assert "the 2026 F1 season is over" in result
    assert "the 2027 schedule hasn't been announced yet" in result


def test_season_without_a_schedule_isnt_called_over():
    """A season the API has no races for is reported as unscheduled rather than finished."""
    with patch("broiestbot.commands.f1.grandprix.fetch_season_races", side_effect=[[], None]):
        result = f1_grand_prix_at(datetime(2026, 1, 4, tzinfo=timezone.utc))

    assert "no 2026 F1 races on the schedule" in result
    assert "the 2027 schedule hasn't been announced yet" in result


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------


def test_failed_race_fetch_returns_error_message():
    """A failed request for the season's races is reported to the room."""
    with patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=None):
        assert f1_grand_prix_at(datetime(2026, 3, 4, tzinfo=timezone.utc)) == API_ERROR_MESSAGE


def test_unexpected_error_returns_error_message(race_upcoming):
    """Unexpected errors are swallowed & reported to the room."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_circuit", return_value={}),
        patch("broiestbot.commands.f1.grandprix.fetch_driver_standings", side_effect=ValueError("boom")),
    ):
        assert f1_grand_prix_at(datetime(2026, 3, 4, tzinfo=timezone.utc)) == API_ERROR_MESSAGE
