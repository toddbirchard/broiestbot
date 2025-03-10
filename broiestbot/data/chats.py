"""Persist chat logs."""

from database import session
from database.models import Chat
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from config import PERSIST_CHAT_DATA
from logger import LOGGER


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
        if PERSIST_CHAT_DATA and bot_username in ("broiestbro", "broiestbot"):
            session.add(Chat(username=user_name, room=room_name, message=chat_message))
            session.commit()
    except IntegrityError as e:
        LOGGER.warning(f"Failed to save duplicate chat entry: {e}")
    except SQLAlchemyError as e:
        LOGGER.warning(f"SQLAlchemyError occurred while persisting chat data from  {user_name}, `{chat_message}`: {e}")
    except Exception as e:
        LOGGER.warning(f"Unexpected error occurred while persisting chat data from {user_name}, `{chat_message}`: {e}")
