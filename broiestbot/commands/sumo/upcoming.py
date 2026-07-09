"""Fetch all announced-but-unfought sumo bouts for the current basho."""

from datetime import date, datetime, timedelta

import pytz
from emoji import emojize
from logger import LOGGER

from config import SUMO_DIVISION

from .matches import (
    SUMO_BASHO_FINAL_DAY,
    SUMO_BASHO_NAMES,
    _format_bout,
    _parse_basho_date,
    fetch_torikumi,
    get_current_or_next_basho,
)


def _is_listable(bout: dict) -> bool:
    """
    Whether a bout is upcoming (no winner yet) and both rikishi have been announced.

    :param dict bout: Torikumi entry from the API.

    :returns: bool
    """
    return bool(bout.get("eastShikona") and bout.get("westShikona") and not bout.get("winnerEn"))


def upcoming_sumo_matches_for_date(today: date) -> str:
    """
    Build chat message of all known upcoming top-division bouts, grouped by basho day.

    Torikumi are only published a day or two in advance, so days are walked
    forward from today until the first day with no announced bouts.

    :param date today: Current date in Japan.

    :returns: str
    """
    try:
        basho = get_current_or_next_basho(today)
        if basho is None:
            return emojize(":crying_face: no sumo basho on the schedule... check back later BROH", language="en")
        basho_start = _parse_basho_date(basho["startDate"])
        basho_name = SUMO_BASHO_NAMES.get(basho_start.month, "Basho")
        first_day = max((today - basho_start).days + 1, 1)
        bouts_by_day = ""
        for day in range(first_day, SUMO_BASHO_FINAL_DAY + 1):
            torikumi = fetch_torikumi(basho["date"], day)
            bouts = torikumi.get("torikumi") if torikumi else None
            if not bouts:
                break
            upcoming_bouts = [bout for bout in bouts if _is_listable(bout)]
            if upcoming_bouts:
                bout_date = basho_start + timedelta(days=day - 1)
                bouts_by_day += emojize(
                    f"\n:calendar: <b>Day {day}</b> ({bout_date.strftime('%a %-m/%-d')})\n", language="en"
                )
                # Torikumi are listed lowest-ranked first; reverse so marquee bouts lead.
                for bout in reversed(upcoming_bouts):
                    bouts_by_day += f"{_format_bout(bout)}\n"
        if not bouts_by_day:
            if today < basho_start:
                return emojize(
                    f":Japan: :hourglass_not_done: no {SUMO_DIVISION} bouts announced yet — "
                    f"<b>{basho_name}</b> begins {basho_start.strftime('%A, %B %-d')}.",
                    language="en",
                )
            return emojize(
                f":Japan: all announced <b>{basho_name}</b> bouts have been fought — "
                "tomorrow's torikumi isn't out yet.",
                language="en",
            )
        response = "\n\n\n"
        response += emojize(f":Japan: <b>{basho_name.upper()} — UPCOMING BOUTS</b>\n", language="en")
        return response + bouts_by_day
    except Exception as e:
        LOGGER.exception(f"Unexpected error when building upcoming sumo bouts message: {e}")
        return emojize(":warning: idk the sumo API shit the bed, try again later.", language="en")


def upcoming_sumo_matches() -> str:
    """
    Fetch all announced upcoming top-division bouts for the current (or next) basho.

    :returns: str
    """
    return upcoming_sumo_matches_for_date(datetime.now(pytz.timezone("Asia/Tokyo")).date())
