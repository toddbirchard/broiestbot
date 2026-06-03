"""Moderate or ban problematic users in Chatango rooms."""

import re
from typing import Optional

from chatango import Room, RoomMessage
from emoji import emojize
from logger import LOGGER

from config import (
    CHATANGO_BANNED_IPS,
    CHATANGO_BLACKLIST_ROOMS,
    CHATANGO_BLACKLISTED_USERS,
    CHATANGO_DADDY_ANON_BAN_ROOMS,
    CHATANGO_EGGSER_USERNAME_WHITELIST,
    CHATANGO_IGNORED_IPS,
    CHATANGO_IGNORED_USERS,
)

from .ban import ban_user


async def check_blacklisted_users(room: Room, user_name: str, message: RoomMessage) -> None:
    """
    Ban and delete chat history of blacklisted user.

    :param Room room: Chatango room in which user appeared.
    :param str user_name: Chatango username to validate against blacklist.
    :param RoomMessage message: User submitted message.

    :returns: None
    """
    if (
        user_name in CHATANGO_BLACKLISTED_USERS or "shaw" in user_name or message.ip in CHATANGO_IGNORED_IPS
    ) and room.name.lower() in CHATANGO_BLACKLIST_ROOMS:
        reply = emojize(f":wave: @{user_name} lmao pz fgt have fun being banned forever :wave:", language="en")
        LOGGER.warning(f"BANNED user: username={message.user.name} ip={message.ip}")
        await room.send_message(reply)
        await room.ban_message(message)
    elif (
        message.ip is not None
        and message.ip in CHATANGO_BANNED_IPS
        and message.user.name.lower() not in CHATANGO_EGGSER_USERNAME_WHITELIST
    ):
        await ban_user(room, message)
    elif is_user_anon(user_name) and "raiders" in message.body.lower():
        await ban_user(room, message)
    elif is_user_anon(user_name) and "tigger" in message.body.lower():
        await ban_user(room, message)
    elif is_user_anon(user_name) and "wordle" in message.body.lower():
        await ban_user(room, message)
    elif "wordle" in message.body.lower() and "tomorrow" in message.body.lower():
        await ban_user(room, message)
    elif "is the wordle" in message.body.lower():
        await ban_user(room, message)


async def ban_daddy_anons(room: Room, user_name: str, message: RoomMessage) -> None:
    """
    Ban and delete chat history of anons who post from Daddy.

    :param Room room: Chatango room in which user appeared.
    :param str user_name: Chatango username to validate against blacklist.
    :param RoomMessage message: User submitted message.

    :returns: None
    """
    if room.name.lower() in CHATANGO_DADDY_ANON_BAN_ROOMS:
        if is_user_anon(user_name) and re.match(
            r"(.+)?(https?:\/\/)?([a-zA-Z0-9\-]+\.)?daddylive[a-zA-Z0-9\-\.]*\.[a-zA-Z]{2,}(\/[^\s]*)?", message.body
        ):
            reply = f"👋🏏 @{user_name} lmao have fun being banned forever 🏏👋"
            LOGGER.warning(f"BANNED Daddy anon user: username={user_name} ip={message.ip}")
            await room.send_message(reply)
            await room.ban_message(message)


def ignored_user(user_name: str, user_ip: str) -> Optional[str]:
    """
    Ignore commands from users who have had bot privileges revoked.

    :param str user_name: Chatango username to validate against blacklist.
    :param str user_ip: IP address of Chatango user to validate against blacklist.

    :returns: str
    """
    return emojize(
        f":wave: @{user_name} bot privileges REVOKED for acting like a CUNT :wave:",
        language="en",
    )


def is_user_anon(user_name: str) -> bool:
    """
    Check whether user is anon.

    :param str user_name: Chatango username to validate as anon.

    :returns: bool
    """
    if "!anon" in user_name or "#" in user_name:
        return True
    return False
