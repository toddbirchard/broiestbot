"""Tests for privilege detection & the moderation actions gated behind it."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from broiestbot.moderation.phrases import ban_word
from broiestbot.moderation.privileges import (
    PrivilegeLevel,
    bot_is_moderator,
    bot_privilege_level,
)

TEST_ROOM = "lmaolove2"


def make_room(privilege_level: int = PrivilegeLevel.MODERATOR) -> MagicMock:
    room = MagicMock()
    room.name = TEST_ROOM
    room.user = MagicMock()
    room.get_level = MagicMock(return_value=privilege_level)
    room.delete_message = AsyncMock(return_value=privilege_level >= PrivilegeLevel.MODERATOR)
    room.send_message = AsyncMock()
    return room


# ---------------------------------------------------------------------------
# bot_privilege_level / bot_is_moderator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "level, expected",
    [
        (0, PrivilegeLevel.USER),
        (1, PrivilegeLevel.MODERATOR),
        (2, PrivilegeLevel.ADMIN),
        (3, PrivilegeLevel.OWNER),
    ],
)
def test_privilege_level_maps_room_levels(level: int, expected: PrivilegeLevel):
    assert bot_privilege_level(make_room(privilege_level=level)) is expected


@pytest.mark.parametrize("level, expected", [(0, False), (1, True), (2, True), (3, True)])
def test_bot_is_moderator_requires_mod_or_higher(level: int, expected: bool):
    assert bot_is_moderator(make_room(privilege_level=level)) is expected


def test_privilege_level_defaults_to_user_before_handshake_completes():
    """A room whose session hasn't resolved a user yet has no privileges to report."""
    room = make_room()
    room.user = None

    assert bot_privilege_level(room) is PrivilegeLevel.USER
    assert bot_is_moderator(room) is False


def test_privilege_level_defaults_to_user_on_unexpected_level():
    """An unrecognized level must fail closed rather than raise into the message handler."""
    room = make_room()
    room.get_level = MagicMock(return_value=99)

    assert bot_privilege_level(room) is PrivilegeLevel.USER


def test_privilege_level_defaults_to_user_when_lookup_raises():
    room = make_room()
    room.get_level = MagicMock(side_effect=AttributeError("no session"))

    assert bot_privilege_level(room) is PrivilegeLevel.USER


# ---------------------------------------------------------------------------
# ban_word
# ---------------------------------------------------------------------------


class TestBanWord:
    def test_deletes_and_warns_as_moderator(self):
        room = make_room()
        message = MagicMock()

        asyncio.run(ban_word(room, message, "offender"))

        room.delete_message.assert_awaited_once_with(message)
        room.send_message.assert_awaited_once()

    def test_deletes_without_warning_when_silent(self):
        room = make_room()
        message = MagicMock()

        asyncio.run(ban_word(room, message, "offender", silent=True))

        room.delete_message.assert_awaited_once_with(message)
        room.send_message.assert_not_called()

    def test_is_a_noop_without_mod_privileges(self):
        """Scolding a user over a message the bot can't delete is noise it can't back up."""
        room = make_room(privilege_level=PrivilegeLevel.USER)
        message = MagicMock()

        asyncio.run(ban_word(room, message, "offender"))

        room.delete_message.assert_not_called()
        room.send_message.assert_not_called()

    def test_does_not_warn_when_deletion_is_rejected(self):
        room = make_room()
        room.delete_message = AsyncMock(return_value=False)
        message = MagicMock()

        asyncio.run(ban_word(room, message, "offender"))

        room.delete_message.assert_awaited_once_with(message)
        room.send_message.assert_not_called()
