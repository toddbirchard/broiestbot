"""Tests for upcoming sumo bout listing."""

from datetime import date
from unittest.mock import patch

from broiestbot.commands.sumo.upcoming import upcoming_sumo_matches_for_date

# ---------------------------------------------------------------------------
# upcoming_sumo_matches_for_date
# ---------------------------------------------------------------------------


def test_upcoming_lists_bouts_across_days(basho_july_2026, bout_upcoming, bout_completed):
    """Unfought bouts from consecutive announced days are grouped under day headers."""
    day_3 = {**basho_july_2026, "torikumi": [bout_upcoming, bout_completed]}
    day_4 = {
        **basho_july_2026,
        "torikumi": [
            {
                "matchNo": 1,
                "eastShikona": "Kirishima",
                "eastRank": "Ozeki 1 East",
                "westShikona": "Atamifuji",
                "westRank": "Sekiwake 1 West",
                "kimarite": "",
                "winnerEn": "",
            }
        ],
    }

    def fake_fetch(basho_id, day):
        return {3: day_3, 4: day_4}.get(day, basho_july_2026)

    with (
        patch("broiestbot.commands.sumo.upcoming.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", side_effect=fake_fetch) as mock_fetch,
    ):
        result = upcoming_sumo_matches_for_date(date(2026, 7, 14))

    assert "UPCOMING BOUTS" in result
    assert "Day 3" in result
    assert "Day 4" in result
    assert "Dewanoryu (Juryo 3) vs Oshoumi (Maegashira 15)" in result
    assert "Kirishima (Ozeki 1) vs Atamifuji (Sekiwake 1)" in result
    # Fought bouts are excluded.
    assert "def." not in result
    # Walking stops at the first day without announced torikumi (day 5).
    assert mock_fetch.call_count == 3


def test_upcoming_excludes_bouts_missing_rikishi(basho_july_2026, bout_upcoming):
    """Bouts without both rikishi announced are filtered out."""
    incomplete_bout = {
        "matchNo": 2,
        "eastShikona": "Takerufuji",
        "eastRank": "Maegashira 1 East",
        "westShikona": "",
        "westRank": "",
        "kimarite": "",
        "winnerEn": "",
    }
    day_3 = {**basho_july_2026, "torikumi": [bout_upcoming, incomplete_bout]}

    def fake_fetch(basho_id, day):
        return day_3 if day == 3 else basho_july_2026

    with (
        patch("broiestbot.commands.sumo.upcoming.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", side_effect=fake_fetch),
    ):
        result = upcoming_sumo_matches_for_date(date(2026, 7, 14))

    assert "Dewanoryu" in result
    assert "Takerufuji" not in result


def test_upcoming_announces_basho_before_torikumi_published(basho_july_2026):
    """Before the basho with no announced bouts, the message shows the start date."""
    with (
        patch("broiestbot.commands.sumo.upcoming.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", return_value=basho_july_2026),
    ):
        result = upcoming_sumo_matches_for_date(date(2026, 7, 8))

    assert "Nagoya Basho" in result
    assert "July 12" in result


def test_upcoming_mid_basho_all_bouts_fought(basho_july_2026, bout_completed):
    """Mid-basho with every announced bout fought reports the torikumi isn't out yet."""
    day_3 = {**basho_july_2026, "torikumi": [bout_completed]}

    def fake_fetch(basho_id, day):
        return day_3 if day == 3 else basho_july_2026

    with (
        patch("broiestbot.commands.sumo.upcoming.get_current_or_next_basho", return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", side_effect=fake_fetch),
    ):
        result = upcoming_sumo_matches_for_date(date(2026, 7, 14))

    assert "torikumi isn't out yet" in result


def test_upcoming_handles_no_scheduled_basho():
    """Fallback message when no basho is found at all."""
    with patch("broiestbot.commands.sumo.upcoming.get_current_or_next_basho", return_value=None):
        result = upcoming_sumo_matches_for_date(date(2026, 7, 8))

    assert "no sumo basho" in result
