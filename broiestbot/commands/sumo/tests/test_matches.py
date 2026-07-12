"""Tests for sumo torikumi fetching & message formatting."""

from datetime import date
from unittest.mock import MagicMock, patch

from broiestbot.commands.sumo.matches import (
    fetch_basho,
    get_current_or_next_basho,
    sumo_matches_for_date,
)

# ---------------------------------------------------------------------------
# fetch_basho
# ---------------------------------------------------------------------------


def test_fetch_basho_returns_scheduled_basho(basho_july_2026):
    """fetch_basho returns basho metadata when the tournament exists."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = basho_july_2026

    with patch("broiestbot.commands.sumo.matches.requests.get", return_value=mock_resp):
        result = fetch_basho("202607")

    assert result == basho_july_2026


def test_fetch_basho_returns_none_for_unscheduled_basho(basho_unscheduled):
    """fetch_basho returns None when the API responds 200 with an empty `date`."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = basho_unscheduled

    with patch("broiestbot.commands.sumo.matches.requests.get", return_value=mock_resp):
        result = fetch_basho("202608")

    assert result is None


# ---------------------------------------------------------------------------
# get_current_or_next_basho
# ---------------------------------------------------------------------------


def test_get_current_or_next_basho_skips_finished_basho(basho_july_2026):
    """A basho whose endDate has passed is skipped in favor of the next one."""
    finished_basho = {
        "date": "202605",
        "startDate": "2026-05-10T00:00:00Z",
        "endDate": "2026-05-24T00:00:00Z",
    }

    def fake_fetch(basho_id):
        return {"202605": finished_basho, "202607": basho_july_2026}.get(basho_id)

    with patch("broiestbot.commands.sumo.matches.fetch_basho", side_effect=fake_fetch):
        result = get_current_or_next_basho(date(2026, 5, 28))

    assert result == basho_july_2026


def test_get_current_or_next_basho_rolls_over_year(basho_july_2026):
    """Searching from December wraps into January of the next year."""
    jan_basho = {
        "date": "202701",
        "startDate": "2027-01-10T00:00:00Z",
        "endDate": "2027-01-24T00:00:00Z",
    }

    def fake_fetch(basho_id):
        return {"202701": jan_basho}.get(basho_id)

    with patch("broiestbot.commands.sumo.matches.fetch_basho", side_effect=fake_fetch):
        result = get_current_or_next_basho(date(2026, 12, 15))

    assert result == jan_basho


def test_get_current_or_next_basho_returns_none_when_nothing_scheduled():
    """Returns None when no upcoming basho is found."""
    with patch("broiestbot.commands.sumo.matches.fetch_basho", return_value=None):
        result = get_current_or_next_basho(date(2026, 7, 8))

    assert result is None


# ---------------------------------------------------------------------------
# sumo_matches_for_date — message formatting
# ---------------------------------------------------------------------------


def test_sumo_matches_formats_bouts_during_basho(basho_july_2026, torikumi_day_3):
    """During a basho, the message contains the day number, results, and upcoming bouts."""
    with (
        patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", return_value=torikumi_day_3),
    ):
        result = sumo_matches_for_date(date(2026, 7, 14))

    assert "DAY 3" in result
    # Completed bout shows winner & kimarite.
    assert "Onosato def. Hoshoryu" in result
    assert "yorikiri" in result
    # Upcoming bout shows both rikishi with abbreviated Japanese ranks.
    assert "<b>Dewanoryu</b> (十両 3 東) vs <b>Oshoumi</b> (前頭 15 西)" in result
    # Marquee (last-listed) bout leads the message.
    assert result.index("Onosato") < result.index("Dewanoryu")


def test_sumo_matches_announces_upcoming_basho(basho_july_2026):
    """Before the basho starts, the message announces the start date."""
    with patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", return_value=basho_july_2026):
        result = sumo_matches_for_date(date(2026, 7, 8))

    assert "Nagoya Basho" in result
    assert "July 12" in result


def test_sumo_matches_handles_no_scheduled_basho():
    """Fallback message when no basho is found at all."""
    with patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", return_value=None):
        result = sumo_matches_for_date(date(2026, 7, 8))

    assert "no sumo basho" in result


def test_sumo_matches_handles_missing_torikumi(basho_july_2026):
    """Fallback message when the day's torikumi has not been announced yet."""
    with (
        patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", return_value=basho_july_2026),
    ):
        result = sumo_matches_for_date(date(2026, 7, 12))

    assert "day 1" in result


def test_sumo_matches_caps_day_at_15(basho_july_2026, torikumi_day_3):
    """Dates past the basho end are clamped to the final day."""
    with (
        patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", return_value=torikumi_day_3) as mock_fetch,
    ):
        sumo_matches_for_date(date(2026, 7, 26))

    mock_fetch.assert_called_once_with("202607", 15)
