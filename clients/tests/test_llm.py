"""Tests for link-gated web fetch & reply parsing in the LLM client."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from clients.llm import LLMClient, LLMRefusalError


@pytest.fixture
def client() -> LLMClient:
    return LLMClient()


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def response(*content, stop_reason: str = "end_turn") -> SimpleNamespace:
    """Build a fake API response with no fallback activity."""
    return SimpleNamespace(
        content=list(content),
        stop_reason=stop_reason,
        stop_details=None,
        model="claude-opus-5",
        usage=SimpleNamespace(iterations=[]),
    )


def call(client: LLMClient, *responses, **kwargs) -> tuple:
    """
    Run `generate_response` against a queue of canned API responses.

    :returns: The reply text & the list of request kwargs the client sent.
    """
    requests = []

    async def fake_create(**request):
        requests.append(request)
        return responses[len(requests) - 1]

    client.client.beta.messages.create = AsyncMock(side_effect=fake_create)
    reply = asyncio.run(client.generate_response([{"role": "user", "content": "hi"}], **kwargs))
    return reply, requests


# `fetchable_hosts` — which links count as an explicit ask
# -------------------------------------------------


@pytest.mark.parametrize(
    "chat_message,expected",
    [
        ("@bro what's this https://example.com/article about", ["example.com"]),
        ("@bro read https://www.example.com", ["www.example.com", "example.com"]),
        ("@bro http://a.co/x vs https://b.co/y", ["a.co", "b.co"]),
        ("@bro https://example.com/a and https://example.com/b", ["example.com"]),
        ("@bro see https://example.com.", ["example.com"]),  # trailing sentence punctuation
        ("@bro https://user:pw@example.com:8443/x", ["example.com"]),
        ("@bro HTTPS://Example.COM/x", ["example.com"]),
    ],
)
def test_links_in_the_prompt_are_fetchable(chat_message: str, expected: list):
    """A link the sender typed into their own message is an explicit ask to read it."""
    assert LLMClient.fetchable_hosts(chat_message) == expected


@pytest.mark.parametrize(
    "chat_message",
    [
        "@bro what's the score",
        "@bro check example.com",  # no scheme, so not a link
        "@broiestbot: `https://example.com` what do you think",  # quoted, not the sender's own
        "@broiestbot: `see https://example.com` lmao",
    ],
)
def test_messages_without_their_own_link_fetch_nothing(chat_message: str):
    """No link of the sender's own means the web fetch tool is never offered."""
    assert LLMClient.fetchable_hosts(chat_message) == []


# Tool attachment — off unless a host was explicitly handed over
# -------------------------------------------------


def test_tool_is_omitted_without_hosts(client):
    """With no link in the prompt, the request carries no tool, so nothing can be fetched."""
    _, requests = call(client, response(text_block("sup")))
    assert "tools" not in requests[0]
    assert requests[0]["system"] == client.base_prompt


def test_tool_is_pinned_to_the_given_hosts(client):
    """The web fetch tool is scoped to exactly the hosts the user handed over."""
    _, requests = call(client, response(text_block("sup")), fetch_hosts=["example.com"])
    tool = requests[0]["tools"][0]
    assert tool["type"] == client.WEB_FETCH_TOOL_TYPE
    assert tool["name"] == "web_fetch"
    assert tool["allowed_domains"] == ["example.com"]
    assert tool["max_uses"] == client.WEB_FETCH_MAX_USES
    assert client.link_prompt in requests[0]["system"]


def test_empty_hosts_are_treated_as_no_hosts(client):
    """An empty host list must not attach an unrestricted tool."""
    _, requests = call(client, response(text_block("sup")), fetch_hosts=[])
    assert "tools" not in requests[0]


# Reply parsing
# -------------------------------------------------


def test_reply_skips_preamble_before_a_tool_call(client):
    """The text before a tool call is a throwaway preamble; the answer comes after it."""
    reply, _ = call(
        client,
        response(
            SimpleNamespace(type="thinking", thinking=""),
            text_block("lemme peep that link"),
            SimpleNamespace(type="server_tool_use", name="web_fetch"),
            SimpleNamespace(type="web_fetch_tool_result"),
            text_block("it's a recipe for chili, bro"),
        ),
    )
    assert reply.strip() == "it's a recipe for chili, bro"


def test_reply_joins_text_after_the_last_tool_block(client):
    """An answer split across blocks is returned whole."""
    reply, _ = call(
        client,
        response(
            SimpleNamespace(type="web_fetch_tool_result"),
            text_block("first half"),
            text_block("second half"),
        ),
    )
    assert "first half" in reply and "second half" in reply


def test_reply_without_tool_blocks_is_unchanged(client):
    """The ordinary no-tool path still returns the single text block."""
    reply, _ = call(client, response(text_block("just vibes")))
    assert reply.strip() == "just vibes"


def test_response_without_text_returns_none(client):
    reply, _ = call(client, response(SimpleNamespace(type="web_fetch_tool_result")))
    assert reply is None


# `pause_turn` resumption
# -------------------------------------------------


def test_paused_turn_is_resumed(client):
    """A turn paused mid-tool-loop is re-sent, and the resumed answer is returned."""
    paused = response(text_block("still reading"), stop_reason="pause_turn")
    reply, requests = call(client, paused, response(text_block("done, it's chili")))
    assert reply.strip() == "done, it's chili"
    assert len(requests) == 2
    # The paused turn is echoed back untouched, with no nudge of our own appended.
    assert requests[1]["messages"][-1] == {"role": "assistant", "content": paused.content}


def test_resumption_is_bounded(client):
    """A turn which never unpauses stops being retried rather than looping forever."""
    paused = [response(text_block("still reading"), stop_reason="pause_turn") for _ in range(5)]
    reply, requests = call(client, *paused)
    assert len(requests) == client.MAX_PAUSE_TURN_RESUMES + 1
    assert reply.strip() == "still reading"


def test_refusal_after_resumption_raises(client):
    """A refusal on the resumed turn is still surfaced."""
    with pytest.raises(LLMRefusalError):
        call(
            client,
            response(text_block("hm"), stop_reason="pause_turn"),
            SimpleNamespace(
                content=[],
                stop_reason="refusal",
                stop_details=SimpleNamespace(category="cyber"),
                model="claude-opus-5",
                usage=SimpleNamespace(iterations=[]),
            ),
        )
