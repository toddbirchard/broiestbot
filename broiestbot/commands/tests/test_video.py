"""Tests for YouTube video link previews & searches."""

import json
from types import SimpleNamespace
from typing import List, Optional

import pytest
from requests.exceptions import ConnectTimeout

from broiestbot.commands import video
from broiestbot.commands.video import (
    YOUTUBE_FAILURE_RESPONSE,
    YOUTUBE_NO_RESULTS_RESPONSE,
    generate_youtube_video_preview,
    sanitize_youtube_query,
    search_youtube_video,
)
from config import (
    YOUTUBE_SEARCH_FAILURE_THRESHOLD,
    YOUTUBE_SEARCH_QUERY_MAX_LENGTH,
    YOUTUBE_SEARCH_REQUEST_RETRIES,
    YOUTUBE_SEARCH_REQUEST_TIMEOUT,
    YOUTUBE_VIDEO_ID_REGEX,
)

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
        self.kwargs: List[dict] = []

    def __call__(self, search_terms: str, max_results: Optional[int] = None, **kwargs) -> SimpleNamespace:
        self.queries.append(search_terms)
        self.kwargs.append({"max_results": max_results, **kwargs})
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


class ExplodingYoutubeSearch(FakeYoutubeSearch):
    """Stand-in for `YoutubeSearch` which fails the way YouTube's bad days make it fail."""

    def __init__(self, error: Exception):
        super().__init__([])
        self.error = error

    def __call__(self, search_terms: str, max_results: Optional[int] = None, **kwargs) -> SimpleNamespace:
        super().__call__(search_terms, max_results, **kwargs)
        raise self.error


@pytest.fixture(autouse=True)
def reset_youtube_circuit_breaker():
    """Clear failures recorded by a previous test so lookups aren't paused going in."""
    video._youtube_failure_count = 0
    video._youtube_paused_until = 0.0
    yield
    video._youtube_failure_count = 0
    video._youtube_paused_until = 0.0


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
        def __call__(self, search_terms, max_results=None, **kwargs):
            self.results = [YOUTUBE_RESULT] if self.queries else [{**YOUTUBE_RESULT, "id": "zubirYfcKNY"}]
            return super().__call__(search_terms, max_results, **kwargs)

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


# Every shape YouTube's bad days take: `youtube_search` slices a JSON blob out of a search page,
# so a consent wall has nothing to slice, shifted markup slices to something which isn't JSON, and
# a page rendered for another layout parses but holds no results.
SCRAPE_FAILURES = [
    pytest.param(json.JSONDecodeError("Expecting value", "", 0), id="unparsable-json"),
    pytest.param(ValueError("substring not found"), id="no-json-blob"),
    pytest.param(KeyError("contents"), id="unexpected-page-shape"),
    pytest.param(IndexError("list index out of range"), id="empty-page-section"),
    pytest.param(TypeError("'NoneType' object is not subscriptable"), id="null-page-section"),
    pytest.param(ConnectTimeout("youtube took too long"), id="network-timeout"),
    pytest.param(RuntimeError("something nobody predicted"), id="unforeseen"),
]


@pytest.mark.parametrize("error", SCRAPE_FAILURES)
def test_scrape_failures_never_escape_the_preview(error, monkeypatch):
    """Every way scraping YouTube blows up comes back as "no preview", never as an exception."""
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", ExplodingYoutubeSearch(error))

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None


@pytest.mark.parametrize("error", SCRAPE_FAILURES)
def test_scrape_failures_are_answered_with_an_excuse(error, monkeypatch):
    """A `?search` is an explicit ask, so a failed scrape earns an excuse rather than silence."""
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", ExplodingYoutubeSearch(error))

    assert search_youtube_video("how to fold a fitted sheet") == YOUTUBE_FAILURE_RESPONSE


def test_search_without_results_says_so(youtube_search_without_results):
    """A search YouTube answered with nothing is distinguished from one which failed."""
    assert search_youtube_video("how to fold a fitted sheet") == YOUTUBE_NO_RESULTS_RESPONSE


def test_search_renders_the_first_result(youtube_search):
    """A successful search renders the video's metadata & a canonical link to it."""
    response = search_youtube_video("never gonna give you up")

    assert youtube_search.query == "never gonna give you up"
    assert f"<b>{YOUTUBE_RESULT['title']}</b>" in response
    assert YOUTUBE_RESULT["thumbnails"][0] in response
    assert f"https://youtu.be/{VIDEO_ID}" in response


# ---------------------------------------------------------------------------
# Guardrails: bad results, bad queries & repeated failures
# ---------------------------------------------------------------------------


def test_results_missing_metadata_are_never_rendered(monkeypatch):
    """`youtube_search` fills unreadable fields with `None`, which must not reach chat.

    Each result is assembled from `.get()` chains against YouTube's markup, so a result whose
    shape the scraper didn't recognize arrives fully-formed & empty rather than raising.
    """
    empty_result = {key: None for key in YOUTUBE_RESULT}
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", FakeYoutubeSearch([empty_result]))

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
    assert search_youtube_video("never gonna give you up") == YOUTUBE_NO_RESULTS_RESPONSE


def test_results_without_a_thumbnail_are_never_rendered(monkeypatch):
    """A `thumbnails` list of `None`s is truthy, but renders a preview with no image in it."""
    monkeypatch.setattr(
        "broiestbot.commands.video.YoutubeSearch",
        FakeYoutubeSearch([{**YOUTUBE_RESULT, "thumbnails": [None]}]),
    )

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None


def test_partial_metadata_is_omitted_rather_than_rendered_empty(monkeypatch):
    """Optional fields YouTube withheld are dropped from the preview instead of shown blank."""
    monkeypatch.setattr(
        "broiestbot.commands.video.YoutubeSearch",
        FakeYoutubeSearch([{**YOUTUBE_RESULT, "views": 0, "publish_time": None}]),
    )
    preview = generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}")

    assert preview is not None
    assert YOUTUBE_RESULT["title"] in preview
    assert f"Duration: {YOUTUBE_RESULT['duration']}" in preview
    assert "None" not in preview
    assert "👀" not in preview
    assert "📅" not in preview


def test_a_result_which_isnt_a_dict_is_discarded(monkeypatch):
    """Results are scraped, not typed, so one which isn't a video is thrown out."""
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", FakeYoutubeSearch(["not a video"]))

    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
    assert search_youtube_video("never gonna give you up") == YOUTUBE_NO_RESULTS_RESPONSE


def test_scrape_returning_something_other_than_a_list_is_discarded(monkeypatch):
    """`to_dict()` handing back a non-list is treated as a failed scrape, not iterated."""
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", FakeYoutubeSearch("💩"))

    assert search_youtube_video("never gonna give you up") == YOUTUBE_FAILURE_RESPONSE


@pytest.mark.parametrize("query", ["", "   ", "\n\t ", None, 42])
def test_empty_queries_never_reach_youtube(query, youtube_search):
    """A query with nothing in it is rejected rather than searched for."""
    assert sanitize_youtube_query(query) is None
    assert search_youtube_video(query) == YOUTUBE_NO_RESULTS_RESPONSE
    assert youtube_search.queries == []


def test_absurdly_long_queries_are_truncated(youtube_search):
    """A wall of text is trimmed to a length YouTube will actually accept."""
    search_youtube_video("z" * 5000)

    assert len(youtube_search.query) == YOUTUBE_SEARCH_QUERY_MAX_LENGTH


def test_scrapes_are_bounded_by_a_timeout_and_retry_cap(youtube_search):
    """Each scrape carries an explicit timeout so an outage can't tie up a worker thread."""
    search_youtube_video("never gonna give you up")

    assert youtube_search.kwargs[0]["timeout"] == YOUTUBE_SEARCH_REQUEST_TIMEOUT
    assert youtube_search.kwargs[0]["retries"] == YOUTUBE_SEARCH_REQUEST_RETRIES


def test_repeated_failures_pause_youtube_lookups(monkeypatch):
    """YouTube refusing to be scraped is a minutes-long outage, not a per-request one.

    Rather than paying several HTTP requests for every chat message throughout it, lookups stop
    being attempted for a cooldown once enough of them fail back to back.
    """
    fake = ExplodingYoutubeSearch(json.JSONDecodeError("Expecting value", "", 0))
    monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", fake)

    for _ in range(YOUTUBE_SEARCH_FAILURE_THRESHOLD):
        assert search_youtube_video("never gonna give you up") == YOUTUBE_FAILURE_RESPONSE
    attempts_before_pause = len(fake.queries)

    assert search_youtube_video("never gonna give you up") == YOUTUBE_FAILURE_RESPONSE
    assert generate_youtube_video_preview(f"https://youtu.be/{VIDEO_ID}") is None
    assert len(fake.queries) == attempts_before_pause, "YouTube was scraped while lookups were paused"


def test_a_successful_scrape_clears_past_failures(monkeypatch):
    """Failures have to be consecutive to pause lookups; a good scrape resets the count."""
    exploding = ExplodingYoutubeSearch(json.JSONDecodeError("Expecting value", "", 0))
    working = FakeYoutubeSearch([YOUTUBE_RESULT])

    for _ in range(YOUTUBE_SEARCH_FAILURE_THRESHOLD - 1):
        monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", exploding)
        assert search_youtube_video("never gonna give you up") == YOUTUBE_FAILURE_RESPONSE
        monkeypatch.setattr("broiestbot.commands.video.YoutubeSearch", working)
        assert search_youtube_video("never gonna give you up") != YOUTUBE_FAILURE_RESPONSE

    assert video._youtube_search_is_paused() is False
