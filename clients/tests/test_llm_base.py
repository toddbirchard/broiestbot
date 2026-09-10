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
