"""Summarize the state of F1: a live grand prix, one just run, the next grand prix, or the offseason."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from emoji import emojize
from logger import LOGGER

from config import F1_GRID_LIMIT, F1_RESULTS_LIMIT, F1_STANDINGS_LIMIT

from .qualifying import fetch_starting_grid, is_qualified
from .races import (
    fetch_circuit,
    fetch_season_races,
    find_live_race,
    find_next_race,
    find_recent_race,
)
from .results import fetch_race_results, is_finisher
from .standings import fetch_driver_standings
from .util import (
    country_code_to_flag,
    driver_flag_from_name,
    format_countdown,
    format_race_date,
    parse_race_date,
)

API_ERROR_MESSAGE = emojize(":warning: idk the F1 API shit the bed, try again later.", language="en")


async def f1_grand_prix_at(now: datetime) -> str:
    """
    Summarize the state of F1 at a given moment: a live race, one just run, the next race, or the offseason.

    A race which finished within the last day reports its results; until they're published (or if
    they can't be fetched), the next race is reported instead.

    :param datetime now: Current UTC time.

    :returns: str
    """
    try:
        races = await fetch_season_races(now.year)
        if races is None:
            return API_ERROR_MESSAGE
        live_race = find_live_race(races, now)
        if live_race:
            return await live_race_message(await _with_circuit(live_race))
        next_race = find_next_race(races, now)
        recent_race = find_recent_race(races, now)
        if recent_race:
            results = await fetch_race_results(recent_race.get("id"), recent_race.get("season"))
            if results:
                return race_results_message(await _with_circuit(recent_race), results, next_race, now)
        if next_race is None:
            return await offseason_message(now.year, now, bool(races))
        return await upcoming_race_message(await _with_circuit(next_race), now)
    except Exception as e:
        LOGGER.exception(f"Unexpected error while building F1 grand prix message: {e}")
        return API_ERROR_MESSAGE


async def f1_grand_prix() -> str:
    """
    Summarize the current state of F1, whether that's a live race, one just run, the next race, or the offseason.

    :returns: str
    """
    return await f1_grand_prix_at(datetime.now(timezone.utc))


async def live_race_message(race: dict) -> str:
    """
    Summarize a grand prix which is currently being run, with the championship & odds to win.

    :param dict race: Normalized race object.

    :returns: str
    """
    message = _race_header(race, ":racing_car:", "LIVE NOW")
    message += _race_details(race)
    return message + await _driver_sections(race)


async def upcoming_race_message(race: dict, now: datetime) -> str:
    """
    Summarize the next grand prix, with the championship standings & odds to win.

    :param dict race: Normalized race object.
    :param datetime now: Current UTC time.

    :returns: str
    """
    message = _race_header(race, ":racing_car:", "NEXT UP")
    message += _race_details(race)
    start_time = parse_race_date(race.get("date"))
    if start_time:
        message += emojize(
            f":calendar: {format_race_date(start_time)} <i>({format_countdown(start_time - now)})</i>\n",
            language="en",
        )
    return message + await _driver_sections(race)


def race_results_message(race: dict, results: List[dict], next_race: Optional[dict], now: datetime) -> str:
    """
    Summarize a grand prix which has just been run, with its finishing order & the race after it.

    :param dict race: Normalized race object.
    :param List[dict] results: Normalized race results, winner first.
    :param Optional[dict] next_race: Normalized race object of the next grand prix, if there is one.
    :param datetime now: Current UTC time.

    :returns: str
    """
    message = _race_header(race, ":chequered_flag:", "RESULTS")
    message += _race_details(race)
    message += _results_section(results)
    start_time = parse_race_date((next_race or {}).get("date"))
    if start_time:
        message += emojize(
            f"\n:calendar: Next up: <b>{_grand_prix_name(next_race)}</b> on {format_race_date(start_time)} "
            f"<i>({format_countdown(start_time - now)})</i>\n",
            language="en",
        )
    return message


async def offseason_message(season: int, now: datetime, season_had_races: bool = True) -> str:
    """
    Report that the F1 season has ended, along with the start of the next season (when known).

    :param int season: Year of the season which has ended.
    :param datetime now: Current UTC time.
    :param bool season_had_races: Whether the season had any races on the schedule to begin with.

    :returns: str
    """
    if season_had_races:
        message = emojize(f":chequered_flag: <b>the {season} F1 season is over</b>, BROH.\n", language="en")
    else:
        message = emojize(f":chequered_flag: <b>no {season} F1 races on the schedule</b>, BROH.\n", language="en")
    next_season_races = await fetch_season_races(season + 1) or []
    next_season_start = _first_race_of_season(next_season_races)
    if next_season_start is None:
        return message + emojize(
            f":hourglass_not_done: the {season + 1} schedule hasn't been announced yet.",
            language="en",
        )
    race, start_time = next_season_start
    message += emojize(
        f":racing_car: <b>{_grand_prix_name(race)}</b> kicks off the {season + 1} season "
        f"on {format_race_date(start_time)} <i>({format_countdown(start_time - now)})</i>.",
        language="en",
    )
    return message


async def _with_circuit(race: dict) -> dict:
    """
    Attach a race's circuit details (name, city & flag) ahead of rendering it.

    :param dict race: Normalized race object.

    :returns: dict
    """
    race["circuit"] = await fetch_circuit(race.get("circuit_id")) or {}
    return race


def _first_race_of_season(races: List[dict]) -> Optional[Tuple[dict, datetime]]:
    """
    Earliest scheduled race of a season, paired with its start time.

    :param List[dict] races: All races in a season.

    :returns: Optional[Tuple[dict, datetime]]
    """
    scheduled_races = [(race, parse_race_date(race.get("date"))) for race in races]
    scheduled_races = [(race, start_time) for race, start_time in scheduled_races if start_time]
    if scheduled_races:
        return min(scheduled_races, key=lambda race: race[1])
    return None


def _race_header(race: dict, icon: str, label: str) -> str:
    """
    Construct the opening line of a grand prix summary.

    :param dict race: Normalized race object.
    :param str icon: Emoji shortcode to lead the message with.
    :param str label: Status of the grand prix, ie: `LIVE NOW`.

    :returns: str
    """
    circuit = race.get("circuit") or {}
    flag = country_code_to_flag(circuit.get("country_code"))
    return emojize(
        f"\n\n\n{icon} <b>{label}: {_grand_prix_name(race).upper()}</b> {flag}\n",
        language="en",
    )


def _race_details(race: dict) -> str:
    """
    Construct circuit, lap count & distance details of a grand prix.

    :param dict race: Normalized race object.

    :returns: str
    """
    details = ""
    circuit = race.get("circuit") or {}
    venue = ", ".join([detail for detail in (circuit.get("name"), circuit.get("city")) if detail])
    if venue:
        details += f"<i>{venue}</i>\n"
    total_laps = (race.get("laps") or {}).get("total")
    distance = race.get("distance")
    race_length = ", ".join(
        [str(detail) for detail in (f"{total_laps} laps" if total_laps else None, distance) if detail]
    )
    if race_length:
        details += f"{race_length}\n"
    if race.get("weather"):
        details += f"{race['weather']}\n"
    return details


async def _driver_sections(race: dict) -> str:
    """
    Construct the driver-facing section of a summary.

    Once qualifying has been run, the starting grid is the more interesting read on a race
    that's about to happen; until then, fall back to the drivers' championship standings.

    :param dict race: Normalized race object.

    :returns: str
    """
    grid = await _grid_section(race)
    if grid:
        return grid
    standings = await _standings_section(race.get("season"))
    if standings:
        return standings
    return emojize(":warning: <i>championship standings unavailable right now.</i>", language="en")


async def _grid_section(race: dict) -> str:
    """
    Construct the starting grid of a grand prix, pole first.

    :param dict race: Normalized race object.

    :returns: str
    """
    grid = await fetch_starting_grid(race.get("id"), race.get("season"))
    if not grid:
        return ""
    section = emojize("\n:stopwatch: <b>STARTING GRID</b>\n", language="en")
    for entry in grid[:F1_GRID_LIMIT]:
        name = entry.get("name") or entry.get("tla") or "Unknown"
        team = f" <i>({entry['team']})</i>" if entry.get("team") else ""
        lap_time = f" — {entry['time']}" if entry.get("time") else ""
        status = "" if is_qualified(entry) or not entry.get("status") else f" <i>({entry['status']})</i>"
        section += (
            f"<b>{entry['position']}.</b> {driver_flag_from_name(entry.get('name'))} "
            f"{name}{team}{lap_time}{status}\n"
        )
    return section


def _results_section(results: List[dict]) -> str:
    """
    Construct the finishing order of a grand prix, winner first.

    :param List[dict] results: Normalized race results, winner first.

    :returns: str
    """
    section = emojize("\n:trophy: <b>FINAL RESULTS</b>\n", language="en")
    for entry in results[:F1_RESULTS_LIMIT]:
        name = entry.get("name") or entry.get("tla") or "Unknown"
        team = f" <i>({entry['team']})</i>" if entry.get("team") else ""
        result = _result_label(entry)
        section += (
            f"<b>{entry['position']}.</b> {driver_flag_from_name(entry.get('name'))} {name}{team}"
            f"{f' — {result}' if result else ''}\n"
        )
    return section


def _result_label(entry: dict) -> str:
    """
    How a driver's race ended: the winner's race time, everyone else's gap to them, or why they didn't finish.

    :param dict entry: Normalized race result entry.

    :returns: str
    """
    if not is_finisher(entry):
        return f"<i>{(entry.get('status') or 'DNF').upper()}</i>"
    if entry.get("position") == 1:
        return entry.get("time") or ""
    laps_behind = entry.get("laps_behind") or 0
    if laps_behind > 0:
        return f"+{laps_behind} lap{'s' if laps_behind > 1 else ''}"
    gap = entry.get("gap")
    return f"+{gap}s" if gap and gap != "0" else ""


async def _standings_section(season: Optional[int]) -> str:
    """
    Construct the drivers' championship standings, leader first.

    :param Optional[int] season: Year of the season being reported on.

    :returns: str
    """
    if season is None:
        return ""
    standings = await fetch_driver_standings(season)
    if not standings:
        return ""
    section = emojize("\n:trophy: <b>DRIVERS' CHAMPIONSHIP</b>\n", language="en")
    for entry in standings[:F1_STANDINGS_LIMIT]:
        name = entry.get("name") or entry.get("tla") or "Unknown"
        team = f" <i>({entry['team']})</i>" if entry.get("team") else ""
        points = entry.get("points")
        points_label = f" — {points:g} pts" if points is not None else ""
        section += (
            f"<b>{entry['position']}.</b> {driver_flag_from_name(entry.get('name'))} {name}{team}{points_label}\n"
        )
    return section


def _grand_prix_name(race: dict) -> str:
    """
    Full name of a grand prix, ie: `Bahrain Grand Prix`.

    :param dict race: Normalized race object.

    :returns: str
    """
    name = race.get("name") or "Formula 1"
    if "grand prix" in name.lower():
        return name
    return f"{name} Grand Prix"
