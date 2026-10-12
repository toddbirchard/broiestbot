"""Tests for how `on_message` routes a message to exactly one handler.

`?search` and `!command` messages are fully handled by their own branch. They must not
also fall through to the link-preview/phrase chain, which would cost every command an
extra `phrases` lookup it can never match.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from broiestbot.bot import Bot
from config import CHATANGO_BOT_USERNAME


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


def dispatch(bot: Bot, room: MagicMock, message: MagicMock, chat_message: str, link_preview: str = None) -> dict:
    """
    Run `on_message` with every DB/network side effect stubbed out.

    :returns: dict of the patched handler mocks, keyed by name.
    """
    message.body = chat_message
    with (
        patch("broiestbot.bot.check_blacklisted_users", new=AsyncMock()),
        patch("broiestbot.bot.ban_daddy_anons", new=AsyncMock()),
        patch("broiestbot.bot.persist_user_data", new=AsyncMock()),
        patch("broiestbot.bot.persist_chat_logs", new=AsyncMock()),
        patch("broiestbot.bot.search_youtube_video", return_value=None) as yt_search,
        patch("broiestbot.bot.generate_youtube_video_preview", return_value=None) as yt_preview,
        patch("broiestbot.bot.generate_link_preview", new=AsyncMock(return_value=link_preview)) as link_preview_mock,
        patch.object(Bot, "_process_command", new=AsyncMock()) as process_command,
        patch.object(Bot, "_process_phrase", new=AsyncMock()) as process_phrase,
        patch.object(Bot, "_respond_llm_prompt", new=AsyncMock()) as llm_prompt,
    ):
        asyncio.run(bot.on_message(room, message))
    return {
        "yt_search": yt_search,
        "yt_preview": yt_preview,
        "link_preview": link_preview_mock,
        "process_command": process_command,
        "process_phrase": process_phrase,
        "llm_prompt": llm_prompt,
    }


@pytest.mark.parametrize(
    "chat_message",
    ["!epltable", "!weather philadelphia", "!!cat gif", "!ein"],
)
def test_command_does_not_also_hit_phrase_lookup(bot, room, message, chat_message: str):
    """A `!command` is handled by `_process_command` alone — no redundant phrase query."""
    mocks = dispatch(bot, room, message, chat_message)
    mocks["process_command"].assert_awaited_once()
    mocks["process_phrase"].assert_not_awaited()


def test_youtube_search_does_not_also_hit_phrase_lookup(bot, room, message):
    """A `?query` search is handled on its own branch & stops there."""
    mocks = dispatch(bot, room, message, "?how to fold a fitted sheet")
    mocks["yt_search"].assert_called_once_with("how to fold a fitted sheet")
    mocks["process_phrase"].assert_not_awaited()
    mocks["process_command"].assert_not_awaited()


def test_short_question_mark_message_still_falls_through(bot, room, message):
    """`?` messages too short to be a search keep falling through to phrase matching."""
    mocks = dispatch(bot, room, message, "?!")
    mocks["yt_search"].assert_not_called()
    mocks["process_phrase"].assert_awaited_once()


def test_command_skips_link_preview_chain(bot, room, message):
    """A command carrying a YouTube link is a command, not a link to preview."""
    mocks = dispatch(bot, room, message, "!tune https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    mocks["process_command"].assert_awaited_once()
    mocks["yt_preview"].assert_not_called()
    mocks["process_phrase"].assert_not_awaited()


def test_plain_message_still_reaches_phrase_lookup(bot, room, message):
    """Ordinary chat is unaffected & still falls through to phrase matching."""
    mocks = dispatch(bot, room, message, "anyway that game was rigged")
    mocks["process_command"].assert_not_awaited()
    mocks["process_phrase"].assert_awaited_once()


def test_youtube_link_still_generates_preview(bot, room, message):
    """A bare YouTube link still routes to the preview branch, not phrase matching."""
    mocks = dispatch(bot, room, message, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    mocks["yt_preview"].assert_called_once()
    mocks["process_phrase"].assert_not_awaited()


def test_bot_never_answers_its_own_mention(bot, room, message):
    """A reply quoting `@bro` must not prompt the bot to answer itself — that loop never ends."""
    message.user.name = CHATANGO_BOT_USERNAME
    mocks = dispatch(bot, room, message, '@anon0937 lmao "@bro mock nugs" — write your own material')
    mocks["llm_prompt"].assert_not_awaited()
    mocks["process_phrase"].assert_not_awaited()


def test_bot_s_own_messages_are_still_logged(bot, room, message):
    """Ignoring its own messages stops the bot answering them, not recording them."""
    message.user.name = CHATANGO_BOT_USERNAME
    message.body = "@broiestbot i am trash, sry m8"
    with (
        patch("broiestbot.bot.check_blacklisted_users", new=AsyncMock()),
        patch("broiestbot.bot.ban_daddy_anons", new=AsyncMock()),
        patch("broiestbot.bot.persist_user_data", new=AsyncMock()),
        patch("broiestbot.bot.persist_chat_logs", new=AsyncMock()) as persist_chat_logs,
        patch.object(Bot, "_respond_llm_prompt", new=AsyncMock()) as llm_prompt,
    ):
        asyncio.run(bot.on_message(room, message))
    persist_chat_logs.assert_awaited_once()
    llm_prompt.assert_not_awaited()


def test_users_still_summon_the_llm(bot, room, message):
    """Anybody who isn't a bot still gets an answer."""
    mocks = dispatch(bot, room, message, "@bro who won the derby")
    mocks["llm_prompt"].assert_awaited_once()


def test_other_link_gets_generic_preview(bot, room, message):
    """A link no dedicated handler owns is previewed from its metadata, and still phrase-matched."""
    mocks = dispatch(bot, room, message, "this is wild https://news.example.com/story", link_preview="<b>card</b>")
    mocks["link_preview"].assert_awaited_once_with("this is wild https://news.example.com/story")
    mocks["process_phrase"].assert_awaited_once()
    room.send_message.assert_awaited_once_with("<b>card</b>", use_html=True)


def test_no_generic_preview_sends_nothing(bot, room, message):
    """A link which yields no preview leaves the room alone."""
    dispatch(bot, room, message, "https://news.example.com/story", link_preview=None)
    room.send_message.assert_not_awaited()


def test_youtube_link_skips_generic_preview(bot, room, message):
    """A link owned by a dedicated handler is never previewed twice."""
    mocks = dispatch(bot, room, message, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    mocks["link_preview"].assert_not_awaited()


def test_command_link_skips_generic_preview(bot, room, message):
    """A command carrying a link is a command, not a link to preview."""
    mocks = dispatch(bot, room, message, "!gif https://news.example.com/story")
    mocks["link_preview"].assert_not_awaited()


def test_llm_prompt_link_skips_generic_preview(bot, room, message):
    """`@bro` reads its own links; previewing the same link as well would double up."""
    mocks = dispatch(bot, room, message, "@bro summarize https://news.example.com/story")
    mocks["llm_prompt"].assert_awaited_once()
    mocks["link_preview"].assert_not_awaited()


def test_other_bots_links_not_previewed(bot, room, message):
    """Another bot's links aren't previewed, so two previewing bots can't feed each other."""
    message.user.name = "someotherbot"
    mocks = dispatch(bot, room, message, "https://news.example.com/story")
    mocks["link_preview"].assert_not_awaited()
