"""Tests for sumo banzuke records & head-to-head fetching."""

import asyncio
from unittest.mock import patch

from aiohttp import ClientConnectionError

from broiestbot.commands.sumo import records
from broiestbot.commands.sumo.records import (
    fetch_basho_records,
    fetch_head_to_head,
    fetch_head_to_heads,
    fetch_last_basho_records,
    fetch_rikishi_profile,
    fetch_rikishi_profiles,
)
from tests.aiohttp_mocks import FakeResponse, patch_http_session

MODULE = "broiestbot.commands.sumo.records"


def _clear_cache():
    records._HEAD_TO_HEAD_CACHE.clear()


# ---------------------------------------------------------------------------
# fetch_basho_records
# ---------------------------------------------------------------------------


def test_fetch_basho_records_merges_both_sides(banzuke_day_3, basho_records):
    """East and west banzuke entries are flattened into one map keyed by rikishi ID."""
    with patch_http_session(MODULE, FakeResponse(json_data=banzuke_day_3)):
        result = asyncio.run(fetch_basho_records("202607"))

    assert result == basho_records


def test_fetch_basho_records_returns_empty_on_error():
    """A failed banzuke request degrades to an empty map rather than raising."""
    with patch_http_session(MODULE, ClientConnectionError("boom")):
        result = asyncio.run(fetch_basho_records("202607"))

    assert result == {}


def test_fetch_basho_records_returns_empty_on_non_200():
    """A non-200 banzuke response degrades to an empty map."""
    with patch_http_session(MODULE, FakeResponse(status=404, json_data={})):
        result = asyncio.run(fetch_basho_records("202607"))

    assert result == {}


# ---------------------------------------------------------------------------
# fetch_head_to_head
# ---------------------------------------------------------------------------


def test_fetch_head_to_head_keeps_summary_only(head_to_head_hoshoryu_onosato):
    """The bout list & kimarite breakdowns are dropped; only the series totals are kept."""
    with patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)) as mock_session:
        result = asyncio.run(fetch_head_to_head(20, 45))

    assert result == {
        "rikishiWins": 6,
        "opponentWins": 3,
        "total": 9,
        "lastMeeting": {"bashoId": "202605", "day": 15, "winnerEn": "Hoshoryu", "kimarite": "yorikiri"},
    }
    session = mock_session.return_value
    assert session.calls[0][1].endswith("/rikishi/20/matches/45")


def test_fetch_head_to_head_returns_none_on_error():
    """A failed head-to-head request returns None rather than raising."""
    with patch_http_session(MODULE, ClientConnectionError("boom")):
        result = asyncio.run(fetch_head_to_head(20, 45))

    assert result is None


# ---------------------------------------------------------------------------
# fetch_head_to_heads
# ---------------------------------------------------------------------------


def test_fetch_head_to_heads_keys_by_bout_id(bout_completed, bout_upcoming, head_to_head_hoshoryu_onosato):
    """Each eligible bout gets a summary keyed by its ID."""
    _clear_cache()
    with patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)):
        result = asyncio.run(fetch_head_to_heads([bout_upcoming, bout_completed]))

    assert set(result) == {bout_upcoming["id"], bout_completed["id"]}
    assert result[bout_completed["id"]]["rikishiWins"] == 6
    assert result[bout_completed["id"]]["lastMeeting"]["bashoId"] == "202605"


def test_fetch_head_to_heads_skips_bouts_missing_rikishi(bout_upcoming, head_to_head_hoshoryu_onosato):
    """Bouts without both rikishi IDs (or no ID) are never looked up."""
    _clear_cache()
    unannounced = {**bout_upcoming, "id": "202607-4-1-135-0", "westId": 0, "westShikona": ""}
    no_id = {"eastId": 1, "westId": 2, "eastShikona": "A", "westShikona": "B"}
    with patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)) as mock_session:
        result = asyncio.run(fetch_head_to_heads([unannounced, no_id]))

    assert result == {}
    assert mock_session.return_value.calls == []


def test_fetch_head_to_heads_drops_failed_lookups(bout_completed, bout_upcoming, head_to_head_hoshoryu_onosato):
    """A bout whose lookup fails is absent from the result; the others still come back."""
    _clear_cache()
    responses = [FakeResponse(json_data=head_to_head_hoshoryu_onosato), ClientConnectionError("boom")]
    with patch_http_session(MODULE, *responses):
        result = asyncio.run(fetch_head_to_heads([bout_upcoming, bout_completed]))

    assert set(result) == {bout_upcoming["id"]}


def test_fetch_head_to_heads_serves_repeat_lookups_from_cache(bout_upcoming, head_to_head_hoshoryu_onosato):
    """A second lookup for the same unfought bout doesn't hit the API."""
    _clear_cache()
    with patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)) as mock_session:
        asyncio.run(fetch_head_to_heads([bout_upcoming]))
        result = asyncio.run(fetch_head_to_heads([bout_upcoming]))

    assert result[bout_upcoming["id"]]["total"] == 9
    assert len(mock_session.return_value.calls) == 1


def test_fetch_head_to_heads_refetches_once_bout_is_fought(bout_upcoming, head_to_head_hoshoryu_onosato):
    """The pre-fight cache entry isn't reused once the bout has a winner."""
    _clear_cache()
    fought = {**bout_upcoming, "winnerEn": bout_upcoming["eastShikona"], "winnerId": bout_upcoming["eastId"]}
    with patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)) as mock_session:
        asyncio.run(fetch_head_to_heads([bout_upcoming]))
        asyncio.run(fetch_head_to_heads([fought]))

    assert len(mock_session.return_value.calls) == 2


def test_fetch_head_to_heads_expires_cache_entries(bout_upcoming, head_to_head_hoshoryu_onosato):
    """An entry past its TTL is refetched."""
    _clear_cache()
    clock = [0.0]
    with (
        patch_http_session(MODULE, FakeResponse(json_data=head_to_head_hoshoryu_onosato)) as mock_session,
        patch(f"{MODULE}.time.monotonic", side_effect=lambda: clock[0]),
    ):
        asyncio.run(fetch_head_to_heads([bout_upcoming]))
        clock[0] += records.SUMO_HEAD_TO_HEAD_CACHE_TTL + 1
        asyncio.run(fetch_head_to_heads([bout_upcoming]))

    assert len(mock_session.return_value.calls) == 2


# ---------------------------------------------------------------------------
# _previous_basho_id
# ---------------------------------------------------------------------------


def test_previous_basho_id_steps_back_two_months():
    """The usual case: two months back, same year."""
    assert records._previous_basho_id("202609") == "202607"


def test_previous_basho_id_wraps_year_boundary():
    """January wraps to November of the prior year."""
    assert records._previous_basho_id("202601") == "202511"


# ---------------------------------------------------------------------------
# fetch_last_basho_records
# ---------------------------------------------------------------------------


def test_fetch_last_basho_records_merges_makuuchi_and_juryo(last_basho_banzuke_makuuchi, last_basho_banzuke_juryo):
    """Records come from the *previous* basho's banzuke, across both divisions."""
    records._LAST_BASHO_RECORDS_CACHE.clear()
    responses = [FakeResponse(json_data=last_basho_banzuke_makuuchi), FakeResponse(json_data=last_basho_banzuke_juryo)]
    with patch_http_session(MODULE, *responses) as mock_session:
        result = asyncio.run(fetch_last_basho_records("202607"))

    assert result == {
        20: {"wins": 12, "losses": 3, "absences": 0},
        45: {"wins": 13, "losses": 2, "absences": 0},
    }
    assert mock_session.return_value.calls[0][1].endswith("/basho/202605/banzuke/Makuuchi")
    assert mock_session.return_value.calls[1][1].endswith("/basho/202605/banzuke/Juryo")


def test_fetch_last_basho_records_caches_successful_result(last_basho_banzuke_makuuchi, last_basho_banzuke_juryo):
    """A second call for the same basho is served from cache."""
    records._LAST_BASHO_RECORDS_CACHE.clear()
    responses = [FakeResponse(json_data=last_basho_banzuke_makuuchi), FakeResponse(json_data=last_basho_banzuke_juryo)]
    with patch_http_session(MODULE, *responses) as mock_session:
        asyncio.run(fetch_last_basho_records("202607"))
        asyncio.run(fetch_last_basho_records("202607"))

    assert len(mock_session.return_value.calls) == 2


def test_fetch_last_basho_records_does_not_cache_failure():
    """A wholly failed fetch isn't cached, so it's retried on the next call."""
    records._LAST_BASHO_RECORDS_CACHE.clear()
    with patch_http_session(MODULE, ClientConnectionError("boom")):
        result = asyncio.run(fetch_last_basho_records("202607"))

    assert result == {}
    assert "202605" not in records._LAST_BASHO_RECORDS_CACHE


# ---------------------------------------------------------------------------
# fetch_rikishi_profile(s)
# ---------------------------------------------------------------------------


def test_fetch_rikishi_profile_keeps_height_and_weight(rikishi_profile_hoshoryu):
    """Only height & weight are kept from the full rikishi payload."""
    with patch_http_session(MODULE, FakeResponse(json_data=rikishi_profile_hoshoryu)) as mock_session:
        result = asyncio.run(fetch_rikishi_profile(20))

    assert result == {"height": 188, "weight": 148}
    assert mock_session.return_value.calls[0][1].endswith("/rikishi/20")


def test_fetch_rikishi_profile_returns_none_on_error():
    """A failed profile request returns None rather than raising."""
    with patch_http_session(MODULE, ClientConnectionError("boom")):
        result = asyncio.run(fetch_rikishi_profile(20))

    assert result is None


def test_fetch_rikishi_profiles_keys_by_id_and_dedupes_ids(rikishi_profile_hoshoryu):
    """A batch lookup returns a map by ID, and skips falsy IDs."""
    records._RIKISHI_PROFILE_CACHE.clear()
    with patch_http_session(MODULE, FakeResponse(json_data=rikishi_profile_hoshoryu)) as mock_session:
        result = asyncio.run(fetch_rikishi_profiles([20, 0, None]))

    assert result == {20: {"height": 188, "weight": 148}}
    assert len(mock_session.return_value.calls) == 1


def test_fetch_rikishi_profiles_drops_failed_lookups(rikishi_profile_hoshoryu):
    """A rikishi whose lookup fails is absent from the result; others still come back."""
    records._RIKISHI_PROFILE_CACHE.clear()
    responses = [FakeResponse(json_data=rikishi_profile_hoshoryu), ClientConnectionError("boom")]
    with patch_http_session(MODULE, *responses):
        result = asyncio.run(fetch_rikishi_profiles([20, 45]))

    assert result == {20: {"height": 188, "weight": 148}}


def test_fetch_rikishi_profiles_serves_repeat_lookups_from_cache(rikishi_profile_hoshoryu):
    """A second lookup for the same rikishi doesn't hit the API."""
    records._RIKISHI_PROFILE_CACHE.clear()
    with patch_http_session(MODULE, FakeResponse(json_data=rikishi_profile_hoshoryu)) as mock_session:
        asyncio.run(fetch_rikishi_profiles([20]))
        asyncio.run(fetch_rikishi_profiles([20]))

    assert len(mock_session.return_value.calls) == 1
