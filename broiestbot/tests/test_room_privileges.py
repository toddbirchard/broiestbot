"""Tests for how the bot reports & reacts to its privilege level in a room."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from broiestbot.bot import Bot
from broiestbot.moderation.privileges import PrivilegeLevel
from config import CHATANGO_BOT_USERNAME

TEST_ROOM = "lmaolove2"


def make_room(privilege_level: int = PrivilegeLevel.MODERATOR) -> MagicMock:
    room = MagicMock()
    room.name = TEST_ROOM
    room.user = MagicMock()
    room.get_level = MagicMock(return_value=privilege_level)
    room.send_message = AsyncMock()
    return room


def make_message(ip: str) -> MagicMock:
    message = MagicMock()
    message.ip = ip
    message.body = "hello"
    return message


@pytest.fixture
def bot() -> Bot:
    return Bot(username=CHATANGO_BOT_USERNAME, password="hunter2", rooms=[])


# ---------------------------------------------------------------------------
# _log_message
# ---------------------------------------------------------------------------


class TestLogMessage:
    def test_logs_ip_at_info_when_present(self):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            Bot._log_message(room, "someuser", make_message("203.0.113.1"))

        logger.info.assert_called_once()
        logger.warning.assert_not_called()

    def test_missing_ip_warns_when_the_bot_is_a_moderator(self):
        """Chatango discloses IPs to mods, so a mod without one is genuinely anomalous."""
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            Bot._log_message(room, "someuser", make_message(""))

        logger.warning.assert_called_once()
        logger.info.assert_not_called()

    def test_missing_ip_is_routine_without_mod_privileges(self):
        """A plain-user bot never receives IPs, so this must not warn on every message."""
        room = make_room(privilege_level=PrivilegeLevel.USER)
        with patch("broiestbot.bot.LOGGER") as logger:
            Bot._log_message(room, "someuser", make_message(""))

        logger.info.assert_called_once()
        logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# Privilege announcements
# ---------------------------------------------------------------------------


class TestPrivilegeAnnouncements:
    def test_join_as_moderator_is_logged_as_success(self, bot):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_inited(room))

        logger.success.assert_called_once()
        logger.warning.assert_not_called()

    def test_join_without_privileges_is_logged_as_a_warning(self, bot):
        room = make_room(privilege_level=PrivilegeLevel.USER)
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_inited(room))

        logger.warning.assert_called_once()
        logger.success.assert_not_called()

    def test_bot_being_modded_mid_session_is_logged(self, bot):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_mod_added(room, room.user))

        logger.success.assert_called_once()

    def test_another_user_being_modded_is_ignored(self, bot):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_mod_added(room, MagicMock()))

        logger.success.assert_not_called()

    def test_bot_being_demodded_mid_session_is_logged(self, bot):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_mod_remove(room, room.user))

        logger.warning.assert_called_once()

    def test_another_user_being_demodded_is_ignored(self, bot):
        room = make_room()
        with patch("broiestbot.bot.LOGGER") as logger:
            asyncio.run(bot.on_mod_remove(room, MagicMock()))

        logger.warning.assert_not_called()
