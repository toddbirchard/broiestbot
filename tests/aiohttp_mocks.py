"""Test doubles for the shared `aiohttp` session used by bot commands.

Command modules import `get_http_session` into their own namespace, so mocks must be
installed against the *command module* rather than `http_client`, ie:

    with patch_http_session("broiestbot.commands.sumo.matches", FakeResponse(json_data=basho)):
        result = asyncio.run(fetch_basho("202607"))
"""

import json as jsonlib
from typing import Any, List, Optional, Sequence, Union
from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError


class FakeResponse:
    """Stand-in for an `aiohttp.ClientResponse`, usable as an async context manager."""

    def __init__(
        self,
        status: int = 200,
        json_data: Any = None,
        text: Optional[str] = None,
        reason: str = "OK",
    ):
        self.status = status
        self.reason = reason
        self._json = json_data
        self._text = text if text is not None else (jsonlib.dumps(json_data) if json_data is not None else "")

    async def json(self, *_args, **_kwargs) -> Any:
        if self._json is None:
            raise ValueError(f"Expecting value: {self._text!r}")
        return self._json

    async def text(self) -> str:
        return self._text

    async def read(self) -> bytes:
        return self._text.encode()

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(None, (), status=self.status, message=self.reason)

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False


class FakeSession:
    """Stand-in for an `aiohttp.ClientSession` which replays canned responses in order."""

    def __init__(self, responses: Sequence[Union[FakeResponse, BaseException]]):
        self._responses = list(responses)
        self.calls: List[tuple] = []

    def _next(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        response = self._responses[0] if len(self._responses) == 1 else self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def get(self, url: str, **kwargs) -> FakeResponse:
        return self._next("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> FakeResponse:
        return self._next("POST", url, **kwargs)


def patch_http_session(module_path: str, *responses: Union[FakeResponse, BaseException]):
    """
    Patch a command module's `get_http_session` with a session replaying `responses`.

    A single response is replayed for every request; several are replayed in order.

    :param str module_path: Import path of the module whose HTTP calls are being faked.
    :param responses: `FakeResponse` objects (or exceptions) to serve, in order.

    :returns: unittest.mock._patch
    """
    session = FakeSession(responses or [FakeResponse()])
    return patch(f"{module_path}.get_http_session", AsyncMock(return_value=session))
