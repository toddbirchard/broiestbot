"""Perform Giphy query to fetch randomized top trending image."""

from random import randint
from typing import Optional

import requests
from emoji import emojize
from requests.exceptions import HTTPError

from config import GIPHY_API_KEY, KLIPY_API_KEY, HTTP_REQUEST_TIMEOUT
from logger import LOGGER


def giphy_image_search(query: str) -> Optional[str]:
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
        resp = requests.get("https://api.giphy.com/v1/gifs/search", params=params, timeout=HTTP_REQUEST_TIMEOUT)
        images = resp.json()["data"]
        if len(images) == 0:
            return None
        image = resp.json()["data"][0]["images"]["downsized"].get("url")
        if image is not None:
            return image
    except HTTPError as e:
        LOGGER.error(f"Giphy failed to fetch `{query}`: {e.response.content}")
        return emojize(":warning: yoooo giphy is down rn lmao :warning:", language="en")
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching Giphy `{query}`: {e}")
        return emojize(":warning: holy sht u broke the bot im telling bro :warning:", language="en")
    except Exception as e:
        LOGGER.error(f"Giphy unexpected error for `{query}`: {e}")
        return emojize(":warning: AAAAAA I'M BROKEN WHAT DID YOU DO :warning:", language="en")


def klipy_image_search(query: str) -> Optional[str]:
    """
    Perform a gif image and return a random result from the top 10 images.

    :param str query: Query passed to Klipy to find gif.

    :returns: Optional[str]
    """
    params = {
        "q": query,
        "limit": 1,
        "per_page": 10,
    }
    try:
        resp = requests.get(
            f"https://api.klipy.io/v1/gifs/search{KLIPY_API_KEY}/gifs/search",
            params=params,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        images = resp.json()["data"]["data"]
        rand = randint(0, len(images) - 1)
        image = resp.json()["data"]["data"][rand]["file"]["md"]["gif"].get("url")
        LOGGER.info(f"Klipy search for `{query}` returned {len(images)} results. Returning result: {resp.json()['data']['data'][rand]}")
        if image is not None:
            return image
    except HTTPError as e:
        LOGGER.error(f"Klipy failed to fetch `{query}`: {e.response.content}")
        return emojize(":warning: yoooo gif API is down rn lmao :warning:", language="en")
    except ValueError as e:
        LOGGER.error(f"ValueError while fetching Klipy `{query}`: {e}")
        return emojize(":warning: holy sht u broke the bot im telling bro :warning:", language="en")
    except Exception as e:
        LOGGER.error(f"Klipy unexpected error for `{query}`: {e}")
        return emojize(":warning: AAAAAA I'M BROKEN WHAT DID YOU DO :warning:", language="en")
