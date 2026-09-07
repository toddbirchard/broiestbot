"""Lookup definitions via Wikipedia, Urban Dictionary, etc"""

import asyncio
from typing import Optional

from aiohttp import ClientError
from bs4 import BeautifulSoup
from emoji import emojize
from http_client import get_http_session, request_timeout
from logger import LOGGER
from PyMultiDictionary import MultiDictionary

from clients import async_wiki, wiki
from config import (
    GOOGLE_TRANSLATE_ENDPOINT,
    RAPID_API_KEY,
    URBAN_DICTIONARY_ENDPOINT,
)


def get_english_definition(user_name: str, word: str) -> str:
    """
    Fetch English Dictionary definition for a given phrase or word.

    :param str user_name: Chatango user requesting a definition.
    :param str word: Word or phrase to fetch English definition for.

    :returns: str
    """
    try:
        response = "\n\n\n"
        dictionary = MultiDictionary()
        word_definitions = dictionary.meaning("en", word)
        for i, word_type in enumerate(word_definitions[0]):
            definition = emojize(f":bookmark: {word_type}\n", language="en")
            definition += emojize(f":left_speech_bubble: {word_definitions[i + 1]}\n", language="en")
            if i < len(word_definitions[0]):
                definition += "\n"
            response += definition
        if response in ("\n\n\n", "\n\n\n\n"):
            return emojize(
                f":warning: @{user_name} there's no dictionary definition for `{word}`; learn english :warning:",
                language="en",
            )
        return response
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching English definition for `{word}`: {e}")
        return emojize(":warning: mfer you broke bot :warning:", language="en")


async def get_urban_definition(term: str) -> str:
    """
    Fetch Urban Dictionary definition for a given phrase or word.

    :param str term: Word or phrase to fetch UD definition for.

    :returns: str
    """
    params = {"term": term}
    headers = {"Content-Type": "application/json"}
    try:
        session = await get_http_session()
        async with session.get(URBAN_DICTIONARY_ENDPOINT, params=params, headers=headers) as resp:
            results = (await resp.json(content_type=None)).get("list")
        if results:
            word = term.upper()
            results = sorted(results, key=lambda i: i["thumbs_down"], reverse=True)
            definition = (str(results[0].get("definition")).replace("[", "").replace("]", ""))[0:1500]
            example = results[0].get("example")
            if example:
                example = str(example).replace("[", "").replace("]", "")[0:250]
                return f"{word}:\n\n {definition} \n\n EXAMPLE: {example}"
            return f"{word}:\n\n {definition}"
        return emojize(":warning: idk wtf ur trying to search for tbh :warning:", language="en")
    except ClientError as e:
        LOGGER.exception(f"ClientError while trying to get Urban definition for `{term}`: {e}")
        return emojize(":warning: wtf urban dictionary is down :warning:", language="en")
    except LookupError as e:
        LOGGER.exception(f"LookupError error when fetching Urban definition for `{term}`: {e}")
        return emojize(":warning: mfer you broke bot :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error when fetching Urban definition for `{term}`: {e}")
        return emojize(":warning: mfer you broke bot :warning:", language="en")


def wiki_summary(query: str) -> str:
    """
    Fetch Wikipedia summary for a given query.

    :param str query: Query to fetch corresponding Wikipedia page.

    :returns: str
    """
    try:
        wiki_page = wiki.page(query)
        if wiki_page.exists():
            title = wiki_page.title.upper()
            main_category = list(wiki_page.categories.values())[0].title.replace("Category:", "Category: ")
            text = wiki_page.text
            if "disambiguation" in main_category and "Other uses" in text:
                text = text.split("Other uses")[0]
            return f"\n\n\n\n{title}: {text[0:1500]}\n \n\n {main_category}"
        return emojize(f":warning: bruh i couldnt find shit for `{query}` :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching wiki summary for `{query}`: {e}")
        return emojize(
            f":warning: BRUH YOU BROKE THE BOT WTF IS `{query}`?! :warning:",
            language="en",
        )


async def create_wiki_preview(url: str) -> Optional[str]:
    """
    Create a link preview for a Wikipedia URL.

    :param str chat_message: Chat message containing URL to a Wikipedia page.

    :returns: Optional[str]
    """
    try:
        page_title = url.split("/")[-1]
        # `AsyncWikipedia.page()` builds a stub without touching the network; each property
        # below is an awaitable which fetches (and caches) on first await. The blocking client
        # fetches on plain attribute access instead, which would stall the event loop here.
        page = async_wiki.page(page_title)
        # Scraping the page for its `og:image` is independent of the API lookups, so overlap
        # them. `displaytitle` costs an `info` call & `summary` an `extracts` call; `sections`
        # is then served from the `extracts` response already cached on the page.
        page_html, display_title, summary = await asyncio.gather(
            _fetch_wiki_page_html(url),
            page.displaytitle,
            page.summary,
        )
        # Served from the `info` response `displaytitle` already fetched, so this costs nothing.
        # Without it a dead link renders a preview card reading "<b>None</b>".
        if not await page.exists():
            LOGGER.info(f"No Wikipedia page exists for `{page_title}`; skipping preview.")
            return None
        sections = await page.sections

        wiki_preview = "\n\n\n\n"
        wiki_preview += f"<b>{display_title}</b>\n\n"
        wiki_preview += f"{summary}\n\n"
        img_tag = BeautifulSoup(page_html, "html.parser").find("meta", property="og:image") if page_html else None
        wiki_preview += f"{img_tag.get('content')} \n\n" if img_tag is not None else ""
        # Guarded on the sections themselves; the old check named a bound method, so it was
        # always true and `sections[0]` raised on a page which had none.
        wiki_preview += f"{sections[0].text[0:500]}\n\n" if sections else "\n\n"
        section_titles = [section._title for section in sections if section._title != "See also"]
        wiki_preview += "- " + "\n- ".join(section_titles) + "\n\n" if section_titles else ""
        return wiki_preview
    except Exception as e:
        LOGGER.exception(f"Unexpected error while creating Wikipedia preview for `{url}`: {e}")
        return None


async def _fetch_wiki_page_html(url: str) -> Optional[bytes]:
    """
    Fetch the raw HTML of a Wikipedia page, used only to scrape its `og:image`.

    Returns None rather than raising, so a failed scrape costs the preview its image
    instead of the whole preview.

    :param str url: URL of the Wikipedia page.

    :returns: Optional[bytes]
    """
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
    }
    try:
        session = await get_http_session()
        async with session.get(url, headers=headers) as resp:
            return await resp.read()
    except ClientError as e:
        LOGGER.warning(f"ClientError while fetching Wikipedia page HTML for `{url}`: {e}")
    except Exception as e:
        LOGGER.warning(f"Unexpected error while fetching Wikipedia page HTML for `{url}`: {e}")
    return None


async def get_english_translation(language_symbol: str, language_full_name: str, phrase: str) -> str:
    """
    Translate a non-english phrase into English.

    :param str language_symbol: Language `symbol` to translate from.
    :param str language_full_name: Language full-name, including flag emoji.
    :param str phrase: Message to be translated.

    :return: str
    """
    try:
        url = GOOGLE_TRANSLATE_ENDPOINT
        data = {
            "q": phrase,
            "target": "en",
            "source": language_symbol,
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "accept-encoding": "application/gzip",
            "X-RapidAPI-Key": RAPID_API_KEY,
            "X-RapidAPI-Host": "google-translate1.p.rapidapi.com",
        }
        session = await get_http_session()
        async with session.post(url, data=data, headers=headers, timeout=request_timeout(30)) as resp:
            if resp.status == 429:
                return "⚠️ yall translated too much shit this month now google tryna charge me smh ⚠️"
            translation = await resp.json(content_type=None)
        language_emoji = language_full_name.split(" ", 1)[0]
        language_name = language_full_name.split(" ", 1)[1].upper()
        return emojize(
            f'{language_emoji} <b>{language_name} TRANSLATION</b>: {translation["data"]["translations"][0]["translatedText"]}',
            language="en",
        )
    except ClientError as e:
        LOGGER.exception(f"ClientError while translating `{phrase}`: {e}")
        return f"⚠️ wtf you broke the api with ur {language_full_name}? SPEAK ENGLISH ⚠️"
    except LookupError as e:
        LOGGER.exception(f"LookupError error while translating `{phrase}`: {e}")
        return f"⚠️ mfer you broke bot with ur {language_full_name}? SPEAK ENGLISH ⚠️"
    except Exception as e:
        LOGGER.exception(f"Unexpected error while translating `{phrase}`: {e}")
        return f"⚠️ mfer you broke bot with ur {language_full_name}? SPEAK ENGLISH ⚠️"
