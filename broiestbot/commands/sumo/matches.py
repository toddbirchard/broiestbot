"""Fetch sumo bouts (torikumi) for the current basho from sumo-api.com."""

from datetime import date, datetime
from typing import Optional

import pytz
import requests
from emoji import emojize
from logger import LOGGER
from requests.exceptions import HTTPError

from .util import format_rank
from config import HTTP_REQUEST_TIMEOUT, SUMO_API_BASE_URL, SUMO_DIVISION

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


def fetch_basho(basho_id: str) -> Optional[dict]:
    """
    Fetch metadata (start/end dates) for a basho.

    :param str basho_id: Basho identifier in `YYYYMM` format.

    :returns: Optional[dict]
    """
    try:
        resp = requests.get(f"{SUMO_API_BASE_URL}/basho/{basho_id}", timeout=HTTP_REQUEST_TIMEOUT)
        if resp.status_code == 200:
            basho = resp.json()
            # Unknown basho IDs still return 200 with an empty `date` field.
            if basho.get("date"):
                return basho
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching sumo basho `{basho_id}`: {e.response.content}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo basho `{basho_id}`: {e}")


def fetch_torikumi(basho_id: str, day: int) -> Optional[dict]:
    """
    Fetch top-division bout schedule/results for a given day of a basho.

    :param str basho_id: Basho identifier in `YYYYMM` format.
    :param int day: Day of the basho (1-15).

    :returns: Optional[dict]
    """
    try:
        endpoint = f"{SUMO_API_BASE_URL}/basho/{basho_id}/torikumi/{SUMO_DIVISION}/{day}"
        resp = requests.get(endpoint, timeout=HTTP_REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching sumo torikumi for `{basho_id}` day {day}: {e.response.content}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo torikumi for `{basho_id}` day {day}: {e}")


def get_current_or_next_basho(today: date) -> Optional[dict]:
    """
    Find the basho currently underway, or the next upcoming one.

    :param date today: Current date in Japan.

    :returns: Optional[dict]
    """
    year, month = today.year, today.month
    if month not in SUMO_BASHO_MONTHS:
        month += 1
    for _ in range(3):
        basho = fetch_basho(f"{year}{month:02d}")
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


def _format_bout(bout: dict) -> str:
    """
    Build a single-line summary of a bout, including the result if it has been fought.

    :param dict bout: Torikumi entry from the API.

    :returns: str
    """
    east = f"<b>{bout['eastShikona']}</b> ({format_rank(bout['eastRank'])})"
    west = f"<b>{bout['westShikona']}</b> ({format_rank(bout['westRank'])})"
    winner = bout.get("winnerEn")
    if winner:
        loser = bout["westShikona"] if winner == bout["eastShikona"] else bout["eastShikona"]
        return f"{winner} def. {loser} <i>({bout.get('kimarite', 'unknown')})</i>"
    return f"{east} vs {west}"


def sumo_matches_for_date(today: date) -> str:
    """
    Build chat message of top-division sumo bouts for a given date.

    :param date today: Current date in Japan.

    :returns: str
    """
    try:
        basho = get_current_or_next_basho(today)
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
        torikumi = fetch_torikumi(basho["date"], day)
        bouts = torikumi.get("torikumi") if torikumi else None
        if not bouts:
            return emojize(
                f":crying_face: no {SUMO_DIVISION} bouts announced yet for <b>{basho_name}</b> day {day}.",
                language="en",
            )
        response = "\n\n\n"
        response += emojize(f":Japan: <b>{basho_name.upper()} — DAY {day}</b>\n", language="en")
        # Torikumi are listed lowest-ranked first; reverse so marquee bouts lead.
        for bout in reversed(bouts):
            response += f"{_format_bout(bout)}\n"
        return response
    except Exception as e:
        LOGGER.exception(f"Unexpected error when building sumo matches message: {e}")
        return emojize(":warning: idk the sumo API shit the bed, try again later.", language="en")


def today_sumo_matches() -> str:
    """
    Fetch today's top-division sumo bouts for the current (or next) basho.

    :returns: str
    """
    return sumo_matches_for_date(datetime.now(pytz.timezone("Asia/Tokyo")).date())
