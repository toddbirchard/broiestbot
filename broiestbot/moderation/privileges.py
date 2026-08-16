"""Determine which actions the bot is actually permitted to take in a given room.

Chatango grants moderator powers per-room, and `chatango-lib` already fails soft on
privileged commands: `ban_message`, `ban_user`, `clear_user` & `delete_message` all
check `Room.get_level()` first and return `False` instead of raising when the bot is
a plain user. Checking the same level up front lets the bot skip the moderation path
entirely, rather than announcing punishments it has no power to carry out.

Two other behaviors follow from a room where the bot is not a moderator:
    * `RoomMessage.ip` is an empty string, since Chatango only discloses IPs to mods.
      `persist_user_data` already treats a missing IP as "nothing to persist".
    * A missing IP is expected rather than anomalous, so it is not worth a warning.
"""

from enum import IntEnum

from chatango import Room
from logger import LOGGER


class PrivilegeLevel(IntEnum):
    """Bot's permission level within a room, mirroring `Room.get_level()`."""

    USER = 0
    MODERATOR = 1
    ADMIN = 2
    OWNER = 3


def bot_privilege_level(room: Room) -> PrivilegeLevel:
    """
    Determine the bot's permission level in a room.

    Defaults to `USER` whenever the level can't be determined — a room whose session
    hasn't finished its handshake has no user to look up yet, and assuming the lowest
    privilege keeps the bot from attempting moderation it may not be entitled to.

    :param Room room: Chatango room to check the bot's privileges in.

    :returns: PrivilegeLevel
    """
    try:
        if room.user is None:
            return PrivilegeLevel.USER
        return PrivilegeLevel(room.get_level(room.user))
    except (AttributeError, ValueError, KeyError) as e:
        LOGGER.warning(f"Could not determine bot privilege level in room `{room.name}`, assuming none: {e}")
        return PrivilegeLevel.USER


def bot_is_moderator(room: Room) -> bool:
    """
    Check whether the bot may ban users & delete messages in a room.

    :param Room room: Chatango room to check the bot's privileges in.

    :returns: bool
    """
    return bot_privilege_level(room) >= PrivilegeLevel.MODERATOR
