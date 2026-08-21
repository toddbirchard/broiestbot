"""Tests for team-filtered leagues across footy commands."""

import asyncio
from typing import List, Optional

import pytest

from broiestbot.commands.footy.upcoming import upcoming_fixture_fetcher
from broiestbot.commands.footy.util import (
    filter_league_fixtures,
    fixture_features_team,
    league_is_team_filtered,
)
from config import (
    AALESUND_TEAM_ID,
    BENFICA_TEAM_ID,
    CLUB_FRIENDLIES_LEAGUE_ID,
    ELITESERIEN_LEAGUE_ID,
    EPL_LEAGUE_ID,
    FOOTY_LEAGUE_TEAM_FILTERS,
    LIVERPOOL_TEAM_ID,
    PRIMEIRA_LIGA_ID,
)
from tests.aiohttp_mocks import FakeResponse, patch_http_session

# Stand-in opponents; no club outside `FOOTY_LEAGUE_TEAM_FILTERS` needs a config constant.
OTHER_TEAM_ID = 212
ANOTHER_TEAM_ID = 228

# Leagues filtered down to a single club, and the display name each is configured under.
SINGLE_TEAM_LEAGUES = [
    pytest.param(PRIMEIRA_LIGA_ID, BENFICA_TEAM_ID, ":Portugal: PRIMEIRA LIGA", id="primeira-liga-benfica"),
    pytest.param(ELITESERIEN_LEAGUE_ID, AALESUND_TEAM_ID, ":Norway: ELITESERIEN", id="eliteserien-aalesund"),
]


def build_fixture(home_team_id: Optional[int], away_team_id: Optional[int], league_id: int = PRIMEIRA_LIGA_ID) -> dict:
    """
    Build a minimal fixture as returned by /v3/fixtures.

    :param Optional[int] home_team_id: ID of the home side.
    :param Optional[int] away_team_id: ID of the away side.
    :param int league_id: ID of the league the fixture belongs to.

    :returns: dict
    """
    return {
        "fixture": {"id": 1, "date": "2026-08-23T19:00:00+00:00"},
        "league": {"id": league_id, "name": "League", "season": 2026},
        "teams": {
            "home": {"id": home_team_id, "name": "Home"},
            "away": {"id": away_team_id, "name": "Away"},
        },
    }


@pytest.fixture
def other_fixture() -> dict:
    """Fixture between two clubs no league is filtered for."""
    return build_fixture(OTHER_TEAM_ID, ANOTHER_TEAM_ID)


@pytest.mark.parametrize(
    "league_id,expected",
    [
        (PRIMEIRA_LIGA_ID, True),
        (ELITESERIEN_LEAGUE_ID, True),
        (CLUB_FRIENDLIES_LEAGUE_ID, True),
        (EPL_LEAGUE_ID, False),
    ],
)
def test_league_is_team_filtered(league_id: int, expected: bool):
    """Only leagues configured in `FOOTY_LEAGUE_TEAM_FILTERS` are team-filtered."""
    assert league_is_team_filtered(league_id) is expected


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_league_is_filtered_to_a_single_club(league_id: int, team_id: int, league_name: str):
    """Each single-club league is scoped to that club alone."""
    assert list(FOOTY_LEAGUE_TEAM_FILTERS[league_id]) == [team_id]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_home_fixture_kept(league_id: int, team_id: int, league_name: str):
    """A fixture with the club we care about at home survives filtering."""
    fixture = build_fixture(team_id, OTHER_TEAM_ID, league_id)
    assert filter_league_fixtures([fixture], league_id) == [fixture]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_away_fixture_kept(league_id: int, team_id: int, league_name: str):
    """A fixture with the club we care about away survives filtering."""
    fixture = build_fixture(ANOTHER_TEAM_ID, team_id, league_id)
    assert filter_league_fixtures([fixture], league_id) == [fixture]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_fixture_without_the_club_discarded(league_id: int, team_id: int, league_name: str, other_fixture: dict):
    """A fixture the club takes no part in is discarded."""
    assert filter_league_fixtures([other_fixture], league_id) == []


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_only_the_clubs_fixtures_survive_a_matchday(
    league_id: int, team_id: int, league_name: str, other_fixture: dict
):
    """A full matchday is reduced to the fixtures the club takes part in."""
    home_fixture = build_fixture(team_id, OTHER_TEAM_ID, league_id)
    away_fixture = build_fixture(ANOTHER_TEAM_ID, team_id, league_id)
    matchday = [other_fixture, home_fixture, other_fixture, away_fixture]
    assert filter_league_fixtures(matchday, league_id) == [home_fixture, away_fixture]


def test_unfiltered_league_passes_through(other_fixture: dict):
    """Fixtures of a league with no team filter are never discarded."""
    assert filter_league_fixtures([other_fixture], EPL_LEAGUE_ID) == [other_fixture]


def test_club_friendlies_still_filtered_by_friendly_clubs():
    """Generalizing the filter leaves club friendlies filtered by `FOOTY_FRIENDLY_CLUBS`."""
    liverpool_friendly = build_fixture(LIVERPOOL_TEAM_ID, OTHER_TEAM_ID, CLUB_FRIENDLIES_LEAGUE_ID)
    unknown_friendly = build_fixture(999999, 999998, CLUB_FRIENDLIES_LEAGUE_ID)
    fixtures = [liverpool_friendly, unknown_friendly]
    assert filter_league_fixtures(fixtures, CLUB_FRIENDLIES_LEAGUE_ID) == [liverpool_friendly]


@pytest.mark.parametrize("fixtures", [None, []])
def test_empty_fixtures_pass_through(fixtures: Optional[List[dict]]):
    """An empty or absent response is returned as-is rather than raising."""
    assert filter_league_fixtures(fixtures, PRIMEIRA_LIGA_ID) == fixtures


@pytest.mark.parametrize(
    "fixture",
    [
        {},
        {"teams": None},
        {"teams": {"home": None, "away": None}},
        {"teams": {"home": {}, "away": {}}},
    ],
)
def test_malformed_fixture_is_discarded_without_raising(fixture: dict):
    """A fixture missing team data can't feature the club we care about, but must not raise."""
    assert fixture_features_team(fixture, [BENFICA_TEAM_ID]) is False
    assert filter_league_fixtures([fixture], PRIMEIRA_LIGA_ID) == []


# ---------------------------------------------------------------------------
# Upcoming-fixture fetch strategy for team-filtered leagues
# ---------------------------------------------------------------------------


def run_upcoming_fetcher(league_name: str, league_id: int, response: dict) -> tuple:
    """
    Run `upcoming_fixture_fetcher` against a canned response.

    :param str league_name: Display name of the league.
    :param int league_id: ID of footy league/cup.
    :param dict response: Canned /v3/fixtures body to serve.

    :returns: tuple of (fixtures returned, params of the request issued)
    """
    patcher = patch_http_session("broiestbot.commands.footy.upcoming", FakeResponse(json_data=response))
    with patcher as mock_session:
        fixtures = asyncio.run(upcoming_fixture_fetcher(league_name, league_id, "America/New_York"))
    session = mock_session.return_value
    return fixtures, session.calls[0][2]["params"]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_single_team_league_fetched_by_date_range(league_id: int, team_id: int, league_name: str, other_fixture: dict):
    """
    A filtered club plays one fixture per matchday, so a `next`-capped request would truncate
    it away. The league is fetched across the full window and filtered instead.
    """
    kept_fixture = build_fixture(team_id, OTHER_TEAM_ID, league_id)
    fixtures, params = run_upcoming_fetcher(
        league_name, league_id, {"response": [other_fixture, kept_fixture, other_fixture]}
    )
    assert "next" not in params
    assert params["league"] == league_id
    assert params["from"] and params["to"]
    assert fixtures == [kept_fixture]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_league_omitted_when_the_club_isnt_playing(league_id: int, team_id: int, league_name: str, other_fixture: dict):
    """A matchday without the filtered club yields nothing for `!upcoming` to render."""
    fixtures, _ = run_upcoming_fetcher(league_name, league_id, {"response": [other_fixture, other_fixture]})
    assert fixtures == []


def test_unfiltered_league_still_fetched_by_next(other_fixture: dict):
    """Leagues with no team filter keep the cheaper `next` request and skip filtering."""
    fixtures, params = run_upcoming_fetcher(":lion: EPL", EPL_LEAGUE_ID, {"response": [other_fixture]})
    assert params["next"] == 8
    assert "from" not in params
    assert fixtures == [other_fixture]
