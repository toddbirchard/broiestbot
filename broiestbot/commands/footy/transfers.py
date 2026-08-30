"""Recent transfer activity across an entire league."""

import asyncio
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import (
    EPL_LEAGUE_ID,
    FOOTY_HTTP_HEADERS,
    FOOTY_TEAMS_ENDPOINT,
    FOOTY_TRANSFERS_ENDPOINT,
)

from .util import abbreviate_team_name, get_season_year

# Number of days back a transfer must fall within to make the ledger.
TRANSFER_WINDOW_DAYS = 10

# Cap on transfers rendered, so a deadline-day ledger doesn't flood the room.
TRANSFER_LEDGER_LIMIT = 20

# `type` values the API uses to mean "we don't know the fee".
UNDISCLOSED_TRANSFER_TYPES = ("n/a", "-", "", "?")

# `type` values which describe the move rather than a fee, normalized for display.
TRANSFER_TYPE_ALIASES = {
    "free agent": "Free",
    "back from loan": "Loan return",
    "return from loan": "Loan return",
}


async def epl_recent_transfers() -> str:
    """
    Construct a ledger of players signed by EPL clubs in the past week.

    :returns: str
    """
    return await league_recent_transfers(EPL_LEAGUE_ID, ":lion: EPL", incoming_only=True)


async def league_recent_transfers(league_id: int, league_name: str, incoming_only: bool = False) -> str:
    """
    Construct a ledger of every recent transfer involving a club in a given league.

    Each club is queried individually (the API has no league-wide transfers endpoint),
    so the per-team responses are merged and deduplicated into a single ledger.

    :param int league_id: ID of footy league to compile transfers for.
    :param str league_name: Display name of the league.
    :param bool incoming_only: Whether to drop departures and keep only arrivals.

    :returns: str
    """
    try:
        team_ids = await fetch_league_team_ids(league_id)
        if not team_ids:
            return emojize(
                f":warning: Couldn't find any {league_name} teams; bot is shit tbh :warning:",
                language="en",
            )
        cutoff = date.today() - timedelta(days=TRANSFER_WINDOW_DAYS)
        responses = await asyncio.gather(
            *[fetch_team_transfers(team_id) for team_id in team_ids],
            return_exceptions=True,
        )
        transfers: List[dict] = []
        for team_id, response in zip(team_ids, responses):
            if isinstance(response, BaseException):
                LOGGER.error(f"Failed to fetch transfers for team {team_id}: {response}")
                continue
            transfers.extend(parse_team_transfers(response, team_id, cutoff))
        if incoming_only:
            transfers = filter_incoming_transfers(transfers, team_ids)
        return format_transfer_ledger(deduplicate_transfers(transfers), league_name, incoming_only=incoming_only)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching {league_name} transfers: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching {league_name} transfers: {e}")
    return emojize(":warning: Couldn't fetch transfers; bot is shit tbh :warning:", language="en")


async def fetch_league_team_ids(league_id: int) -> List[int]:
    """
    Fetch the IDs of every club currently competing in a given league.

    :param int league_id: ID of footy league to fetch clubs for.

    :returns: List[int]
    """
    try:
        params = {"league": league_id, "season": get_season_year(league_id)}
        session = await get_http_session()
        async with session.get(FOOTY_TEAMS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params=params) as resp:
            teams = (await resp.json(content_type=None)).get("response")
        if not teams:
            return []
        return [team["team"]["id"] for team in teams if (team.get("team") or {}).get("id")]
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching teams for league {league_id}: {e}")
    except KeyError as e:
        LOGGER.exception(f"KeyError while fetching teams for league {league_id}: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching teams for league {league_id}: {e}")
    return []


async def fetch_team_transfers(team_id: int) -> List[dict]:
    """
    Fetch the complete transfer history of every player associated with a club.

    :param int team_id: ID of footy club to fetch transfers for.

    :returns: List[dict]
    """
    session = await get_http_session()
    async with session.get(FOOTY_TRANSFERS_ENDPOINT, headers=FOOTY_HTTP_HEADERS, params={"team": team_id}) as resp:
        return (await resp.json(content_type=None)).get("response") or []


def parse_team_transfers(response: List[dict], team_id: int, cutoff: date) -> List[dict]:
    """
    Reduce a club's transfer history to the moves it made on or after `cutoff`.

    A team query returns each player's *entire* career history, hence the filtering
    on both date and the club's own involvement in the move.

    :param List[dict] response: `/transfers` response for a single club.
    :param int team_id: ID of the club the response was fetched for.
    :param date cutoff: Earliest date a transfer may have occurred on.

    :returns: List[dict]
    """
    recent_transfers = []
    for player_record in response or []:
        player = player_record.get("player") or {}
        player_name = player.get("name")
        if not player_name:
            continue
        for transfer in player_record.get("transfers") or []:
            transfer_date = parse_transfer_date(transfer.get("date"))
            if transfer_date is None or transfer_date < cutoff:
                continue
            teams = transfer.get("teams") or {}
            team_out = teams.get("out") or {}
            team_in = teams.get("in") or {}
            if team_id not in (team_out.get("id"), team_in.get("id")):
                continue
            if not team_out.get("name") or not team_in.get("name"):
                continue
            recent_transfers.append(
                {
                    "player_id": player.get("id"),
                    "player_name": player_name,
                    "date": transfer_date,
                    "type": transfer.get("type"),
                    "team_out_id": team_out.get("id"),
                    "team_out": team_out["name"],
                    "team_in_id": team_in.get("id"),
                    "team_in": team_in["name"],
                }
            )
    return recent_transfers


def parse_transfer_date(transfer_date: Optional[str]) -> Optional[date]:
    """
    Parse a transfer's `YYYY-MM-DD` date, tolerating the nulls the API sometimes serves.

    :param Optional[str] transfer_date: Raw date value of a single transfer.

    :returns: Optional[date]
    """
    if not transfer_date:
        return None
    try:
        return datetime.strptime(transfer_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        LOGGER.warning(f"Unparseable transfer date: {transfer_date}")
        return None


def transfer_key(transfer: dict) -> Tuple:
    """
    Build the identity of a move, so the same transfer is only ever counted once.

    A single move surfaces repeatedly: the API records it on consecutive days, and it
    appears again in the response of every club involved.

    :param dict transfer: Single parsed transfer.

    :returns: Tuple
    """
    return (
        transfer["player_id"] or transfer["player_name"],
        transfer["team_out_id"] or transfer["team_out"],
        transfer["team_in_id"] or transfer["team_in"],
    )


def transfer_type_precedence(transfer_type: Optional[str]) -> int:
    """
    Rank how informative a transfer's `type` is, to pick a winner among duplicates.

    Duplicate records of one move often disagree: the same signing is recorded as both
    `-` and `Transfer`, or as both `Transfer` and a fee.

    :param Optional[str] transfer_type: Raw `type` value of a single transfer.

    :returns: int
    """
    if transfer_type is None or transfer_type.strip().lower() in UNDISCLOSED_TRANSFER_TYPES:
        return 0
    if any(char.isdigit() for char in transfer_type):
        return 2
    return 1


def filter_incoming_transfers(transfers: List[dict], league_team_ids: Iterable[int]) -> List[dict]:
    """
    Discard departures, keeping only moves which land a player at a club in the league.

    A move between two clubs of the same league is an arrival for the buying club, so it
    survives; a move from a league club out to a foreign one does not.

    :param List[dict] transfers: Parsed transfers in either direction.
    :param Iterable[int] league_team_ids: IDs of every club in the league.

    :returns: List[dict]
    """
    team_ids = set(league_team_ids)
    return [transfer for transfer in transfers if transfer["team_in_id"] in team_ids]


def deduplicate_transfers(transfers: List[dict]) -> List[dict]:
    """
    Collapse duplicate records of the same move into one, newest first.

    The surviving record carries the latest date the move was recorded on and the most
    informative `type` seen across its duplicates.

    :param List[dict] transfers: Parsed transfers, possibly containing duplicates.

    :returns: List[dict]
    """
    unique_transfers: Dict[Tuple, dict] = {}
    for transfer in transfers:
        key = transfer_key(transfer)
        existing = unique_transfers.get(key)
        if existing is None:
            unique_transfers[key] = dict(transfer)
            continue
        if transfer["date"] > existing["date"]:
            existing["date"] = transfer["date"]
        if transfer_type_precedence(transfer["type"]) > transfer_type_precedence(existing["type"]):
            existing["type"] = transfer["type"]
    return sorted(unique_transfers.values(), key=lambda t: (t["date"], t["player_name"]), reverse=True)


def format_transfer_type(transfer_type: Optional[str]) -> str:
    """
    Normalize a transfer's `type` into something worth reading in chat.

    :param Optional[str] transfer_type: Raw `type` value of a single transfer.

    :returns: str
    """
    if transfer_type is None or transfer_type.strip().lower() in UNDISCLOSED_TRANSFER_TYPES:
        return "Undisclosed"
    transfer_type = transfer_type.strip()
    return TRANSFER_TYPE_ALIASES.get(transfer_type.lower(), transfer_type)


def format_transfer_ledger(transfers: List[dict], league_name: str, incoming_only: bool = False) -> str:
    """
    Render deduplicated transfers as a chat-friendly ledger.

    :param List[dict] transfers: Deduplicated transfers, newest first.
    :param str league_name: Display name of the league.
    :param bool incoming_only: Whether the ledger holds arrivals only, rather than both directions.

    :returns: str
    """
    heading = "TRANSFERS IN" if incoming_only else "TRANSFERS"
    if not transfers:
        return emojize(
            f":warning: No {league_name} {heading.lower()} in the past {TRANSFER_WINDOW_DAYS} days :warning:",
            language="en",
        )
    ledger = f"\n\n\n\n<b>:counterclockwise_arrows_button: {league_name} {heading}</b>"
    ledger += f" <i>(past {TRANSFER_WINDOW_DAYS} days)</i>\n"
    for transfer in transfers[:TRANSFER_LEDGER_LIMIT]:
        team_out = abbreviate_team_name(transfer["team_out"])
        team_in = abbreviate_team_name(transfer["team_in"])
        movement = f"{team_out} → {team_in}"
        ledger += (
            f"<b>{transfer['player_name']}</b>: {movement} "
            f"<i>({format_transfer_type(transfer['type'])}, {transfer['date'].strftime('%b %d')})</i>\n"
        )
    remaining = len(transfers) - TRANSFER_LEDGER_LIMIT
    if remaining > 0:
        ledger += f"<i>...and {remaining} more</i>\n"
    return emojize(ledger, language="en")
