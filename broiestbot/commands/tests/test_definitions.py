"""Tests for the Wikipedia link preview.

`wikipediaapi` pages fetch lazily on attribute access, so the blocking client fetched over
the network wherever `.summary` / `.displaytitle` / `.sections` were read — on the event
loop, despite the page object itself being built in a thread. The preview now uses the
async client, whose equivalent properties are awaitables.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from broiestbot.commands.definitions import create_wiki_preview

URL = "https://en.wikipedia.org/wiki/Association_football"
PAGE_HTML = b'<html><head><meta property="og:image" content="https://upload.test/img.jpg"></head></html>'


def build_page(exists: bool = True, sections: list = None, display_title: str = "Association football"):
    """
    Build a stand-in `AsyncWikipediaPage` whose data properties are awaitables.

    :param bool exists: Whether the page exists on Wikipedia.
    :param list sections: Section stubs the page should report.
    :param str display_title: The page's rendered title.

    :returns: MagicMock
    """
    page = MagicMock()
    page.exists = AsyncMock(return_value=exists)

    async def _value(v):
        return v

    # `displaytitle`/`summary`/`sections` are properties returning coroutines.
    type(page).displaytitle = property(lambda _: _value(display_title))
    type(page).summary = property(lambda _: _value("Association football is a team sport."))
    type(page).sections = property(lambda _: _value(sections if sections is not None else []))
    return page


def build_section(title: str, text: str = "section body"):
    section = MagicMock()
    section._title = title
    section.text = text
    return section


def run_preview(page, page_html=PAGE_HTML):
    """Run `create_wiki_preview` with the wiki client & HTML fetch stubbed out."""
    with patch("broiestbot.commands.definitions.async_wiki") as wiki:
        wiki.page.return_value = page
        with patch(
            "broiestbot.commands.definitions._fetch_wiki_page_html",
            new=AsyncMock(return_value=page_html),
        ):
            return asyncio.run(create_wiki_preview(URL))


def test_preview_renders_title_summary_and_image():
    """A normal page yields its title, summary, og:image & section list."""
    page = build_page(sections=[build_section("History"), build_section("Rules")])
    preview = run_preview(page)

    assert "<b>Association football</b>" in preview
    assert "Association football is a team sport." in preview
    assert "https://upload.test/img.jpg" in preview
    assert "- History" in preview and "- Rules" in preview


def test_missing_page_returns_no_preview():
    """A dead Wikipedia link produces no preview rather than a card reading 'None'."""
    page = build_page(exists=False, display_title=None)
    assert run_preview(page) is None


def test_page_without_sections_does_not_raise():
    """A page with no sections still previews; the old check indexed into an empty list."""
    page = build_page(sections=[])
    preview = run_preview(page)

    assert preview is not None
    assert "<b>Association football</b>" in preview


def test_see_also_section_is_excluded():
    """`See also` is filtered out of the section list."""
    page = build_page(sections=[build_section("History"), build_section("See also")])
    preview = run_preview(page)

    assert "- History" in preview
    assert "See also" not in preview


def test_failed_image_scrape_still_previews():
    """Losing the og:image scrape costs the image, not the whole preview."""
    page = build_page(sections=[build_section("History")])
    preview = run_preview(page, page_html=None)

    assert preview is not None
    assert "<b>Association football</b>" in preview
    assert "upload.test" not in preview


def test_uses_the_async_client_not_the_blocking_one():
    """The blocking `wiki` client must never be touched from this coroutine."""
    page = build_page(sections=[build_section("History")])
    with patch("broiestbot.commands.definitions.wiki") as blocking_wiki:
        run_preview(page)
    blocking_wiki.page.assert_not_called()
