"""Commands for fetching video stream info from Twitch and YouTube."""

from datetime import datetime
from time import monotonic
from typing import List, Optional

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER
from requests.exceptions import RequestException
from youtube_search import YoutubeSearch

from config import (
    TWITCH_BROADCASTERS,
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
    TWITCH_STREAMS_ENDPOINT,
    TWITCH_TOKEN_ENDPOINT,
    YOUTUBE_SEARCH_ATTEMPTS,
    YOUTUBE_SEARCH_COOLDOWN,
    YOUTUBE_SEARCH_FAILURE_THRESHOLD,
    YOUTUBE_SEARCH_QUERY_MAX_LENGTH,
    YOUTUBE_SEARCH_REQUEST_RETRIES,
    YOUTUBE_SEARCH_REQUEST_TIMEOUT,
    YOUTUBE_VIDEO_ID_REGEX,
    YOUTUBE_VIDEO_REQUIRED_FIELDS,
    YOUTUBE_VIDEO_SEARCH_URL,
    YOUTUBE_VIDEO_SHORT_URL,
)

YOUTUBE_FAILURE_RESPONSE = emojize(
    ":television: :warning: youtube is being a little bitch rn, try again later :warning: :television:",
    language="en",
)
YOUTUBE_NO_RESULTS_RESPONSE = emojize(
    ":television: :cross_mark: couldn't find a single video for that, nice one :cross_mark: :television:",
    language="en",
)


async def get_all_live_twitch_streams() -> str:
    """
    Check all Twitch broadcasters for live streams.

    :returns: str
    """
    token = await get_twitch_auth_token()
    try:
        twitch_streams = []
        i = 0
        for user, broadcaster_id in TWITCH_BROADCASTERS.items():
            stream = await get_live_twitch_stream(broadcaster_id, token)
            if stream:
                i += 1
                twitch_streams.append(stream)
                if i == 1:
                    twitch_streams.insert(0, "\n\n\n\n")
                elif i > 1:
                    return "\n-----------------------\n".join(twitch_streams)
                return "".join(twitch_streams)
        return "🚫🎮🙁 no memers streaming twitch rn 🙁🎮🚫"
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching Twitch streams: {e}")
        return "🙁 twitch is down or something idk 🙁"
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching Twitch streams: {e}")
        return "🙁⚠️ fmga bot died trying to get meme streamers ⚠️🙁"


async def get_live_twitch_stream(broadcaster_id: str, token: str) -> Optional[str]:
    """
    Check if Twitch user is live-streaming and return stream info.

    :param str broadcaster_id: Twitch ID of broadcaster to check for a live stream.
    :param str token: Bearer token for fetching twitch streams.

    :returns: str
    """
    try:
        endpoint = TWITCH_STREAMS_ENDPOINT
        params = {"user_id": broadcaster_id}
        headers = {
            "Authorization": f"Bearer {token}",
            "client-id": TWITCH_CLIENT_ID,
            "Accept": "application/vnd.twitchtv.v5+json",
        }
        session = await get_http_session()
        async with session.get(endpoint, params=params, headers=headers) as resp:
            streams = (await resp.json(content_type=None)).get("data")
        if bool(streams):
            return format_twitch_response(streams[0])
        return None
    except ClientError as e:
        LOGGER.exception(f"ClientError when fetching Twitch channel: {e}")
    except IndexError as e:
        LOGGER.exception(f"IndexError when fetching Twitch channel: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching Twitch channel: {e}")


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
    duration = (datetime.utcnow() - datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S")).seconds / 60
    thumbnail = stream.get("thumbnail_url").replace("{width}", "550").replace("{height}", "300")
    url = f"https://www.twitch.tv/{broadcaster}"
    return f"\n\n\n<b>{broadcaster}</b> is streaming <b>{game}</b>\n<i>{title}</i>\n{viewers} viewers, {int(duration)} minutes\n{url}\n\n{thumbnail}"


async def get_twitch_auth_token() -> Optional[str]:
    """
    Generate Twitch auth token prior to fetching live streams.

    :returns: str
    """
    try:
        endpoint = TWITCH_TOKEN_ENDPOINT
        params = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }
        session = await get_http_session()
        async with session.post(endpoint, params=params) as resp:
            token_response = await resp.json(content_type=None)
            return token_response.get("access_token")
    except ClientError as e:
        LOGGER.exception(f"ClientError when fetching Twitch auth token: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching Twitch auth token: {e}")


# Consecutive failed scrapes, & the point in time (per `monotonic()`) until which YouTube lookups
# are skipped outright. Reset on any scrape which comes back readable.
_youtube_failure_count = 0
_youtube_paused_until = 0.0


def _youtube_search_is_paused() -> bool:
    """
    Determine whether YouTube lookups are currently being skipped after repeated failures.

    :returns: bool
    """
    return monotonic() < _youtube_paused_until


def _record_youtube_failure() -> None:
    """Count a failed scrape, pausing YouTube lookups once enough of them fail back to back."""
    global _youtube_failure_count, _youtube_paused_until
    _youtube_failure_count += 1
    if _youtube_failure_count >= YOUTUBE_SEARCH_FAILURE_THRESHOLD:
        _youtube_failure_count = 0
        _youtube_paused_until = monotonic() + YOUTUBE_SEARCH_COOLDOWN
        LOGGER.warning(
            f"YouTube search failed {YOUTUBE_SEARCH_FAILURE_THRESHOLD} times in a row; "
            f"skipping YouTube lookups for {YOUTUBE_SEARCH_COOLDOWN} seconds."
        )


def _record_youtube_success() -> None:
    """Forget past failures after a scrape YouTube served readable results for."""
    global _youtube_failure_count
    _youtube_failure_count = 0


def sanitize_youtube_query(query: Optional[str]) -> Optional[str]:
    """
    Normalize a search query, rejecting one YouTube can't do anything with.

    :param Optional[str] query: Raw search query pulled out of a chat message.

    :returns: Optional[str]
    """
    if not isinstance(query, str):
        return None
    query = query.strip()
    if not query:
        return None
    if len(query) > YOUTUBE_SEARCH_QUERY_MAX_LENGTH:
        LOGGER.warning(f"Truncating {len(query)}-character YouTube query to {YOUTUBE_SEARCH_QUERY_MAX_LENGTH}")
        query = query[:YOUTUBE_SEARCH_QUERY_MAX_LENGTH].strip()
    return query


def validate_youtube_video(video: object) -> Optional[dict]:
    """
    Discard a scraped result too incomplete to render into chat.

    `youtube_search` assembles each result from `.get()` chains against YouTube's markup, so a
    result whose shape it didn't recognize comes back fully-formed with empty values rather than
    missing keys — rendering one of those puts a literal `None` in chat.

    :param object video: A single result as scraped by `YoutubeSearch.to_dict()`.

    :returns: Optional[dict]
    """
    if not isinstance(video, dict):
        LOGGER.warning(f"Discarding YouTube result which isn't a dict: {video}")
        return None
    missing = [field for field in YOUTUBE_VIDEO_REQUIRED_FIELDS if not video.get(field)]
    if missing:
        LOGGER.warning(f"Discarding YouTube result missing {missing}: {video}")
        return None
    thumbnails = video["thumbnails"]
    if not isinstance(thumbnails, list) or not thumbnails or not thumbnails[0]:
        LOGGER.warning(f"Discarding YouTube result without a thumbnail: {video}")
        return None
    return video


def search_youtube(query: str, max_results: int = 1) -> Optional[List[dict]]:
    """
    Scrape YouTube search results for a query, failing soft rather than raising.

    `youtube_search` has no API behind it: it slices a JSON blob out of a search results page,
    so each of YouTube's bad days surfaces as a different exception. A consent wall or captcha
    has no blob to slice (`ValueError`), markup which shifted around the blob slices to
    something which isn't JSON (`JSONDecodeError`, itself a `ValueError` — the
    "Expecting value: line 1 column 1 (char 0)" seen in production), and a page which parses
    but was rendered for another layout has no search results in it (`KeyError`). None of that
    is worth killing a chat response over, so every one of them comes back as a failed lookup.

    :param str query: Search query, either a canonical video URL or free text from chat.
    :param int max_results: Maximum number of results to scrape.

    :returns: Optional[List[dict]] -- results YouTube served, or None if the lookup failed.
    """
    search_query = sanitize_youtube_query(query)
    if search_query is None:
        LOGGER.warning("Refusing to search YouTube for an empty query")
        return []
    if _youtube_search_is_paused():
        LOGGER.warning(f"Skipping YouTube search for `{search_query}`; lookups paused after repeated failures.")
        return None
    try:
        results = YoutubeSearch(
            search_query,
            max_results=max_results,
            retries=YOUTUBE_SEARCH_REQUEST_RETRIES,
            timeout=YOUTUBE_SEARCH_REQUEST_TIMEOUT,
        ).to_dict()
    except RequestException as e:
        LOGGER.warning(f"Network error while searching YouTube for `{search_query}`: {e}")
        _record_youtube_failure()
        return None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        LOGGER.warning(f"Failed to scrape YouTube results for `{search_query}`: {type(e).__name__}: {e}")
        _record_youtube_failure()
        return None
    except Exception as e:
        LOGGER.error(f"Unexpected error while searching YouTube for `{search_query}`: {type(e).__name__}: {e}")
        _record_youtube_failure()
        return None
    if not isinstance(results, list):
        LOGGER.warning(f"YouTube search for `{search_query}` returned {type(results).__name__} instead of a list")
        _record_youtube_failure()
        return None
    _record_youtube_success()
    if not results:
        LOGGER.warning(f"No YouTube search results found for `{search_query}`")
    return results


def format_youtube_video(video: dict, bold_title: bool = False) -> str:
    """
    Render a validated video into a chat message, omitting any metadata YouTube withheld.

    :param dict video: A validated result as scraped by `YoutubeSearch.to_dict()`.
    :param bool bold_title: Whether the video's title should be bolded.

    :returns: str
    """
    title = f"<b>{video['title']}</b>" if bold_title else video["title"]
    preview = f"\n\n\n\n{video['thumbnails'][0]}\n{title}\n\n"
    if video.get("duration"):
        preview += emojize(f":hourglass_not_done: Duration: {video['duration']}\n", language="en")
    if video.get("views"):
        preview += emojize(f":eyes: {video['views']}\n", language="en")
    if video.get("channel"):
        preview += emojize(f":cinema: Channel: {video['channel']}\n", language="en")
    if video.get("publish_time"):
        preview += emojize(f":calendar: {video['publish_time']}\n", language="en")
    return f"{preview}\n{YOUTUBE_VIDEO_SHORT_URL.format(video_id=video['id'])}"


def fetch_youtube_video_by_id(video_id: str) -> Optional[dict]:
    """
    Look a YouTube video up by its ID, discarding results for any other video.

    YouTube's search resolves a *canonical* watch URL straight to its video; the same
    URL carrying share params (`?si=`, `&t=`) or a bare video ID does not, and instead
    ranks as a plain search term which returns an unrelated video or nothing at all.
    Search occasionally serves a suggestion in place of the video regardless, hence the
    ID check and the retry.

    :param str video_id: 11-character ID of a YouTube video.

    :returns: Optional[dict]
    """
    for _ in range(YOUTUBE_SEARCH_ATTEMPTS):
        if _youtube_search_is_paused():
            break
        video_results = search_youtube(YOUTUBE_VIDEO_SEARCH_URL.format(video_id=video_id), max_results=1)
        if not video_results:
            continue
        video = validate_youtube_video(video_results[0])
        if video is None:
            continue
        if video["id"] == video_id:
            return video
        LOGGER.warning(f"YouTube returned video `{video['id']}` while looking up `{video_id}`")
    return None


def generate_youtube_video_preview(chat_message: str) -> Optional[str]:
    """
    Generate a link preview for a Youtube video from its URL.

    :param str chat_message: Chat message containing URL to a YouTube video.

    :returns: Optional[str]
    """
    if not isinstance(chat_message, str):
        return None
    video_id_match = YOUTUBE_VIDEO_ID_REGEX.search(chat_message)
    if video_id_match is None:
        return None
    video_id = video_id_match.group(1)
    try:
        video = fetch_youtube_video_by_id(video_id)
        if video is None:
            return None
        return format_youtube_video(video)
    except Exception as e:
        LOGGER.error(f"Unexpected error while generating preview for YouTube video `{video_id}`: {e}")
        return None


def search_youtube_video(chat_message: str) -> str:
    """
    Search YouTube for a video by query string and return the first result.

    Always answers, since this is only ever reached because a user asked for a video by name:
    a scrape YouTube refused or served garbage for gets an excuse rather than silence.

    :param str chat_message: Search query string.

    :returns: str
    """
    try:
        video_results = search_youtube(chat_message, max_results=1)
        if video_results is None:
            return YOUTUBE_FAILURE_RESPONSE
        if not video_results:
            return YOUTUBE_NO_RESULTS_RESPONSE
        video = validate_youtube_video(video_results[0])
        if video is None:
            return YOUTUBE_NO_RESULTS_RESPONSE
        return format_youtube_video(video, bold_title=True)
    except Exception as e:
        LOGGER.error(f"Unexpected error while searching YouTube for `{chat_message}`: {e}")
        return YOUTUBE_FAILURE_RESPONSE


'''def create_youtube_video_preview(video_url: str) -> str:
    """
    Generate a link preview for a Youtube video by URL.

    :param str video_url: Full URL to a YouTube video.

    :returns: str
    """
    try:
        video_preview = "\n\n\n\n"
        video_id = video_url.split("v=")[1]
        LOGGER.warning(f"video_id = {video_id}")
        video = yt.videos().list(part="snippet,contentDetails,statistics", id=video_id).execute()
        LOGGER.warning(f"video = {video}")
        video_thumbnail = video.get("thumbnails").split("?")[0]
        video_title = video.get("title")
        video_views = video.get("views")
        video_likes = video.get("video_likes")
        video_dislikes = video.get("video_dislikes")
        video_channel = video.get("channel")
        video_category = video.get("category")
        video_publish_time = video.get("publishdate")
        if video_title:
            video_preview += f"<b>{video_title}</b>\n"
        if video_url:
            video_preview += f"{video_url}\n"
        if video_views:
            video_preview += emojize(f":eyes: {video_views.replace(' views', '')}\n", language="en")
        if video_likes and video_dislikes:
            video_preview += emojize(f":thumbsup: {video_likes} :thumbsdown: {video_dislikes}\n", language="en")
        if video_category:
            video_preview += emojize(f":file_cabinet: {video_category}\n", language="en")
        if video_publish_time:
            video_preview += emojize(f":calendar: {video_publish_time}\n", language="en")
        if video_channel:
            emojize(f":television: {video_channel}\n", language="en")
        if video_thumbnail:
            video_preview += f"{video_thumbnail}"
        return video_preview
    except Exception as e:
        LOGGER.error(f"Error while fetching YouTube video: {e}")'''
