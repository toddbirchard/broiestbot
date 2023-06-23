"""Fetch weather for a given location."""
from typing import Optional
from datetime import datetime

import requests
from database import session
from database.models import Weather
from emoji import emojize
from requests.exceptions import HTTPError

from config import (
    CHATANGO_OBI_ROOM,
    METRIC_SYSTEM_USERS,
    WEATHERSTACK_API_ENDPOINT,
    WEATHERSTACK_API_KEY,
    HTTP_REQUEST_TIMEOUT,
)
from logger import LOGGER


def get_current_weather(location: str, room: str, user: str) -> str:
    """
    Return temperature and weather per city/state/zip.

    :param str location: Location to fetch weather for.
    :param room: Chatango room from which request originated.
    :param str user: User who made the request.

    :returns: str
    """
    try:
        measurement_units = get_user_preferred_units(room, user)
        weather_response = fetch_current_weather_by_location(location, measurement_units)
        if weather_response:
            return parse_weather_response(weather_response, measurement_units)
    except Exception as e:
        LOGGER.error(f"Failed to fetch & parse weather for `{location}`: {e}")
        return emojize(
            f":warning:️️ omfg u broke the bot WHAT DID YOU DO IM DEAD AHHHHHH :warning:",
            language="en",
        )


def fetch_current_weather_by_location(location: str, measurement_units: str) -> Optional[dict]:
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
        resp = requests.get(WEATHERSTACK_API_ENDPOINT, params=params, timeout=HTTP_REQUEST_TIMEOUT)
        return resp.json()
    except HTTPError as e:
        LOGGER.error(f"Failed to get weather for `{location}`: {e.response.content}")
        return emojize(f":warning:️️ ughhh fgma me the weather API is down or something :warning:", language="en")
    except LookupError as e:
        LOGGER.error(f"KeyError while fetching weather for `{location}`: {e}", language="en")
        return emojize(
            f":warning:️️ sry but BROUGH coded this bert like a MORAN and it DIED! :warning:",
            language="en",
        )
    except Exception as e:
        LOGGER.error(f"Failed to get weather for `{location}`: {e}")
        return emojize(
            f":warning:️️ omfg u broke the bot WHAT DID YOU DO IM DEAD AHHHHHH :warning:",
            language="en",
        )


def parse_weather_response(weather: dict, measurement_units: str) -> str:
    """
    Parse weather response returned by API.

    :param dict resp: Weather response returned by API.
    :param str measurement_units: `Metric` or `Imperial` units.

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
        local_time = datetime.utcfromtimestamp(weather["location"]["localtime_epoch"]).strftime("%I:%M")
        weather_emoji = get_weather_emoji(weather_code, is_day)
        precipitation_emoji = get_precipitation_emoji(weather["current"]["precip"])
        humidity_emoji = get_humidity_emoji(humidity)
        cloud_cover_emoji = get_cloud_cover_emoji(cloud_cover)
        response += f"<b>{weather['request']['query']}</b>\n \
                    {weather_emoji} {weather_summary}\n \
                    :thermometer: Temp: {temperature}°{'c' if measurement_units == 'm' else 'f'} <i>(feels like {feels_like}{'c' if measurement_units == 'm' else 'f'}°)</i>\n"
        if precipitation:
            response += f"{precipitation_emoji} {precipitation}{'mm' if measurement_units == 'm' else 'in'}"
        response += f"{humidity_emoji} Humidity: {humidity}%\n \
                    {cloud_cover_emoji} Cloud cover: {cloud_cover}%\n \
                    :wind_face: Wind speed: {wind_speed}{'km/h' if measurement_units == 'm' else 'mph'}\n \
                    :six-thirty: {local_time}"
        response = emojize(response, language="en")
        return response
    except Exception as e:
        LOGGER.error(f"Failed to parse weather response: {e}")
        return emojize(
            f":warning:️️ omfg u broke the bot WHAT DID YOU DO IM DEAD AHHHHHH :warning:",
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


def get_weather_emoji(weather_code: int, is_day: str) -> str:
    """
    Fetch emoji to best represent location weather based on weather code and time of day.

    :param int weather_code: Numerical code representing general weather type.
    :param str is_day: Whether the target location is currently experiencing daylight.

    :returns: str
    """
    weather_emoji = session.query(Weather).filter(Weather.code == weather_code).one_or_none()
    if weather_emoji is not None:
        return weather_emoji.icon
    elif is_day == "no" and weather_emoji.group in [
        "sun",
        None,
    ]:
        return emojize(":night_with_stars:", language="en")
    elif weather_emoji.icon and is_day == "no":
        return weather_emoji.icon
    return ":sun:"


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
