"""Tests for link-gated web fetch, vision & reply parsing in the Anthropic LLM client."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from anthropic import BadRequestError

from clients.llm import AnthropicClient, LLMRefusalError

FAKE_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.fixture
def client() -> AnthropicClient:
    return AnthropicClient()


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


def call(client: AnthropicClient, *responses, messages=None, **kwargs) -> tuple:
    """
    Run `generate_response` against a queue of canned API responses.

    :returns: The reply text & the list of request kwargs the client sent.
    """
    requests = []

    async def fake_create(**request):
        requests.append(request)
        result = responses[len(requests) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    client.client.beta.messages.create = AsyncMock(side_effect=fake_create)
    if messages is None:
        messages = [{"role": "user", "content": "hi"}]
    reply = asyncio.run(client.generate_response(messages, **kwargs))
    return reply, requests


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


# Vision — request shape (image selection itself is covered in test_llm_base.py)
# -------------------------------------------------

IMAGE = "https://i.imgur.com/wppfinC.png"
GIF = "https://media0.giphy.com/media/abc/giphy.gif?cid=xyz"


def history(*bodies) -> list:
    """A formatted history where every entry is a user turn, oldest first."""
    return [{"role": "user", "content": body} for body in bodies]


def image_blocks(request) -> list:
    """The `image` content blocks attached to the request, if any. Untouched turns stay plain text."""
    return [
        block
        for message in request["messages"]
        if not isinstance(message["content"], str)
        for block in message["content"]
        if block["type"] == "image"
    ]


def test_prompt_carrying_its_own_image_needs_no_intent(client):
    """A link in the prompt is an explicit ask, so it skips the "is this about an image" gate."""
    _, requests = call(client, response(text_block("that's a dog")), chat_message=f"@bro {IMAGE}")
    request = requests[0]
    assert [block["source"]["url"] for block in image_blocks(request)] == [IMAGE]
    assert client.vision_prompt in request["system"]


def test_images_are_hoisted_onto_the_last_user_turn(client):
    """The bot posts gifs too, and an `assistant` turn cannot carry an image block."""
    messages = [
        {"role": "assistant", "content": f"here u go {GIF}"},
        {"role": "user", "content": "<sean>: @bro what is that gif"},
    ]
    _, requests = call(client, response(text_block("a dog")), chat_message="@bro what is that gif", messages=messages)
    request = requests[0]
    assert request["messages"][0] == messages[0], "the assistant turn is left as plain text"
    attached = request["messages"][1]
    assert attached["role"] == "user"
    assert attached["content"][0] == {"type": "text", "text": "<sean>: @bro what is that gif"}
    assert [block["source"]["url"] for block in attached["content"][1:]] == [GIF]
    assert all(block["source"]["type"] == "url" for block in attached["content"][1:])


def test_attaching_images_does_not_mutate_the_caller_history(client):
    """`format_chat_history`'s output is the caller's; vision must copy rather than rewrite it."""
    messages = history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic")
    original = [dict(message) for message in messages]
    call(client, response(text_block("ok")), chat_message="@bro what is that pic", messages=messages)
    assert messages == original


def test_unreadable_image_falls_back_to_text(client):
    """A 404'd or hotlink-blocked image costs the picture, not the whole reply."""
    error = BadRequestError("invalid_image_url", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    reply, requests = call(
        client,
        error,
        response(text_block("cant see it, but liverpool")),
        chat_message="@bro what is that pic",
        messages=history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic"),
    )
    assert reply.strip() == "cant see it, but liverpool"
    assert len(requests) == 2
    # The retry drops the images and the rule describing them, and restores the plain text.
    assert requests[1]["messages"][0]["content"] == f"<sean>: {IMAGE}"
    assert client.vision_prompt not in requests[1]["system"]


def test_bad_request_without_images_is_not_retried(client):
    """A 400 which had nothing to do with an image is a real error, not something to paper over."""
    error = BadRequestError("nope", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    with pytest.raises(BadRequestError):
        call(client, error, chat_message="@bro sup", messages=history("<sean>: @bro sup"))


def test_history_with_no_user_turn_is_left_alone(client):
    """With nowhere valid to hang an image, the history is sent unchanged rather than corrupted."""
    messages = [{"role": "assistant", "content": f"here u go {IMAGE}"}]
    _, requests = call(client, response(text_block("ok")), chat_message="@bro what is that pic", messages=messages)
    request = requests[0]
    assert request["messages"] == messages
    assert image_blocks(request) == []


# Vision & web fetch together
# -------------------------------------------------


def make_mixed_call(client, *responses):
    """Run a prompt carrying both an image and a readable link."""
    prompt = f"@bro what is this pic {IMAGE} vs https://example.com/x"
    return call(
        client,
        *responses,
        messages=[{"role": "user", "content": f"<sean>: {prompt}"}],
        chat_message=prompt,
        fetch_hosts=client.fetchable_hosts(prompt),
    )


def test_images_and_web_fetch_coexist(client):
    """A prompt with both a picture and a link gets both capabilities, and both persona rules."""
    _, requests = make_mixed_call(client, response(text_block("ok")))
    request = requests[0]
    assert request["tools"][0]["type"] == client.WEB_FETCH_TOOL_TYPE
    assert client.link_prompt in request["system"]
    assert client.vision_prompt in request["system"]
    assert [block["source"]["url"] for block in image_blocks(request)] == [IMAGE]


def test_dropping_a_bad_image_keeps_web_fetch(client):
    """Losing the picture must not also cost the request its fetch tool or its link rules."""
    error = BadRequestError("bad image", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    _, requests = make_mixed_call(client, error, response(text_block("ok")))
    retry = requests[1]
    assert retry["tools"] == requests[0]["tools"]
    assert client.link_prompt in retry["system"]
    assert client.vision_prompt not in retry["system"]
    assert image_blocks(retry) == []


def test_the_retry_happens_only_once(client):
    """A 400 which survives dropping the images is a real error, not a retry loop."""
    error = BadRequestError("still bad", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    with pytest.raises(BadRequestError):
        make_mixed_call(client, error, error)
