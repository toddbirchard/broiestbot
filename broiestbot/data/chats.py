"""Persist chat logs."""

from logger import LOGGER
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import PERSIST_CHAT_DATA
from database import Session
from database.models import Chat


def persist_chat_logs(user_name: str, room_name: str, chat_message: str, bot_username: str) -> None:
    """
    Persist chat log record.

    :param str user_name: Chatango username of chatter.
    :param str room_name: Chatango room where chat occurred.
    :param str chat_message: Content of the chat message.
    :param str bot_username: Name of the account currently operating the bot.

    :returns: None
    """
    try:
        if not PERSIST_CHAT_DATA or bot_username not in ("broiestbro", "broiestbot"):
            return
        with Session.begin() as db:
            db.add(Chat(username=user_name, room=room_name, message=chat_message))
        return
    except IntegrityError as e:
        LOGGER.warning(f"Failed to save duplicate chat entry: {e}")
    except SQLAlchemyError as e:
        LOGGER.warning(f"SQLAlchemyError persisting chat from {user_name}: {e}")
    except Exception as e:
        LOGGER.warning(f"Unexpected error persisting chat from {user_name}: {e}")
