"""Tests for `@` mention detection which routes a message to the LLM."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from broiestbot.bot import Bot
from config import (
    CHATANGO_BOT_MENTION_REGEX,
    CHATANGO_BOT_NICKNAME,
    CHATANGO_BOT_USERNAME,
)

MENTIONS = [
    f"@{CHATANGO_BOT_NICKNAME}",
    f"@{CHATANGO_BOT_NICKNAME.upper()}",
    f"@{CHATANGO_BOT_NICKNAME.capitalize()}",
    f"@{CHATANGO_BOT_USERNAME}",
    f"@{CHATANGO_BOT_USERNAME.upper()}",
    f"@{CHATANGO_BOT_USERNAME.capitalize()}",
    "@BrOiEsTbOt",
]

NON_MENTIONS = [
    "no mention here",
    "bro without an at sign",
    "broiestbot without an at sign",
    "@brotherhood of the traveling pants",
    "@bros",
    "@bro1",
    "@broiestbots",
    "@broiestbro",  # a different bot entirely
    "@",
]


@pytest.mark.parametrize("mention", MENTIONS)
def test_regex_matches_mentions(mention: str):
    """Both the nickname & username are recognized regardless of casing."""
    assert CHATANGO_BOT_MENTION_REGEX.search(f"{mention} what's the score") is not None


@pytest.mark.parametrize("chat_message", NON_MENTIONS)
def test_regex_ignores_non_mentions(chat_message: str):
    """Names which merely start with the bot's name are not mentions."""
    assert CHATANGO_BOT_MENTION_REGEX.search(chat_message) is None


@pytest.mark.parametrize(
    "chat_message",
    [
        f"hey @{CHATANGO_BOT_NICKNAME}, who won",
        f"who won @{CHATANGO_BOT_USERNAME.upper()}",
        f"@{CHATANGO_BOT_NICKNAME.capitalize()}!",
        f"@{CHATANGO_BOT_USERNAME}?",
    ],
)
def test_regex_matches_mid_message(chat_message: str):
    """A mention is honored anywhere in a message & when followed by punctuation."""
    assert CHATANGO_BOT_MENTION_REGEX.search(chat_message) is not None


@pytest.fixture
def bot() -> Bot:
    return Bot(username=CHATANGO_BOT_USERNAME, password="hunter2", rooms=[])


@pytest.fixture
def room() -> MagicMock:
    room = MagicMock()
    room.name = "__pytest_room__"
    room.history = []
    room.send_message = AsyncMock()
    return room


@pytest.fixture
def message() -> MagicMock:
    message = MagicMock()
    message.ip = "203.0.113.1"  # TEST-NET-3, documentation-only range
    message.user = MagicMock()
    message.user.name = "__pytest__user1"
    return message


def dispatch(bot: Bot, room: MagicMock, message: MagicMock, chat_message: str) -> tuple[AsyncMock, AsyncMock]:
    """
    Run `on_message` with every DB/network side effect stubbed out.

    :returns: The patched `_respond_llm_prompt` & `_process_phrase` mocks.
    """
    message.body = chat_message
    with (
        patch("broiestbot.bot.check_blacklisted_users", new=AsyncMock()),
        patch("broiestbot.bot.ban_daddy_anons", new=AsyncMock()),
        patch("broiestbot.bot.persist_user_data", new=AsyncMock()),
        patch("broiestbot.bot.persist_chat_logs", new=AsyncMock()),
        patch.object(Bot, "_respond_llm_prompt", new=AsyncMock()) as llm_prompt,
        patch.object(Bot, "_process_phrase", new=AsyncMock()) as process_phrase,
    ):
        asyncio.run(bot.on_message(room, message))
    return llm_prompt, process_phrase


@pytest.mark.parametrize("mention", MENTIONS)
def test_mention_triggers_llm_response(bot, room, message, mention: str):
    """Any casing of either bot name routes the message to the LLM."""
    llm_prompt, process_phrase = dispatch(bot, room, message, f"{mention} what's the score")
    llm_prompt.assert_awaited_once_with(message.user.name, room)
    process_phrase.assert_not_awaited()


@pytest.mark.parametrize("chat_message", NON_MENTIONS)
def test_non_mention_falls_through_to_phrase(bot, room, message, chat_message: str):
    """Messages without a mention keep falling through to phrase matching."""
    llm_prompt, process_phrase = dispatch(bot, room, message, chat_message)
    llm_prompt.assert_not_awaited()
    process_phrase.assert_awaited_once()
