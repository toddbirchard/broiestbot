"""Tests for link-gated web search & reply parsing in the OpenAI LLM client."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import BadRequestError

from clients.llm import LLMRefusalError, OpenAIClient

FAKE_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")


@pytest.fixture
def client() -> OpenAIClient:
    return OpenAIClient()


def text_part(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="output_text", text=text)


def message(*parts) -> SimpleNamespace:
    return SimpleNamespace(type="message", content=list(parts))


def search_call() -> SimpleNamespace:
    return SimpleNamespace(type="web_search_call")


def response(*output, status: str = "completed", incomplete_details=None) -> SimpleNamespace:
    """Build a fake Responses API payload."""
    return SimpleNamespace(output=list(output), status=status, incomplete_details=incomplete_details)


def call(client: OpenAIClient, response_payload, messages=None, **kwargs) -> tuple:
    """
    Run `generate_response` against a canned API response.

    :returns: The reply text & the request kwargs the client sent.
    """
    requests = []

    async def fake_create(**request):
        requests.append(request)
        return response_payload

    client.client.responses.create = AsyncMock(side_effect=fake_create)
    if messages is None:
        messages = [{"role": "user", "content": "hi"}]
    reply = asyncio.run(client.generate_response(messages, **kwargs))
    return reply, requests[0]


# Request shape
# -------------------------------------------------


def test_request_targets_the_responses_api(client):
    """The persona rides in `instructions`, the history in `input`, and nothing is retained."""
    _, request = call(client, response(message(text_part("sup"))))
    assert request["model"] == client.model
    assert request["instructions"] == client.base_prompt
    assert request["input"] == [{"role": "user", "content": "hi"}]
    assert request["reasoning"] == {"effort": client.REASONING_EFFORT}
    assert request["store"] is False
    # The Responses API spells the cap differently to the Messages API; a rename here would
    # silently uncap the reply rather than error.
    assert request["max_output_tokens"] == 4096


def test_max_tokens_is_forwarded(client):
    """A caller's token budget reaches the API rather than being dropped for the default."""
    _, request = call(client, response(message(text_part("sup"))), max_tokens=512)
    assert request["max_output_tokens"] == 512


# Tool attachment — off unless a host was explicitly handed over
# -------------------------------------------------


def test_tool_is_omitted_without_hosts(client):
    """With no link in the prompt, the request carries no tool, so nothing can be read."""
    _, request = call(client, response(message(text_part("sup"))))
    assert "tools" not in request
    assert request["instructions"] == client.base_prompt


def test_tool_is_pinned_to_the_given_hosts(client):
    """The web search tool is scoped to exactly the hosts the user handed over."""
    _, request = call(client, response(message(text_part("sup"))), fetch_hosts=["example.com"])
    tool = request["tools"][0]
    assert tool["type"] == client.WEB_SEARCH_TOOL_TYPE
    assert tool["filters"] == {"allowed_domains": ["example.com"]}
    assert request["max_tool_calls"] == client.WEB_SEARCH_MAX_CALLS
    assert client.link_prompt in request["instructions"]


def test_empty_hosts_are_treated_as_no_hosts(client):
    """An empty host list must not attach an unrestricted tool."""
    _, request = call(client, response(message(text_part("sup"))), fetch_hosts=[])
    assert "tools" not in request


# Reply parsing
# -------------------------------------------------


def test_reply_skips_preamble_before_a_tool_call(client):
    """The text before a search call is a throwaway preamble; the answer comes after it."""
    reply, _ = call(
        client,
        response(
            SimpleNamespace(type="reasoning"),
            message(text_part("lemme peep that link")),
            search_call(),
            message(text_part("it's a recipe for chili, bro")),
        ),
    )
    assert reply.strip() == "it's a recipe for chili, bro"


def test_reply_joins_text_after_the_last_tool_block(client):
    """An answer split across parts is returned whole."""
    reply, _ = call(client, response(search_call(), message(text_part("first half"), text_part("second half"))))
    assert "first half" in reply and "second half" in reply


def test_reply_without_tool_blocks_is_unchanged(client):
    """The ordinary no-tool path still returns the single message."""
    reply, _ = call(client, response(message(text_part("just vibes"))))
    assert reply.strip() == "just vibes"


def test_response_without_text_returns_none(client):
    reply, _ = call(client, response(search_call()))
    assert reply is None


# Refusals
# -------------------------------------------------


def test_refusal_part_raises(client):
    """A `refusal` content part is a decline, not a reply."""
    with pytest.raises(LLMRefusalError):
        call(client, response(message(SimpleNamespace(type="refusal", refusal="nope"))))


def test_moderation_cutoff_raises(client):
    """A turn cut short by the moderation filter is a decline too, and never raises on its own."""
    with pytest.raises(LLMRefusalError):
        call(
            client,
            response(
                message(text_part("half an ans")),
                status="incomplete",
                incomplete_details=SimpleNamespace(reason="content_filter"),
            ),
        )


def test_length_cutoff_is_not_a_refusal(client):
    """Running out of output tokens is not a decline; whatever was said still gets sent."""
    reply, _ = call(
        client,
        response(
            message(text_part("ran long")),
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        ),
    )
    assert reply.strip() == "ran long"


# Vision — which images the model gets to see
# -------------------------------------------------

IMAGE = "https://i.imgur.com/wppfinC.png"
GIF = "https://media0.giphy.com/media/abc/giphy.gif?cid=xyz"
TWEET_IMAGE = "https://pbs.twimg.com/media/ABC123?format=jpg&name=large"


def history(*bodies) -> list:
    """A formatted history where every entry is a user turn, oldest first."""
    return [{"role": "user", "content": body} for body in bodies]


def image_parts(request) -> list:
    """The `input_image` parts attached to the request, if any. Untouched turns stay plain text."""
    return [
        part
        for message in request["input"]
        if not isinstance(message["content"], str)
        for part in message["content"]
        if part["type"] == "input_image"
    ]


@pytest.mark.parametrize(
    "url,expected",
    [
        (IMAGE, [IMAGE]),
        (GIF, [GIF]),  # extension survives Giphy's mandatory query string
        (TWEET_IMAGE, [TWEET_IMAGE]),  # extensionless, matched on host
        ("https://media.tenor.com/x/y.gif", ["https://media.tenor.com/x/y.gif"]),  # subdomain host
        ("https://example.com/article", []),
        ("https://example.com/notanimage.html", []),
        ("no link here at all", []),
    ],
)
def test_image_urls_detection(url: str, expected: list):
    """A link counts as an image by extension or by host, and nothing else does."""
    assert OpenAIClient.image_urls(f"<sean>: check {url} out") == expected


def test_prompt_carrying_its_own_image_needs_no_intent(client):
    """A link in the prompt is an explicit ask, so it skips the "is this about an image" gate."""
    _, request = call(
        client,
        response(message(text_part("that's a dog"))),
        chat_message=f"@bro {IMAGE}",
    )
    assert [part["image_url"] for part in image_parts(request)] == [IMAGE]
    assert client.vision_prompt in request["instructions"]


def test_image_prompt_reaches_back_into_history(client):
    """A prompt about an image picks up one somebody else posted earlier."""
    _, request = call(
        client,
        response(message(text_part("it's a dog"))),
        chat_message="@bro what is that pic",
        messages=history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic"),
    )
    assert [part["image_url"] for part in image_parts(request)] == [IMAGE]


def test_unrelated_prompt_ignores_images_in_history(client):
    """A gif six lines up has nothing to do with "who won the derby"."""
    _, request = call(
        client,
        response(message(text_part("liverpool"))),
        chat_message="@bro who won the derby",
        messages=history(f"<sean>: {GIF}", "<sean>: @bro who won the derby"),
    )
    assert image_parts(request) == []
    assert isinstance(request["input"][0]["content"], str)
    assert client.vision_prompt not in request["instructions"]


def test_image_prompt_with_no_image_in_history_attaches_nothing(client):
    """Asking about a picture nobody posted must not invent one."""
    _, request = call(
        client,
        response(message(text_part("what pic"))),
        chat_message="@bro what is that pic",
        messages=history("<sean>: @bro what is that pic"),
    )
    assert image_parts(request) == []


def test_newest_images_win_and_are_capped(client):
    """Only the most recent `VISION_MAX_IMAGES` are shipped, oldest of those first."""
    urls = [f"https://i.imgur.com/{n}.png" for n in range(4)]
    _, request = call(
        client,
        response(message(text_part("ok"))),
        chat_message="@bro describe this",
        messages=history(*[f"<sean>: {url}" for url in urls], "<sean>: @bro describe this"),
    )
    assert [part["image_url"] for part in image_parts(request)] == urls[-client.VISION_MAX_IMAGES :]


def test_images_are_hoisted_onto_the_last_user_turn(client):
    """The bot posts gifs too, and an `assistant` turn cannot carry an `input_image`."""
    messages = [
        {"role": "assistant", "content": f"here u go {GIF}"},
        {"role": "user", "content": "<sean>: @bro what is that gif"},
    ]
    _, request = call(
        client,
        response(message(text_part("a dog"))),
        chat_message="@bro what is that gif",
        messages=messages,
    )
    assert request["input"][0] == messages[0], "the assistant turn is left as plain text"
    attached = request["input"][1]
    assert attached["role"] == "user"
    assert attached["content"][0] == {"type": "input_text", "text": "<sean>: @bro what is that gif"}
    assert [part["image_url"] for part in attached["content"][1:]] == [GIF]
    assert all(part["detail"] == client.VISION_IMAGE_DETAIL for part in attached["content"][1:])


def test_attaching_images_does_not_mutate_the_caller_history(client):
    """`format_chat_history`'s output is the caller's; vision must copy rather than rewrite it."""
    messages = history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic")
    original = [dict(message) for message in messages]
    call(client, response(message(text_part("ok"))), chat_message="@bro what is that pic", messages=messages)
    assert messages == original


def test_missing_chat_message_never_attaches_images(client):
    """Without the triggering message there is no gate to apply, so vision stays off."""
    _, request = call(
        client,
        response(message(text_part("ok"))),
        messages=history(f"<sean>: {IMAGE}"),
    )
    assert image_parts(request) == []


def test_unreadable_image_falls_back_to_text(client):
    """A 404'd or hotlink-blocked image costs the picture, not the whole reply."""
    requests = []
    responses = [BadRequestError("invalid_image_url", response=httpx.Response(400, request=FAKE_REQUEST), body=None)]
    responses.append(response(message(text_part("cant see it, but liverpool"))))

    async def fake_create(**request):
        requests.append(request)
        result = responses[len(requests) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    client.client.responses.create = AsyncMock(side_effect=fake_create)
    reply = asyncio.run(
        client.generate_response(
            history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic"),
            chat_message="@bro what is that pic",
        )
    )
    assert reply.strip() == "cant see it, but liverpool"
    assert len(requests) == 2
    # The retry drops the images and the rule describing them, and restores the plain text.
    assert requests[1]["input"][0]["content"] == f"<sean>: {IMAGE}"
    assert client.vision_prompt not in requests[1]["instructions"]


def test_bad_request_without_images_is_not_retried(client):
    """A 400 which had nothing to do with an image is a real error, not something to paper over."""
    error = BadRequestError("nope", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    client.client.responses.create = AsyncMock(side_effect=error)
    with pytest.raises(BadRequestError):
        asyncio.run(client.generate_response(history("<sean>: @bro sup"), chat_message="@bro sup"))
    assert client.client.responses.create.await_count == 1


def test_quoted_image_is_still_readable(client):
    """
    Quoting the image you're asking about is the natural way to ask, so it stays eligible.

    This differs from link reading on purpose, where a quote means "not my ask". The closing
    backtick of the quote must not survive into the URL — an image URL is sent verbatim, so a
    stray character makes it unfetchable rather than merely untidy.
    """
    quoted = f"@bro `<sean>: {IMAGE}` what is this pic"
    assert OpenAIClient.image_urls(quoted) == [IMAGE]
    _, request = call(client, response(message(text_part("a dog"))), chat_message=quoted)
    assert [part["image_url"] for part in image_parts(request)] == [IMAGE]


def test_duplicate_links_in_one_message_are_collapsed(client):
    """The same image posted twice in one breath is one image, not two."""
    assert OpenAIClient.image_urls(f"<sean>: {IMAGE} lol {IMAGE}") == [IMAGE]


def test_a_repost_moves_an_image_back_to_newest(client):
    """An image posted early and reposted later is recent again, and survives the cap."""
    old_image, new_image = "https://i.imgur.com/old.png", "https://i.imgur.com/new.png"
    _, request = call(
        client,
        response(message(text_part("ok"))),
        chat_message="@bro describe this pic",
        messages=history(
            f"<sean>: {old_image}",
            f"<bob>: {new_image}",
            f"<sean>: {old_image} again",
            "<sean>: @bro describe this pic",
        ),
    )
    # Without the move-to-newest, the cap would have dropped the reposted image.
    assert [part["image_url"] for part in image_parts(request)] == [new_image, old_image]


def test_own_link_wins_over_older_images_in_history(client):
    """The image in the prompt is the ask; an older one in history must not crowd it out."""
    _, request = call(
        client,
        response(message(text_part("ok"))),
        chat_message=f"@bro what is {IMAGE}",
        messages=history(f"<bob>: {GIF}", f"<sean>: @bro what is {IMAGE}"),
    )
    assert [part["image_url"] for part in image_parts(request)] == [IMAGE]


def test_history_with_no_user_turn_is_left_alone(client):
    """With nowhere valid to hang an image, the history is sent unchanged rather than corrupted."""
    messages = [{"role": "assistant", "content": f"here u go {IMAGE}"}]
    _, request = call(
        client,
        response(message(text_part("ok"))),
        chat_message="@bro what is that pic",
        messages=messages,
    )
    assert request["input"] == messages
    assert image_parts(request) == []


def test_already_multimodal_history_entries_are_skipped(client):
    """A caller who pre-built content parts must not crash the image scan."""
    messages = [
        {"role": "user", "content": [{"type": "input_text", "text": f"<bob>: {IMAGE}"}]},
        {"role": "user", "content": "<sean>: @bro what is that pic"},
    ]
    _, request = call(
        client, response(message(text_part("ok"))), chat_message="@bro what is that pic", messages=messages
    )
    assert image_parts(request) == []


# Vision & web search together
# -------------------------------------------------


def make_mixed_call(client, *responses):
    """Run a prompt carrying both an image and a readable link."""
    prompt = f"@bro what is this pic {IMAGE} vs https://example.com/x"
    requests = []

    async def fake_create(**request):
        requests.append(request)
        result = responses[len(requests) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    client.client.responses.create = AsyncMock(side_effect=fake_create)
    reply = asyncio.run(
        client.generate_response(
            [{"role": "user", "content": f"<sean>: {prompt}"}],
            chat_message=prompt,
            fetch_hosts=client.fetchable_hosts(prompt),
        )
    )
    return reply, requests


def test_images_and_web_search_coexist(client):
    """A prompt with both a picture and a link gets both capabilities, and both persona rules."""
    _, requests = make_mixed_call(client, response(message(text_part("ok"))))
    request = requests[0]
    assert request["tools"][0]["type"] == client.WEB_SEARCH_TOOL_TYPE
    assert request["max_tool_calls"] == client.WEB_SEARCH_MAX_CALLS
    assert client.link_prompt in request["instructions"]
    assert client.vision_prompt in request["instructions"]
    assert [part["image_url"] for part in image_parts(request)] == [IMAGE]


def test_dropping_a_bad_image_keeps_web_search(client):
    """Losing the picture must not also cost the request its search tool or its link rules."""
    error = BadRequestError("bad image", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    _, requests = make_mixed_call(client, error, response(message(text_part("ok"))))
    retry = requests[1]
    assert retry["tools"] == requests[0]["tools"]
    assert retry["max_tool_calls"] == client.WEB_SEARCH_MAX_CALLS
    assert client.link_prompt in retry["instructions"]
    assert client.vision_prompt not in retry["instructions"]
    assert image_parts(retry) == []


def test_the_retry_happens_only_once(client):
    """A 400 which survives dropping the images is a real error, not a retry loop."""
    error = BadRequestError("still bad", response=httpx.Response(400, request=FAKE_REQUEST), body=None)
    with pytest.raises(BadRequestError):
        make_mixed_call(client, error, error)
    assert client.client.responses.create.await_count == 2


def test_close_closes_the_sdk_client(client):
    """`asgi.py` closes the client on lifespan shutdown; it must reach the SDK."""
    client.client.close = AsyncMock()
    asyncio.run(client.close())
    client.client.close.assert_awaited_once()
