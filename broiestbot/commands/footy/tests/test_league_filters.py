"""Tests for team-filtered leagues across footy commands."""

import asyncio
import time
from typing import List, Optional

import pytest
from aiohttp import ClientError

from broiestbot.commands.footy import util
from broiestbot.commands.footy.upcoming import upcoming_fixture_fetcher
from broiestbot.commands.footy.util import (
    fetch_league_team_ids,
    filter_league_fixtures,
    fixture_features_team,
    fixture_features_youth_team,
    league_is_team_filtered,
)
from config import (
    AALESUND_TEAM_ID,
    ATLETICO_MADRID_TEAM_ID,
    BARCELONA_TEAM_ID,
    BENFICA_TEAM_ID,
    CARABOU_CUP_ID,
    CLUB_FRIENDLIES_LEAGUE_ID,
    ELITESERIEN_LEAGUE_ID,
    ENGLAND_INT_TEAM_ID,
    EPL_LEAGUE_ID,
    FA_CUP_ID,
    FOOTY_FRIENDLY_NATIONS,
    FOOTY_LEAGUE_MEMBER_FILTERS,
    FOOTY_LEAGUE_TEAM_FILTERS,
    INT_FRIENDLIES_LEAGUE_ID,
    LIGA_LEAGUE_ID,
    LIVERPOOL_TEAM_ID,
    PRIMEIRA_LIGA_ID,
    REAL_MADRID_TEAM_ID,
    SPAIN_INT_TEAM_ID,
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


@pytest.fixture(autouse=True)
def empty_league_teams_cache():
    """Every test starts without any league's clubs cached."""
    util._LEAGUE_TEAMS_CACHE.clear()
    yield
    util._LEAGUE_TEAMS_CACHE.clear()


def run_filter(fixtures: Optional[List[dict]], league_id: int) -> Optional[List[dict]]:
    """
    Run `filter_league_fixtures` to completion.

    :param Optional[List[dict]] fixtures: Fixtures fetched for a single league/cup.
    :param int league_id: ID of footy league/cup the fixtures belong to.

    :returns: Optional[List[dict]]
    """
    return asyncio.run(filter_league_fixtures(fixtures, league_id))


@pytest.mark.parametrize(
    "league_id,expected",
    [
        (PRIMEIRA_LIGA_ID, True),
        (ELITESERIEN_LEAGUE_ID, True),
        (LIGA_LEAGUE_ID, True),
        (FA_CUP_ID, True),
        (CARABOU_CUP_ID, True),
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
    assert run_filter([fixture], league_id) == [fixture]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_away_fixture_kept(league_id: int, team_id: int, league_name: str):
    """A fixture with the club we care about away survives filtering."""
    fixture = build_fixture(ANOTHER_TEAM_ID, team_id, league_id)
    assert run_filter([fixture], league_id) == [fixture]


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_fixture_without_the_club_discarded(league_id: int, team_id: int, league_name: str, other_fixture: dict):
    """A fixture the club takes no part in is discarded."""
    assert run_filter([other_fixture], league_id) == []


@pytest.mark.parametrize("league_id,team_id,league_name", SINGLE_TEAM_LEAGUES)
def test_only_the_clubs_fixtures_survive_a_matchday(
    league_id: int, team_id: int, league_name: str, other_fixture: dict
):
    """A full matchday is reduced to the fixtures the club takes part in."""
    home_fixture = build_fixture(team_id, OTHER_TEAM_ID, league_id)
    away_fixture = build_fixture(ANOTHER_TEAM_ID, team_id, league_id)
    matchday = [other_fixture, home_fixture, other_fixture, away_fixture]
    assert run_filter(matchday, league_id) == [home_fixture, away_fixture]


def test_unfiltered_league_passes_through(other_fixture: dict):
    """Fixtures of a league with no team filter are never discarded."""
    assert run_filter([other_fixture], EPL_LEAGUE_ID) == [other_fixture]


def test_club_friendlies_still_filtered_by_friendly_clubs():
    """Generalizing the filter leaves club friendlies filtered by `FOOTY_FRIENDLY_CLUBS`."""
    liverpool_friendly = build_fixture(LIVERPOOL_TEAM_ID, OTHER_TEAM_ID, CLUB_FRIENDLIES_LEAGUE_ID)
    unknown_friendly = build_fixture(999999, 999998, CLUB_FRIENDLIES_LEAGUE_ID)
    fixtures = [liverpool_friendly, unknown_friendly]
    assert run_filter(fixtures, CLUB_FRIENDLIES_LEAGUE_ID) == [liverpool_friendly]


def test_la_liga_filtered_to_its_big_three():
    """La Liga keeps fixtures featuring Real Madrid, Atletico or Barcelona, and drops the rest."""
    el_clasico = build_fixture(BARCELONA_TEAM_ID, REAL_MADRID_TEAM_ID, LIGA_LEAGUE_ID)
    madrid_derby = build_fixture(ATLETICO_MADRID_TEAM_ID, REAL_MADRID_TEAM_ID, LIGA_LEAGUE_ID)
    atleti_away = build_fixture(OTHER_TEAM_ID, ATLETICO_MADRID_TEAM_ID, LIGA_LEAGUE_ID)
    other_liga_fixture = build_fixture(OTHER_TEAM_ID, ANOTHER_TEAM_ID, LIGA_LEAGUE_ID)
    matchday = [other_liga_fixture, el_clasico, madrid_derby, other_liga_fixture, atleti_away]
    assert run_filter(matchday, LIGA_LEAGUE_ID) == [el_clasico, madrid_derby, atleti_away]


# ---------------------------------------------------------------------------
# Cups filtered to clubs currently in another league (ie: FA Cup -> EPL)
# ---------------------------------------------------------------------------

# Stand-in EPL roster, served by a faked /v3/teams request.
EPL_CLUB_ID = LIVERPOOL_TEAM_ID
OTHER_EPL_CLUB_ID = 746
EPL_TEAMS_RESPONSE = {"response": [{"team": {"id": EPL_CLUB_ID}}, {"team": {"id": OTHER_EPL_CLUB_ID}}]}

DOMESTIC_CUPS = pytest.mark.parametrize("league_id", [FA_CUP_ID, CARABOU_CUP_ID], ids=["fa-cup", "carabou-cup"])


def test_domestic_cups_filtered_to_epl_clubs_config():
    """Both domestic cups are filtered to whichever clubs are in the EPL, not to a fixed list."""
    assert FOOTY_LEAGUE_MEMBER_FILTERS == {FA_CUP_ID: EPL_LEAGUE_ID, CARABOU_CUP_ID: EPL_LEAGUE_ID}
    assert FA_CUP_ID not in FOOTY_LEAGUE_TEAM_FILTERS and CARABOU_CUP_ID not in FOOTY_LEAGUE_TEAM_FILTERS


@DOMESTIC_CUPS
def test_domestic_cups_keep_ties_featuring_an_epl_club(league_id: int):
    """A cup keeps ties featuring a club in this season's EPL, against anyone, and drops the rest."""
    epl_vs_lower_league = build_fixture(OTHER_TEAM_ID, EPL_CLUB_ID, league_id)
    epl_vs_epl = build_fixture(OTHER_EPL_CLUB_ID, EPL_CLUB_ID, league_id)
    lower_league_tie = build_fixture(OTHER_TEAM_ID, ANOTHER_TEAM_ID, league_id)
    round_of_ties = [lower_league_tie, epl_vs_lower_league, lower_league_tie, epl_vs_epl]
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=EPL_TEAMS_RESPONSE)) as mock:
        assert run_filter(round_of_ties, league_id) == [epl_vs_lower_league, epl_vs_epl]
    params = mock.return_value.calls[0][2]["params"]
    assert params == {"league": EPL_LEAGUE_ID, "season": util.get_season_year(EPL_LEAGUE_ID)}


def test_epl_clubs_fetched_once_for_both_cups(other_fixture: dict):
    """Both cups share one cached EPL roster, so filtering costs one /v3/teams request a day."""
    fa_cup_tie = build_fixture(EPL_CLUB_ID, OTHER_TEAM_ID, FA_CUP_ID)
    carabou_cup_tie = build_fixture(OTHER_TEAM_ID, EPL_CLUB_ID, CARABOU_CUP_ID)
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=EPL_TEAMS_RESPONSE)) as mock:
        assert run_filter([fa_cup_tie, other_fixture], FA_CUP_ID) == [fa_cup_tie]
        assert run_filter([carabou_cup_tie], CARABOU_CUP_ID) == [carabou_cup_tie]
        assert run_filter([fa_cup_tie], FA_CUP_ID) == [fa_cup_tie]
    assert len(mock.return_value.calls) == 1


def test_cup_without_fixtures_skips_the_roster_lookup():
    """A cup with nothing on today never pays for an EPL roster request."""
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=EPL_TEAMS_RESPONSE)) as mock:
        assert run_filter([], FA_CUP_ID) == []
    assert mock.return_value.calls == []


def test_expired_roster_is_refreshed():
    """Once the cached roster expires it is fetched again, so promoted clubs are picked up."""
    promoted_club_tie = build_fixture(ANOTHER_TEAM_ID, OTHER_TEAM_ID, FA_CUP_ID)
    season = util.get_season_year(EPL_LEAGUE_ID)
    util._LEAGUE_TEAMS_CACHE[EPL_LEAGUE_ID] = (time.monotonic() - 1, season, [EPL_CLUB_ID])
    promoted_roster = {"response": [{"team": {"id": EPL_CLUB_ID}}, {"team": {"id": ANOTHER_TEAM_ID}}]}
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=promoted_roster)):
        assert run_filter([promoted_club_tie], FA_CUP_ID) == [promoted_club_tie]


def test_roster_from_last_season_is_refreshed():
    """A roster cached for last season is refetched even before its TTL is up."""
    season = util.get_season_year(EPL_LEAGUE_ID)
    util._LEAGUE_TEAMS_CACHE[EPL_LEAGUE_ID] = (time.monotonic() + 3600, season - 1, [ANOTHER_TEAM_ID])
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=EPL_TEAMS_RESPONSE)) as mock:
        assert asyncio.run(fetch_league_team_ids(EPL_LEAGUE_ID)) == [EPL_CLUB_ID, OTHER_EPL_CLUB_ID]
    assert len(mock.return_value.calls) == 1


@pytest.mark.parametrize(
    "failure",
    [ClientError("boom"), FakeResponse(json_data={"response": []}), FakeResponse(status=500, text="upstream boom")],
    ids=["client-error", "empty-response", "server-error"],
)
def test_failed_refresh_serves_the_stale_roster(failure):
    """A failed refresh keeps the last roster rather than discarding every tie of the cup."""
    epl_tie = build_fixture(EPL_CLUB_ID, OTHER_TEAM_ID, FA_CUP_ID)
    season = util.get_season_year(EPL_LEAGUE_ID)
    util._LEAGUE_TEAMS_CACHE[EPL_LEAGUE_ID] = (time.monotonic() - 1, season - 1, [EPL_CLUB_ID])
    with patch_http_session("broiestbot.commands.footy.util", failure):
        assert run_filter([epl_tie], FA_CUP_ID) == [epl_tie]


def test_cup_ties_discarded_when_the_roster_cannot_be_fetched(other_fixture: dict):
    """With no roster fetched yet and the API failing, the cup's ties are discarded, not dumped unfiltered."""
    epl_tie = build_fixture(EPL_CLUB_ID, OTHER_TEAM_ID, FA_CUP_ID)
    with patch_http_session("broiestbot.commands.footy.util", ClientError("boom")):
        assert run_filter([epl_tie, other_fixture], FA_CUP_ID) == []
    assert util._LEAGUE_TEAMS_CACHE == {}


def test_fetch_league_team_ids_parses_response():
    """Team IDs are extracted from a /teams response, skipping entries without one."""
    response = {"response": [{"team": {"id": 33, "name": "Manchester United"}}, {"team": {}}, {"team": {"id": 51}}]}
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data=response)):
        assert asyncio.run(fetch_league_team_ids(39)) == [33, 51]


def test_fetch_league_team_ids_empty_response():
    """An empty /teams response yields no IDs rather than raising, and isn't cached."""
    with patch_http_session("broiestbot.commands.footy.util", FakeResponse(json_data={"response": []})):
        assert asyncio.run(fetch_league_team_ids(39)) == []
    assert util._LEAGUE_TEAMS_CACHE == {}


def build_named_fixture(home_team_name: str, away_team_name: str, league_id: int = INT_FRIENDLIES_LEAGUE_ID) -> dict:
    """
    Build a minimal fixture between two named sides.

    :param str home_team_name: Name of the home side.
    :param str away_team_name: Name of the away side.
    :param int league_id: ID of the league the fixture belongs to.

    :returns: dict
    """
    fixture = build_fixture(OTHER_TEAM_ID, ANOTHER_TEAM_ID, league_id)
    fixture["teams"]["home"]["name"] = home_team_name
    fixture["teams"]["away"]["name"] = away_team_name
    return fixture


@pytest.mark.parametrize(
    "home_team_name,away_team_name,expected",
    [
        ("England U17", "Spain U17", True),
        ("Arsenal U21", "Brighton", True),
        ("Brazil", "Canada W U17", True),
        ("England", "Spain", False),
        ("Barcelona B", "Rangers II", False),
        ("U Craiova 1948", "FC Schalke 04", False),
    ],
)
def test_youth_teams_are_detected_by_age_group(home_team_name: str, away_team_name: str, expected: bool):
    """A side named for an age group is a youth team; reserve & numbered club names are not."""
    fixture = build_named_fixture(home_team_name, away_team_name)
    assert fixture_features_youth_team(fixture) is expected


def test_int_friendlies_drop_youth_fixtures():
    """International friendlies between youth sides are discarded; senior ones are kept."""
    senior = build_named_fixture("England", "Spain")
    youth = build_named_fixture("England U19", "Spain U19")
    for fixture in (senior, youth):
        fixture["teams"]["home"]["id"] = ENGLAND_INT_TEAM_ID
        fixture["teams"]["away"]["id"] = SPAIN_INT_TEAM_ID
    assert run_filter([senior, youth], INT_FRIENDLIES_LEAGUE_ID) == [senior]


@pytest.mark.parametrize("nation_id", FOOTY_FRIENDLY_NATIONS)
@pytest.mark.parametrize("home", [True, False], ids=["home", "away"])
def test_int_friendlies_keep_fixtures_of_friendly_nations(nation_id: int, home: bool):
    """A friendly featuring one of `FOOTY_FRIENDLY_NATIONS`, home or away, is kept."""
    fixture = (
        build_fixture(nation_id, OTHER_TEAM_ID, INT_FRIENDLIES_LEAGUE_ID)
        if home
        else build_fixture(OTHER_TEAM_ID, nation_id, INT_FRIENDLIES_LEAGUE_ID)
    )
    assert run_filter([fixture], INT_FRIENDLIES_LEAGUE_ID) == [fixture]


def test_int_friendlies_drop_fixtures_without_friendly_nations():
    """A friendly between two nations nobody follows (e.g. Russia v Namibia) is discarded."""
    england_friendly = build_fixture(ENGLAND_INT_TEAM_ID, OTHER_TEAM_ID, INT_FRIENDLIES_LEAGUE_ID)
    other_friendly = build_named_fixture("Russia", "Namibia")
    assert run_filter([england_friendly, other_friendly], INT_FRIENDLIES_LEAGUE_ID) == [england_friendly]


def test_club_friendlies_drop_youth_fixtures_of_friendly_clubs():
    """A friendly club's youth side is discarded even though its team filter would keep it."""
    senior = build_named_fixture("Liverpool", "Athletic Club", CLUB_FRIENDLIES_LEAGUE_ID)
    youth = build_named_fixture("Liverpool U21", "Everton U21", CLUB_FRIENDLIES_LEAGUE_ID)
    senior["teams"]["home"]["id"] = LIVERPOOL_TEAM_ID
    youth["teams"]["home"]["id"] = LIVERPOOL_TEAM_ID
    assert run_filter([senior, youth], CLUB_FRIENDLIES_LEAGUE_ID) == [senior]


def test_youth_fixtures_of_other_leagues_are_kept():
    """Only friendlies are youth-filtered; a youth competition keeps its youth fixtures."""
    youth = build_named_fixture("England U21", "Spain U21", EPL_LEAGUE_ID)
    assert run_filter([youth], EPL_LEAGUE_ID) == [youth]


@pytest.mark.parametrize("fixtures", [None, []])
def test_empty_fixtures_pass_through(fixtures: Optional[List[dict]]):
    """An empty or absent response is returned as-is rather than raising."""
    assert run_filter(fixtures, PRIMEIRA_LIGA_ID) == fixtures


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
    assert run_filter([fixture], PRIMEIRA_LIGA_ID) == []


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
