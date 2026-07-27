"""Tests for YouTube video link previews."""

from types import SimpleNamespace
from typing import List, Optional

import pytest

from broiestbot.commands.video import generate_youtube_video_preview
from config import YOUTUBE_VIDEO_ID_REGEX

VIDEO_ID = "dQw4w9WgXcQ"

# YouTube's search only resolves a video from a *canonical* watch URL; a bare video ID
# ranks as a plain search term and surfaces an unrelated video.
CANONICAL_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

# A single result as scraped by `youtube_search.YoutubeSearch.to_dict()`.
YOUTUBE_RESULT = {
    "id": VIDEO_ID,
    "thumbnails": ["https://i.ytimg.com/vi/dQw4w9WgXcQ/hq720.jpg"],
    "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
    "long_desc": "The official video for Never Gonna Give You Up",
    "channel": "Rick Astley",
    "duration": "3:33",
    "views": "1,600,000,000 views",
    "publish_time": "16 years ago",
    "url_suffix": "/watch?v=dQw4w9WgXcQ",
}

# Every YouTube URL shape which shows up in chat, each pointing at `VIDEO_ID`.
YOUTUBE_URLS = [
    # Standard watch URLs
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    "www.youtube.com/watch?v=dQw4w9WgXcQ",
    # Shortened URLs
    "https://youtu.be/dQw4w9WgXcQ",
    "youtu.be/dQw4w9WgXcQ",
    # Shorts
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    # Live streams
    "https://www.youtube.com/live/dQw4w9WgXcQ",
    # Embeds
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
    "https://www.youtube.com/e/dQw4w9WgXcQ",
    "https://www.youtube.com/v/dQw4w9WgXcQ",
    "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
]

# The same URLs carrying the extra querystring params YouTube's share dialog tacks on.
YOUTUBE_URLS_WITH_PARAMS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLFgquLnL59ak5C6t2Xr3XkPSXNMcXOSpz&index=3",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=youtu.be&ab_channel=RickAstley",
    "https://www.youtube.com/watch?app=desktop&v=dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ&pp=ygUJcmljayByb2xs",
    "https://youtu.be/dQw4w9WgXcQ?si=Xyz-123_abcd",
    "https://youtu.be/dQw4w9WgXcQ?t=42",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share",
    "https://www.youtube.com/live/dQw4w9WgXcQ?si=Xyz-123_abcd",
    "https://www.youtube.com/embed/dQw4w9WgXcQ?start=42&autoplay=1",
]

# Messages which must never trigger a YouTube preview, so that link previews for other
# services (X, Wikipedia) still get their turn in `Bot.on_message`'s if/elif chain.
NON_YOUTUBE_MESSAGES = [
    "hello world",
    "youtube.com is a website",
    "i love youtube",
    "https://www.youtube.com/@RickAstleyYT",
    "https://x.com/PSG_inside/status/1234567890123456789",
    "https://en.wikipedia.org/wiki/YouTube",
    "https://vimeo.com/347119375",
    "https://youtu.be/tooshort",
]


class FakeYoutubeSearch:
    """Stand-in for `YoutubeSearch` which records queries instead of scraping YouTube."""

    def __init__(self, results: Optional[list]):
        self.results = results
        self.queries: List[str] = []

    def __call__(self, search_terms: str, max_results: Optional[int] = None) -> SimpleNamespace:
        self.queries.append(search_terms)
        return SimpleNamespace(to_dict=lambda clear_cache=True: self.results)

    @property
    def query(self) -> Optional[str]:
        """The single query issued, asserting no others were made."""
        assert len(self.queries) == 1, f"expected exactly one YouTube query, got {self.queries}"
        return self.queries[0]

    @property
    def unique_queries(self) -> set:
        """The distinct queries issued, ignoring retries of the same lookup."""
        return set(self.queries)


@pytest.fixture
def youtube_search(monkeypatch) -> FakeYoutubeSearch:
    """Patch `YoutubeSearch` to return a canned video result."""
    fake = FakeYoutubeSearch([YOUTUBE_RESULT])
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", fake)
    return fake


@pytest.fixture
def youtube_search_without_results(monkeypatch) -> FakeYoutubeSearch:
    """Patch `YoutubeSearch` to return no results at all."""
    fake = FakeYoutubeSearch([])
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", fake)
    return fake


# ---------------------------------------------------------------------------
# Video ID extraction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", YOUTUBE_URLS + YOUTUBE_URLS_WITH_PARAMS)
def test_video_id_is_extracted_from_every_url_variant(url):
    """Watch URLs, shortlinks, shorts, live streams & embeds all yield the video ID."""
    match = YOUTUBE_VIDEO_ID_REGEX.search(url)
    assert match is not None, f"no video ID found in {url}"
    assert match.group(1) == VIDEO_ID


@pytest.mark.parametrize(
    "url,video_id",
    [
        ("https://youtu.be/2Vv-BfVoq4g", "2Vv-BfVoq4g"),
        ("https://www.youtube.com/watch?v=aB3_-dEfGh1", "aB3_-dEfGh1"),
        ("https://www.youtube.com/shorts/_-aB3dEfGh1", "_-aB3dEfGh1"),
    ],
)
def test_video_ids_may_contain_hyphens_and_underscores(url, video_id):
    """Hyphens & underscores are legal in video IDs and aren't treated as delimiters."""
    assert YOUTUBE_VIDEO_ID_REGEX.search(url).group(1) == video_id


@pytest.mark.parametrize("message", NON_YOUTUBE_MESSAGES)
def test_non_youtube_messages_are_ignored(message, youtube_search):
    """Messages without a YouTube video are skipped without hitting YouTube."""
    assert YOUTUBE_VIDEO_ID_REGEX.search(message) is None
    assert generate_youtube_video_preview(message) is None
    assert youtube_search.queries == []


# ---------------------------------------------------------------------------
# Preview generation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", YOUTUBE_URLS)
def test_preview_is_generated_for_every_url_variant(url, youtube_search):
    """Every YouTube URL shape produces a preview for the video it points at."""
    preview = generate_youtube_video_preview(url)

    assert preview is not None, f"no preview generated for {url}"
    assert youtube_search.query == CANONICAL_URL
    assert YOUTUBE_RESULT["title"] in preview


@pytest.mark.parametrize("url", YOUTUBE_URLS_WITH_PARAMS)
def test_extra_querystring_params_do_not_break_previews(url, youtube_search):
    """Share-dialog params (`&t=`, `?si=`, `&list=`) are stripped before searching.

    Searching the full URL lets these tokens derail YouTube's result ranking, which
    previously returned an unrelated video or nothing at all.
    """
    preview = generate_youtube_video_preview(url)

    assert preview is not None, f"no preview generated for {url}"
    assert youtube_search.query == CANONICAL_URL
    assert YOUTUBE_RESULT["title"] in preview


def test_preview_contains_all_video_metadata(youtube_search):
    """Previews carry the thumbnail, title, duration, views, channel & publish date."""
    preview = generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}")

    assert YOUTUBE_RESULT["thumbnails"][0] in preview
    assert YOUTUBE_RESULT["title"] in preview
    assert f"Duration: {YOUTUBE_RESULT['duration']}" in preview
    assert YOUTUBE_RESULT["views"] in preview
    assert f"Channel: {YOUTUBE_RESULT['channel']}" in preview
    assert YOUTUBE_RESULT["publish_time"] in preview


def test_preview_links_to_a_canonical_url(youtube_search):
    """The preview's link is rebuilt from the video ID rather than echoed from chat."""
    preview = generate_youtube_video_preview("check this out https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s lol")

    assert f"https://youtu.be/{VIDEO_ID}" in preview
    assert "check this out" not in preview
    assert "lol" not in preview
    assert "&t=42s" not in preview


def test_preview_is_prefixed_with_newlines(youtube_search):
    """Previews open with blank lines so Chatango renders the thumbnail on its own."""
    preview = generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}")

    assert preview.startswith("\n\n\n\n")


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_video_without_search_results_has_no_preview(youtube_search_without_results):
    """A video YouTube's search can't surface is skipped rather than half-rendered."""
    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
    assert youtube_search_without_results.unique_queries == {CANONICAL_URL}


def test_unrelated_search_result_has_no_preview(monkeypatch):
    """A result for some *other* video is discarded rather than previewed as this one."""
    fake = FakeYoutubeSearch([{**YOUTUBE_RESULT, "id": "zubirYfcKNY"}])
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", fake)

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
    assert fake.unique_queries == {CANONICAL_URL}


def test_wrong_video_is_retried(monkeypatch):
    """YouTube serving a suggestion in place of the video is retried, not given up on."""

    class FlakyYoutubeSearch(FakeYoutubeSearch):
        def __call__(self, search_terms, max_results=None):
            self.results = [YOUTUBE_RESULT] if self.queries else [{**YOUTUBE_RESULT, "id": "zubirYfcKNY"}]
            return super().__call__(search_terms, max_results)

    fake = FlakyYoutubeSearch([])
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", fake)
    preview = generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}")

    assert preview is not None
    assert YOUTUBE_RESULT["title"] in preview
    assert len(fake.queries) == 2


def test_incomplete_search_result_has_no_preview(monkeypatch):
    """A result missing expected keys is skipped rather than raising."""
    monkeypatch.setattr(
        "broiestbot.commands.video.YoutubeSearch",
        FakeYoutubeSearch([{"id": VIDEO_ID, "title": "Never Gonna Give You Up"}]),
    )

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None


def test_youtube_outage_has_no_preview(monkeypatch):
    """An exception while scraping YouTube is swallowed so the bot keeps running."""

    def explode(*args, **kwargs):
        raise ConnectionError("youtube is down")

    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", explode)

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
