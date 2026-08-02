"""Perform Giphy query to fetch randomized top trending image."""

from random import randint
from typing import Optional

from aiohttp import ClientError, ClientResponseError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from config import GIPHY_API_KEY, KLIPY_API_KEY


async def giphy_image_search(query: str) -> Optional[str]:
    """
    Perform a gif image and return a random result from the top-20 images.

    :param str query: Query passed to Giphy to find gif.

    :returns: Optional[str]
    """
    rand = randint(0, 15)
    params = {
        "api_key": GIPHY_API_KEY,
        "q": query,
        "limit": 1,
        "offset": rand,
        "rating": "r",
        "lang": "en",
    }
    try:
        session = await get_http_session()
        async with session.get("https://api.giphy.com/v1/gifs/search", params=params) as resp:
            images = (await resp.json(content_type=None))["data"]
        if len(images) == 0:
            return None
        image = images[0]["images"]["downsized"].get("url")
        if image is not None:
            return image
    except ClientResponseError as e:
        LOGGER.error(f"Giphy failed to fetch `{query}`: {e}")
        return emojize(":warning: yoooo giphy is down rn lmao :warning:", language="en")
    except (ClientError, ValueError) as e:
        LOGGER.error(f"Error while fetching Giphy `{query}`: {e}")
        return emojize(":warning: holy sht u broke the bot im telling bro :warning:", language="en")
    except Exception as e:
        LOGGER.error(f"Giphy unexpected error for `{query}`: {e}")
        return emojize(":warning: AAAAAA I'M BROKEN WHAT DID YOU DO :warning:", language="en")


async def klipy_image_search(query: str) -> Optional[str]:
    """
    Perform a gif image and return a random result from the top 10 images.

    :param str query: Query passed to Klipy to find gif.

    :returns: Optional[str]
    """
    params = {
        "q": query,
        "page": 1,
        "per_page": 10,
    }
    try:
        session = await get_http_session()
        async with session.get(f"https://api.klipy.com/api/v1/{KLIPY_API_KEY}/gifs/search", params=params) as resp:
            resp.raise_for_status()
            if resp.status == 204:
                return None
            images = (await resp.json(content_type=None))["data"]["data"]
        if len(images) > 0:
            rand = randint(0, len(images) - 1)
            image = images[rand]["file"]["md"]["gif"].get("url")
            if image is not None:
                return image
    except ClientResponseError as e:
        LOGGER.error(f"Klipy failed to fetch `{query}`: {e}")
        return emojize(":warning: yoooo gif API is down rn lmao :warning:", language="en")
    except (ClientError, ValueError) as e:
        LOGGER.error(f"Error while fetching Klipy `{query}`: {e}")
        return emojize(":warning: holy sht u broke the bot im telling bro :warning:", language="en")
    except Exception as e:
        LOGGER.error(f"Klipy unexpected error for `{query}`: {e}")
        return emojize(":warning: AAAAAA I'M BROKEN WHAT DID YOU DO :warning:", language="en")
