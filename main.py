"""Bot application entry point."""
from broiestbot import join_rooms
from config import (
    CHATANGO_ROOMS,
    CHATANGO_TEST_ROOM,
    ENVIRONMENT,
)
from logger import LOGGER


def run():
    """Initialize bot depending on environment."""
    if ENVIRONMENT == "production":
        LOGGER.info(f'Joining {", ".join(CHATANGO_ROOMS)}')
        join_rooms(CHATANGO_ROOMS)
    else:
        LOGGER.info("Starting in dev mode...")
        join_rooms([CHATANGO_TEST_ROOM])


if __name__ == "__main__":
    run()
