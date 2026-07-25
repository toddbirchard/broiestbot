"""Tests for the `!f1` grand prix summary."""

from datetime import datetime, timezone
from unittest.mock import patch

from broiestbot.commands.f1.grandprix import API_ERROR_MESSAGE, f1_grand_prix_at

RACE_WINNER_ODDS = [("Max Verstappen", 1.72), ("Lando Norris", 3.25), ("Charles Leclerc", 4.5)]

# ---------------------------------------------------------------------------
# Live grand prix
# ---------------------------------------------------------------------------


def test_live_race_lists_drivers_by_position(race_live, race_rankings):
    """A live race reports its current lap & running order."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_live]),
        patch("broiestbot.commands.f1.grandprix.fetch_race_rankings", return_value=race_rankings),
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds") as mock_odds,
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 8, 16, tzinfo=timezone.utc))

    assert "LIVE NOW: BAHRAIN GRAND PRIX" in result
    assert "🇧🇭" in result
    assert "Bahrain International Circuit, Sakhir" in result
    assert "Lap 32/57" in result
    assert "<b>1.</b> 🇳🇱 Max Verstappen <i>(Red Bull Racing)</i> 1:02:11.404" in result
    assert "<b>2.</b> 🇲🇨 Charles Leclerc <i>(Ferrari)</i> +2.104" in result
    assert "<b>3.</b> 🇬🇧 Lewis Hamilton <i>(Ferrari)</i> +8.921" in result
    # Positions are listed in running order, not the order the API returned them.
    assert result.index("Max Verstappen") < result.index("Charles Leclerc") < result.index("Lewis Hamilton")
    mock_odds.assert_not_called()


def test_live_race_falls_back_to_odds_without_positions(race_live):
    """A live race with no published positions lists drivers by odds instead."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_live]),
        patch("broiestbot.commands.f1.grandprix.fetch_race_rankings", return_value=[]),
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds", return_value=RACE_WINNER_ODDS),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 8, 16, tzinfo=timezone.utc))

    assert "LIVE NOW: BAHRAIN GRAND PRIX" in result
    assert "Lap 32/57" in result
    assert "ODDS TO WIN" in result
    assert "🇳🇱 Max Verstappen: <b>1.72</b>" in result


# ---------------------------------------------------------------------------
# Upcoming grand prix
# ---------------------------------------------------------------------------


def test_upcoming_race_lists_drivers_by_odds(race_completed, race_upcoming):
    """A race which is still days out is listed with odds to win, favorite first."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_completed, race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_starting_grid") as mock_grid,
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds", return_value=RACE_WINNER_ODDS),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 4, 15, tzinfo=timezone.utc))

    assert "NEXT UP: BAHRAIN GRAND PRIX" in result
    assert "57 laps, 308.238 km" in result
    assert "Sun Mar 8, 11:00am ET <i>(in 4 days)</i>" in result
    assert "ODDS TO WIN" in result
    assert result.index("Max Verstappen") < result.index("Lando Norris") < result.index("Charles Leclerc")
    assert "🇬🇧 Lando Norris: <b>3.25</b>" in result
    # Starting grids aren't published this far out, so don't bother asking for one.
    mock_grid.assert_not_called()


def test_upcoming_race_lists_starting_grid_after_qualifying(race_upcoming, starting_grid):
    """Once qualifying is done, drivers are listed by grid position instead of odds."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_starting_grid", return_value=starting_grid),
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds") as mock_odds,
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 7, 18, tzinfo=timezone.utc))

    assert "NEXT UP: BAHRAIN GRAND PRIX" in result
    assert "STARTING GRID" in result
    assert "<b>P1</b> 🇳🇱 Max Verstappen <i>(Red Bull Racing)</i> 1:29.179" in result
    assert "<b>P2</b> 🇩🇪 Nico Hulkenberg <i>(Audi)</i> 1:29.512" in result
    assert "<b>P3</b> 🇯🇵 Yuki Tsunoda <i>(Racing Bulls)</i> 1:29.740" in result
    assert "ODDS TO WIN" not in result
    mock_odds.assert_not_called()


def test_imminent_race_without_a_grid_lists_odds(race_upcoming):
    """A race whose qualifying hasn't run yet still falls back to odds."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_starting_grid", return_value=[]),
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds", return_value=RACE_WINNER_ODDS),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 7, 18, tzinfo=timezone.utc))

    assert "STARTING GRID" not in result
    assert "ODDS TO WIN" in result


def test_upcoming_race_without_odds_says_so(race_upcoming):
    """A race with no odds available still reports the grand prix itself."""
    with (
        patch("broiestbot.commands.f1.grandprix.fetch_season_races", return_value=[race_upcoming]),
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds", return_value=None),
    ):
        result = f1_grand_prix_at(datetime(2026, 3, 4, 15, tzinfo=timezone.utc))

    assert "NEXT UP: BAHRAIN GRAND PRIX" in result
    assert "no odds available" in result


# ---------------------------------------------------------------------------
# Offseason
# ---------------------------------------------------------------------------


def test_finished_season_reports_next_season_opener(race_completed, race_upcoming):
    """Once every race has been run, the start of next season is reported."""
    next_season_opener = {
        **race_upcoming,
        "id": 1201,
        "season": 2027,
        "competition": {"id": 22, "name": "Australia", "location": {"country": "Australia", "city": "Melbourne"}},
        "date": "2027-03-07T05:00:00+00:00",
    }
    with patch(
        "broiestbot.commands.f1.grandprix.fetch_season_races",
        side_effect=[[race_completed], [next_season_opener, {**next_season_opener, "date": "2027-03-21T15:00:00Z"}]],
    ):
        result = f1_grand_prix_at(datetime(2026, 12, 20, tzinfo=timezone.utc))

    assert "the 2026 F1 season is over" in result
    assert "Australia Grand Prix" in result
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
        patch("broiestbot.commands.f1.grandprix.fetch_race_winner_odds", side_effect=ValueError("boom")),
    ):
        assert f1_grand_prix_at(datetime(2026, 3, 4, tzinfo=timezone.utc)) == API_ERROR_MESSAGE
