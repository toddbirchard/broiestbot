"""Fetch NSFW images from RedGifs."""

from typing import Optional
from datetime import datetime
from random import randint

import redgifs
from redgifs import Order
from redgifs.models import Image

import pytz
from emoji import emojize


class NSFWRedGifs:
    """Class to handle NSFW image fetching from RedGifs."""

    def __init__(self):
        self.api = redgifs.API()

    def login(self):
        """Login to RedGifs API."""
        try:
            self.api.login()
        except Exception as e:
            print(f"Failed to login to RedGifs: {e}")

    def close(self):
        """Close the RedGifs API session."""
        try:
            self.api.close()
        except Exception as e:
            print(f"Failed to close RedGifs session: {e}")

    @staticmethod
    def is_after_dark() -> bool:
        """
        Determine if current time is within threshold for `After Dark` mode.

        :return: Boolean
        """
        tz = pytz.timezone("America/New_York")
        now = datetime.now(tz=tz)
        start_time = datetime(year=now.year, month=now.month, day=now.day, hour=0, tzinfo=now.tzinfo)
        end_time = datetime(year=now.year, month=now.month, day=now.day, hour=5, tzinfo=now.tzinfo)
        if start_time > now and now < end_time:
            return True
        return False

    def get_random_gif(self, query: str) -> Optional[Image]:
        """
        Fetch a special kind of gif, if you know what I mean ;).

        :param str query: Search query for the GIF.

        :returns: str
        """
        try:
            self.login()
            rand = randint(0, 15)
            results = self.api.search(query, order=Order.trending, count=15, page=1)
            if results.total == 0:
                return emojize(f":warning: No results found for '{query}' :warning:", language="en")
            if results.total < rand:
                rand = randint(0, results.total -1)
            img = results.gifs[rand]
            return img
        except Exception as e:
            print(f"Unexpected error while attempting to fetch NSFW gif: {e}")
        finally:
            self.close()
