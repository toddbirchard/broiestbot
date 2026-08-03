"""Fetch weather for a given location."""

from datetime import datetime
from typing import Optional

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER
from sqlalchemy import select

from config import (
    CHATANGO_OBI_ROOM,
    METRIC_SYSTEM_USERS,
    WEATHERSTACK_API_ENDPOINT,
    WEATHERSTACK_API_KEY,
)
from database import async_session
from database.models import Weather


async def get_current_weather(location: str, room: str, user: str) -> str:
    """
    Return temperature and weather per city/state/zip.

    :param str location: Location to fetch weather for.
    :param room: Chatango room from which request originated.
    :param str user: User who made the request.

    :returns: str
    """
    try:
        measurement_units = get_user_preferred_units(room, user)
        weather_response = await fetch_current_weather_by_location(location, measurement_units)
        if weather_response is not None and weather_response.get("current"):
            return await parse_weather_response(weather_response, measurement_units, room, user)
        return f"😢⛈️ sry @{user} i couldn't find da weather for `{location}` ⛈️😢"
    except Exception as e:
        LOGGER.exception(f"Failed to fetch & parse weather for `{location}`: {e}")
        return "⚠️ omfg u broke the bot WHAT DID YOU DO IM DEAD AHHHHHH ⚠️"


async def fetch_current_weather_by_location(location: str, measurement_units: str) -> Optional[dict]:
    """
    Return temperature and weather per city/state/zip.

    :param str location: Location to fetch weather for.
    :param room: Chatango room from which request originated.
    :param str user: User who made the request.
    :param str measurement_units: `Metric` or `Imperial` units.

    :returns: str
    """
    try:
        params = {
            "access_key": WEATHERSTACK_API_KEY,
            "query": location.replace(";", ""),
            "units": measurement_units,
        }
        session = await get_http_session()
        async with session.get(WEATHERSTACK_API_ENDPOINT, params=params) as resp:
            return await resp.json(content_type=None)
    except ClientError as e:
        LOGGER.error(f"Failed to get weather for `{location}`: {e}")
    except LookupError as e:
        LOGGER.error(f"KeyError while fetching weather for `{location}`: {e}")
    except Exception as e:
        LOGGER.exception(f"Failed to get weather for `{location}`: {e}")


async def parse_weather_response(weather: dict, measurement_units: str, room: str, user: str) -> str:
    """
    Parse weather response returned by API.

    :param dict resp: Weather response returned by API.
    :param str measurement_units: `Metric` or `Imperial` units.
    :param room: Chatango room from which request originated.
    :param str user: User who made the request.

    :returns: str
    """
    try:
        response = "\n\n"
        weather_code = weather["current"]["weather_code"]
        weather_summary = weather["current"]["weather_descriptions"][0]
        is_day = weather["current"]["is_day"]
        temperature = weather["current"]["temperature"]
        feels_like = weather["current"]["feelslike"]
        precipitation = weather["current"]["precip"]
        cloud_cover = weather["current"]["cloudcover"]
        humidity = weather["current"]["humidity"]
        wind_speed = weather["current"]["wind_speed"]
        local_time = datetime.utcfromtimestamp(weather["location"]["localtime_epoch"]).strftime("%I:%M %p").lower()
        if room == CHATANGO_OBI_ROOM or user in METRIC_SYSTEM_USERS:
            local_time = datetime.utcfromtimestamp(weather["location"]["localtime_epoch"]).strftime("%R")
        weather_emoji = await get_weather_emoji(weather_code, is_day)
        precipitation_emoji = get_precipitation_emoji(weather["current"]["precip"])
        humidity_emoji = get_humidity_emoji(humidity)
        cloud_cover_emoji = get_cloud_cover_emoji(cloud_cover)
        response += f"<b>{weather['request']['query']}</b>\n \
                    {weather_emoji} {weather_summary}\n \
                    :thermometer: Temp: {temperature}°{'c' if measurement_units == 'm' else 'f'} <i>(feels like {feels_like}{'c' if measurement_units == 'm' else 'f'}°)</i>\n"
        if precipitation:
            response += f"{precipitation_emoji} {precipitation}{'mm' if measurement_units == 'm' else 'in'}\n"
        response += f"{humidity_emoji} Humidity: {humidity}%\n \
                    {cloud_cover_emoji} Cloud cover: {cloud_cover}%\n \
                    :wind_face: Wind speed: {wind_speed}{'km/h' if measurement_units == 'm' else 'mph'}\n \
                    :six-thirty: {local_time}"
        response = emojize(response, language="en")
        return response
    except Exception as e:
        LOGGER.exception(f"Failed to parse weather response: {e}")
        return emojize(
            ":warning:️️ omfg u broke the bot WHAT DID YOU DO IM DEAD AHHHHHH :warning:",
            language="en",
        )


def get_user_preferred_units(room: str, user: str) -> str:
    """
    Determine whether to use metric or imperial units.

    :param room: Chatango room from which request originated.
    :param str user: User who made the request.

    :returns: str
    """
    if room == CHATANGO_OBI_ROOM or user in METRIC_SYSTEM_USERS:
        return "m"
    return "f"


async def get_weather_emoji(weather_code: int, is_day: str) -> str:
    """
    Fetch emoji to best represent location weather based on weather code and time of day.

    :param int weather_code: Numerical code representing general weather type.
    :param str is_day: Whether the target location is currently experiencing daylight.

    :returns: str
    """
    async with async_session() as db:
        result = await db.execute(select(Weather).where(Weather.code == weather_code))
        weather_emoji = result.scalars().one_or_none()
    if weather_emoji is None:
        return ":sun:"
    # A sun after dark makes no sense, so sun-group conditions get a night sky instead.
    if is_day == "no" and weather_emoji.group in ("sun", None):
        return emojize(":night_with_stars:", language="en")
    return weather_emoji.icon


def get_precipitation_emoji(precipitation: int) -> str:
    """
    Get emoji based on forecasted precipitation.

    :param int precipitation: Percentage chance of precipitation on the day.

    :returns: str
    """
    if precipitation > 70:
        return ":cloud_with_rain:"
    if precipitation > 50:
        return ":cloud:"
    return ":sparkles:"


def get_humidity_emoji(humidity: int) -> str:
    """
    Get emoji based on current humidity.

    :param int humidity: Current humidity percentage.

    :returns: str
    """
    if humidity > 75:
        return ":downcast_face_with_sweat:"
    if humidity > 50:
        return ":grinning_face_with_sweat:"
    return ":slightly_smiling_face:"


def get_cloud_cover_emoji(cloud_cover: int) -> str:
    """
    Get emoji based on forecasted precipitation.

    :param int cloud_cover: Percentage of current cloud cover.

    :returns: str
    """
    if cloud_cover > 60:
        return ":cloud:"
    if cloud_cover > 40:
        return ":sun_behind_cloud:"
    return ":thumbs_up_light_skin_tone:"
