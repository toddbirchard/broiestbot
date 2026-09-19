"""Tests for sumo torikumi fetching & message formatting."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

from broiestbot.commands.sumo.matches import (
    _format_bout,
    _format_bout_detail,
    _format_last_meeting,
    _format_stat_comparison,
    fetch_basho,
    get_current_or_next_basho,
    sumo_matches_for_date,
)
from tests.aiohttp_mocks import FakeResponse, patch_http_session

# ---------------------------------------------------------------------------
# fetch_basho
# ---------------------------------------------------------------------------


def test_fetch_basho_returns_scheduled_basho(basho_july_2026):
    """fetch_basho returns basho metadata when the tournament exists."""
    with patch_http_session("broiestbot.commands.sumo.matches", FakeResponse(json_data=basho_july_2026)):
        result = asyncio.run(fetch_basho("202607"))

    assert result == basho_july_2026


def test_fetch_basho_returns_none_for_unscheduled_basho(basho_unscheduled):
    """fetch_basho returns None when the API responds 200 with an empty `date`."""
    with patch_http_session("broiestbot.commands.sumo.matches", FakeResponse(json_data=basho_unscheduled)):
        result = asyncio.run(fetch_basho("202608"))

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

    with patch("broiestbot.commands.sumo.matches.fetch_basho", new_callable=AsyncMock, side_effect=fake_fetch):
        result = asyncio.run(get_current_or_next_basho(date(2026, 5, 28)))

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

    with patch("broiestbot.commands.sumo.matches.fetch_basho", new_callable=AsyncMock, side_effect=fake_fetch):
        result = asyncio.run(get_current_or_next_basho(date(2026, 12, 15)))

    assert result == jan_basho


def test_get_current_or_next_basho_returns_none_when_nothing_scheduled():
    """Returns None when no upcoming basho is found."""
    with patch("broiestbot.commands.sumo.matches.fetch_basho", new_callable=AsyncMock, return_value=None):
        result = asyncio.run(get_current_or_next_basho(date(2026, 7, 8)))

    assert result is None


# ---------------------------------------------------------------------------
# sumo_matches_for_date — message formatting
# ---------------------------------------------------------------------------


def test_sumo_matches_shows_only_remaining_bouts_with_detail(basho_july_2026, torikumi_day_3):
    """The message drops already-fought bouts and shows the remaining bout with its detail block."""
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi_day_3),
        patch("broiestbot.commands.sumo.matches.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
        patch(
            "broiestbot.commands.sumo.matches.fetch_rikishi_profiles",
            new_callable=AsyncMock,
            return_value={135: {"height": 180, "weight": 150}, 95: {"height": 175, "weight": 140}},
        ),
        patch("broiestbot.commands.sumo.matches.fetch_last_basho_records", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 14)))

    assert "DAY 3" in result
    # The already-fought bout is gone entirely — results live in neither `!todaysumo` nor `!sumo`.
    assert "Onosato" not in result
    assert "yorikiri" not in result
    # The remaining bout shows, with its expanded detail.
    assert "<b>Dewanoryu</b> vs <b>Oshoumi</b>" in result
    assert "📏 <b>180cm</b> vs 175cm" in result


def test_sumo_matches_points_to_sumo_command_when_all_bouts_fought(basho_july_2026, bout_completed):
    """When every bout for the day is already fought, point to `!sumo` rather than show nothing."""
    torikumi = {**basho_july_2026, "torikumi": [bout_completed]}
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 14)))

    assert "!sumo" in result
    assert "Onosato" not in result


def test_sumo_matches_announces_upcoming_basho(basho_july_2026):
    """Before the basho starts, the message announces the start date."""
    with patch(
        "broiestbot.commands.sumo.matches.get_current_or_next_basho",
        new_callable=AsyncMock,
        return_value=basho_july_2026,
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 8)))

    assert "Nagoya Basho" in result
    assert "July 12" in result


def test_sumo_matches_handles_no_scheduled_basho():
    """Fallback message when no basho is found at all."""
    with patch("broiestbot.commands.sumo.matches.get_current_or_next_basho", new_callable=AsyncMock, return_value=None):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 8)))

    assert "no sumo basho" in result


def test_sumo_matches_handles_missing_torikumi(basho_july_2026):
    """Fallback message when the day's torikumi has not been announced yet."""
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=basho_july_2026),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 12)))

    assert "day 1" in result


def test_sumo_matches_caps_day_at_15(basho_july_2026, torikumi_day_3):
    """Dates past the basho end are clamped to the final day."""
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch(
            "broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi_day_3
        ) as mock_fetch,
        patch("broiestbot.commands.sumo.matches.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_rikishi_profiles", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_last_basho_records", new_callable=AsyncMock, return_value={}),
    ):
        asyncio.run(sumo_matches_for_date(date(2026, 7, 26)))

    mock_fetch.assert_called_once_with("202607", 15)


def test_sumo_matches_enriches_remaining_bout_with_records_and_series(
    basho_july_2026, torikumi_day_3, basho_records, bout_upcoming
):
    """Basho records and the head-to-head badge are woven into the surviving bout's summary line."""
    head_to_heads = {bout_upcoming["id"]: {"rikishiWins": 0, "opponentWins": 0, "total": 0}}
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi_day_3),
        patch(
            "broiestbot.commands.sumo.matches.fetch_basho_records", new_callable=AsyncMock, return_value=basho_records
        ),
        patch(
            "broiestbot.commands.sumo.matches.fetch_head_to_heads", new_callable=AsyncMock, return_value=head_to_heads
        ) as mock_h2h,
        patch("broiestbot.commands.sumo.matches.fetch_rikishi_profiles", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_last_basho_records", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 14)))

    # The already-fought bout is dropped entirely, its result included.
    assert "Onosato" not in result
    assert "Hoshoryu" not in result
    # The remaining bout keeps its record on the summary line; Dewanoryu is a Juryo visitor with
    # no banzuke record, Oshoumi has an absence. The head-to-head now gets its own line.
    assert "<b>Dewanoryu</b> vs <b>Oshoumi</b> (2-3-1)" in result
    assert "🤼 first meeting" in result
    # Only the surviving (candidate) bout's head-to-head was fetched — not the fought one's too.
    mock_h2h.assert_called_once_with([bout_upcoming])


# ---------------------------------------------------------------------------
# _format_bout
# ---------------------------------------------------------------------------


def test_format_bout_without_enrichment_matches_legacy_shape(bout_completed, bout_upcoming):
    """With no records or series, bout lines render exactly as they did before enrichment."""
    assert _format_bout(bout_completed) == "Onosato def. Hoshoryu <i>(yorikiri)</i>"
    assert _format_bout(bout_upcoming) == "<b>Dewanoryu</b> vs <b>Oshoumi</b>"


def test_format_bout_omits_empty_records(bout_upcoming):
    """A 0-0 record (day 1) is omitted rather than rendered."""
    records = {135: {"wins": 0, "losses": 0, "absences": 0}, 95: {"wins": 0, "losses": 0, "absences": 0}}
    assert _format_bout(bout_upcoming, records) == "<b>Dewanoryu</b> vs <b>Oshoumi</b>"


def test_format_bout_series_phrasing(bout_completed):
    """The series reads from whichever rikishi leads, or `tied` when level."""
    bout_id = bout_completed["id"]
    west_leads = {bout_id: {"rikishiWins": 2, "opponentWins": 5, "total": 7}}
    assert _format_bout(bout_completed, {}, west_leads).endswith("<i>Onosato leads 5-2</i>")
    tied = {bout_id: {"rikishiWins": 4, "opponentWins": 4, "total": 8}}
    assert _format_bout(bout_completed, {}, tied).endswith("<i>tied 4-4</i>")


# ---------------------------------------------------------------------------
# _format_stat_comparison / _format_last_meeting / _format_bout_detail
# ---------------------------------------------------------------------------


def test_format_stat_comparison_renders_emoji_and_both_values():
    """The shortcode is resolved to an emoji and both values are shown side by side."""
    assert _format_stat_comparison(":straight_ruler:", "190cm", "176cm", 190, 176) == "📏 <b>190cm</b> vs 176cm"


def test_format_stat_comparison_bolds_the_higher_side():
    """Whichever side's key is higher gets bolded; the other side is left plain."""
    assert _format_stat_comparison(":straight_ruler:", "176cm", "190cm", 176, 190) == "📏 176cm vs <b>190cm</b>"


def test_format_stat_comparison_leaves_a_tie_unbolded():
    """Equal keys bold neither side."""
    assert _format_stat_comparison(":straight_ruler:", "180cm", "180cm", 180, 180) == "📏 180cm vs 180cm"


def test_format_stat_comparison_empty_when_either_side_missing():
    """A one-sided comparison isn't useful, so it's omitted entirely."""
    assert _format_stat_comparison(":straight_ruler:", "", "176cm", 0, 176) == ""
    assert _format_stat_comparison(":straight_ruler:", "190cm", "", 190, 0) == ""
    assert _format_stat_comparison(":straight_ruler:", "", "", 0, 0) == ""


def test_format_last_meeting_renders_basho_day_and_result():
    """Basho ID is resolved to its name; winner and kimarite are shown, with a lead-in emoji."""
    last_meeting = {"bashoId": "202605", "day": 15, "winnerEn": "Hoshoryu", "kimarite": "yorikiri"}
    assert _format_last_meeting(last_meeting) == "⚔️ Last met: Hoshoryu (Natsu Basho 2026)"


def test_format_last_meeting_empty_when_no_prior_meeting():
    """A `None` last meeting (first-ever bout) renders nothing."""
    assert _format_last_meeting(None) == ""


def test_format_bout_detail_joins_available_comparisons(bout_completed):
    """Height, weight, last-basho, and last-meeting lines are joined; missing ones are skipped."""
    profiles = {20: {"height": 188, "weight": 148}, 45: {"height": 192, "weight": 180}}
    last_basho = {45: {"wins": 13, "losses": 2, "absences": 0}}
    head_to_heads = {
        bout_completed["id"]: {
            "rikishiWins": 6,
            "opponentWins": 3,
            "total": 9,
            "lastMeeting": {"bashoId": "202605", "day": 15, "winnerEn": "Hoshoryu", "kimarite": "yorikiri"},
        }
    }
    result = _format_bout_detail(bout_completed, profiles, last_basho, head_to_heads)
    # Head-to-head leads; height & weight compare both sides (west is higher on both, so west is
    # bolded); last basho is one-sided (Hoshoryu absent) and omitted.
    assert result == (
        "🤼 Hoshoryu leads 6-3\n"
        "📏 188cm vs <b>192cm</b>\n⚖️ 148kg vs <b>180kg</b>\n⚔️ Last met: Hoshoryu (Natsu Basho 2026)"
    )


def test_format_bout_detail_empty_when_nothing_available(bout_completed):
    """No profiles, no last-basho records, and no head-to-head renders an empty string."""
    assert _format_bout_detail(bout_completed, {}, {}, {}) == ""


# ---------------------------------------------------------------------------
# sumo_matches_for_date — detailed-bout selection
# ---------------------------------------------------------------------------


def test_sumo_matches_shows_only_top_n_remaining_bouts(basho_july_2026):
    """Only the top `SUMO_DETAILED_BOUT_COUNT` unfought bouts appear at all; the rest are dropped."""

    def bout(match_no, east_id, west_id, winner=None):
        return {
            "id": f"202607-3-{match_no}-{east_id}-{west_id}",
            "matchNo": match_no,
            "eastId": east_id,
            "eastShikona": f"East{east_id}",
            "eastRank": "Maegashira 1 East",
            "westId": west_id,
            "westShikona": f"West{west_id}",
            "westRank": "Maegashira 1 West",
            "kimarite": "yorikiri" if winner else "",
            "winnerEn": f"East{east_id}" if winner else "",
        }

    # Listed lowest-ranked first, matching the API's ordering; 7 unfought + 1 already fought.
    bouts = [bout(n, 100 + n, 200 + n) for n in range(1, 8)] + [bout(8, 108, 208, winner=True)]
    torikumi = {**basho_july_2026, "torikumi": bouts}

    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi),
        patch("broiestbot.commands.sumo.matches.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
        patch(
            "broiestbot.commands.sumo.matches.fetch_rikishi_profiles",
            new_callable=AsyncMock,
            # Height/weight double as the rikishi ID so each bout's comparison line is distinct.
            return_value={rikishi_id: {"height": rikishi_id, "weight": rikishi_id} for rikishi_id in range(101, 208)},
        ) as mock_profiles,
        patch("broiestbot.commands.sumo.matches.fetch_last_basho_records", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 14)))

    # Marquee (highest-numbered, listed last, shown first) bouts 7 down to 3 appear, with detail.
    # West's ID is always higher than East's here, so West's value is always bolded.
    for n in (7, 6, 5, 4, 3):
        assert f"East{100 + n}" in result
        assert f"📏 {100 + n}cm vs <b>{200 + n}cm</b>" in result
    # The two lowest-ranked unfought bouts, and the already-fought bout, don't appear at all.
    for n in (2, 1, 8):
        assert f"East{100 + n}" not in result
    # Marquee ordering is preserved among the surviving bouts.
    assert result.index("107cm") < result.index("103cm")
    # Only the 5 detailed bouts' rikishi were looked up.
    requested_ids = set(mock_profiles.await_args.args[0])
    assert requested_ids == {r for n in (3, 4, 5, 6, 7) for r in (100 + n, 200 + n)}


def test_sumo_matches_keeps_candidate_bout_when_all_detail_lookups_fail(basho_july_2026, torikumi_day_3):
    """A candidate bout still shows (records-only) even if every detail lookup fails; only bouts
    outside the top N are dropped, not ones whose enrichment happened to come back empty."""
    with (
        patch(
            "broiestbot.commands.sumo.matches.get_current_or_next_basho",
            new_callable=AsyncMock,
            return_value=basho_july_2026,
        ),
        patch("broiestbot.commands.sumo.matches.fetch_torikumi", new_callable=AsyncMock, return_value=torikumi_day_3),
        patch("broiestbot.commands.sumo.matches.fetch_basho_records", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_head_to_heads", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_rikishi_profiles", new_callable=AsyncMock, return_value={}),
        patch("broiestbot.commands.sumo.matches.fetch_last_basho_records", new_callable=AsyncMock, return_value={}),
    ):
        result = asyncio.run(sumo_matches_for_date(date(2026, 7, 14)))

    # The candidate (remaining) bout still shows, just without a detail block.
    assert "<b>Dewanoryu</b> vs <b>Oshoumi</b>" in result
    assert "Last met" not in result
    # The already-fought bout is dropped regardless.
    assert "Onosato" not in result
