"""Tests for generic link previews built from a page's own metadata.

Any link no dedicated handler claims is fetched and previewed from its OpenGraph / Twitter card /
plain HTML metadata. The link is whatever somebody typed into chat, so the fetch must refuse
anything that isn't on the public internet, at every redirect hop.
"""

import asyncio
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
from aiohttp import ClientConnectionError

from broiestbot.commands.previews import (
    _is_public_host,
    format_link_preview,
    generate_link_preview,
    metadata_url,
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


# Image fallbacks
# -------------------------------------------------
# A page without a card image can still name one elsewhere in its `<head>`: the older
# `<link rel="image_src">`, JSON-LD, or schema.org microdata — tried in that order.


def image_of(head: str) -> str:
    return parse_link_metadata(f"<head><title>t</title>{head}</head>".encode(), URL)["image"]


def test_card_image_outranks_every_fallback():
    head = """<meta property="og:image" content="https://cdn.example.com/og.jpg">
    <link rel="image_src" href="https://cdn.example.com/link.jpg">
    <script type="application/ld+json">{"@type": "NewsArticle", "image": "https://cdn.example.com/ld.jpg"}</script>
    <meta itemprop="image" content="https://cdn.example.com/microdata.jpg">"""
    assert image_of(head) == "https://cdn.example.com/og.jpg"


def test_link_image_src():
    assert image_of('<link rel="image_src" href="/img/lead.jpg">') == "https://news.example.com/img/lead.jpg"


def test_link_image_src_outranks_json_ld():
    head = """<script type="application/ld+json">{"@type": "NewsArticle", "image": "https://cdn.example.com/ld.jpg"}</script>
    <link rel="image_src" href="https://cdn.example.com/link.jpg">"""
    assert image_of(head) == "https://cdn.example.com/link.jpg"


@pytest.mark.parametrize(
    "json_ld",
    [
        '{"@type": "NewsArticle", "image": "https://cdn.example.com/lead.jpg"}',
        '{"@type": "NewsArticle", "image": ["https://cdn.example.com/lead.jpg", "https://cdn.example.com/2.jpg"]}',
        '{"@type": "NewsArticle", "image": {"@type": "ImageObject", "url": "https://cdn.example.com/lead.jpg"}}',
        '{"@type": "NewsArticle", "image": [{"@type": "ImageObject", "contentUrl": "https://cdn.example.com/lead.jpg"}]}',
        '{"@type": "VideoObject", "thumbnailUrl": ["https://cdn.example.com/lead.jpg"]}',
        # A list of documents, and a `@graph`.
        '[{"@type": "BreadcrumbList"}, {"@type": "Article", "image": "https://cdn.example.com/lead.jpg"}]',
        '{"@context": "https://schema.org", "@graph": [{"@type": "Article", "image": "https://cdn.example.com/lead.jpg"}]}',
    ],
)
def test_json_ld_image_shapes(json_ld: str):
    assert image_of(f'<script type="application/ld+json">{json_ld}</script>') == "https://cdn.example.com/lead.jpg"


def test_json_ld_logos_and_avatars_skipped():
    """An `Organization` or `Person` image is a logo or headshot, not a picture of the page."""
    json_ld = """{"@graph": [
        {"@type": "Organization", "image": "https://cdn.example.com/logo.png"},
        {"@type": ["Person"], "image": "https://cdn.example.com/author.jpg"},
        {"@type": "Article", "author": {"image": "https://cdn.example.com/nested.jpg"},
         "image": "https://cdn.example.com/lead.jpg"}
    ]}"""
    assert image_of(f'<script type="application/ld+json">{json_ld}</script>') == "https://cdn.example.com/lead.jpg"


def test_malformed_json_ld_skipped():
    head = """<script type="application/ld+json">{"image": "https://cdn.example.com/broken.jpg",</script>
    <script type="application/ld+json">{"@type": "Article", "image": "https://cdn.example.com/lead.jpg"}</script>"""
    assert image_of(head) == "https://cdn.example.com/lead.jpg"


@pytest.mark.parametrize(
    "tag",
    [
        '<meta itemprop="image" content="https://cdn.example.com/lead.jpg">',
        '<link itemprop="image" href="https://cdn.example.com/lead.jpg">',
        '<img itemprop="image" src="https://cdn.example.com/lead.jpg">',
    ],
)
def test_microdata_image(tag: str):
    assert image_of(tag) == "https://cdn.example.com/lead.jpg"


def test_unsafe_candidate_falls_through_to_the_next():
    """One malformed tag doesn't cost the card its image when another candidate is fine."""
    head = """<meta property="og:image" content="javascript:alert(1)">
    <meta name="twitter:image" content="https://cdn.example.com/card.jpg">"""
    assert image_of(head) == "https://cdn.example.com/card.jpg"


def test_body_images_never_guessed():
    html = b'<head><title>t</title></head><body><img src="https://cdn.example.com/logo.png"></body>'
    assert parse_link_metadata(html, URL)["image"] is None


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
# New Reddit serves link unfurlers a stub — the same placeholder image and "Explore this post"
# description for every post — so Reddit links are fetched from old Reddit, which still serves the
# post's own metadata. The fixtures mirror each: old Reddit's has HTML-entity-encoded `&amp;` in
# its image query strings, and declares its tags on `property` throughout, Twitter's included.

REDDIT_POST_URL = "https://www.reddit.com/r/eagles/comments/1g2abcd/hurts_to_brown_for_6/"
OLD_REDDIT_POST_URL = "https://old.reddit.com/r/eagles/comments/1g2abcd/hurts_to_brown_for_6/"
REDDIT_IMAGE = "https://preview.redd.it/hurts-brown.png?width=1200&height=628&auto=webp&s=0a1b2c"
REDDIT_POST_PAGE = """<!doctype html><html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>
<title>Hurts to Brown for 6 &amp; we&#39;re up 21-3 : eagles</title>
<meta name="description" content="Meta description which OpenGraph outranks" />
<meta property="og:site_name" content="reddit">
<meta property="og:description" content="Posted in r/eagles by u/birdsfan • 1,234 points and 210 comments">
<meta property="og:title" content="Hurts to Brown for 6 &amp; we&#39;re up 21-3">
<meta property="og:image"
  content="https://preview.redd.it/hurts-brown.png?width=1200&amp;height=628&amp;auto=webp&amp;s=0a1b2c">
<meta property="og:image:height" content="628">
<meta property="og:image:width" content="1200">
<meta property="twitter:image"
  content="https://preview.redd.it/hurts-brown.png?width=600&amp;height=300&amp;auto=webp&amp;s=3d4e5f">
<meta property="twitter:card" content="summary_large_image">
<meta property="twitter:title" content="Twitter title which OpenGraph outranks">
</head><body></body></html>"""

REDDIT_TEXT_POST_PAGE = """<!doctype html><html><head>
<title>Game thread etiquette : eagles</title>
<meta property="og:site_name" content="reddit">
<meta property="og:title" content="Game thread etiquette">
<meta property="og:description" content="Please keep the game thread to the game. Memes go in the post-game thread.">
</head><body></body></html>"""

REDDIT_SUBREDDIT_PAGE = """<!doctype html><html><head>
<title>Philadelphia Eagles</title>
<meta property="og:site_name" content="reddit">
<meta property="og:title" content="Philadelphia Eagles • r/eagles">
<meta property="og:description" content="The home of Philadelphia Eagles fans on Reddit.">
<meta property="og:image" content="https://styles.redditmedia.com/t5_2qhqk/styles/bannerBackgroundImage_abc.jpg">
</head><body></body></html>"""


def reddit_preview(page: str, *responses: FakeResponse, url: str = REDDIT_POST_URL) -> tuple:
    """Run a Reddit link through the full preview path; return the card and the URLs requested."""
    with public_hosts(), patch_http_session(MODULE, *responses, html_response(page)) as session_mock:
        preview = asyncio.run(generate_link_preview(url))
    return preview, [call[1] for call in session_mock.return_value.calls]


@pytest.mark.parametrize(
    "url, expected",
    [
        (REDDIT_POST_URL, OLD_REDDIT_POST_URL),
        ("https://reddit.com/r/eagles/", "https://old.reddit.com/r/eagles/"),
        ("https://m.reddit.com/comments/1g2abcd", "https://old.reddit.com/comments/1g2abcd"),
        ("https://new.reddit.com/r/eagles/?sort=top", "https://old.reddit.com/r/eagles/?sort=top"),
        ("https://WWW.Reddit.com/r/eagles/", "https://old.reddit.com/r/eagles/"),
        # Already old Reddit.
        (OLD_REDDIT_POST_URL, OLD_REDDIT_POST_URL),
        # App share links only resolve on new Reddit; old Reddit bounces them to its submit page.
        ("https://www.reddit.com/r/eagles/s/AbCdEf1234", "https://www.reddit.com/r/eagles/s/AbCdEf1234"),
        ("https://www.reddit.com/u/birdsfan/s/AbCdEf1234", "https://www.reddit.com/u/birdsfan/s/AbCdEf1234"),
        # Reddit's other hosts, and lookalikes, are left alone.
        ("https://redd.it/1g2abcd", "https://redd.it/1g2abcd"),
        ("https://notreddit.com/r/eagles/", "https://notreddit.com/r/eagles/"),
        (URL, URL),
    ],
)
def test_metadata_url(url: str, expected: str):
    assert metadata_url(url) == expected


def test_reddit_post_fetched_from_old_reddit():
    """A Reddit post renders title, site name, description and image — taken from old Reddit's OpenGraph."""
    preview, requested = reddit_preview(REDDIT_POST_PAGE)
    assert requested == [OLD_REDDIT_POST_URL]
    assert preview == (
        "\n\n<b>Hurts to Brown for 6 &amp; we&#x27;re up 21-3</b>\n"
        "🔗 <i>reddit</i>\n"
        "\nPosted in r/eagles by u/birdsfan • 1,234 points and 210 comments\n"
        f"\n{REDDIT_IMAGE}\n"
    )
    # OpenGraph outranks the Twitter card, the meta description and the page `<title>`.
    assert "Twitter title" not in preview
    assert "Meta description" not in preview


def test_reddit_post_metadata():
    """The raw elements read from an old Reddit post, before rendering."""
    assert parse_link_metadata(REDDIT_POST_PAGE.encode(), OLD_REDDIT_POST_URL) == {
        "title": "Hurts to Brown for 6 & we're up 21-3",
        "description": "Posted in r/eagles by u/birdsfan • 1,234 points and 210 comments",
        # Entity-encoded `&amp;` comes back as a plain `&`, so the link works when posted.
        "image": REDDIT_IMAGE,
        "site_name": "reddit",
    }


def test_new_reddit_stub_is_never_fetched():
    """The stub's placeholder image is what the bot used to post; it's no longer requested at all."""
    with public_hosts(), patch_http_session(MODULE, html_response(REDDIT_POST_PAGE)) as session_mock:
        preview = asyncio.run(generate_link_preview(REDDIT_POST_URL))
    assert all(urlparse(call[1]).hostname == "old.reddit.com" for call in session_mock.return_value.calls)
    assert "share.redd.it" not in preview
    assert "Explore this post" not in preview


def test_reddit_text_post_has_no_image_line():
    """A self post without an image still previews; the card simply has no image."""
    preview, _ = reddit_preview(REDDIT_TEXT_POST_PAGE)
    assert preview == (
        "\n\n<b>Game thread etiquette</b>\n"
        "🔗 <i>reddit</i>\n"
        "\nPlease keep the game thread to the game. Memes go in the post-game thread.\n"
    )


def test_reddit_subreddit_link_previewed():
    preview, requested = reddit_preview(REDDIT_SUBREDDIT_PAGE, url="https://www.reddit.com/r/eagles/")
    assert requested == ["https://old.reddit.com/r/eagles/"]
    assert "<b>Philadelphia Eagles • r/eagles</b>" in preview
    assert "The home of Philadelphia Eagles fans on Reddit." in preview
    assert "https://styles.redditmedia.com/t5_2qhqk/styles/bannerBackgroundImage_abc.jpg" in preview


@pytest.mark.parametrize(
    "short_url, redirects_to",
    [
        # Post short link: Reddit redirects it to new Reddit's ID-only permalink.
        ("https://redd.it/1g2abcd", "https://www.reddit.com/comments/1g2abcd"),
        # Mobile app share link: new Reddit resolves it to the full permalink.
        ("https://www.reddit.com/r/eagles/s/AbCdEf1234", REDDIT_POST_URL),
        # Hosted video, which redirects to the post it belongs to.
        ("https://v.redd.it/abc123xyz", REDDIT_POST_URL),
    ],
)
def test_reddit_short_links_land_on_old_reddit(short_url: str, redirects_to: str):
    """Every redirect hop is rewritten, so a short link's destination is still fetched from old Reddit."""
    redirect = FakeResponse(status=301, headers={"Location": redirects_to})
    preview, requested = reddit_preview(REDDIT_POST_PAGE, redirect, url=short_url)
    assert requested == [short_url, metadata_url(redirects_to)]
    assert urlparse(requested[-1]).hostname == "old.reddit.com"
    assert "<b>Hurts to Brown for 6" in preview


def test_old_reddit_id_only_permalink_redirect_followed():
    """Old Reddit answers an ID-only permalink with a redirect to the full one, which is followed."""
    redirect = FakeResponse(status=301, headers={"Location": OLD_REDDIT_POST_URL})
    preview, requested = reddit_preview(REDDIT_POST_PAGE, redirect, url="https://www.reddit.com/comments/1g2abcd")
    assert requested == ["https://old.reddit.com/comments/1g2abcd", OLD_REDDIT_POST_URL]
    assert REDDIT_IMAGE in preview


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
