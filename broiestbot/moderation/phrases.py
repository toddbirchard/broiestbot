"""Delete chats containing blacklisted phrases."""

from chatango import Room, RoomMessage

from .privileges import bot_is_moderator


async def ban_word(room: Room, message: RoomMessage, user_name: str, silent=False) -> None:
    """
    Delete chat containing banned word and warn offending user.

    No-op in rooms where the bot isn't a moderator: without the power to delete the
    message, scolding the user is noise the bot can't back up.

    :param Room room: Current Chatango room object.
    :param RoomMessage message: Message sent by user.
    :param str user_name: User responsible for triggering command.
    :param bool silent: Whether offending user should be warned.

    :returns: None
    """
    if not bot_is_moderator(room):
        return
    deleted = await room.delete_message(message)
    if deleted and silent is not True:
        await room.send_message(f"DO NOT SAY THAT WORD @{user_name.upper()} :@")
