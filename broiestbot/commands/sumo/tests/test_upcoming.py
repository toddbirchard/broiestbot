"""Tests for upcoming sumo bout listing."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

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
        patch(
            "broiestbot.commands.sumo.upcoming.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch(
            "broiestbot.commands.sumo.upcoming.fetch_torikumi", new_callable=AsyncMock, side_effect=fake_fetch
        ) as mock_fetch,
        patch("broiestbot.commands.sumo.upcoming.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.upcoming.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 14)))

    assert "UPCOMING BOUTS" in result
    assert "Day 3" in result
    assert "Day 4" in result
    assert "<b>Dewanoryu</b> vs <b>Oshoumi</b>" in result
    assert "<b>Kirishima</b> vs <b>Atamifuji</b>" in result
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
        patch(
            "broiestbot.commands.sumo.upcoming.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", new_callable=AsyncMock, side_effect=fake_fetch),
        patch("broiestbot.commands.sumo.upcoming.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.upcoming.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 14)))

    assert "Dewanoryu" in result
    assert "Takerufuji" not in result


def test_upcoming_announces_basho_before_torikumi_published(basho_july_2026):
    """Before the basho with no announced bouts, the message shows the start date."""
    with (
        patch(
            "broiestbot.commands.sumo.upcoming.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", new_callable=AsyncMock, return_value=basho_july_2026),
        patch("broiestbot.commands.sumo.upcoming.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.upcoming.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 8)))

    assert "Nagoya Basho" in result
    assert "July 12" in result


def test_upcoming_mid_basho_all_bouts_fought(basho_july_2026, bout_completed):
    """Mid-basho with every announced bout fought reports the torikumi isn't out yet."""
    day_3 = {**basho_july_2026, "torikumi": [bout_completed]}

    def fake_fetch(basho_id, day):
        return day_3 if day == 3 else basho_july_2026

    with (
        patch(
            "broiestbot.commands.sumo.upcoming.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", new_callable=AsyncMock, side_effect=fake_fetch),
        patch("broiestbot.commands.sumo.upcoming.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.upcoming.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 14)))

    assert "torikumi isn't out yet" in result


def test_upcoming_handles_no_scheduled_basho():
    """Fallback message when no basho is found at all."""
    with patch(
        "broiestbot.commands.sumo.upcoming.get_current_or_next_basho", new_callable=AsyncMock, return_value=None
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 8)))

    assert "no sumo basho" in result


def test_upcoming_enriches_bouts_and_fetches_series_per_day(
    basho_july_2026, bout_upcoming, bout_completed, basho_records
):
    """Records come from one banzuke fetch; head-to-heads are fetched per day for the unfought bouts only."""
    day_3 = {**basho_july_2026, "torikumi": [bout_upcoming, bout_completed]}
    day_4_bout = {
        "id": "202607-4-20-45-20",
        "matchNo": 20,
        "eastId": 45,
        "eastShikona": "Onosato",
        "eastRank": "Yokozuna 1 West",
        "westId": 20,
        "westShikona": "Hoshoryu",
        "westRank": "Yokozuna 1 East",
        "kimarite": "",
        "winnerEn": "",
    }
    day_4 = {**basho_july_2026, "torikumi": [day_4_bout]}

    def fake_fetch(basho_id, day):
        return {3: day_3, 4: day_4}.get(day, basho_july_2026)

    def fake_head_to_heads(bouts):
        return {bout["id"]: {"rikishiWins": 3, "opponentWins": 6, "total": 9} for bout in bouts}

    with (
        patch(
            "broiestbot.commands.sumo.upcoming.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.upcoming.fetch_torikumi", new_callable=AsyncMock, side_effect=fake_fetch),
        patch(
            "broiestbot.commands.sumo.upcoming.fetch_basho_records", new_callable=AsyncMock, return_value=basho_records
        ) as mock_records,
        patch(
            "broiestbot.commands.sumo.upcoming.fetch_head_to_heads",
            new_callable=AsyncMock,
            side_effect=fake_head_to_heads,
        ) as mock_h2h,
    ):
        result = asyncio.run(upcoming_sumo_matches_for_date(date(2026, 7, 14)))

    assert "<b>Dewanoryu</b> vs <b>Oshoumi</b> (2-3-1) <i>Oshoumi leads 6-3</i>" in result
    assert "<b>Onosato</b> (6-0) vs <b>Hoshoryu</b> (5-1) <i>Hoshoryu leads 6-3</i>" in result
    mock_records.assert_awaited_once_with("202607")
    assert [call.args[0] for call in mock_h2h.await_args_list] == [[bout_upcoming], [day_4_bout]]
