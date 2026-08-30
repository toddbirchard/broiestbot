"""Tests for the league transfer ledger in broiestbot/commands/footy/transfers.py."""

import asyncio
from datetime import date, timedelta

import pytest

from broiestbot.commands.footy.transfers import (
    TRANSFER_LEDGER_LIMIT,
    epl_recent_transfers,
    deduplicate_transfers,
    fetch_league_team_ids,
    filter_incoming_transfers,
    format_transfer_ledger,
    format_transfer_type,
    league_recent_transfers,
    parse_team_transfers,
    parse_transfer_date,
)
from tests.aiohttp_mocks import FakeResponse, patch_http_session

MODULE = "broiestbot.commands.footy.transfers"

MANU = 33
BRIGHTON = 51


def _player_record(player_id, player_name, transfers):
    return {"player": {"id": player_id, "name": player_name}, "transfers": transfers}


def _transfer(transfer_date, transfer_type, out_id, out_name, in_id, in_name):
    return {
        "date": transfer_date,
        "type": transfer_type,
        "teams": {
            "out": {"id": out_id, "name": out_name},
            "in": {"id": in_id, "name": in_name},
        },
    }


# ---------------------------------------------------------------------------
# parse_transfer_date
# ---------------------------------------------------------------------------


def test_parse_transfer_date_valid():
    """A well-formed YYYY-MM-DD date parses into a date object."""
    assert parse_transfer_date("2026-08-24") == date(2026, 8, 24)


@pytest.mark.parametrize("value", [None, "", "not-a-date", "24-08-2026"])
def test_parse_transfer_date_invalid(value):
    """Null or malformed dates yield None rather than raising."""
    assert parse_transfer_date(value) is None


# ---------------------------------------------------------------------------
# parse_team_transfers
# ---------------------------------------------------------------------------


def test_parse_team_transfers_keeps_recent_move():
    """A move on or after the cutoff involving the queried club is kept."""
    cutoff = date(2026, 8, 23)
    response = [
        _player_record(
            356041,
            "C. Baleba",
            [_transfer("2026-08-24", "Transfer", BRIGHTON, "Brighton", MANU, "Manchester United")],
        )
    ]
    result = parse_team_transfers(response, MANU, cutoff)
    assert len(result) == 1
    assert result[0]["player_name"] == "C. Baleba"
    assert result[0]["team_out"] == "Brighton"
    assert result[0]["team_in"] == "Manchester United"
    assert result[0]["date"] == date(2026, 8, 24)


def test_parse_team_transfers_drops_historic_moves():
    """A team query returns each player's whole career; stale moves are discarded."""
    cutoff = date(2026, 8, 23)
    response = [
        _player_record(
            19285,
            "L. Steele",
            [
                _transfer("2006-08-10", "€ 250K", MANU, "Manchester United", 60, "West Brom"),
                _transfer("2026-08-24", "Transfer", MANU, "Manchester United", 60, "West Brom"),
            ],
        )
    ]
    result = parse_team_transfers(response, MANU, cutoff)
    assert len(result) == 1
    assert result[0]["date"] == date(2026, 8, 24)


def test_parse_team_transfers_drops_move_cutoff_boundary():
    """A move exactly on the cutoff date is kept; the day before is not."""
    cutoff = date(2026, 8, 23)
    response = [
        _player_record(1, "On Cutoff", [_transfer("2026-08-23", "Transfer", MANU, "Manu", 2, "Other")]),
        _player_record(2, "Before Cutoff", [_transfer("2026-08-22", "Transfer", MANU, "Manu", 2, "Other")]),
    ]
    result = parse_team_transfers(response, MANU, cutoff)
    assert [transfer["player_name"] for transfer in result] == ["On Cutoff"]


def test_parse_team_transfers_drops_uninvolved_club():
    """A recent move which doesn't involve the queried club is discarded."""
    cutoff = date(2026, 8, 23)
    response = [
        _player_record(1, "Someone Else", [_transfer("2026-08-24", "Transfer", 60, "West Brom", 61, "Hull City")])
    ]
    assert parse_team_transfers(response, MANU, cutoff) == []


def test_parse_team_transfers_tolerates_null_fields():
    """Null players, names, teams and dates are skipped instead of raising."""
    cutoff = date(2026, 8, 23)
    response = [
        {"player": None, "transfers": [_transfer("2026-08-24", "Transfer", MANU, "Manu", 2, "Other")]},
        _player_record(1, None, [_transfer("2026-08-24", "Transfer", MANU, "Manu", 2, "Other")]),
        _player_record(2, "No Transfers", None),
        _player_record(3, "Null Date", [_transfer(None, "Transfer", MANU, "Manu", 2, "Other")]),
        _player_record(4, "Null Team Name", [_transfer("2026-08-24", "Transfer", MANU, None, 2, "Other")]),
        _player_record(5, "Null Teams", [{"date": "2026-08-24", "type": "Transfer", "teams": None}]),
    ]
    assert parse_team_transfers(response, MANU, cutoff) == []


def test_parse_team_transfers_empty_response():
    """An empty or null response yields no transfers."""
    assert parse_team_transfers([], MANU, date(2026, 8, 23)) == []
    assert parse_team_transfers(None, MANU, date(2026, 8, 23)) == []


# ---------------------------------------------------------------------------
# deduplicate_transfers
# ---------------------------------------------------------------------------


def _parsed(player_id, name, day, transfer_type, out_id, out_name, in_id, in_name):
    return {
        "player_id": player_id,
        "player_name": name,
        "date": day,
        "type": transfer_type,
        "team_out_id": out_id,
        "team_out": out_name,
        "team_in_id": in_id,
        "team_in": in_name,
    }


def test_deduplicate_collapses_consecutive_day_records():
    """The API records one move on consecutive days; only one entry survives."""
    transfers = [
        _parsed(356041, "C. Baleba", date(2026, 8, 23), "Transfer", BRIGHTON, "Brighton", MANU, "Manchester United"),
        _parsed(356041, "C. Baleba", date(2026, 8, 24), "Transfer", BRIGHTON, "Brighton", MANU, "Manchester United"),
    ]
    result = deduplicate_transfers(transfers)
    assert len(result) == 1
    assert result[0]["date"] == date(2026, 8, 24)


def test_deduplicate_collapses_cross_team_records():
    """A move between two league clubs appears in both feeds but is counted once."""
    from_manu_feed = _parsed(
        356041, "C. Baleba", date(2026, 8, 24), "Transfer", BRIGHTON, "Brighton", MANU, "Manchester United"
    )
    from_brighton_feed = _parsed(
        356041, "C. Baleba", date(2026, 8, 23), "Transfer", BRIGHTON, "Brighton", MANU, "Manchester United"
    )
    assert len(deduplicate_transfers([from_manu_feed, from_brighton_feed])) == 1


def test_deduplicate_prefers_informative_type():
    """Duplicates disagreeing on `type` keep the most informative value."""
    transfers = [
        _parsed(1, "Ethan Williams", date(2026, 8, 12), "-", MANU, "Manu", 2, "Peterborough"),
        _parsed(1, "Ethan Williams", date(2026, 8, 11), "Transfer", MANU, "Manu", 2, "Peterborough"),
    ]
    result = deduplicate_transfers(transfers)
    assert len(result) == 1
    assert result[0]["type"] == "Transfer"
    assert result[0]["date"] == date(2026, 8, 12)


def test_deduplicate_prefers_fee_over_word():
    """A fee outranks a generic 'Transfer' label among duplicates."""
    transfers = [
        _parsed(1, "Player", date(2026, 8, 24), "Transfer", 1, "A", 2, "B"),
        _parsed(1, "Player", date(2026, 8, 24), "€ 60M", 1, "A", 2, "B"),
    ]
    assert deduplicate_transfers(transfers)[0]["type"] == "€ 60M"


def test_deduplicate_keeps_distinct_moves_for_same_player():
    """A player moving twice (eg. loan out then recalled) yields two entries."""
    transfers = [
        _parsed(1, "Player", date(2026, 8, 24), "Loan", 1, "A", 2, "B"),
        _parsed(1, "Player", date(2026, 8, 25), "Loan return", 2, "B", 1, "A"),
    ]
    assert len(deduplicate_transfers(transfers)) == 2


def test_deduplicate_sorts_newest_first():
    """The ledger is ordered by date descending."""
    transfers = [
        _parsed(1, "Older", date(2026, 8, 24), "Transfer", 1, "A", 2, "B"),
        _parsed(2, "Newer", date(2026, 8, 27), "Transfer", 1, "A", 3, "C"),
    ]
    assert [t["player_name"] for t in deduplicate_transfers(transfers)] == ["Newer", "Older"]


def test_deduplicate_falls_back_to_names_when_ids_missing():
    """Records with null IDs still deduplicate on player and club names."""
    transfers = [
        _parsed(None, "Player", date(2026, 8, 24), "Transfer", None, "A", None, "B"),
        _parsed(None, "Player", date(2026, 8, 25), "Transfer", None, "A", None, "B"),
    ]
    assert len(deduplicate_transfers(transfers)) == 1


# ---------------------------------------------------------------------------
# filter_incoming_transfers
# ---------------------------------------------------------------------------


def test_filter_incoming_keeps_arrival_from_outside_league():
    """A player signed from a foreign club is an arrival and survives."""
    transfers = [_parsed(1, "M. Di Gregorio", date(2026, 8, 24), "Loan", 496, "Juventus", 35, "Bournemouth")]
    assert filter_incoming_transfers(transfers, [MANU, 35]) == transfers


def test_filter_incoming_drops_departure_to_outside_league():
    """A player sold to a foreign club is a departure and is dropped."""
    transfers = [_parsed(1, "O. Kellyman", date(2026, 8, 24), "Loan", 49, "Chelsea", 95, "Strasbourg")]
    assert filter_incoming_transfers(transfers, [49, MANU]) == []


def test_filter_incoming_keeps_intra_league_move():
    """A move between two league clubs is an arrival for the buying club, so it survives."""
    transfers = [
        _parsed(356041, "C. Baleba", date(2026, 8, 24), "€ 60M", BRIGHTON, "Brighton", MANU, "Manchester United")
    ]
    assert filter_incoming_transfers(transfers, [MANU, BRIGHTON]) == transfers


def test_filter_incoming_drops_move_between_two_outside_clubs():
    """A move touching neither league club (shouldn't occur, but is guarded) is dropped."""
    transfers = [_parsed(1, "Nobody", date(2026, 8, 24), "Transfer", 60, "West Brom", 61, "Hull City")]
    assert filter_incoming_transfers(transfers, [MANU, BRIGHTON]) == []


def test_filter_incoming_handles_null_destination_id():
    """A transfer with no destination club ID is dropped rather than raising."""
    transfers = [_parsed(1, "Player", date(2026, 8, 24), "Transfer", MANU, "Manu", None, "Unknown")]
    assert filter_incoming_transfers(transfers, [MANU]) == []


# ---------------------------------------------------------------------------
# format_transfer_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "N/A", "-", "", "  "])
def test_format_transfer_type_undisclosed(value):
    """Placeholder `type` values render as 'Undisclosed'."""
    assert format_transfer_type(value) == "Undisclosed"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Free agent", "Free"),
        ("Back from Loan", "Loan return"),
        ("Return from loan", "Loan return"),
        ("Loan", "Loan"),
        ("Transfer", "Transfer"),
        ("€ 20M", "€ 20M"),
    ],
)
def test_format_transfer_type_normalized(value, expected):
    """Known aliases are normalized; fees and plain labels pass through."""
    assert format_transfer_type(value) == expected


# ---------------------------------------------------------------------------
# format_transfer_ledger
# ---------------------------------------------------------------------------


def test_format_transfer_ledger_renders_move():
    """A rendered ledger names the player, both clubs, the type and the date."""
    transfers = [_parsed(1, "C. Baleba", date(2026, 8, 24), "€ 60M", BRIGHTON, "Brighton", MANU, "Manchester United")]
    result = format_transfer_ledger(transfers, ":lion: EPL")
    assert "C. Baleba" in result
    assert "Brighton" in result
    # Long club names are abbreviated for readability.
    assert "Manu" in result
    assert "€ 60M" in result
    assert "Aug 24" in result


def test_format_transfer_ledger_empty():
    """An empty ledger reports no transfers rather than rendering a bare header."""
    assert "No" in format_transfer_ledger([], ":lion: EPL")


def test_format_transfer_ledger_heading_reflects_direction():
    """An arrivals-only ledger says so in its heading, so departures aren't assumed missing."""
    transfers = [_parsed(1, "Player", date(2026, 8, 24), "Transfer", 1, "A", 2, "B")]
    assert "TRANSFERS IN" in format_transfer_ledger(transfers, ":lion: EPL", incoming_only=True)
    assert "TRANSFERS IN" not in format_transfer_ledger(transfers, ":lion: EPL")
    assert "transfers in" in format_transfer_ledger([], ":lion: EPL", incoming_only=True)


def test_format_transfer_ledger_caps_output():
    """Only TRANSFER_LEDGER_LIMIT transfers render, with the remainder summarized."""
    transfers = [
        _parsed(i, f"Player {i}", date(2026, 8, 24), "Transfer", 1, "A", 2, "B")
        for i in range(TRANSFER_LEDGER_LIMIT + 5)
    ]
    result = format_transfer_ledger(transfers, ":lion: EPL")
    assert result.count("→") == TRANSFER_LEDGER_LIMIT
    assert "and 5 more" in result


# ---------------------------------------------------------------------------
# fetch_league_team_ids
# ---------------------------------------------------------------------------


def test_fetch_league_team_ids_parses_response():
    """Team IDs are extracted from a /teams response."""
    response = {"response": [{"team": {"id": 33, "name": "Manchester United"}}, {"team": {"id": 51}}]}
    with patch_http_session(MODULE, FakeResponse(json_data=response)):
        assert asyncio.run(fetch_league_team_ids(39)) == [33, 51]


def test_fetch_league_team_ids_empty_response():
    """An empty /teams response yields no IDs rather than raising."""
    with patch_http_session(MODULE, FakeResponse(json_data={"response": []})):
        assert asyncio.run(fetch_league_team_ids(39)) == []


# ---------------------------------------------------------------------------
# league_recent_transfers (end to end)
# ---------------------------------------------------------------------------


def test_league_recent_transfers_end_to_end():
    """Two clubs reporting the same move produce a single deduplicated ledger entry."""
    today = date.today()
    recent = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    stale = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    teams_response = {"response": [{"team": {"id": MANU}}, {"team": {"id": BRIGHTON}}]}
    move = _transfer(recent, "€ 60M", BRIGHTON, "Brighton", MANU, "Manchester United")
    old_move = _transfer(stale, "Loan", MANU, "Manchester United", 60, "West Brom")
    manu_response = {"response": [_player_record(356041, "C. Baleba", [move, old_move])]}
    brighton_response = {"response": [_player_record(356041, "C. Baleba", [move])]}
    with patch_http_session(
        MODULE,
        FakeResponse(json_data=teams_response),
        FakeResponse(json_data=manu_response),
        FakeResponse(json_data=brighton_response),
    ):
        result = asyncio.run(league_recent_transfers(39, ":lion: EPL"))
    assert result.count("C. Baleba") == 1
    assert "€ 60M" in result
    assert "West Brom" not in result


def test_league_recent_transfers_survives_failing_team():
    """One club's request failing doesn't sink the whole ledger."""
    today = date.today()
    recent = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    teams_response = {"response": [{"team": {"id": MANU}}, {"team": {"id": BRIGHTON}}]}
    manu_response = {
        "response": [
            _player_record(1, "C. Baleba", [_transfer(recent, "Transfer", BRIGHTON, "Brighton", MANU, "Manu")])
        ]
    }
    with patch_http_session(
        MODULE,
        FakeResponse(json_data=teams_response),
        FakeResponse(json_data=manu_response),
        FakeResponse(status=500, text="upstream boom"),
    ):
        result = asyncio.run(league_recent_transfers(39, ":lion: EPL"))
    assert "C. Baleba" in result


def test_league_recent_transfers_no_teams():
    """A league whose clubs can't be resolved reports a warning."""
    with patch_http_session(MODULE, FakeResponse(json_data={"response": []})):
        result = asyncio.run(league_recent_transfers(39, ":lion: EPL"))
    assert "Couldn't find any" in result


def test_epl_recent_transfers_excludes_departures():
    """`epl_recent_transfers` renders arrivals at EPL clubs and drops moves away from them."""
    today = date.today()
    recent = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    teams_response = {"response": [{"team": {"id": MANU}}, {"team": {"id": BRIGHTON}}]}
    arrival = _transfer(recent, "€ 60M", BRIGHTON, "Brighton", MANU, "Manchester United")
    departure = _transfer(recent, "Loan", MANU, "Manchester United", 95, "Strasbourg")
    manu_response = {
        "response": [
            _player_record(356041, "C. Baleba", [arrival]),
            _player_record(2, "O. Kellyman", [departure]),
        ]
    }
    brighton_response = {"response": [_player_record(356041, "C. Baleba", [arrival])]}
    with patch_http_session(
        MODULE,
        FakeResponse(json_data=teams_response),
        FakeResponse(json_data=manu_response),
        FakeResponse(json_data=brighton_response),
    ):
        result = asyncio.run(epl_recent_transfers())
    assert result.count("C. Baleba") == 1
    assert "O. Kellyman" not in result
    assert "Strasbourg" not in result
    assert "TRANSFERS IN" in result
