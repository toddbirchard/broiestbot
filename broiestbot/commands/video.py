from datetime import datetime
from typing import Optional

import requests
from emoji import emojize

# from clients import yt
# from googleapiclient.errors import HttpError
from requests.exceptions import HTTPError

from config import (
    TWITCH_BROADCASTER_ID,
    TWITCH_BROADCASTERS,
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
)
from logger import LOGGER


def get_all_live_twitch_streams():
    twitch_streams = "\n\n\n"
    for user, broadcaster_id in TWITCH_BROADCASTERS.items():
        stream = get_live_twitch_stream(broadcaster_id)
        if stream is not None:
            twitch_streams += stream + "\n"
    if twitch_streams != "\n\n\n\n":
        return twitch_streams
    return emojize(
        f":frowning: no memers streaming twitch rn :frowning:",
        use_aliases=True,
    )


def get_live_twitch_stream(broadcaster_id: str) -> Optional[str]:
    """
    Check if Twitch user is live streaming and return stream info.

    :returns: str
    """
    endpoint = "https://api.twitch.tv/helix/streams"
    token = get_twitch_auth_token()
    params = {"user_id": broadcaster_id}
    headers = {
        "Authorization": f"Bearer {token}",
        "client-id": TWITCH_CLIENT_ID,
        "Accept": "application/vnd.twitchtv.v5+json",
    }
    try:
        req = requests.get(endpoint, params=params, headers=headers)
        resp = req.json().get("data")[0]
        if resp:
            return format_twitch_response(resp)
        return None
    except HTTPError as e:
        LOGGER.error(f"HTTPError when fetching Twitch channel: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching Twitch channel: {e}")


def format_twitch_response(stream: dict) -> str:
    """
    Construct chat message containing stream info.

    :param dict stream: Live Twitch stream metadata.

    :returns: str
    """
    broadcaster = stream.get("user_name")
    game = stream.get("game_name")
    title = stream.get("title")
    viewers = stream.get("viewer_count")
    start_time = stream.get("started_at").replace("Z", "")
    duration = (
        datetime.utcnow() - datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")
    ).seconds / 60
    thumbnail = (
        stream.get("thumbnail_url").replace("{width}", "550").replace("{height}", "300")
    )
    url = f"https://www.twitch.tv/{broadcaster}"
    return f"\n\n\n{broadcaster.upper()} is streaming {game}\n{title}\n{viewers} viewers, {int(duration)} minutes\n{url}\n\n{thumbnail}"


def get_twitch_auth_token() -> Optional[str]:
    """
    Generate Twitch auth token.

    :returns: str
    """
    try:
        endpoint = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
        resp = requests.post(endpoint, params=params)
        return resp.json().get("access_token")
    except HTTPError as e:
        LOGGER.error(f"HTTPError when fetching Twitch auth token: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching Twitch auth token: {e}")


'''def search_youtube_for_video(query: str) -> str:
    """
    Search for a Youtube video.

    :param str query: Query to fetch most relevant YouTube Video.

    :returns: str
    """
    try:
        request = yt.search().list(
            part="snippet", q=query, maxResults=1, safeSearch=None
        )
        response = request.execute()
        LOGGER.info(response)
        return response
    except HttpError as e:
        LOGGER.error(f"HttpError while fetching YouTube video: {e}")
    except Exception as e:
        LOGGER.error(f"Error while fetching YouTube video: {e}")'''