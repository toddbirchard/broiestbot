"""Tests for the redgifs command's async client handling.

The command used to run the blocking `redgifs.API` through `asyncio.to_thread` and
re-authenticate on every search. It now awaits `redgifs.aio.API` and reuses its token.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redgifs.errors import InvalidTag

import broiestbot.commands.afterdark as afterdark
from broiestbot.commands.afterdark import fetch_redgifs_gif, get_redgifs_client


@pytest.fixture(autouse=True)
def reset_client_state():
    """Each test starts with no client & no cached token."""
    afterdark._redgifs_client = None
    afterdark._logged_in = False
    yield
    afterdark._redgifs_client = None
    afterdark._logged_in = False


def build_client() -> MagicMock:
    """Build a stand-in `redgifs.aio.API` whose login & search are awaitable."""
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    gif = MagicMock()
    gif.urls.web_url = "https://redgifs.test/gif"
    gif.urls.thumbnail = "https://redgifs.test/thumb.jpg"
    gif.tags = ["a", "b"]
    gif.likes = 10
    gif.views = 100
    client.search = AsyncMock(return_value=MagicMock(gifs=[gif]))
    return client


def test_login_happens_once_across_calls():
    """The auth token is reused; only the first command pays for a login round trip."""
    client = build_client()
    with patch("broiestbot.commands.afterdark.redgifs.aio.API", return_value=client):
        asyncio.run(fetch_redgifs_gif("cats", "user", False))
        asyncio.run(fetch_redgifs_gif("cats", "user", False))
        asyncio.run(fetch_redgifs_gif("cats", "user", False))

    assert client.login.await_count == 1, f"expected a single login, got {client.login.await_count}"
    assert client.search.await_count == 3


def test_expired_token_triggers_one_re_login():
    """An HTTP failure re-authenticates once and retries, rather than giving up."""
    from redgifs.errors import HTTPException

    client = build_client()
    gif_result = client.search.return_value
    # `HTTPException.__init__` insists on a real requests/aiohttp response; the handler only
    # cares about the type, so build a bare instance.
    expired_token = HTTPException.__new__(HTTPException)
    client.search = AsyncMock(side_effect=[expired_token, gif_result])

    with patch("broiestbot.commands.afterdark.redgifs.aio.API", return_value=client):
        result = asyncio.run(fetch_redgifs_gif("cats", "user", False))

    assert client.login.await_count == 2, "should re-authenticate exactly once on an HTTP error"
    assert client.search.await_count == 2
    assert "redgifs.test" in result


def test_invalid_tag_answers_instead_of_raising():
    """`RedGifsError` derives from BaseException, so it needs catching explicitly."""
    client = build_client()
    client.search = AsyncMock(side_effect=InvalidTag("zzqq"))

    with patch("broiestbot.commands.afterdark.redgifs.aio.API", return_value=client):
        result = asyncio.run(fetch_redgifs_gif("zzqq", "someuser", False))

    assert result is not None, "an unknown tag must produce a reply, not silence"
    assert "someuser" in result


def test_client_is_built_once_and_closed():
    """The client is constructed lazily on first use & discarded on close."""
    client = build_client()
    with patch("broiestbot.commands.afterdark.redgifs.aio.API", return_value=client) as ctor:

        async def run():
            await get_redgifs_client()
            await get_redgifs_client()
            await afterdark.close_redgifs_client()

        asyncio.run(run())

    assert ctor.call_count == 1
    client.close.assert_awaited_once()
    assert afterdark._redgifs_client is None


def test_after_dark_gate_short_circuits_outside_hours():
    """Outside `after dark` hours the command answers without ever building a client."""
    with patch("broiestbot.commands.afterdark.is_after_dark", return_value=False):
        with patch("broiestbot.commands.afterdark.redgifs.aio.API") as ctor:
            result = asyncio.run(fetch_redgifs_gif("cats", "user", True))

    ctor.assert_not_called()
    assert result == "https://i.imgur.com/oGMHkqT.jpg"
