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
    if ENVIRONMENT == "production":
        LOGGER.info(f'Joining {", ".join(CHATANGO_ROOMS)}')
        join_rooms(CHATANGO_ROOMS)
    else:
        LOGGER.info("Starting in dev mode...")
        join_rooms([CHATANGO_TEST_ROOM])
    return f"Joined {len(CHATANGO_ROOMS)} rooms."


def join_rooms(rooms: List[str]):
    """
    Create bot instance for single Chatango room.

    :param List[str] rooms: Chatango rooms to join.
    """
    while True:
        broiestbot = Bot(
            CHATANGO_USERS["BROIESTBRO"]["USERNAME"],
            CHATANGO_USERS["BROIESTBRO"]["PASSWORD"],
        )
        try:
            for room in rooms:
                broiestbot.join_room(room)
            broiestbot.main()
        except KeyboardInterrupt as e:
            broiestbot.stop()
            print(f"KeyboardInterrupt while joining Chatango room: {e}")
            break
        except Exception as e:
            broiestbot.stop()
            print(f"Unexpected exception while joining Chatango room: {e}")
            break
