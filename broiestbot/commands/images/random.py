"""Fetch meme images."""

from random import randint

from emoji import emojize

from logger import LOGGER


def random_image(message: str) -> str:
    """
    Select a random image from a fixed set associated with a command.
    NOTE: This is a legacy command which should later be replaced with `fetch_image_from_gcs`.

    :param str message: Query matching a command to set a random image from a set.

    :returns: str
    """
    try:
        image_list = message.replace(" ", "").split(";")
        random_pic = image_list[randint(0, len(image_list) - 1)]
        return random_pic
    except ValueError as e:
        LOGGER.exception(f"ValueError when fetching random image for `{message}`: {e}")
        return emojize(":warning: omfg bot just broke wtf did u do :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching random image for `{message}`: {e}")
        return emojize(":warning: o shit i broke im a trash bot :warning:", language="en")
