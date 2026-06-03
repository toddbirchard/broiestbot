"""Delete chats containing blacklisted phrases."""

from chatango import Room, RoomMessage


async def ban_word(room: Room, message: RoomMessage, user_name: str, silent=False) -> None:
    """
    Delete chat containing banned word and warn offending user.

    :param Room room: Current Chatango room object.
    :param RoomMessage message: Message sent by user.
    :param str user_name: User responsible for triggering command.
    :param bool silent: Whether offending user should be warned.

    :returns: None
    """
    await room.delete_message(message)
    if silent is not True:
        await room.send_message(f"DO NOT SAY THAT WORD @{user_name.upper()} :@")
