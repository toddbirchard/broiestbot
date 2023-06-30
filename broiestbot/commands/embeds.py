"""Generate link previews from URLs."""
from typing import Optional
from datetime import datetime

import requests
from requests.models import Request
import re
from bs4 import BeautifulSoup
from requests import Response
from requests.exceptions import HTTPError
from emoji import emojize

from config import INSTAGRAM_APP_ID, HTTP_REQUEST_TIMEOUT, TWITTER_BEARER_TOKEN, TWITTER_API_V1_ENDPOINT
from logger import LOGGER


def generate_twitter_preview(message: str) -> Optional[str]:
    """
    Check chat message for Twitter URL and generate preview.

    :param str message: Chatango message to check for Twitter URL.

    :returns: Optional[str]
    """
    try:
        twitter_url_match = re.search(r"^https://twitter\.com/[a-zA-Z0-9_]+/status/([0-9]+)", message)
        if twitter_url_match:
            tweet_id = twitter_url_match.group(1)
            if tweet_id is not None:
                tweet_data = fetch_tweet_by_id(tweet_id)
                if tweet_data:
                    return parse_tweet_preview(tweet_data)
        return None
    except Exception as e:
        LOGGER.error(f"Unexpected error while creating Twitter embed: {e}")


def fetch_tweet_by_id(tweet_id: str) -> Optional[dict]:
    """
    Fetch Tweet JSON by Tweet ID.

    :param str tweet_id: Tweet ID to fetch.

    :returns: Optional[dict]
    """
    try:
        LOGGER.warning(f"Fetching Tweet by ID: {tweet_id}")
        endpoint = TWITTER_API_V1_ENDPOINT
        params = {
            "id": tweet_id,
            "include_entities": "true",
        }
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        resp = requests.get(endpoint, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()[0]
        LOGGER.warning(
            f"Got unexpected status code while fetching Tweet by ID `{tweet_id}`: {resp.status_code}, {resp.content}"
        )
    except HTTPError as e:
        LOGGER.error(f"HTTPError error while fetching Tweet by ID `{tweet_id}`: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error while fetching Tweet by ID `{tweet_id}`: {e}")


def parse_tweet_preview(tweet: dict) -> Optional[str]:
    """
    Create formatted Tweet preview chat message from JSON response.

    :param dict tweet_data: JSON object representing Tweet.

    :returns: Optional[str]
    """
    try:
        tweet_response = "\n\n"
        # Tweet User Info
        tweet_author_name = tweet["user"]["name"]
        tweet_author_username = tweet["user"]["screen_name"]
        tweet_author_location = tweet["user"]["location"]
        # Tweet Data
        tweet_body = tweet["text"]
        tweet_hashtags = tweet["entities"]["hashtags"]
        tweet_retweets = tweet["retweet_count"]
        tweet_likes = tweet["favorite_count"]
        tweet_date = tweet["created_at"].split(" +")[0]
        # tweet_date_formatted = f":calendar: {datetime.strptime(tweet_date, '%Y-%m-%dT%H:%M:%S')}"
        tweet_response += f":bust_in_silhouette: <b>{tweet_author_name}</b> <i>@{tweet_author_username}</i>\n \
            :calendar: {tweet_date}\n\n \
            :speech_balloon: {tweet_body}\n\n"
        # Tweet Photos
        tweet_attachments = tweet["extended_entities"].get("media")
        if tweet_attachments:
            tweet_image_urls = [
                attachment["media_url_https"] for attachment in tweet_attachments if attachment["type"] == "photo"
            ]
            tweet_response += f"{' '.join(tweet_image_urls)}\n\n"
        # Tweet Metadata
        tweet_response += f":shuffle_tracks_button: <b>{tweet_retweets} retweets</b>\n \
            :red_heart: <b>{tweet_likes} faves</b>\n"
        if tweet_hashtags:
            tweet_response += f":keycap_#: {' '.join(tweet_hashtags)}"
        if tweet_response != "\n\n":
            return emojize(
                tweet_response,
                language="en",
            )
    except KeyError as e:
        LOGGER.error(f"KeyError while parsing Tweet: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error while parsing Tweet: {e}")


def twitter_bearer_oauth(req: Request) -> Request:
    """
    Method required by bearer token authentication.

    :param Request req: Prepared API request to fetch Tweet from Twitter API.

    :returns: Request
    """
    req.headers["Authorization"] = f"Bearer {TWITTER_BEARER_TOKEN}"
    req.headers["User-Agent"] = "v2TweetLookupPython"
    return req


def create_instagram_preview(url: str) -> Optional[str]:
    """
    Generate link preview for Instagram post URLs.

    :param str url: Instagram post URL (image or video).

    :returns: Optional[str]
    """
    try:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        req = requests.get(url, headers=headers, timeout=HTTP_REQUEST_TIMEOUT)
        html = BeautifulSoup(req.content, "html.parser")
        img_tag = html.find("meta", property="og:image")
        if img_tag is not None:
            img = img_tag.get("content")
            description = html.find("title").get_text()
            return f"{img} {description}"
        return None
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching Instagram URL `{url}`: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error while creating Instagram embed: {e}")


def get_instagram_token() -> Optional[Response]:
    """
    Generate Instagram OAuth token.

    :returns: Optional[Response]
    """
    try:
        params = {
            "client_id": INSTAGRAM_APP_ID,
        }
        return requests.post(f"https://www.facebook.com/x/oauth/status", params=params, timeout=HTTP_REQUEST_TIMEOUT)
    except HTTPError as e:
        LOGGER.error(f"HTTPError while fetching Instagram token: {e.response.content}")
    except Exception as e:
        LOGGER.error(f"Unexpected error when fetching Instagram token: {e}")
