"""Generate link previews for URLs posted in chat."""

import asyncio
import ipaddress
import json
import socket
from html import escape
from typing import Any, Dict, Iterator, Optional, Tuple, cast
from urllib.parse import ParseResult, urljoin, urlparse

from aiohttp import ClientError
from bs4 import BeautifulSoup, Tag
from emoji import emojize
from http_client import get_http_session, request_timeout
from logger import LOGGER

from config import (
    CHATANGO_QUOTE_REGEX,
    IMAGE_FILE_EXTENSIONS,
    IMAGE_URL_HOSTS,
    LINK_PREVIEW_DESCRIPTION_LENGTH,
    LINK_PREVIEW_EXCLUDED_HOSTS,
    LINK_PREVIEW_IGNORED_URL_PATTERNS,
    LINK_PREVIEW_JSON_LD_SKIPPED_TYPES,
    LINK_PREVIEW_MAX_BYTES,
    LINK_PREVIEW_MAX_REDIRECTS,
    LINK_PREVIEW_REQUEST_TIMEOUT,
    LINK_PREVIEW_TITLE_LENGTH,
    LINK_PREVIEW_USER_AGENT,
    REDDIT_PREVIEW_HOST,
    REDDIT_REWRITTEN_HOSTS,
    REDDIT_SHARE_LINK_REGEX,
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
    handler owns or which only ever serve a login wall, and URLs matching
    `LINK_PREVIEW_IGNORED_URL_PATTERNS`. Only the first eligible link is previewed, so a message
    pasting a list of links costs the room one card rather than a wall of them.

    :param str chat_message: Raw chat message which may carry a link.

    :returns: Optional[str]
    """
    for url in URL_REGEX.findall(CHATANGO_QUOTE_REGEX.sub(" ", chat_message)):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host or _is_excluded_url(url, host) or _is_image_url(parsed, host):
            continue
        return cast(Optional[str], url)
    return None


async def fetch_page_head(url: str) -> Optional[Tuple[bytes, str, Optional[str]]]:
    """
    Fetch the start of an HTML page, following redirects by hand.

    Any link typed into chat is fetched from the bot's own server, so every hop is checked to
    point at the public internet before it's requested — otherwise a link (or a redirect) to
    `localhost` or a private address would have the bot probing its own network. Redirects are
    followed manually for that reason, rather than by `aiohttp`. Each hop is also checked against
    `LINK_PREVIEW_EXCLUDED_HOSTS` and `LINK_PREVIEW_IGNORED_URL_PATTERNS`, so a short link can't
    reach a host or URL excluded by name, and rewritten to the variant of the page with usable
    metadata (see `metadata_url`).

    Only the start of the body is read: the metadata lives in `<head>`, so reading stops once that
    closes, or at `LINK_PREVIEW_MAX_BYTES` regardless.

    :param str url: Link to fetch.

    :returns: Optional[Tuple[bytes, str, Optional[str]]]: Body read so far, the URL it was finally
        served from (for resolving relative image paths), and the charset the server declared.
    """
    session = await get_http_session()
    headers = {"User-Agent": LINK_PREVIEW_USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    for _ in range(LINK_PREVIEW_MAX_REDIRECTS + 1):
        url = metadata_url(url)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        # Re-checked on every hop, so a shortener (or `instagr.am`) can't launder an excluded host.
        if _is_excluded_url(url, parsed.hostname.lower()):
            LOGGER.info(f"Not previewing `{url}`: redirected to an excluded host or URL.")
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


def metadata_url(url: str) -> str:
    """
    Point a link at the variant of its page which serves usable preview metadata.

    New Reddit hands link unfurlers a stub with a placeholder image, so Reddit links are fetched
    from old Reddit — except app share links, which only new Reddit can resolve. Anything else is
    returned unchanged.

    :param str url: Link about to be fetched.

    :returns: str
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() in REDDIT_REWRITTEN_HOSTS and not REDDIT_SHARE_LINK_REGEX.match(parsed.path):
        return parsed._replace(netloc=REDDIT_PREVIEW_HOST).geturl()
    return url


def parse_link_metadata(html: bytes, url: str, encoding: Optional[str] = None) -> Dict[str, Optional[str]]:
    """
    Read a page's preview metadata, preferring OpenGraph, then Twitter cards, then plain HTML.

    The image has further fallbacks for pages without a card image — `<link rel="image_src">`,
    JSON-LD, then schema.org `itemprop="image"` — and the first candidate which is safe to post
    wins, so one malformed tag doesn't cost the card its image.

    :param bytes html: Start of the page's HTML.
    :param str url: URL the page was served from; relative image paths are resolved against it.
    :param Optional[str] encoding: Charset declared by the server, if any. Without one, the page's
        own `<meta charset>` is used.

    :returns: Dict[str, Optional[str]]: `title`, `description`, `image` & `site_name`.
    """
    soup = BeautifulSoup(html, "html.parser", from_encoding=encoding)
    tags: Dict[str, str] = {}
    for tag in soup.find_all("meta"):
        if not isinstance(tag, Tag):
            continue
        # OpenGraph is specified on `property`, but plenty of sites put it on `name` instead.
        key = (_attr(tag, "property") or _attr(tag, "name") or "").strip().lower()
        content = _clean_text(_attr(tag, "content"))
        if key and content:
            tags.setdefault(key, content)

    def first(*keys: str) -> Optional[str]:
        return next((tags[key] for key in keys if key in tags), None)

    page_title = _clean_text(soup.title.get_text()) if soup.title else None
    images = (urljoin(url, image.strip()) for image in _image_candidates(soup, tags) if image.strip())
    return {
        "title": first("og:title", "twitter:title") or page_title,
        "description": first("og:description", "twitter:description", "description"),
        "image": next((image for image in images if _is_postable_url(image)), None),
        "site_name": first("og:site_name", "application-name"),
    }


def _attr(tag: Tag, name: str) -> Optional[str]:
    """
    Read a single-valued attribute off a tag.

    :param Tag tag: Parsed HTML tag.
    :param str name: Attribute name.

    :returns: Optional[str]: The value, or None when it is absent or multi-valued (`rel`, `class`).
    """
    value = tag.get(name)
    return value if isinstance(value, str) else None


def _image_candidates(soup: BeautifulSoup, tags: Dict[str, str]) -> Iterator[str]:
    """
    Yield a page's candidate preview images, most authoritative first.

    Card tags first, then the older `<link rel="image_src">`, then JSON-LD (which publishers fill in
    for Google even when they skip OpenGraph), then schema.org microdata. Nothing is guessed from
    the page's `<img>` tags: without layout, a hero image can't be told from a logo or an ad.

    :param BeautifulSoup soup: Parsed page.
    :param Dict[str, str] tags: The page's `<meta>` tags, keyed by lowercased `property` / `name`.

    :returns: Iterator[str]
    """
    for key in ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src"):
        if key in tags:
            yield tags[key]
    for link in soup.find_all("link", rel="image_src", href=True):
        href = _attr(link, "href") if isinstance(link, Tag) else None
        if href:
            yield href
    yield from _json_ld_images(soup)
    for tag in soup.find_all(attrs={"itemprop": "image"}):
        source = (_attr(tag, "content") or _attr(tag, "href") or _attr(tag, "src")) if isinstance(tag, Tag) else None
        if source:
            yield source


def _json_ld_images(soup: BeautifulSoup) -> Iterator[str]:
    """
    Yield the `image` / `thumbnailUrl` of each JSON-LD node on the page, skipping logos and avatars.

    Only top-level nodes (and those in an `@graph`) are read — a nested `image` usually belongs to
    the publisher or author.

    :param BeautifulSoup soup: Parsed page.

    :returns: Iterator[str]
    """
    for script in soup.find_all("script", type=lambda value: value and "ld+json" in value.lower()):
        if not isinstance(script, Tag):
            continue
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for node in _json_ld_nodes(data):
            node_types = node.get("@type")
            node_types = node_types if isinstance(node_types, list) else [node_types]
            if any(node_type in LINK_PREVIEW_JSON_LD_SKIPPED_TYPES for node_type in node_types):
                continue
            yield from _json_ld_urls(node.get("image"))
            yield from _json_ld_urls(node.get("thumbnailUrl"))


def _json_ld_nodes(data: Any) -> Iterator[Dict[str, Any]]:
    """Flatten a JSON-LD document's top-level nodes, including any inside an `@graph`."""
    if isinstance(data, list):
        for item in data:
            yield from _json_ld_nodes(item)
    elif isinstance(data, dict):
        yield data
        yield from _json_ld_nodes(data.get("@graph"))


def _json_ld_urls(value: Any) -> Iterator[str]:
    """Read URLs out of a JSON-LD image value: a URL, an `ImageObject`, or a list of either."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _json_ld_urls(item)
    elif isinstance(value, dict):
        yield from _json_ld_urls(value.get("url") or value.get("contentUrl"))


def _is_postable_url(url: str) -> bool:
    """
    Whether an image URL is safe to post into chat as-is.

    It must be a well-formed http(s) link with nothing in it which could break out into markup.
    """
    return urlparse(url).scheme in ("http", "https") and not any(char in url for char in " <>\"'`")


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


def _is_excluded_url(url: str, host: str) -> bool:
    """Whether a link is never previewed: its host is excluded, or it matches an ignored URL pattern."""
    return _host_matches(host, LINK_PREVIEW_EXCLUDED_HOSTS) or any(
        pattern.search(url) for pattern in LINK_PREVIEW_IGNORED_URL_PATTERNS
    )


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
    return None
