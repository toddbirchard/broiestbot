"""Commands for NSFW images."""

from emoji import emojize

from clients import rgifs
from logger import LOGGER


def fetch_nsfw_gif(query: str, username: str) -> str:
    """
    Fetch a random NSFW GIF from RedGifs based on the query.

    :param str query: Search query for the GIF.
    :param str username: Sick degenerate user requesting the GIF.

    :returns: str
    """
    is_night = rgifs.is_after_dark()
    LOGGER.info(f"Is it after dark? {is_night}")
    if True:
        LOGGER.info(f"Getting NSFW GIF for user {username} with query: `{query}`...")
        img = rgifs.get_random_gif(query)
        LOGGER.info(f"NSFW query `{query}` returned: {img}")
        if img and img.urls.sd:
            return img.urls.sd
        return emojize(f" <b>:warning: No results found for '{query}' :warning:</b>", language="en")
    return "https://i.imgur.com/oGMHkqT.jpg"
