"""Tests for generic link previews built from a page's own metadata.

Any link no dedicated handler claims is fetched and previewed from its OpenGraph / Twitter card /
plain HTML metadata. The link is whatever somebody typed into chat, so the fetch must refuse
anything that isn't on the public internet, at every redirect hop.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientConnectionError

from broiestbot.commands.previews import (
    _is_public_host,
    format_link_preview,
    generate_link_preview,
    parse_link_metadata,
    previewable_url,
)
from config import LINK_PREVIEW_DESCRIPTION_LENGTH
from tests.aiohttp_mocks import FakeResponse, patch_http_session

MODULE = "broiestbot.commands.previews"
URL = "https://news.example.com/2026/10/story"
HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8"}

OG_PAGE = """<!doctype html><html><head>
<title>Fallback title | Example News</title>
<meta property="og:title" content="Eagles win again">
<meta property="og:description" content="The Birds are 6-0 after another
    comeback.">
<meta property="og:image" content="/images/eagles.jpg">
<meta property="og:site_name" content="Example News">
<meta name="twitter:title" content="Twitter title">
</head><body><p>body</p></body></html>"""


def html_response(html: str = OG_PAGE, status: int = 200, headers: dict = None) -> FakeResponse:
    return FakeResponse(status=status, text=html, headers=headers or HTML_HEADERS)


def public_hosts():
    """Treat every host as public, so tests never touch DNS."""
    return patch(f"{MODULE}._is_public_host", AsyncMock(return_value=True))


# Picking the link
# -------------------------------------------------


@pytest.mark.parametrize(
    "chat_message, expected",
    [
        ("look at this https://news.example.com/story", "https://news.example.com/story"),
        ("https://news.example.com/story.", "https://news.example.com/story"),
        ("no links here", None),
        # Image links are already rendered inline by Chatango.
        ("https://cdn.example.com/cat.JPG", None),
        ("https://media0.giphy.com/media/abc/giphy?cid=1", None),
        # Hosts owned by a dedicated handler, including subdomains.
        ("https://www.youtube.com/@channel", None),
        ("https://en.m.wikipedia.org/wiki/Eagles", None),
        ("https://x.com/someone", None),
        # Every YouTube & Wikipedia URL shape, including the ones the dedicated handlers decline
        # (channels, playlists, malformed IDs) — those fall through to here and must stay unpreviewed.
        ("https://youtube.com/playlist?list=PL123", None),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("https://youtu.be/short", None),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", None),
        ("https://wikipedia.org", None),
        ("https://de.wikipedia.org/wiki/Fu%C3%9Fball", None),
        # An excluded link doesn't block a different one later in the message.
        ("https://www.youtube.com/@channel https://news.example.com", "https://news.example.com"),
        # The first eligible link wins; ineligible ones before it are skipped.
        ("https://i.imgur.com/a.png https://one.example.com https://two.example.com", "https://one.example.com"),
        # A quoted link isn't the sender's own.
        ("@somebody: `https://quoted.example.com/page` lol", None),
    ],
)
def test_previewable_url(chat_message: str, expected):
    assert previewable_url(chat_message) == expected


# Reading metadata
# -------------------------------------------------


def test_opengraph_preferred_over_twitter_and_title():
    metadata = parse_link_metadata(OG_PAGE.encode(), URL)
    assert metadata["title"] == "Eagles win again"
    # Whitespace (including newlines) inside a tag is collapsed.
    assert metadata["description"] == "The Birds are 6-0 after another comeback."
    # Relative image paths are resolved against the page URL.
    assert metadata["image"] == "https://news.example.com/images/eagles.jpg"
    assert metadata["site_name"] == "Example News"


def test_falls_back_to_twitter_then_plain_html():
    html = b"""<html><head><title> Plain   title </title>
    <meta name="twitter:description" content="Card description">
    <meta name="description" content="Meta description">
    <meta name="twitter:image" content="https://cdn.example.com/card.png">
    </head></html>"""
    metadata = parse_link_metadata(html, URL)
    assert metadata["title"] == "Plain title"
    assert metadata["description"] == "Card description"
    assert metadata["image"] == "https://cdn.example.com/card.png"
    assert metadata["site_name"] is None


def test_opengraph_on_name_attribute_and_any_case():
    html = b'<head><meta name="OG:Title" content="Misdeclared"><meta name="description" content="d"></head>'
    assert parse_link_metadata(html, URL)["title"] == "Misdeclared"


@pytest.mark.parametrize(
    "image",
    ["javascript:alert(1)", "data:image/png;base64,AAAA", 'https://cdn.example.com/a.png"><script>'],
)
def test_unsafe_image_urls_dropped(image: str):
    html = f'<head><meta property="og:title" content="t"><meta property="og:image" content=\'{image}\'></head>'
    assert parse_link_metadata(html.encode(), URL)["image"] is None


def test_declared_charset_used_to_decode():
    html = '<head><meta property="og:title" content="Café crème"></head>'.encode("latin-1")
    assert parse_link_metadata(html, URL, "latin-1")["title"] == "Café crème"


# Rendering the card
# -------------------------------------------------


def test_preview_card_contents():
    preview = format_link_preview(parse_link_metadata(OG_PAGE.encode(), URL), URL)
    assert "<b>Eagles win again</b>" in preview
    assert "<i>Example News</i>" in preview
    assert "The Birds are 6-0 after another comeback." in preview
    assert "https://news.example.com/images/eagles.jpg" in preview


def test_site_name_falls_back_to_host():
    preview = format_link_preview({"title": "t", "description": "d"}, "https://www.example.com/a")
    assert "<i>example.com</i>" in preview


def test_page_text_is_escaped():
    metadata = {"title": "<script>x</script>", "description": "Tom & Jerry <b>", "site_name": "a<i>"}
    preview = format_link_preview(metadata, URL)
    assert "<script>" not in preview
    assert "&lt;script&gt;x&lt;/script&gt;" in preview
    assert "Tom &amp; Jerry &lt;b&gt;" in preview


def test_long_description_truncated():
    preview = format_link_preview({"title": "t", "description": "word " * 500}, URL)
    description = preview.strip().splitlines()[-1]
    assert len(description) <= LINK_PREVIEW_DESCRIPTION_LENGTH
    assert description.endswith("…")


@pytest.mark.parametrize(
    "metadata",
    [
        {"title": None, "description": "d", "image": "https://cdn.example.com/a.png"},
        # A bare `<title>` is usually a login wall or error page.
        {"title": "Sign in", "description": None, "image": None},
    ],
)
def test_too_little_metadata_is_not_previewed(metadata: dict):
    assert format_link_preview(metadata, URL) is None


def test_title_and_image_alone_is_enough():
    assert format_link_preview({"title": "t", "image": "https://cdn.example.com/a.png"}, URL) is not None


# Fetching
# -------------------------------------------------


def test_generates_preview_end_to_end():
    with public_hosts(), patch_http_session(MODULE, html_response()) as session_mock:
        preview = asyncio.run(generate_link_preview(f"lol {URL}"))
    assert "<b>Eagles win again</b>" in preview
    session = session_mock.return_value
    method, url, kwargs = session.calls[0]
    assert url == URL
    # Redirects are followed by hand so every hop is vetted.
    assert kwargs["allow_redirects"] is False


def test_redirect_followed_and_image_resolved_against_final_url():
    redirect = FakeResponse(status=301, headers={"Location": "https://other.example.org/final"})
    with public_hosts(), patch_http_session(MODULE, redirect, html_response()) as session_mock:
        preview = asyncio.run(generate_link_preview(URL))
    assert [call[1] for call in session_mock.return_value.calls] == [URL, "https://other.example.org/final"]
    assert "https://other.example.org/images/eagles.jpg" in preview


def test_redirect_to_private_host_refused():
    """A public link which redirects inward must not be followed."""
    redirect = FakeResponse(status=302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})
    with patch_http_session(MODULE, redirect, html_response()) as session_mock:
        with patch(f"{MODULE}._is_public_host", AsyncMock(side_effect=[True, False])):
            assert asyncio.run(generate_link_preview(URL)) is None
    assert len(session_mock.return_value.calls) == 1


def test_private_link_never_requested():
    with patch_http_session(MODULE, html_response()) as session_mock:
        assert asyncio.run(generate_link_preview("http://127.0.0.1:8000/admin")) is None
    assert session_mock.return_value.calls == []


def test_redirect_loop_gives_up():
    redirect = FakeResponse(status=302, headers={"Location": URL})
    with public_hosts(), patch_http_session(MODULE, redirect) as session_mock:
        assert asyncio.run(generate_link_preview(URL)) is None
    assert len(session_mock.return_value.calls) > 1


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(status=404, text=OG_PAGE, headers=HTML_HEADERS),
        FakeResponse(status=200, text="%PDF-1.7", headers={"Content-Type": "application/pdf"}),
        FakeResponse(status=200, json_data={"title": "json"}),
    ],
)
def test_non_html_or_failed_responses_not_previewed(response: FakeResponse):
    with public_hosts(), patch_http_session(MODULE, response):
        assert asyncio.run(generate_link_preview(URL)) is None


def test_connection_error_is_silent():
    with public_hosts(), patch_http_session(MODULE, ClientConnectionError("boom")):
        assert asyncio.run(generate_link_preview(URL)) is None


def test_reads_only_up_to_the_head():
    page = OG_PAGE + ("<p>filler</p>" * 50_000)
    with (
        public_hosts(),
        patch_http_session(MODULE, html_response(page)),
        patch(f"{MODULE}.parse_link_metadata", wraps=parse_link_metadata) as parse,
    ):
        asyncio.run(generate_link_preview(URL))
    assert len(parse.call_args.args[0]) < len(page)


# Public-address check
# -------------------------------------------------


@pytest.mark.parametrize(
    "host, expected",
    [
        ("127.0.0.1", False),
        ("10.0.0.5", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),
        ("0.0.0.0", False),
        ("::1", False),
        ("[::1]", False),
        ("::ffff:127.0.0.1", False),
        ("224.0.0.1", False),
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
    ],
)
def test_ip_literals(host: str, expected: bool):
    assert asyncio.run(_is_public_host(host)) is expected


def _addrinfo(*ips: str):
    return [(None, None, None, "", (ip, 0)) for ip in ips]


def test_hostname_resolving_anywhere_private_is_refused():
    async def check():
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=_addrinfo("93.184.215.14", "10.0.0.1"))):
            return await _is_public_host("sneaky.example.com")

    assert asyncio.run(check()) is False


def test_hostname_resolving_publicly_is_allowed():
    async def check():
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=_addrinfo("93.184.215.14"))):
            return await _is_public_host("example.com")

    assert asyncio.run(check()) is True


def test_unresolvable_hostname_is_refused():
    async def check():
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(side_effect=OSError("nodename nor servname"))):
            return await _is_public_host("nope.invalid")

    assert asyncio.run(check()) is False


# Instagram
# -------------------------------------------------
# Instagram is excluded outright (`LINK_PREVIEW_EXCLUDED_HOSTS`): from a server it serves a login
# wall rather than post metadata, so no link to it is ever fetched — posts, reels or profiles.


@pytest.mark.parametrize(
    "chat_message",
    [
        "https://www.instagram.com/p/C9xYz12AbCd/",
        "https://instagram.com/p/C9xYz12AbCd/?igsh=MWQ1ZGUxMzBkMA==",
        "https://www.instagram.com/birdsfan/p/C9xYz12AbCd/",
        # Instagram's short-form video ("shorts") are Reels, served under `/reel/` and `/reels/`.
        "https://www.instagram.com/reel/C9xYz12AbCd/",
        "https://www.instagram.com/reels/C9xYz12AbCd/",
        "check this reel lol https://www.instagram.com/reel/C9xYz12AbCd/?utm_source=ig_web_copy_link",
        "https://m.instagram.com/p/C9xYz12AbCd/",
        "https://instagr.am/p/C9xYz12AbCd/",
    ],
)
def test_instagram_links_are_never_previewed_or_fetched(chat_message: str):
    with public_hosts(), patch_http_session(MODULE, html_response()) as session_mock:
        assert asyncio.run(generate_link_preview(chat_message)) is None
    assert session_mock.return_value.calls == []


def test_short_link_to_instagram_is_not_followed():
    """A shortener can't launder an excluded host: the redirect into Instagram is refused."""
    redirect = FakeResponse(status=301, headers={"Location": "https://www.instagram.com/reel/C9xYz12AbCd/"})
    with public_hosts(), patch_http_session(MODULE, redirect, html_response()) as session_mock:
        assert asyncio.run(generate_link_preview("https://bit.ly/3abcDEF")) is None
    assert [call[1] for call in session_mock.return_value.calls] == ["https://bit.ly/3abcDEF"]


# Reddit
# -------------------------------------------------
# Reddit is previewed generically. The fixtures mirror the metadata Reddit serves on post pages:
# OpenGraph title/description/image, a `summary_large_image` Twitter card, and HTML-entity-encoded
# `&amp;` in its image query strings.

REDDIT_POST_URL = "https://www.reddit.com/r/eagles/comments/1g2abcd/hurts_to_brown_for_6/"
REDDIT_IMAGE = "https://external-preview.redd.it/hurts-brown.jpg?width=1080&format=pjpg&auto=webp&s=0a1b2c"
REDDIT_POST_PAGE = """<!DOCTYPE html><html lang="en-US"><head>
<meta charset="utf-8">
<title>Hurts to Brown for 6 : r/eagles</title>
<meta name="description" content="Meta description which OpenGraph outranks">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Reddit">
<meta property="og:title" content="r/eagles on Reddit: Hurts to Brown for 6 &amp; we&#39;re up 21-3">
<meta property="og:description" content="Posted by u/birdsfan - 1,234 votes and 210 comments">
<meta property="og:image"
  content="https://external-preview.redd.it/hurts-brown.jpg?width=1080&amp;format=pjpg&amp;auto=webp&amp;s=0a1b2c">
<meta property="og:image:width" content="1080">
<meta property="og:image:height" content="607">
<meta property="og:url" content="https://www.reddit.com/r/eagles/comments/1g2abcd/hurts_to_brown_for_6/">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Twitter title which OpenGraph outranks">
<meta name="twitter:image" content="https://share.redd.it/preview/post/1g2abcd">
</head><body><shreddit-app></shreddit-app></body></html>"""

REDDIT_TEXT_POST_PAGE = """<!DOCTYPE html><html><head>
<title>Game thread etiquette : r/eagles</title>
<meta property="og:site_name" content="Reddit">
<meta property="og:title" content="r/eagles on Reddit: Game thread etiquette">
<meta property="og:description" content="Please keep the game thread to the game. Memes go in the post-game thread.">
</head><body></body></html>"""

REDDIT_SUBREDDIT_PAGE = """<!DOCTYPE html><html><head>
<title>r/eagles</title>
<meta property="og:site_name" content="Reddit">
<meta property="og:title" content="r/eagles">
<meta property="og:description" content="The home of Philadelphia Eagles fans on Reddit.">
<meta property="og:image" content="https://styles.redditmedia.com/t5_2qhqk/styles/communityIcon_abc.png">
</head><body></body></html>"""


def reddit_preview(page: str, *responses: FakeResponse, url: str = REDDIT_POST_URL) -> tuple:
    """Run a Reddit link through the full preview path; return the card and the URLs requested."""
    with public_hosts(), patch_http_session(MODULE, *responses, html_response(page)) as session_mock:
        preview = asyncio.run(generate_link_preview(url))
    return preview, [call[1] for call in session_mock.return_value.calls]


def test_reddit_post_preview_elements():
    """A Reddit post renders title, site name, description and image — taken from OpenGraph."""
    preview, requested = reddit_preview(REDDIT_POST_PAGE)
    assert requested == [REDDIT_POST_URL]
    assert preview == (
        "\n\n<b>r/eagles on Reddit: Hurts to Brown for 6 &amp; we&#x27;re up 21-3</b>\n"
        "🔗 <i>Reddit</i>\n"
        "\nPosted by u/birdsfan - 1,234 votes and 210 comments\n"
        f"\n{REDDIT_IMAGE}\n"
    )
    # OpenGraph outranks the Twitter card, the meta description and the page `<title>`.
    assert "Twitter title" not in preview
    assert "Meta description" not in preview
    assert "share.redd.it" not in preview


def test_reddit_post_metadata():
    """The raw elements read from a Reddit post, before rendering."""
    assert parse_link_metadata(REDDIT_POST_PAGE.encode(), REDDIT_POST_URL) == {
        "title": "r/eagles on Reddit: Hurts to Brown for 6 & we're up 21-3",
        "description": "Posted by u/birdsfan - 1,234 votes and 210 comments",
        # Entity-encoded `&amp;` comes back as a plain `&`, so the link works when posted.
        "image": REDDIT_IMAGE,
        "site_name": "Reddit",
    }


def test_reddit_text_post_has_no_image_line():
    """A self post without an image still previews; the card simply has no image."""
    preview, _ = reddit_preview(REDDIT_TEXT_POST_PAGE)
    assert preview == (
        "\n\n<b>r/eagles on Reddit: Game thread etiquette</b>\n"
        "🔗 <i>Reddit</i>\n"
        "\nPlease keep the game thread to the game. Memes go in the post-game thread.\n"
    )


def test_reddit_subreddit_link_previewed():
    preview, _ = reddit_preview(REDDIT_SUBREDDIT_PAGE, url="https://www.reddit.com/r/eagles/")
    assert "<b>r/eagles</b>" in preview
    assert "The home of Philadelphia Eagles fans on Reddit." in preview
    assert "https://styles.redditmedia.com/t5_2qhqk/styles/communityIcon_abc.png" in preview


@pytest.mark.parametrize(
    "short_url",
    [
        # Post short link.
        "https://redd.it/1g2abcd",
        # Mobile app share link.
        "https://www.reddit.com/r/eagles/s/AbCdEf1234",
        # Hosted video, which redirects to the post it belongs to.
        "https://v.redd.it/abc123xyz",
    ],
)
def test_reddit_short_links_follow_redirect_to_post(short_url: str):
    redirect = FakeResponse(status=301, headers={"Location": REDDIT_POST_URL})
    preview, requested = reddit_preview(REDDIT_POST_PAGE, redirect, url=short_url)
    assert requested == [short_url, REDDIT_POST_URL]
    assert "<b>r/eagles on Reddit: Hurts to Brown for 6" in preview


@pytest.mark.parametrize(
    "chat_message",
    [
        "https://i.redd.it/abc123.jpeg",
        "https://preview.redd.it/abc123.png?width=640&format=png&auto=webp&s=abc",
        "https://external-preview.redd.it/abc123?auto=webp&s=abc",
    ],
)
def test_reddit_image_links_left_to_chatango(chat_message: str):
    """Reddit's image hosts are rendered inline by Chatango, so they're not fetched."""
    with public_hosts(), patch_http_session(MODULE, html_response()) as session_mock:
        assert asyncio.run(generate_link_preview(chat_message)) is None
    assert session_mock.return_value.calls == []


def test_reddit_blocking_the_bot_is_silent():
    """Reddit answers many server IPs with a 403 "blocked" page; that's no preview, not an error."""
    blocked = FakeResponse(status=403, text="<html><title>Blocked</title></html>", headers=HTML_HEADERS)
    with public_hosts(), patch_http_session(MODULE, blocked):
        assert asyncio.run(generate_link_preview(REDDIT_POST_URL)) is None
