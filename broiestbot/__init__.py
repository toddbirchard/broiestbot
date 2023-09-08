"""Initialize bot."""
from typing import List

from broiestbot.bot import Bot
from config import CHATANGO_USERS


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
