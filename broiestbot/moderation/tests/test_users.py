"""Tests for anon/daddylive ban logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from broiestbot.moderation.privileges import PrivilegeLevel
from broiestbot.moderation.users import (
    ban_daddy_anons,
    check_blacklisted_users,
    is_user_anon,
)

TEST_ROOM = "lmaolove2"


def make_room(name: str = TEST_ROOM, privilege_level: int = PrivilegeLevel.MODERATOR) -> MagicMock:
    """Build a room in which the bot holds `privilege_level` (mod by default)."""
    room = MagicMock()
    room.name = name
    room.user = MagicMock()
    room.get_level = MagicMock(return_value=privilege_level)
    room.ban_message = AsyncMock(return_value=privilege_level >= PrivilegeLevel.MODERATOR)
    room.clear_user = AsyncMock(return_value=privilege_level >= PrivilegeLevel.MODERATOR)
    room.ban_user = AsyncMock(return_value=privilege_level >= PrivilegeLevel.MODERATOR)
    room.send_message = AsyncMock()
    return room


def make_user(name: str) -> MagicMock:
    user = MagicMock()
    user.name = name
    # Chatango sets `isanon` itself; mirror it from the name so a bare MagicMock
    # attribute doesn't make every test user look like an anon.
    user.isanon = is_user_anon(name)
    return user


def make_message(body: str, ip: str = "203.0.113.1") -> MagicMock:
    message = MagicMock()
    message.body = body
    message.ip = ip
    return message


# ---------------------------------------------------------------------------
# is_user_anon
# ---------------------------------------------------------------------------


def test_is_user_anon_true_for_anon_prefixed_name():
    assert is_user_anon("anon8329") is True


def test_is_user_anon_true_for_hash_name():
    assert is_user_anon("#somebody") is True


def test_is_user_anon_false_for_regular_username():
    assert is_user_anon("regularuser123") is False


def test_is_user_anon_false_for_whitelisted_exception():
    assert is_user_anon("anon0937") is False


# ---------------------------------------------------------------------------
# ban_daddy_anons
# ---------------------------------------------------------------------------


class TestBanDaddyAnons:
    def test_bans_anon_posting_daddylive_link_single_line(self):
        """Reproduces the reported anon8329 message: a single-line daddylive plug."""
        room = make_room()
        user = make_user("anon8329")
        message = make_message(
            "🏆 Fifa World Cup 2026, ⚽ Soccer, 🏏 Cricket, 🏀 NBA, 🏈 NFL, 🎾 Tennis & 🏍️ MotoGP "
            "— Streaming Live: daddylive.nl"
        )

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.clear_user.assert_awaited_once_with(user)
        room.ban_user.assert_awaited_once_with(user.name)
        room.send_message.assert_awaited_once()

    def test_bans_anon_posting_daddylive_link_multiline(self):
        """
        Regression test: the daddylive link on its own line (real newlines, as Chatango
        sends multi-line messages) used to bypass the ban because the old regex used
        re.match with a leading (.+)? that can't cross a newline.
        """
        room = make_room()
        user = make_user("anon8329")
        message = make_message(
            "🏆 Fifa World Cup 2026\n⚽ Soccer\n🏏 Cricket\n🏀 NBA\n🏈 NFL\n🎾 Tennis\n"
            "🏍️ MotoGP\nStreaming Live: daddylive.nl"
        )

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.clear_user.assert_awaited_once_with(user)
        room.ban_user.assert_awaited_once_with(user.name)

    def test_does_not_ban_non_anon_user_posting_daddylive_link(self):
        room = make_room()
        user = make_user("regularuser123")
        message = make_message("Streaming Live: daddylive.nl")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.ban_message.assert_not_called()
        room.clear_user.assert_not_called()
        room.ban_user.assert_not_called()

    def test_does_not_ban_anon_user_without_daddylive_link(self):
        room = make_room()
        user = make_user("anon8329")
        message = make_message("just chatting about the game tonight")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.ban_message.assert_not_called()
        room.clear_user.assert_not_called()
        room.ban_user.assert_not_called()

    def test_does_not_ban_outside_configured_rooms(self):
        room = make_room(name="some-other-room")
        user = make_user("anon8329")
        message = make_message("Streaming Live: daddylive.nl")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.ban_message.assert_not_called()
        room.clear_user.assert_not_called()
        room.ban_user.assert_not_called()

    def test_bans_anon_for_alternate_daddylive_domain(self):
        """Different TLD/subdomain variations should still be caught."""
        room = make_room()
        user = make_user("anon1111")
        message = make_message("watch it here: daddyliveall.sx/6")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.ban_user.assert_awaited_once_with(user.name)


# ---------------------------------------------------------------------------
# Non-moderator rooms
# ---------------------------------------------------------------------------


class TestNonModeratorRooms:
    """
    In rooms where the bot is a plain user, moderation must degrade quietly: no ban
    attempts, and — critically — no taunts announcing bans the bot cannot deliver.
    """

    def test_ban_daddy_anons_is_a_noop_without_mod_privileges(self):
        room = make_room(privilege_level=PrivilegeLevel.USER)
        user = make_user("anon8329")
        message = make_message("Streaming Live: daddylive.nl")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.clear_user.assert_not_called()
        room.ban_user.assert_not_called()
        room.send_message.assert_not_called()

    def test_ban_daddy_anons_stays_silent_when_the_ban_is_rejected(self):
        """A mod-level bot whose ban is refused by the server must not taunt either."""
        room = make_room()
        room.ban_user = AsyncMock(return_value=False)
        user = make_user("anon8329")
        message = make_message("Streaming Live: daddylive.nl")

        with patch("broiestbot.moderation.users.CHATANGO_DADDY_ANON_BAN_ROOMS", [TEST_ROOM]):
            asyncio.run(ban_daddy_anons(room, user, message))

        room.ban_user.assert_awaited_once_with(user.name)
        room.send_message.assert_not_called()

    def test_check_blacklisted_users_is_a_noop_without_mod_privileges(self):
        room = make_room(privilege_level=PrivilegeLevel.USER)
        message = make_message("hello")
        message.user = make_user("blacklisted_guy")

        with (
            patch("broiestbot.moderation.users.CHATANGO_BLACKLISTED_USERS", ["blacklisted_guy"]),
            patch("broiestbot.moderation.users.CHATANGO_BLACKLIST_ROOMS", [TEST_ROOM]),
        ):
            asyncio.run(check_blacklisted_users(room, "blacklisted_guy", message))

        room.ban_message.assert_not_called()
        room.send_message.assert_not_called()

    def test_check_blacklisted_users_taunts_only_after_a_successful_ban(self):
        room = make_room()
        message = make_message("hello")
        message.user = make_user("blacklisted_guy")

        with (
            patch("broiestbot.moderation.users.CHATANGO_BLACKLISTED_USERS", ["blacklisted_guy"]),
            patch("broiestbot.moderation.users.CHATANGO_BLACKLIST_ROOMS", [TEST_ROOM]),
        ):
            asyncio.run(check_blacklisted_users(room, "blacklisted_guy", message))

        room.ban_message.assert_awaited_once_with(message)
        room.send_message.assert_awaited_once()

    def test_check_blacklisted_users_stays_silent_when_the_ban_is_rejected(self):
        room = make_room()
        room.ban_message = AsyncMock(return_value=False)
        message = make_message("hello")
        message.user = make_user("blacklisted_guy")

        with (
            patch("broiestbot.moderation.users.CHATANGO_BLACKLISTED_USERS", ["blacklisted_guy"]),
            patch("broiestbot.moderation.users.CHATANGO_BLACKLIST_ROOMS", [TEST_ROOM]),
        ):
            asyncio.run(check_blacklisted_users(room, "blacklisted_guy", message))

        room.ban_message.assert_awaited_once_with(message)
        room.send_message.assert_not_called()
