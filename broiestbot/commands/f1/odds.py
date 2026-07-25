"""Fetch bookmaker odds of drivers winning a grand prix."""

from typing import List, Optional, Tuple

import requests
from logger import LOGGER
from requests.exceptions import HTTPError

from config import (
    F1_ODDS_HTTP_HEADERS,
    F1_ODDS_SPECIAL_MARKETS_ENDPOINT,
    F1_ODDS_SPORTS_ENDPOINT,
    HTTP_REQUEST_TIMEOUT,
)

from .util import normalize_name, parse_race_date

# Cached sport ID of F1, which is resolved by name to avoid hardcoding a bookmaker's internal ID.
_F1_SPORT_ID: Optional[int] = None


def fetch_f1_sport_id() -> Optional[int]:
    """
    Look up (and cache) the bookmaker's ID for Formula 1.

    :returns: Optional[int]
    """
    global _F1_SPORT_ID
    if _F1_SPORT_ID is not None:
        return _F1_SPORT_ID
    sports = _fetch_odds_data(F1_ODDS_SPORTS_ENDPOINT, {}, "sports")
    if not sports:
        return None
    for sport in sports:
        if "formula" in (sport.get("name") or "").lower() and sport.get("id"):
            _F1_SPORT_ID = int(sport["id"])
            return _F1_SPORT_ID
    LOGGER.warning("No Formula 1 sport found in odds API's list of sports.")
    return None


def fetch_race_winner_odds(race: dict) -> Optional[List[Tuple[str, float]]]:
    """
    Fetch each driver's odds of winning a given grand prix, sorted by favorite.

    :param dict race: Race object returned by the F1 API.

    :returns: Optional[List[Tuple[str, float]]]
    """
    try:
        sport_id = fetch_f1_sport_id()
        if sport_id is None:
            return None
        for event_type in ("prematch", "live"):
            specials = _fetch_odds_data(
                F1_ODDS_SPECIAL_MARKETS_ENDPOINT,
                {"sport_id": sport_id, "event_type": event_type, "is_have_odds": "true"},
                "specials",
            )
            if not specials:
                continue
            market = _match_race_winner_market(specials, race)
            if market:
                odds = _parse_odds_from_market(market)
                if odds:
                    return odds
        LOGGER.warning(f"No race-winner odds found for F1 race `{race.get('id')}`.")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching F1 race winner odds: {e}")
    return None


def _fetch_odds_data(endpoint: str, params: dict, response_key: str) -> Optional[List[dict]]:
    """
    Fetch & unwrap a response from the odds API.

    :param str endpoint: Odds API endpoint to be fetched.
    :param dict params: Query parameters to be passed to the endpoint.
    :param str response_key: Key which the endpoint nests its results under.

    :returns: Optional[List[dict]]
    """
    try:
        resp = requests.get(
            endpoint,
            headers=F1_ODDS_HTTP_HEADERS,
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            LOGGER.warning(f"Non-200 response from odds API `{endpoint}`: {resp.status_code} {resp.text[:300]}")
            return None
        data = resp.json()
        if isinstance(data, dict):
            data = data.get(response_key)
        if isinstance(data, list):
            return data
        LOGGER.warning(f"Unexpected response shape from odds API `{endpoint}`: {str(data)[:300]}")
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while fetching odds from `{endpoint}`: {getattr(e.response, 'content', e)}")
    except ValueError as e:
        LOGGER.exception(f"Malformed JSON returned by odds API `{endpoint}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching odds from `{endpoint}`: {e}")
    return None


def _match_race_winner_market(specials: List[dict], race: dict) -> Optional[dict]:
    """
    Find the race-winner market which belongs to a given grand prix.

    Markets are matched on the grand prix' name/location, falling back to whichever
    winner market starts closest to the race itself.

    :param List[dict] specials: Special (outright) markets offered for F1.
    :param dict race: Race object returned by the F1 API.

    :returns: Optional[dict]
    """
    race_start = parse_race_date(race.get("date"))
    candidates = []
    for special in specials:
        if not _parse_odds_from_market(special):
            continue
        description = normalize_name(
            " ".join(
                [
                    str(special.get("category") or ""),
                    str(special.get("name") or ""),
                    str(special.get("league_name") or ""),
                ]
            )
        )
        if "winner" not in description:
            continue
        market_start = parse_race_date(special.get("starts") or special.get("cutoff"))
        matches_race = any(term and term in description for term in _race_search_terms(race))
        if race_start and market_start:
            proximity = abs((market_start - race_start).total_seconds())
        else:
            proximity = float("inf")
        candidates.append((not matches_race, proximity, special))
    if candidates:
        return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
    return None


def _race_search_terms(race: dict) -> List[str]:
    """
    Terms which identify a grand prix in a bookmaker's market name.

    :param dict race: Race object returned by the F1 API.

    :returns: List[str]
    """
    competition = race.get("competition") or {}
    location = competition.get("location") or {}
    circuit = race.get("circuit") or {}
    return [
        normalize_name(competition.get("name")),
        normalize_name(location.get("city")),
        normalize_name(location.get("country")),
        normalize_name(circuit.get("name")),
    ]


def _parse_odds_from_market(market: dict) -> List[Tuple[str, float]]:
    """
    Parse driver names & prices out of a bookmaker's market, sorted by favorite.

    :param dict market: Special (outright) market offered for F1.

    :returns: List[Tuple[str, float]]
    """
    lines = market.get("lines") or market.get("participants") or []
    if isinstance(lines, dict):
        lines = list(lines.values())
    odds = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        name = line.get("name") or line.get("participant") or line.get("driver")
        price = line.get("price", line.get("odds", line.get("moneyline")))
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if name and price:
            odds.append((str(name), price))
    # Ascending price is favorite-first for both decimal (1.72 < 26.0) and American (-140 < +2500) prices.
    return sorted(odds, key=lambda driver: driver[1])
