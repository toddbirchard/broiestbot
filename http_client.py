"""Shared `aiohttp` session used for all outbound HTTP requests made by bot commands."""

import asyncio
from typing import Optional

import aiohttp

from config import HTTP_REQUEST_TIMEOUT

_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def get_http_session() -> aiohttp.ClientSession:
    """
    Return the process-wide `aiohttp` session, creating it on first use.

    A single session is shared by every command so that connections are pooled and DNS
    lookups are cached across requests. The session is bound to the running event loop,
    hence it is created lazily rather than at import time.

    :returns: aiohttp.ClientSession
    """
    global _session
    if _session is None or _session.closed:
        async with _session_lock:
            if _session is None or _session.closed:
                _session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=HTTP_REQUEST_TIMEOUT),
                    raise_for_status=False,
                )
    return _session


def request_timeout(seconds: float) -> aiohttp.ClientTimeout:
    """
    Build a per-request timeout which overrides the session default.

    :param float seconds: Total number of seconds a request may take.

    :returns: aiohttp.ClientTimeout
    """
    return aiohttp.ClientTimeout(total=seconds)


async def close_http_session() -> None:
    """
    Close the shared `aiohttp` session; called when the bot shuts down.

    :returns: None
    """
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None
