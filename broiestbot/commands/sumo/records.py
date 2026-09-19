"""Fetch per-rikishi basho records, profiles, and head-to-head histories from sumo-api.com."""

import asyncio
import time
from typing import Dict, List, Optional, Tuple

from aiohttp import ClientError
from http_client import get_http_session
from logger import LOGGER

from config import (
    SUMO_API_BASE_URL,
    SUMO_DIVISION,
    SUMO_HEAD_TO_HEAD_CACHE_TTL,
    SUMO_JURYO_DIVISION,
    SUMO_MAX_CONCURRENT_REQUESTS,
    SUMO_RIKISHI_PROFILE_CACHE_TTL,
)

# Head-to-head summaries keyed on `(bout id, fought)` -> `(expires_at, summary)`. A bout's series
# record changes exactly once (when it is fought), so the pre-fight and post-fight lookups are
# cached separately rather than letting an early `!sumo` serve a stale record to `!todaysumo`.
_HEAD_TO_HEAD_CACHE: Dict[Tuple[str, bool], Tuple[float, dict]] = {}

# Rikishi profiles (height/weight) keyed by rikishi ID -> `(expires_at, profile)`. These change
# at most once a basho, so a day-long TTL is plenty fresh.
_RIKISHI_PROFILE_CACHE: Dict[int, Tuple[float, dict]] = {}

# Every previous basho's final records, keyed by that basho's ID -> `{rikishiID: record}`. Once a
# basho is over its results never change, so this is cached for the life of the process rather
# than on a TTL; only a successful (non-empty) fetch is cached, so a request failure doesn't
# poison it permanently.
_LAST_BASHO_RECORDS_CACHE: Dict[str, Dict[int, dict]] = {}


async def _fetch_division_banzuke_records(basho_id: str, division: str) -> Dict[int, dict]:
    """
    Fetch every rikishi's record for one division of a basho, keyed by rikishi ID.

    :param str basho_id: Basho identifier in `YYYYMM` format.
    :param str division: Division name, e.g. `Makuuchi` or `Juryo`.

    :returns: Dict[int, dict]
    """
    try:
        endpoint = f"{SUMO_API_BASE_URL}/basho/{basho_id}/banzuke/{division}"
        session = await get_http_session()
        async with session.get(endpoint) as resp:
            if resp.status == 200:
                banzuke = await resp.json(content_type=None)
                return {
                    rikishi["rikishiID"]: {
                        "wins": rikishi.get("wins", 0),
                        "losses": rikishi.get("losses", 0),
                        "absences": rikishi.get("absences", 0),
                    }
                    for side in ("east", "west")
                    for rikishi in banzuke.get(side) or []
                    if rikishi.get("rikishiID")
                }
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching sumo banzuke for `{basho_id}` ({division}): {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo banzuke for `{basho_id}` ({division}): {e}")
    return {}


async def fetch_basho_records(basho_id: str) -> Dict[int, dict]:
    """
    Fetch every top-division rikishi's running record for a basho, keyed by rikishi ID.

    :param str basho_id: Basho identifier in `YYYYMM` format.

    :returns: Dict[int, dict]
    """
    return await _fetch_division_banzuke_records(basho_id, SUMO_DIVISION)


def _previous_basho_id(basho_id: str) -> str:
    """
    Compute the basho immediately preceding a given one.

    Honbasho are held every other month, so the previous one is always two months back,
    wrapping from January to November of the prior year.

    :param str basho_id: Basho identifier in `YYYYMM` format.

    :returns: str
    """
    year, month = int(basho_id[:4]), int(basho_id[4:6])
    month -= 2
    if month < 1:
        month += 12
        year -= 1
    return f"{year}{month:02d}"


async def fetch_last_basho_records(basho_id: str) -> Dict[int, dict]:
    """
    Fetch every rikishi's final record from the basho preceding this one, keyed by rikishi ID.

    Checks both Makuuchi and Juryo so a recently promoted (or demoted) rikishi is still found.

    :param str basho_id: Basho identifier (`YYYYMM`) of the *current* basho.

    :returns: Dict[int, dict]
    """
    previous_id = _previous_basho_id(basho_id)
    cached = _LAST_BASHO_RECORDS_CACHE.get(previous_id)
    if cached is not None:
        return cached
    makuuchi, juryo = await asyncio.gather(
        _fetch_division_banzuke_records(previous_id, SUMO_DIVISION),
        _fetch_division_banzuke_records(previous_id, SUMO_JURYO_DIVISION),
    )
    merged = {**juryo, **makuuchi}
    if merged:
        _LAST_BASHO_RECORDS_CACHE[previous_id] = merged
    return merged


async def fetch_head_to_head(rikishi_id: int, opponent_id: int) -> Optional[dict]:
    """
    Fetch the career series record between two rikishi, from `rikishi_id`'s perspective.

    Keeps only the series totals and the most recent meeting; the full bout list and
    kimarite breakdowns are dropped.

    :param int rikishi_id: ID of the rikishi whose wins are reported as `rikishiWins`.
    :param int opponent_id: ID of their opponent.

    :returns: Optional[dict]
    """
    try:
        endpoint = f"{SUMO_API_BASE_URL}/rikishi/{rikishi_id}/matches/{opponent_id}"
        session = await get_http_session()
        async with session.get(endpoint) as resp:
            if resp.status == 200:
                summary = await resp.json(content_type=None)
                matches = summary.get("matches") or []
                last_meeting = None
                if matches:  # Newest meeting first.
                    match = matches[0]
                    last_meeting = {
                        "bashoId": match.get("bashoId", ""),
                        "day": match.get("day"),
                        "winnerEn": match.get("winnerEn", ""),
                        "kimarite": match.get("kimarite", "unknown"),
                    }
                return {
                    "rikishiWins": summary.get("rikishiWins", 0),
                    "opponentWins": summary.get("opponentWins", 0),
                    "total": summary.get("total", 0),
                    "lastMeeting": last_meeting,
                }
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching sumo head-to-head `{rikishi_id}` vs `{opponent_id}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo head-to-head `{rikishi_id}` vs `{opponent_id}`: {e}")


def _cache_key(bout: dict) -> Tuple[str, bool]:
    """
    Cache key for a bout's head-to-head: its ID plus whether it has been fought.

    :param dict bout: Torikumi entry from the API.

    :returns: Tuple[str, bool]
    """
    return bout["id"], bool(bout.get("winnerEn"))


async def _cached_head_to_head(bout: dict, semaphore: asyncio.Semaphore) -> Optional[dict]:
    """
    Serve a bout's head-to-head from cache, fetching (under the concurrency cap) on a miss.

    :param dict bout: Torikumi entry from the API.
    :param asyncio.Semaphore semaphore: Cap on concurrent API requests.

    :returns: Optional[dict]
    """
    key = _cache_key(bout)
    cached = _HEAD_TO_HEAD_CACHE.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    async with semaphore:
        summary = await fetch_head_to_head(bout["eastId"], bout["westId"])
    if summary is not None:
        now = time.monotonic()
        for stale_key in [k for k, (expires_at, _) in _HEAD_TO_HEAD_CACHE.items() if expires_at <= now]:
            del _HEAD_TO_HEAD_CACHE[stale_key]
        _HEAD_TO_HEAD_CACHE[key] = (now + SUMO_HEAD_TO_HEAD_CACHE_TTL, summary)
    return summary


async def fetch_head_to_heads(bouts: List[dict]) -> Dict[str, dict]:
    """
    Fetch head-to-head records for every bout with both rikishi announced, keyed by bout ID.

    Lookups are best-effort: a bout whose lookup fails is simply absent from the result.

    :param List[dict] bouts: Torikumi entries from the API.

    :returns: Dict[str, dict]
    """
    eligible = [bout for bout in bouts if bout.get("id") and bout.get("eastId") and bout.get("westId")]
    if not eligible:
        return {}
    semaphore = asyncio.Semaphore(SUMO_MAX_CONCURRENT_REQUESTS)
    results = await asyncio.gather(
        *[_cached_head_to_head(bout, semaphore) for bout in eligible],
        return_exceptions=True,
    )
    head_to_heads = {}
    for bout, result in zip(eligible, results):
        if isinstance(result, BaseException):
            LOGGER.error(f"Failed to fetch sumo head-to-head for bout `{bout['id']}`: {result}")
        elif result is not None:
            head_to_heads[bout["id"]] = result
    return head_to_heads


async def fetch_rikishi_profile(rikishi_id: int) -> Optional[dict]:
    """
    Fetch a rikishi's height & weight.

    :param int rikishi_id: Rikishi ID.

    :returns: Optional[dict]
    """
    try:
        endpoint = f"{SUMO_API_BASE_URL}/rikishi/{rikishi_id}"
        session = await get_http_session()
        async with session.get(endpoint) as resp:
            if resp.status == 200:
                rikishi = await resp.json(content_type=None)
                if rikishi.get("height") and rikishi.get("weight"):
                    return {"height": rikishi["height"], "weight": rikishi["weight"]}
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching sumo rikishi profile `{rikishi_id}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching sumo rikishi profile `{rikishi_id}`: {e}")


async def _cached_rikishi_profile(rikishi_id: int, semaphore: asyncio.Semaphore) -> Optional[dict]:
    """
    Serve a rikishi's profile from cache, fetching (under the concurrency cap) on a miss.

    :param int rikishi_id: Rikishi ID.
    :param asyncio.Semaphore semaphore: Cap on concurrent API requests.

    :returns: Optional[dict]
    """
    cached = _RIKISHI_PROFILE_CACHE.get(rikishi_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    async with semaphore:
        profile = await fetch_rikishi_profile(rikishi_id)
    if profile is not None:
        now = time.monotonic()
        for stale_id in [k for k, (expires_at, _) in _RIKISHI_PROFILE_CACHE.items() if expires_at <= now]:
            del _RIKISHI_PROFILE_CACHE[stale_id]
        _RIKISHI_PROFILE_CACHE[rikishi_id] = (now + SUMO_RIKISHI_PROFILE_CACHE_TTL, profile)
    return profile


async def fetch_rikishi_profiles(rikishi_ids: List[int]) -> Dict[int, dict]:
    """
    Fetch height & weight for a list of rikishi, keyed by rikishi ID.

    Lookups are best-effort: a rikishi whose lookup fails is simply absent from the result.

    :param List[int] rikishi_ids: Rikishi IDs to look up.

    :returns: Dict[int, dict]
    """
    ids = [rikishi_id for rikishi_id in rikishi_ids if rikishi_id]
    if not ids:
        return {}
    semaphore = asyncio.Semaphore(SUMO_MAX_CONCURRENT_REQUESTS)
    results = await asyncio.gather(
        *[_cached_rikishi_profile(rikishi_id, semaphore) for rikishi_id in ids],
        return_exceptions=True,
    )
    profiles = {}
    for rikishi_id, result in zip(ids, results):
        if isinstance(result, BaseException):
            LOGGER.error(f"Failed to fetch sumo rikishi profile for `{rikishi_id}`: {result}")
        elif result is not None:
            profiles[rikishi_id] = result
    return profiles
