"""Tests for fetching, normalizing & classifying F1 races."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from broiestbot.commands.f1.races import (
    fetch_circuit,
    fetch_season_races,
    find_live_race,
    find_next_race,
    is_race_abandoned,
    is_race_finished,
    is_race_live,
    normalize_race,
)
from tests.aiohttp_mocks import FakeResponse, patch_http_session

RACE_START = datetime(2026, 3, 8, 15, tzinfo=timezone.utc)

# Raw Hyprace grand prix, as returned by /v2/grands-prix.
HYPRACE_GRAND_PRIX = {
    "id": "8b17825a",
    "round": 11,
    "name": "Hungarian Grand Prix",
    "officialName": "FORMULA 1 AWS HUNGARIAN GRAND PRIX 2026",
    "circuitId": "2a1c1543",
    "season": {"id": "e7d2c760", "year": 2026},
    "schedule": [
        {"id": "ae20361c", "type": "MainRace", "startDate": "2026-07-26T13:00:00Z", "endDate": "2026-07-26T15:00:00Z"},
        {"id": "7c7ba77f", "type": "StandardQualifying", "startDate": "2026-07-25T14:00:00Z"},
        {"id": "3c705c4d", "type": "FirstPractice", "startDate": "2026-07-24T11:30:00Z"},
    ],
    "startDate": "2026-07-24T11:30:00Z",
    "status": "Active",
    "scheduledLaps": 70,
    "scheduledDistance": 306.63,
}

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def test_grand_prix_is_normalized():
    """A raw Hyprace grand prix is flattened into the shape the command consumes."""
    race = normalize_race(HYPRACE_GRAND_PRIX)
    assert race["id"] == "8b17825a"
    assert race["name"] == "Hungarian Grand Prix"
    assert race["round"] == 11
    assert race["season"] == 2026
    assert race["circuit_id"] == "2a1c1543"
    # The race session's start time is what matters, not practice/qualifying.
    assert race["date"] == "2026-07-26T13:00:00Z"
    assert race["laps"] == {"total": 70, "current": None}
    assert race["distance"] == "306.63 km"


def test_normalization_without_a_race_session_falls_back_to_weekend_start():
    """A grand prix missing its race session falls back to the weekend's start time."""
    grand_prix = {**HYPRACE_GRAND_PRIX, "schedule": [{"type": "FirstPractice", "startDate": "2026-07-24T11:30:00Z"}]}
    assert normalize_race(grand_prix)["date"] == "2026-07-24T11:30:00Z"


def test_normalization_without_a_distance():
    """A grand prix without a scheduled distance omits it rather than printing `None km`."""
    assert normalize_race({**HYPRACE_GRAND_PRIX, "scheduledDistance": None})["distance"] is None


# ---------------------------------------------------------------------------
# Race state
# ---------------------------------------------------------------------------


def test_race_is_live_once_it_starts(race_live):
    """A race which has started but isn't finished is live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 16, tzinfo=timezone.utc)) is True


def test_race_is_not_live_before_lights_out(race_live):
    """A race weekend which is active but whose race hasn't started isn't live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 14, tzinfo=timezone.utc)) is False


def test_race_is_not_live_long_after_it_started(race_live):
    """A race which started well beyond its runtime is no longer considered live."""
    assert is_race_live(race_live, datetime(2026, 3, 8, 23, tzinfo=timezone.utc)) is False


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
    later_race = {**race_upcoming, "id": "gp-later", "date": "2026-04-05T15:00:00Z"}
    races = [later_race, race_completed, race_cancelled, race_upcoming]
    assert find_next_race(races, datetime(2026, 3, 4, tzinfo=timezone.utc)) == race_upcoming


def test_no_next_race_once_the_season_ends(race_completed):
    """A season of finished races has no next race."""
    assert find_next_race([race_completed], datetime(2026, 12, 20, tzinfo=timezone.utc)) is None


# ---------------------------------------------------------------------------
# API requests
# ---------------------------------------------------------------------------


def test_season_races_are_resolved_then_paged():
    """A season's ID is resolved, then its grands prix are fetched & normalized."""
    seasons = {"items": [{"id": "season-2026", "year": 2026}]}
    grands_prix = {"items": [HYPRACE_GRAND_PRIX], "hasNext": False, "totalPages": 1}
    with patch(
        "broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(side_effect=[seasons, grands_prix])
    ) as mock_fetch:
        races = asyncio.run(fetch_season_races(2026))

    assert len(races) == 1
    assert races[0]["name"] == "Hungarian Grand Prix"
    # The grands prix are keyed on the resolved season ID, paged via `pageNumber`.
    assert mock_fetch.call_args_list[1].args[1]["seasonId"] == "season-2026"
    assert mock_fetch.call_args_list[1].args[1]["pageNumber"] == 1


def test_season_races_follow_pagination():
    """Every page of a season's grands prix is gathered, not just the first."""
    seasons = {"items": [{"id": "season-2026", "year": 2026}]}
    page_one = {"items": [HYPRACE_GRAND_PRIX], "hasNext": True, "totalPages": 2}
    page_two = {"items": [{**HYPRACE_GRAND_PRIX, "id": "round-12"}], "hasNext": False, "totalPages": 2}
    with patch("broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(side_effect=[seasons, page_one, page_two])):
        races = asyncio.run(fetch_season_races(2026))

    assert [race["id"] for race in races] == ["8b17825a", "round-12"]


def test_pagination_dedupes_repeated_pages():
    """A page served twice (should the API ignore `pageNumber`) is never double-counted."""
    seasons = {"items": [{"id": "season-2026", "year": 2026}]}
    repeated_page = {"items": [HYPRACE_GRAND_PRIX], "hasNext": True, "totalPages": 2}
    final_page = {"items": [HYPRACE_GRAND_PRIX], "hasNext": False, "totalPages": 2}
    with patch(
        "broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(side_effect=[seasons, repeated_page, final_page])
    ):
        races = asyncio.run(fetch_season_races(2026))

    assert [race["id"] for race in races] == ["8b17825a"]


def test_unknown_season_returns_none():
    """A season the API has no record of yields no races."""
    with patch("broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(return_value={"items": []})):
        assert asyncio.run(fetch_season_races(2099)) is None


def test_failed_season_request_returns_none():
    """A failed season lookup is swallowed & reported as no data."""
    with patch("broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(return_value=None)):
        assert asyncio.run(fetch_season_races(2026)) is None


def test_circuit_is_mapped_to_name_city_and_flag():
    """A circuit response is flattened to the fields a race summary needs."""
    circuit_response = {
        "name": "Hungaroring",
        "place": "Budapest",
        "country": {"name": "Hungary", "alphaTwoCode": "HU"},
    }
    with patch("broiestbot.commands.f1.races._fetch_hyprace", AsyncMock(return_value=circuit_response)):
        circuit = asyncio.run(fetch_circuit("2a1c1543"))

    assert circuit == {"name": "Hungaroring", "city": "Budapest", "country": "Hungary", "country_code": "HU"}


def test_circuit_without_an_id_is_skipped():
    """A race with no circuit ID doesn't trigger a pointless request."""
    with patch("broiestbot.commands.f1.races._fetch_hyprace", AsyncMock()) as mock_fetch:
        assert asyncio.run(fetch_circuit(None)) is None
    mock_fetch.assert_not_called()


def test_non_200_response_returns_none():
    """Non-200 responses are logged & swallowed."""
    from broiestbot.commands.f1.races import _fetch_hyprace

    with patch_http_session("broiestbot.commands.f1.races", FakeResponse(status=429, text="Too many requests")):
        assert asyncio.run(_fetch_hyprace("https://hyprace/v2/seasons", {})) is None


def test_request_exception_returns_none():
    """Connection errors are logged & swallowed."""
    from broiestbot.commands.f1.races import _fetch_hyprace

    with patch_http_session("broiestbot.commands.f1.races", TimeoutError("timed out")):
        assert asyncio.run(_fetch_hyprace("https://hyprace/v2/seasons", {})) is None
