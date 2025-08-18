"""Initialize bot."""

import asyncio
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
    LOGGER.info("Starting bot...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = configure_bot()
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt as e:
        LOGGER.error(f"[KeyboardInterrupt] Killed bot: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while running bot: {e}")
    finally:
        loop.stop()
        loop.close()


def configure_bot() -> Bot:
    """
    Connect bot for each Chatango room.

    :returns: Bot configured for given environment.
    """
    if ENVIRONMENT == "production":
        LOGGER.info(f'Joining {", ".join(CHATANGO_ROOMS)}')
        return Bot(
            CHATANGO_USERS["BROIESTBRO"]["USERNAME"], CHATANGO_USERS["BROIESTBRO"]["PASSWORD"], CHATANGO_ROOMS, pm=False
        )
    LOGGER.info("Starting in dev mode...")
    return Bot(
        CHATANGO_USERS["BROIESTBRO"]["USERNAME"], CHATANGO_USERS["BROIESTBRO"]["PASSWORD"], CHATANGO_TEST_ROOM, pm=False
    )
