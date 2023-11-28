"""Initialize bot."""
from typing import List

from broiestbot.bot import Bot
from config import (
    CHATANGO_USERS,
    CHATANGO_ROOMS,
    CHATANGO_TEST_ROOM,
    ENVIRONMENT,
)
from logger import LOGGER


def start_bot():
    """Initialize bot depending on environment."""
    try:
        username = CHATANGO_USERS["BROIESTBRO"]["USERNAME"]
        password = CHATANGO_USERS["BROIESTBRO"]["PASSWORD"]
        if ENVIRONMENT == "production":
            rooms = ", ".join(CHATANGO_ROOMS)
            Bot.easy_start(rooms, username, password)
            LOGGER.info(f'Joining {", ".join(CHATANGO_ROOMS)}')
        else:
            rooms = [CHATANGO_TEST_ROOM]
            Bot.easy_start(rooms, username, password)
            LOGGER.info(f'Joining {", ".join(CHATANGO_ROOMS)} in dev mode...')
    except KeyboardInterrupt as e:
        LOGGER.warning(f"KeyboardInterrupt while joining Chatango room: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected exception while joining Chatango room: {e}")
