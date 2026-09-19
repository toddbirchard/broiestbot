"""Fetch sumo bouts (torikumi) for the current basho from sumo-api.com."""

import asyncio
from datetime import date, datetime
from typing import Dict, Optional

import pytz
from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import SUMO_API_BASE_URL, SUMO_DETAILED_BOUT_COUNT, SUMO_DIVISION

from .records import fetch_basho_records, fetch_head_to_heads, fetch_last_basho_records, fetch_rikishi_profiles

# Six honbasho per year, held in odd-numbered months.
SUMO_BASHO_MONTHS = (1, 3, 5, 7, 9, 11)
SUMO_BASHO_NAMES = {
    1: "Hatsu Basho",
    3: "Haru Basho",
    5: "Natsu Basho",
    7: "Nagoya Basho",
    9: "Aki Basho",
    11: "Kyushu Basho",
}
SUMO_BASHO_FINAL_DAY = 15


async def fetch_basho(basho_id: str) -> Optional[dict]:
    """
    Fetch metadata (start/end dates) for a basho.

    :param str basho_id: Basho identifier in `YYYYMM` format.

    :returns: Optional[dict]
    """
    try:
        session = await get_http_session()
        async with session.get(f"{SUMO_API_BASE_URL}/basho/{basho_id}") as resp:
            if resp.status == 200:
                basho = await resp.json(content_type=None)
                # Unknown basho IDs still return 200 with an empty `date` field.
                if basho.get("date"):
                    return basho
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching sumo basho `{basho_id}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo basho `{basho_id}`: {e}")


async def fetch_torikumi(basho_id: str, day: int) -> Optional[dict]:
    """
    Fetch top-division bout schedule/results for a given day of a basho.

    :param str basho_id: Basho identifier in `YYYYMM` format.
    :param int day: Day of the basho (1-15).

    :returns: Optional[dict]
    """
    try:
        endpoint = f"{SUMO_API_BASE_URL}/basho/{basho_id}/torikumi/{SUMO_DIVISION}/{day}"
        session = await get_http_session()
        async with session.get(endpoint) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching sumo torikumi for `{basho_id}` day {day}: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo torikumi for `{basho_id}` day {day}: {e}")


async def get_current_or_next_basho(today: date) -> Optional[dict]:
    """
    Find the basho currently underway, or the next upcoming one.

    :param date today: Current date in Japan.

    :returns: Optional[dict]
    """
    year, month = today.year, today.month
    if month not in SUMO_BASHO_MONTHS:
        month += 1
    for _ in range(3):
        basho = await fetch_basho(f"{year}{month:02d}")
        if basho and _parse_basho_date(basho["endDate"]) >= today:
            return basho
        month += 2
        if month > 12:
            year, month = year + 1, 1


def _parse_basho_date(timestamp: str) -> date:
    """
    Parse a basho `startDate`/`endDate` timestamp into a date.

    :param str timestamp: ISO-8601 UTC timestamp, e.g. `2026-07-12T00:00:00Z`.

    :returns: date
    """
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").date()


def _format_record(rikishi_id: Optional[int], records: Dict[int, dict]) -> str:
    """
    Format a rikishi's running basho record (`5-1`, or `5-1-2` with absences).

    Empty when the rikishi isn't on the top-division banzuke (a Juryo visitor) or has
    nothing on the board yet, so day 1 doesn't read as a wall of `0-0`.

    :param Optional[int] rikishi_id: Rikishi ID from the torikumi.
    :param Dict[int, dict] records: Basho records keyed by rikishi ID.

    :returns: str
    """
    record = records.get(rikishi_id) if rikishi_id else None
    if not record:
        return ""
    wins, losses, absences = record.get("wins", 0), record.get("losses", 0), record.get("absences", 0)
    if not (wins or losses or absences):
        return ""
    return f"{wins}-{losses}-{absences}" if absences else f"{wins}-{losses}"


def _format_head_to_head(bout: dict, head_to_heads: Dict[str, dict]) -> str:
    """
    Format the career series between a bout's rikishi (`Onosato leads 14-3`, `tied 2-2`, `first meeting`).

    :param dict bout: Torikumi entry from the API.
    :param Dict[str, dict] head_to_heads: Head-to-head summaries keyed by bout ID.

    :returns: str
    """
    series = head_to_heads.get(bout.get("id"))
    if series is None:
        return ""
    east_wins, west_wins = series.get("rikishiWins", 0), series.get("opponentWins", 0)
    if not series.get("total"):
        return "first meeting"
    if east_wins == west_wins:
        return f"tied {east_wins}-{west_wins}"
    if east_wins > west_wins:
        return f"{bout['eastShikona']} leads {east_wins}-{west_wins}"
    return f"{bout['westShikona']} leads {west_wins}-{east_wins}"


def _format_bout(
    bout: dict,
    records: Optional[Dict[int, dict]] = None,
    head_to_heads: Optional[Dict[str, dict]] = None,
    include_head_to_head: bool = True,
) -> str:
    """
    Build a single-line summary of a bout, including the result if it has been fought.

    Basho records are appended when available, and silently omitted otherwise. The head-to-head
    series is appended the same way unless `include_head_to_head` is False, for callers that put
    it on its own line instead (the marquee bout detail block).

    :param dict bout: Torikumi entry from the API.
    :param Optional[Dict[int, dict]] records: Basho records keyed by rikishi ID.
    :param Optional[Dict[str, dict]] head_to_heads: Head-to-head summaries keyed by bout ID.
    :param bool include_head_to_head: Whether to append the head-to-head series inline.

    :returns: str
    """
    records = records or {}
    east_record = _format_record(bout.get("eastId"), records)
    west_record = _format_record(bout.get("westId"), records)
    series = _format_head_to_head(bout, head_to_heads or {}) if include_head_to_head else ""
    suffix = f" <i>{series}</i>" if series else ""
    winner = bout.get("winnerEn")
    if winner:
        east_wins = winner == bout["eastShikona"]
        loser = bout["westShikona"] if east_wins else bout["eastShikona"]
        winner_record, loser_record = (east_record, west_record) if east_wins else (west_record, east_record)
        winner = f"{winner} ({winner_record})" if winner_record else winner
        loser = f"{loser} ({loser_record})" if loser_record else loser
        return f"{winner} def. {loser} <i>({bout.get('kimarite', 'unknown')})</i>{suffix}"
    east = f"<b>{bout['eastShikona']}</b> ({east_record})" if east_record else f"<b>{bout['eastShikona']}</b>"
    west = f"<b>{bout['westShikona']}</b> ({west_record})" if west_record else f"<b>{bout['westShikona']}</b>"
    return f"{east} vs {west}{suffix}"


def _format_stat_comparison(emoji_code: str, east_value: str, west_value: str, east_key: float, west_key: float) -> str:
    """
    Format one east-vs-west stat comparison line (`:straight_ruler: <b>190cm</b> vs 176cm`),
    bolding whichever side's `east_key`/`west_key` is higher. A tie is left unbolded.

    Omitted when either side's display value is missing, since a one-sided comparison isn't
    useful.

    :param str emoji_code: `emoji` package shortcode identifying the stat at a glance.
    :param str east_value: East rikishi's formatted display value, or empty if unavailable.
    :param str west_value: West rikishi's formatted display value, or empty if unavailable.
    :param float east_key: East rikishi's raw value to compare on (unused if `east_value` is empty).
    :param float west_key: West rikishi's raw value to compare on (unused if `west_value` is empty).

    :returns: str
    """
    if not east_value or not west_value:
        return ""
    east_display = f"<b>{east_value}</b>" if east_key > west_key else east_value
    west_display = f"<b>{west_value}</b>" if west_key > east_key else west_value
    return emojize(f"{emoji_code} {east_display} vs {west_display}", language="en")


def _format_head_to_head_line(bout: dict, head_to_heads: Dict[str, dict]) -> str:
    """
    Format a bout's career head-to-head series as its own line
    (`:people_wrestling: Onosato leads 14-3`).

    :param dict bout: Torikumi entry from the API.
    :param Dict[str, dict] head_to_heads: Head-to-head summaries keyed by bout ID.

    :returns: str
    """
    series = _format_head_to_head(bout, head_to_heads)
    if not series:
        return ""
    return emojize(f":people_wrestling: {series}", language="en")


def _format_last_meeting(last_meeting: Optional[dict]) -> str:
    """
    Format a head-to-head's most recent meeting
    (`:crossed_swords: Last met: Onosato (Natsu Basho 2026)`).

    :param Optional[dict] last_meeting: `lastMeeting` entry from a head-to-head summary.

    :returns: str
    """
    if not last_meeting:
        return ""
    basho_id = last_meeting.get("bashoId", "")
    year, month = basho_id[:4], int(basho_id[4:6]) if len(basho_id) == 6 else None
    basho_name = SUMO_BASHO_NAMES.get(month, "Basho")
    winner = last_meeting.get("winnerEn") or "unknown"
    return emojize(f":crossed_swords: Last met: {winner} ({basho_name} {year})", language="en")


def _format_bout_detail(
    bout: dict, profiles: Dict[int, dict], last_basho: Dict[int, dict], head_to_heads: Dict[str, dict]
) -> str:
    """
    Build the expanded detail block for a marquee bout: the head-to-head series, an east-vs-west
    comparison of height, weight and last basho's record, plus when the pair last met. A line
    missing data is omitted; an empty string means there was nothing to add at all.

    :param dict bout: Torikumi entry from the API.
    :param Dict[int, dict] profiles: Height/weight profiles keyed by rikishi ID.
    :param Dict[int, dict] last_basho: Previous basho's records keyed by rikishi ID.
    :param Dict[str, dict] head_to_heads: Head-to-head summaries keyed by bout ID.

    :returns: str
    """
    east_id, west_id = bout.get("eastId"), bout.get("westId")
    east_profile, west_profile = profiles.get(east_id) or {}, profiles.get(west_id) or {}
    east_last_basho, west_last_basho = last_basho.get(east_id) or {}, last_basho.get(west_id) or {}
    lines = [
        _format_head_to_head_line(bout, head_to_heads),
        _format_stat_comparison(
            ":straight_ruler:",
            f"{east_profile['height']}cm" if east_profile.get("height") else "",
            f"{west_profile['height']}cm" if west_profile.get("height") else "",
            east_profile.get("height", 0),
            west_profile.get("height", 0),
        ),
        _format_stat_comparison(
            ":balance_scale:",
            f"{east_profile['weight']}kg" if east_profile.get("weight") else "",
            f"{west_profile['weight']}kg" if west_profile.get("weight") else "",
            east_profile.get("weight", 0),
            west_profile.get("weight", 0),
        ),
        _format_stat_comparison(
            ":bar_chart:",
            _format_record(east_id, last_basho),
            _format_record(west_id, last_basho),
            # "Higher" for a win-loss record means more wins.
            east_last_basho.get("wins", 0),
            west_last_basho.get("wins", 0),
        ),
        _format_last_meeting((head_to_heads.get(bout.get("id")) or {}).get("lastMeeting")),
    ]
    return "\n".join(line for line in lines if line)


async def sumo_matches_for_date(today: date) -> str:
    """
    Build chat message of the day's marquee top-division sumo bouts.

    Only the top `SUMO_DETAILED_BOUT_COUNT` bouts still to be fought are shown, each with its
    expanded profile detail. Fought bouts and bouts past that cutoff are dropped — `!sumo` is
    where the full remaining card lives.

    :param date today: Current date in Japan.

    :returns: str
    """
    try:
        basho = await get_current_or_next_basho(today)
        if basho is None:
            return emojize(":crying_face: no sumo basho on the schedule... check back later BROH", language="en")
        basho_start = _parse_basho_date(basho["startDate"])
        basho_name = SUMO_BASHO_NAMES.get(basho_start.month, "Basho")
        if today < basho_start:
            return emojize(
                f":Japan: :hourglass_not_done: <b>{basho_name}</b> begins {basho_start.strftime('%A, %B %-d')}.",
                language="en",
            )
        day = min((today - basho_start).days + 1, SUMO_BASHO_FINAL_DAY)
        torikumi = await fetch_torikumi(basho["date"], day)
        bouts = torikumi.get("torikumi") if torikumi else None
        if not bouts:
            return emojize(
                f":crying_face: no {SUMO_DIVISION} bouts announced yet for <b>{basho_name}</b> day {day}.",
                language="en",
            )
        # Torikumi are listed lowest-ranked first; reverse so marquee bouts lead, then keep only
        # the top `SUMO_DETAILED_BOUT_COUNT` still to be fought — everything else (fought, or
        # further down the card) is `!sumo`'s job to show.
        remaining_bouts = [bout for bout in reversed(bouts) if not bout.get("winnerEn")]
        candidate_bouts = remaining_bouts[:SUMO_DETAILED_BOUT_COUNT]
        if not candidate_bouts:
            return emojize(
                f":crying_face: no {SUMO_DIVISION} bouts left to fight today — check !sumo for what's next.",
                language="en",
            )
        rikishi_ids = [
            rikishi_id
            for bout in candidate_bouts
            for rikishi_id in (bout.get("eastId"), bout.get("westId"))
            if rikishi_id
        ]
        records, head_to_heads, profiles, last_basho = await asyncio.gather(
            fetch_basho_records(basho["date"]),
            fetch_head_to_heads(candidate_bouts),
            fetch_rikishi_profiles(rikishi_ids),
            fetch_last_basho_records(basho["date"]),
        )
        blocks = []
        for bout in candidate_bouts:
            line = _format_bout(bout, records, head_to_heads, include_head_to_head=False)
            detail = _format_bout_detail(bout, profiles, last_basho, head_to_heads)
            blocks.append(f"{line}\n{detail}" if detail else line)
        response = "\n\n\n"
        response += emojize(f":Japan: <b>{basho_name.upper()} — DAY {day}</b>\n", language="en")
        response += "\n\n".join(blocks)
        return response + "\n"
    except Exception as e:
        LOGGER.exception(f"Unexpected error when building sumo matches message: {e}")
        return emojize(":warning: idk the sumo API shit the bed, try again later.", language="en")


async def today_sumo_matches() -> str:
    """
    Fetch today's top-division sumo bouts for the current (or next) basho.

    :returns: str
    """
    return await sumo_matches_for_date(datetime.now(pytz.timezone("Asia/Tokyo")).date())
