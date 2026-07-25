"""Summarize the state of F1: a live grand prix, the next grand prix, or the offseason."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from emoji import emojize
from logger import LOGGER

from config import F1_ODDS_DRIVER_LIMIT, F1_QUALIFYING_LOOKAHEAD_HOURS

from .odds import fetch_race_winner_odds
from .races import (
    current_lap,
    fetch_race_rankings,
    fetch_season_races,
    fetch_starting_grid,
    find_live_race,
    find_next_race,
)
from .util import (
    country_flag,
    driver_flag,
    driver_flag_from_name,
    format_countdown,
    format_odds,
    format_race_date,
    parse_race_date,
)

API_ERROR_MESSAGE = emojize(":warning: idk the F1 API shit the bed, try again later.", language="en")


def f1_grand_prix_at(now: datetime) -> str:
    """
    Summarize the state of F1 at a given moment: a live race, the next race, or the offseason.

    :param datetime now: Current UTC time.

    :returns: str
    """
    try:
        races = fetch_season_races(now.year)
        if races is None:
            return API_ERROR_MESSAGE
        live_race = find_live_race(races, now)
        if live_race:
            return live_race_message(live_race)
        next_race = find_next_race(races, now)
        if next_race is None:
            return offseason_message(now.year, now, bool(races))
        return upcoming_race_message(next_race, now)
    except Exception as e:
        LOGGER.exception(f"Unexpected error while building F1 grand prix message: {e}")
        return API_ERROR_MESSAGE


def f1_grand_prix() -> str:
    """
    Summarize the current state of F1, whether that's a live race, the next race, or the offseason.

    :returns: str
    """
    return f1_grand_prix_at(datetime.now(timezone.utc))


def live_race_message(race: dict) -> str:
    """
    Summarize a grand prix which is currently being run, including live driver positions.

    :param dict race: Race object returned by the F1 API.

    :returns: str
    """
    message = _race_header(race, ":racing_car:", "LIVE NOW")
    message += _race_details(race)
    lap = current_lap(race)
    if lap:
        message += emojize(f":stopwatch: <b>Lap {lap}</b>\n", language="en")
    positions = _sort_by_position(fetch_race_rankings(race.get("id")) or [])
    if positions:
        message += "\n"
        for entry in positions:
            message += _ranking_line(entry)
        return message
    # Positions aren't published until a race is properly underway; odds fill the gap until then.
    return message + _odds_section(race)


def upcoming_race_message(race: dict, now: datetime) -> str:
    """
    Summarize the next grand prix, listing the starting grid if qualifying is done, else odds.

    :param dict race: Race object returned by the F1 API.
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
    if start_time and start_time - now <= timedelta(hours=F1_QUALIFYING_LOOKAHEAD_HOURS):
        grid = _sort_by_position(fetch_starting_grid(race.get("id")) or [])
        if grid:
            message += emojize("\n:chequered_flag: <b>STARTING GRID</b>\n", language="en")
            for entry in grid:
                message += _grid_line(entry)
            return message
    return message + _odds_section(race)


def offseason_message(season: int, now: datetime, season_had_races: bool = True) -> str:
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
    next_season_races = fetch_season_races(season + 1) or []
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

    :param dict race: Race object returned by the F1 API.
    :param str icon: Emoji shortcode to lead the message with.
    :param str label: Status of the grand prix, ie: `LIVE NOW`.

    :returns: str
    """
    location = (race.get("competition") or {}).get("location") or {}
    flag = country_flag(location.get("country"))
    return emojize(
        f"\n\n\n{icon} <b>{label}: {_grand_prix_name(race).upper()}</b> {flag}\n",
        language="en",
    )


def _race_details(race: dict) -> str:
    """
    Construct circuit, lap count & weather details of a grand prix.

    :param dict race: Race object returned by the F1 API.

    :returns: str
    """
    details = ""
    circuit_name = (race.get("circuit") or {}).get("name")
    location = (race.get("competition") or {}).get("location") or {}
    venue = ", ".join([detail for detail in (circuit_name, location.get("city")) if detail])
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


def _odds_section(race: dict) -> str:
    """
    Construct a list of drivers by their odds of winning a grand prix.

    :param dict race: Race object returned by the F1 API.

    :returns: str
    """
    odds = fetch_race_winner_odds(race)
    if not odds:
        return emojize(":warning: <i>no odds available for this one.</i>", language="en")
    section = emojize("\n:money_bag: <b>ODDS TO WIN</b>\n", language="en")
    for driver_name, price in odds[:F1_ODDS_DRIVER_LIMIT]:
        section += f"{driver_flag_from_name(driver_name)} {driver_name}: <b>{format_odds(price)}</b>\n"
    return section


def _ranking_line(entry: dict) -> str:
    """
    Construct a single driver's line in a live race's running order.

    :param dict entry: Driver ranking returned by the F1 API.

    :returns: str
    """
    driver = entry.get("driver") or {}
    team = (entry.get("team") or {}).get("name")
    gap = entry.get("gap") or entry.get("time") or ""
    line = f"<b>{entry['position']}.</b> {driver_flag(driver)} {driver.get('name', 'Unknown')}"
    if team:
        line += f" <i>({team})</i>"
    if gap:
        line += f" {gap}"
    return line + "\n"


def _grid_line(entry: dict) -> str:
    """
    Construct a single driver's line in a starting grid.

    :param dict entry: Starting grid position returned by the F1 API.

    :returns: str
    """
    driver = entry.get("driver") or {}
    team = (entry.get("team") or {}).get("name")
    lap_time = entry.get("time") or ""
    line = f"<b>P{entry['position']}</b> {driver_flag(driver)} {driver.get('name', 'Unknown')}"
    if team:
        line += f" <i>({team})</i>"
    if lap_time:
        line += f" {lap_time}"
    return line + "\n"


def _sort_by_position(entries: List[dict]) -> List[dict]:
    """
    Sort driver rankings or grid slots by position, dropping any which lack one.

    :param List[dict] entries: Driver rankings or starting grid positions.

    :returns: List[dict]
    """
    positioned_entries = []
    for entry in entries:
        try:
            entry["position"] = int(entry["position"])
        except (KeyError, TypeError, ValueError):
            continue
        positioned_entries.append(entry)
    return sorted(positioned_entries, key=lambda entry: entry["position"])


def _grand_prix_name(race: dict) -> str:
    """
    Full name of a grand prix, ie: `Bahrain Grand Prix`.

    :param dict race: Race object returned by the F1 API.

    :returns: str
    """
    competition_name = (race.get("competition") or {}).get("name") or "Formula 1"
    if "grand prix" in competition_name.lower():
        return competition_name
    return f"{competition_name} Grand Prix"
