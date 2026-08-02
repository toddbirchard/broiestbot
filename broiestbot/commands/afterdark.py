"""Commands only available from 10pm to 5am EST."""

from datetime import datetime
from random import randint
from typing import Optional

import pytz
from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER
from redgifs import Order

from clients import redgifs_client
from config import (
    REDGIFS_ACCESS_KEY,
    REDGIFS_IMAGE_SEARCH_ENDPOINT,
    REDGIFS_TOKEN_ENDPOINT,
)


def is_after_dark() -> bool:
    """
    Determine if current time is within threshold for `After Dark` mode.

    :return: Boolean
    """
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz=tz)
    LOGGER.info(
        f"Current time is {now.hour}. After Dark mode is {'ON' if (now.hour >= 0 and now.hour < 5) else 'OFF'}."
    )
    start_time = datetime(year=now.year, month=now.month, day=now.day, hour=22, tzinfo=now.tzinfo)
    end_time = datetime(year=now.year, month=now.month, day=now.day, hour=5, tzinfo=now.tzinfo)
    if start_time <= now or now > end_time:
        return True
    return False


def fetch_redgifs_gif(query: str, username: str, after_dark_only: bool = False) -> Optional[str]:
    """
    Fetch a special kind of gif, if you know what I mean ;).

    :param str query: Gif search query.
    :param str username: Chatango user who triggered the command.
    :param bool after_dark_only: Whether results should be limited to the `after dark` timeframe.

    :returns: Optional[str]
    """
    try:
        night_mode = is_after_dark()
        if (after_dark_only and night_mode) or after_dark_only is False:
            redgifs_client.login()
            results = redgifs_client.search(search_text=query, order=Order.TRENDING, count=20)
            gifs = results.gifs
            if gifs:
                gif = gifs[randint(0, len(gifs) - 1)]
                url = gif.urls.web_url
                thumbnail = gif.urls.thumbnail
                tags = ", #".join(gif.tags[:5]) if gif.tags else ""
                tag_str = f"#{tags}" if tags else ""
                return f"\n\n\n{thumbnail} \n\n \
                        {url}\n \
                        👍 Likes {gif.likes}\n \
                        👀 Views {gif.views}\n \
                        🏷️ Tags: {tag_str}"
            elif username == "thegreatpizza":
                return "🍕 *h* wow pizza ur taste in lesbians is so dank that I coughldnt find nething sry :( *h* 🍕"
            return f"⚠️ wow @{username} u must b a freak tf r u even searching foughr jfc ⚠️"
        return "https://i.imgur.com/oGMHkqT.jpg"
    except Exception as e:
        LOGGER.warning(f"Unexpected error while fetching nsfw image for `{query}`: {e}")
        return f"⚠️ @{username} dude u must b a freak cuz that just broke bot ⚠️"


async def get_redgifs_gif(query: str, username: str, after_dark_only: bool = False) -> Optional[str]:
    """
    Fetch a special kind of gif, if you know what I mean ;).

    :param str query: Gif search query.
    :param str username: Chatango user who triggered the command.
    :param bool after_dark_only: Whether results should be limited to the `after dark` timeframe.

    :returns: Optional[str]
    """
    try:
        night_mode = is_after_dark()
        if (after_dark_only and night_mode) or after_dark_only is False:
            token = await redgifs_auth_token()
            endpoint = REDGIFS_IMAGE_SEARCH_ENDPOINT
            params = {"search_text": query.title(), "order": "trending", "count": 80}
            headers = {"Authorization": f"Bearer {token}"}
            session = await get_http_session()
            async with session.get(endpoint, params=params, headers=headers) as resp:
                status = resp.status
                body = await resp.json(content_type=None)
            results = body.get("gifs", None)
            if status == 200 and results is not None:
                results = [result for result in results if result["urls"].get("sd") is not None]
                if bool(results):
                    rand = randint(0, len(results) - 1)
                    image_json = results[rand]
                    return get_full_gif_metadata(image_json)
                elif username == "thegreatpizza":
                    return emojize(
                        ":pizza: *h* wow pizza ur taste in lesbians is so dank that I coughldnt find nething sry :( *h* :pizza:",
                        language="en",
                    )
                elif username == "broiestbro":
                    return emojize("bro wot r u searching 4 go2bed", language="en")
                else:
                    return emojize(
                        f":warning: wow @{username} u must b a freak tf r u even searching foughr jfc :warning:",
                        language="en",
                    )
            else:
                LOGGER.error(f"Error {status} fetching NSFW gif: {body}")
                return emojize(
                    f":warning: omfg @{username} u broke bot with ur kinky ass bs smfh :warning:",
                    language="en",
                )
        return "https://i.imgur.com/oGMHkqT.jpg"
    except ClientError as e:
        LOGGER.warning(f"ClientError while fetching nsfw image for `{query}`: {e}")
        return emojize(f":warning: yea nah idk wtf ur searching for :warning:", language="en")
    except IndexError as e:
        LOGGER.warning(f"IndexError while fetching nsfw image for `{query}`: {e}")
        return emojize(f":warning: yea nah idk wtf ur searching for :warning:", language="en")
    except Exception as e:
        LOGGER.warning(f"Unexpected error while fetching nsfw image for `{query}`: {e}")
        return emojize(f":warning: dude u must b a freak cuz that just broke bot :warning:", language="en")


def get_full_gif_metadata(image: dict) -> str:
    """
    Parses additional metadata for a randomly selected gif.

    :param dict image: Dictionary containing a single gif response.

    :returns: str
    """
    try:
        image_url = image["urls"]["sd"].replace("-mobile", "").replace(".mp4", "-small.gif")
        likes = image["likes"]
        views = image["views"]
        tags = ", #".join(image["tags"])
        return emojize(
            f"\n\n\n{image_url}\n:thumbsup: Likes {likes}\n:eyes: Views {views}\n#{tags}",
            language="en",
        )
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching nsfw image for id `{image['id']}`: {e}")
        return emojize(":warning: dude u must b a freak cuz that just broke bot :warning:", language="en")


async def redgifs_auth_token() -> Optional[str]:
    """
    Authenticate with redgifs to receive access token.

    :returns: Optional[str]
    """
    endpoint = REDGIFS_TOKEN_ENDPOINT
    body = {"access_key": REDGIFS_ACCESS_KEY}
    headers = {"Content-Type": "application/json"}
    try:
        session = await get_http_session()
        async with session.post(endpoint, json=body, headers=headers) as resp:
            token_response = await resp.json(content_type=None)
            if resp.status == 200:
                return token_response.get("access_token")
            LOGGER.error(f"Failed to get Redgifs token with status code {resp.status}: {token_response}")
    except ClientError as e:
        LOGGER.exception(f"ClientError when fetching Redgifs auth token: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching Redgifs auth token: {e}")
