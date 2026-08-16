"""Ban a user from a room and delete their chat history."""

from chatango import Room, RoomMessage
from logger import LOGGER


async def ban_user(room: Room, message: RoomMessage) -> bool:
    """
    Ban a user and delete the triggering message.

    :param Room room: Chatango room object.
    :param RoomMessage message: User submitted message.

    :returns: bool
    """
    banned = await room.ban_message(message)
    if banned:
        LOGGER.warning(f"BANNED user: username={message.user.name} ip={message.ip}")
    else:
        LOGGER.warning(
            f"Could not ban user (bot lacks mod privileges in `{room.name}`): "
            f"username={message.user.name} ip={message.ip}"
        )
    return banned
