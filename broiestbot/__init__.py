"""Initialize bot."""
from datadog import initialize

from broiestbot.bot import Bot
from config import CHATANGO_ROOMS, CHATANGO_TEST_ROOM, CHATANGO_USERS, ENVIRONMENT


def join_rooms():
    """
    Create bot instance for single Chatango room.
    """
    if ENVIRONMENT == "development":
        start_bot_development_mode(
            CHATANGO_USERS["BROIESTBRO"]["USERNAME"],
            CHATANGO_USERS["BROIESTBRO"]["PASSWORD"],
        )
    else:
        start_bot_production_mode(
            CHATANGO_USERS["BROIESTBRO"]["USERNAME"],
            CHATANGO_USERS["BROIESTBRO"]["PASSWORD"],
        )


def start_bot_development_mode(user: str, password: str):
    """
    Initialize bot in development room for testing purposes.

    :param str user: Chatango username to authenticate as.
    :param str password: Chatango password for authentication.
    """
    Bot.easy_start(rooms=[CHATANGO_TEST_ROOM], name=user, password=password)


def start_bot_production_mode(user: str, password: str):
    """
    Join all production rooms.

    :param str user: Chatango username to authenticate as.
    :param str password: Chatango password for authentication.
    """
    options = {"statsd_host": "127.0.0.1", "statsd_port": 8125}
    initialize(**options)
    print(f'Joining {", ".join(CHATANGO_ROOMS)}')
    Bot.easy_start(rooms=[CHATANGO_ROOMS], name=user, password=password)
