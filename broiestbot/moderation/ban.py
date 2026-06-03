"""Ban a user from a room and delete their chat history."""

from chatango import Room, RoomMessage
from logger import LOGGER


async def ban_user(room: Room, message: RoomMessage) -> None:
    """
    Ban a user and delete the triggering message.

    :param Room room: Chatango room object.
    :param RoomMessage message: User submitted message.

    :returns: None
    """
    LOGGER.warning(f"BANNED user: username={message.user.name} ip={message.ip}")
    await room.ban_message(message)
