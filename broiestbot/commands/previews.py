"""Generate link previews for URLs posted in chat."""

import asyncio
import ipaddress
import socket
from html import escape
from typing import Dict, Optional, Tuple
from urllib.parse import ParseResult, urljoin, urlparse

from aiohttp import ClientError
from bs4 import BeautifulSoup
from emoji import emojize
from http_client import get_http_session, request_timeout
from logger import LOGGER

from config import (
    CHATANGO_QUOTE_REGEX,
    IMAGE_FILE_EXTENSIONS,
    IMAGE_URL_HOSTS,
    LINK_PREVIEW_DESCRIPTION_LENGTH,
    LINK_PREVIEW_EXCLUDED_HOSTS,
    LINK_PREVIEW_MAX_BYTES,
    LINK_PREVIEW_MAX_REDIRECTS,
    LINK_PREVIEW_REQUEST_TIMEOUT,
    LINK_PREVIEW_TITLE_LENGTH,
    LINK_PREVIEW_USER_AGENT,
    URL_REGEX,
)

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "3600",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
}


REDIRECT_STATUSES = (301, 302, 303, 307, 308)
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


async def generate_link_preview(chat_message: str) -> Optional[str]:
    """
    Build a preview card for the first link in a message no dedicated preview handler owns.

    The card is built from the page's own metadata — OpenGraph first, then Twitter card tags, then
    the plain `<title>` and `<meta name="description">`. A preview nobody asked for isn't worth an
    error, so every failure (unreachable host, non-HTML link, page with no usable metadata) is
    silent.

    :param str chat_message: Raw chat message which may carry a link.

    :returns: Optional[str]
    """
    url = previewable_url(chat_message)
    if url is None:
        return None
    try:
        page = await fetch_page_head(url)
        if page is None:
            return None
        html, final_url, encoding = page
        return format_link_preview(parse_link_metadata(html, final_url, encoding), final_url)
    except ClientError as e:
        LOGGER.info(f"ClientError while generating link preview for `{url}`: {e}")
    except asyncio.TimeoutError:
        LOGGER.info(f"Timed out generating link preview for `{url}`.")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while generating link preview for `{url}`: {e}")
    return None


def previewable_url(chat_message: str) -> Optional[str]:
    """
    Pick the link in a message worth previewing, if any.

    Only the sender's own words count — a quoted link was previewed when it was first posted.
    Image links are skipped, since Chatango already renders those inline, as are hosts a dedicated
    handler owns or which only ever serve a login wall. Only the first eligible link is previewed,
    so a message pasting a list of links costs the room one card rather than a wall of them.

    :param str chat_message: Raw chat message which may carry a link.

    :returns: Optional[str]
    """
    for url in URL_REGEX.findall(CHATANGO_QUOTE_REGEX.sub(" ", chat_message)):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host or _host_matches(host, LINK_PREVIEW_EXCLUDED_HOSTS) or _is_image_url(parsed, host):
            continue
        return url
    return None


async def fetch_page_head(url: str) -> Optional[Tuple[bytes, str, Optional[str]]]:
    """
    Fetch the start of an HTML page, following redirects by hand.

    Any link typed into chat is fetched from the bot's own server, so every hop is checked to
    point at the public internet before it's requested — otherwise a link (or a redirect) to
    `localhost` or a private address would have the bot probing its own network. Redirects are
    followed manually for that reason, rather than by `aiohttp`. Each hop is also checked against
    `LINK_PREVIEW_EXCLUDED_HOSTS`, so a short link can't reach a host excluded by name.

    Only the start of the body is read: the metadata lives in `<head>`, so reading stops once that
    closes, or at `LINK_PREVIEW_MAX_BYTES` regardless.

    :param str url: Link to fetch.

    :returns: Optional[Tuple[bytes, str, Optional[str]]]: Body read so far, the URL it was finally
        served from (for resolving relative image paths), and the charset the server declared.
    """
    session = await get_http_session()
    headers = {"User-Agent": LINK_PREVIEW_USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    for _ in range(LINK_PREVIEW_MAX_REDIRECTS + 1):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        # Re-checked on every hop, so a shortener (or `instagr.am`) can't launder an excluded host.
        if _host_matches(parsed.hostname.lower(), LINK_PREVIEW_EXCLUDED_HOSTS):
            LOGGER.info(f"Not previewing `{url}`: redirected to an excluded host.")
            return None
        if not await _is_public_host(parsed.hostname):
            LOGGER.warning(f"Refusing to preview `{url}`: host is not on the public internet.")
            return None
        async with session.get(
            url,
            headers=headers,
            allow_redirects=False,
            timeout=request_timeout(LINK_PREVIEW_REQUEST_TIMEOUT),
        ) as resp:
            if resp.status in REDIRECT_STATUSES:
                location = resp.headers.get("Location")
                if not location:
                    return None
                url = urljoin(url, location)
                continue
            if resp.status != 200 or resp.content_type not in HTML_CONTENT_TYPES:
                return None
            body = bytearray()
            async for chunk in resp.content.iter_chunked(64 * 1024):
                body.extend(chunk)
                if len(body) >= LINK_PREVIEW_MAX_BYTES or b"</head" in chunk.lower():
                    break
            return bytes(body[:LINK_PREVIEW_MAX_BYTES]), url, resp.charset
    LOGGER.info(f"Gave up on link preview after {LINK_PREVIEW_MAX_REDIRECTS} redirects: `{url}`")
    return None


def parse_link_metadata(html: bytes, url: str, encoding: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Read a page's preview metadata, preferring OpenGraph, then Twitter cards, then plain HTML.

    :param bytes html: Start of the page's HTML.
    :param str url: URL the page was served from; relative image paths are resolved against it.
    :param Optional[str] encoding: Charset declared by the server, if any. Without one, the page's
        own `<meta charset>` is used.

    :returns: Dict[str, Optional[str]]: `title`, `description`, `image` & `site_name`.
    """
    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    tags: Dict[str, str] = {}
    for tag in soup.find_all("meta"):
        # OpenGraph is specified on `property`, but plenty of sites put it on `name` instead.
        key = (tag.get("property") or tag.get("name") or "").strip().lower()
        content = _clean_text(tag.get("content"))
        if key and content:
            tags.setdefault(key, content)

    def first(*keys: str) -> Optional[str]:
        return next((tags[key] for key in keys if key in tags), None)

    page_title = _clean_text(soup.title.get_text()) if soup.title else None
    image = first("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if image:
        image = urljoin(url, image)
        # It's posted into chat as-is, so it must be a well-formed http(s) link with nothing in it
        # which could break out into markup.
        if urlparse(image).scheme not in ("http", "https") or any(char in image for char in " <>\"'`"):
            image = None
    return {
        "title": first("og:title", "twitter:title") or page_title,
        "description": first("og:description", "twitter:description", "description"),
        "image": image,
        "site_name": first("og:site_name", "application-name"),
    }


def format_link_preview(metadata: Dict[str, Optional[str]], url: str) -> Optional[str]:
    """
    Render page metadata as a chat preview card.

    A page needs a title plus a description or an image to be previewed — a bare `<title>` is
    usually a login wall or an error page, and isn't worth a line of chat.

    :param Dict[str, Optional[str]] metadata: Output of `parse_link_metadata`.
    :param str url: URL the page was served from, used to name the site when it doesn't.

    :returns: Optional[str]
    """
    title = metadata.get("title")
    description = metadata.get("description")
    image = metadata.get("image")
    if not title or not (description or image):
        return None
    site_name = metadata.get("site_name") or (urlparse(url).hostname or "").removeprefix("www.")
    # Page text is untrusted and the card is sent as HTML, so everything taken from it is escaped.
    preview = f"\n\n<b>{escape(_truncate(title, LINK_PREVIEW_TITLE_LENGTH))}</b>\n"
    if site_name:
        site_label = escape(_truncate(site_name, LINK_PREVIEW_TITLE_LENGTH))
        preview += f"{emojize(':link:', language='en')} <i>{site_label}</i>\n"
    if description:
        preview += f"\n{escape(_truncate(description, LINK_PREVIEW_DESCRIPTION_LENGTH))}\n"
    if image:
        preview += f"\n{image}\n"
    return preview


async def _is_public_host(host: str) -> bool:
    """
    Check a host resolves only to public internet addresses.

    Fails closed: a host which doesn't resolve, or resolves to *any* loopback, private, link-local
    or otherwise reserved address, is refused.

    :param str host: Hostname or IP literal.

    :returns: bool
    """
    try:
        addresses = [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError:
            return False
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses:
        return False
    for address in addresses:
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global or address.is_multicast:
            return False
    return True


def _host_matches(host: str, domains: Tuple[str, ...]) -> bool:
    """Whether `host` is one of `domains`, or a subdomain of one."""
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def _is_image_url(parsed: ParseResult, host: str) -> bool:
    """Whether a link points straight at an image, which Chatango renders inline on its own."""
    return parsed.path.lower().endswith(IMAGE_FILE_EXTENSIONS) or _host_matches(host, IMAGE_URL_HOSTS)


def _clean_text(text: Optional[str]) -> Optional[str]:
    """Collapse runs of whitespace (newlines included) to single spaces; empty becomes None."""
    if not text:
        return None
    return " ".join(text.split()) or None


def _truncate(text: str, length: int) -> str:
    """Cut `text` to at most `length` characters, marking the cut with an ellipsis."""
    return text if len(text) <= length else f"{text[: length - 1].rstrip()}…"


async def generate_twitter_preview(tweet_url: str) -> Optional[str]:
    """
    Generate a Twitter preview card from a tweet URL.

    :param str tweet_url: URL of the target tweet.

    :returns: Optional[str]
    """
    try:
        twitter_preview = "\n\n\n\n"
        url = tweet_url.replace("https://x.com", "https://api.vxtwitter.com")
        session = await get_http_session()
        async with session.get(url, headers=headers, timeout=request_timeout(20)) as resp:
            tweet_data = await resp.json(content_type=None) if resp.status == 200 else None
        if tweet_data:
            tweet_text = tweet_data.get("text")
            tweet_author = tweet_data.get("user_name")
            tweet_author_handle = tweet_data.get("user_screen_name")
            if tweet_author and tweet_author_handle:
                twitter_preview += f"👤 <b>@{tweet_author_handle}</b> ({tweet_author})\n\n"
            if tweet_text:
                twitter_preview += f"{tweet_text}\n\n"
            for media in tweet_data["media_extended"]:
                twitter_preview += f"{media['thumbnail_url']} "
                twitter_preview += "\n\n"
            tweet_date = tweet_data.get("date").split(" +0000")[0] if tweet_data.get("date") else None
            if tweet_date:
                twitter_preview += f"🗓️ {tweet_date}\n"
            tweet_likes = tweet_data.get("likes")
            if tweet_likes:
                twitter_preview += f"👍 {tweet_likes} Likes\n"
            tweet_retweets = tweet_data.get("retweets")
            if tweet_retweets:
                twitter_preview += f"🔁 {tweet_retweets} Retweets\n"
        if twitter_preview != "\n\n\n\n":
            return twitter_preview
    except ClientError as e:
        LOGGER.error(f"ClientError while generating Twitter preview for URL `{tweet_url}`: {e}")
    except KeyError as e:
        LOGGER.error(f"KeyError while generating Twitter preview: {e}")
    except Exception as e:
        LOGGER.error(f"Unexpected error while generating Twitter preview for URL `{tweet_url}`: {e}")
