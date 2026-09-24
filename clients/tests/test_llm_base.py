"""Tests for the provider-agnostic half of the LLM client, shared by both providers."""

from unittest.mock import patch

import pytest

from clients.llm import (
    LLM_CLIENTS,
    AnthropicClient,
    BaseLLMClient,
    LLMClient,
    OpenAIClient,
)

# Provider selection — one flag, two clients
# -------------------------------------------------


@pytest.mark.parametrize(
    "llm_type,expected",
    [
        ("claude", AnthropicClient),
        ("chatgpt", OpenAIClient),
        ("  ChatGPT  ", OpenAIClient),  # whitespace & casing are the `.env`'s business, not ours
    ],
)
def test_flag_picks_the_provider(llm_type: str, expected: type):
    """`LLM_TYPE` alone decides which client the rest of the bot talks to."""
    with patch("clients.llm.LLM_TYPE", llm_type):
        assert isinstance(LLMClient(), expected)


@pytest.mark.parametrize("llm_type", ["", None, "gemini"])
def test_unknown_provider_is_rejected(llm_type):
    """A typo'd flag fails loudly at startup rather than silently picking a provider."""
    with patch("clients.llm.LLM_TYPE", llm_type):
        with pytest.raises(ValueError):
            LLMClient()


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_every_provider_satisfies_the_contract(client_class):
    """Each provider is a `BaseLLMClient` carrying the pieces callers rely on."""
    client = client_class()
    assert isinstance(client, BaseLLMClient)
    assert issubclass(client.RATE_LIMIT_ERROR, Exception)
    assert issubclass(client.API_ERROR, Exception)
    # The rate limit reply must not be swallowed by the general API error handler above it.
    assert issubclass(client.RATE_LIMIT_ERROR, client.API_ERROR)


# The persona & its link-reading rules
# -------------------------------------------------


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_providers_share_one_persona(client_class):
    """Swapping providers must not swap personalities."""
    assert client_class().base_prompt == AnthropicClient().base_prompt


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_link_rules_are_appended_only_when_a_link_is_handed_over(client_class):
    """The link-reading rules ride along with the tool, and never without it."""
    client = client_class()
    assert client.system_prompt() == client.base_prompt
    assert client.system_prompt([]) == client.base_prompt
    with_link = client.system_prompt(["example.com"])
    assert client.base_prompt in with_link
    # Each provider's rules must name that provider's own tool.
    assert f"`{client.LINK_TOOL_NAME}`" in with_link


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
    assert BaseLLMClient.fetchable_hosts(chat_message) == expected


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
    assert BaseLLMClient.fetchable_hosts(chat_message) == []


# Alt modes — per-room persona switching
# -------------------------------------------------


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_room_defaults_to_base_prompt(client_class):
    """A room which never switched modes always gets the default persona."""
    client = client_class()
    assert client.active_mode("room-a") is None
    assert client.system_prompt(room_name="room-a") == client.base_prompt
    assert client.system_prompt() == client.base_prompt  # no room_name at all


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
@pytest.mark.parametrize(
    "mode,prompt_attr",
    [("dubs", "dubs_prompt"), ("cryptkeeper", "cryptkeeper_prompt"), ("motherinlaw", "motherinlaw_prompt")],
)
def test_activating_a_mode_swaps_the_persona_for_that_room(client_class, mode, prompt_attr):
    """Activating a mode in one room switches only that room's system prompt."""
    client = client_class()
    client.activate_mode("room-a", mode)
    assert client.active_mode("room-a") == mode
    assert client.system_prompt(room_name="room-a") == getattr(client, prompt_attr)
    # An untouched room is unaffected.
    assert client.active_mode("room-b") is None
    assert client.system_prompt(room_name="room-b") == client.base_prompt


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_activating_a_second_mode_replaces_the_first(client_class):
    """A room runs at most one mode at a time — switching modes doesn't stack them."""
    client = client_class()
    client.activate_mode("room-a", "dubs")
    client.activate_mode("room-a", "cryptkeeper")
    assert client.active_mode("room-a") == "cryptkeeper"
    assert client.system_prompt(room_name="room-a") == client.cryptkeeper_prompt


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_unknown_mode_is_rejected(client_class):
    """A typo'd mode key fails loudly rather than silently doing nothing."""
    client = client_class()
    with pytest.raises(KeyError):
        client.activate_mode("room-a", "not-a-real-mode")


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_deactivating_a_mode_restores_the_base_prompt(client_class):
    """The reverse trigger switches a room back to its default persona."""
    client = client_class()
    client.activate_mode("room-a", "dubs")
    client.deactivate_mode("room-a", "dubs")
    assert client.active_mode("room-a") is None
    assert client.system_prompt(room_name="room-a") == client.base_prompt


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_deactivating_an_untouched_room_is_a_noop(client_class):
    """Deactivating a room never in that mode raises nothing and changes nothing."""
    client = client_class()
    client.deactivate_mode("room-a", "dubs")
    assert client.active_mode("room-a") is None


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_deactivating_the_wrong_mode_is_a_noop(client_class):
    """A stale deactivate for a mode that isn't the room's current one doesn't clear it."""
    client = client_class()
    client.activate_mode("room-a", "cryptkeeper")
    client.deactivate_mode("room-a", "dubs")
    assert client.active_mode("room-a") == "cryptkeeper"


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_active_mode_persona_still_gets_link_rules(client_class):
    """The link-reading rules are appended regardless of which persona is active."""
    client = client_class()
    client.activate_mode("room-a", "dubs")
    with_link = client.system_prompt(["example.com"], room_name="room-a")
    assert with_link == client.dubs_prompt + client.link_prompt


# Vision — image detection & selection, shared by both providers
# -------------------------------------------------

IMAGE = "https://i.imgur.com/wppfinC.png"
GIF = "https://media0.giphy.com/media/abc/giphy.gif?cid=xyz"
TWEET_IMAGE = "https://pbs.twimg.com/media/ABC123?format=jpg&name=large"


def history(*bodies) -> list:
    """A formatted history where every entry is a user turn, oldest first."""
    return [{"role": "user", "content": body} for body in bodies]


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
    assert BaseLLMClient.image_urls(f"<sean>: check {url} out") == expected


def test_duplicate_links_in_one_message_are_collapsed():
    """The same image posted twice in one breath is one image, not two."""
    assert BaseLLMClient.image_urls(f"<sean>: {IMAGE} lol {IMAGE}") == [IMAGE]


def test_quoted_image_url_is_still_detected():
    """
    Quoting the image you're asking about is the natural way to ask, so the link itself must
    still parse — the quote gate that would exclude it lives in `fetchable_hosts`, not here.
    """
    quoted = f"@bro `<sean>: {IMAGE}` what is this pic"
    assert BaseLLMClient.image_urls(quoted) == [IMAGE]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_prompt_carrying_its_own_image_needs_no_intent(client_class):
    """A link in the prompt is an explicit ask, so it skips the "is this about an image" gate."""
    client = client_class()
    assert client._vision_images([], f"@bro {IMAGE}") == [IMAGE]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_image_prompt_reaches_back_into_history(client_class):
    """A prompt about an image picks up one somebody else posted earlier."""
    client = client_class()
    messages = history(f"<sean>: {IMAGE}", "<sean>: @bro what is that pic")
    assert client._vision_images(messages, "@bro what is that pic") == [IMAGE]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_unrelated_prompt_ignores_images_in_history(client_class):
    """A gif six lines up has nothing to do with "who won the derby"."""
    client = client_class()
    messages = history(f"<sean>: {GIF}", "<sean>: @bro who won the derby")
    assert client._vision_images(messages, "@bro who won the derby") == []


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_image_prompt_with_no_image_in_history_attaches_nothing(client_class):
    """Asking about a picture nobody posted must not invent one."""
    client = client_class()
    messages = history("<sean>: @bro what is that pic")
    assert client._vision_images(messages, "@bro what is that pic") == []


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_newest_images_win_and_are_capped(client_class):
    """Only the most recent `VISION_MAX_IMAGES` are kept, oldest of those first."""
    client = client_class()
    urls = [f"https://i.imgur.com/{n}.png" for n in range(4)]
    messages = history(*[f"<sean>: {url}" for url in urls], "<sean>: @bro describe this")
    assert client._vision_images(messages, "@bro describe this") == urls[-client.VISION_MAX_IMAGES :]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_missing_chat_message_never_selects_images(client_class):
    """Without the triggering message there is no gate to apply, so vision stays off."""
    client = client_class()
    messages = history(f"<sean>: {IMAGE}")
    assert client._vision_images(messages, None) == []


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_a_repost_moves_an_image_back_to_newest(client_class):
    """An image posted early and reposted later is recent again, and survives the cap."""
    client = client_class()
    old_image, new_image = "https://i.imgur.com/old.png", "https://i.imgur.com/new.png"
    messages = history(
        f"<sean>: {old_image}",
        f"<bob>: {new_image}",
        f"<sean>: {old_image} again",
        "<sean>: @bro describe this pic",
    )
    # Without the move-to-newest, the cap would have dropped the reposted image.
    assert client._vision_images(messages, "@bro describe this pic") == [new_image, old_image]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_own_link_wins_over_older_images_in_history(client_class):
    """The image in the prompt is the ask; an older one in history must not crowd it out."""
    client = client_class()
    messages = history(f"<bob>: {GIF}", f"<sean>: @bro what is {IMAGE}")
    assert client._vision_images(messages, f"@bro what is {IMAGE}") == [IMAGE]


@pytest.mark.parametrize("client_class", LLM_CLIENTS.values())
def test_already_multimodal_history_entries_are_skipped(client_class):
    """A caller who pre-built content parts must not crash the image scan."""
    client = client_class()
    messages = [
        {"role": "user", "content": [{"type": "text", "text": f"<bob>: {IMAGE}"}]},
        {"role": "user", "content": "<sean>: @bro what is that pic"},
    ]
    assert client._vision_images(messages, "@bro what is that pic") == []
