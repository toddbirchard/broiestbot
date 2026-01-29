"""Lookup definitions via Wikipedia, Urban Dictionary, etc"""

from typing import Optional
import requests
from emoji import emojize
from PyMultiDictionary import MultiDictionary
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup

from clients import wiki
from config import (
    RAPID_API_KEY,
    HTTP_REQUEST_TIMEOUT,
    GOOGLE_TRANSLATE_ENDPOINT,
    URBAN_DICTIONARY_ENDPOINT,
)
from logger import LOGGER


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


def get_urban_definition(term: str) -> str:
    """
    Fetch Urban Dictionary definition for a given phrase or word.

    :param str term: Word or phrase to fetch UD definition for.

    :returns: str
    """
    params = {"term": term}
    headers = {"Content-Type": "application/json"}
    try:
        req = requests.get(
            URBAN_DICTIONARY_ENDPOINT,
            params=params,
            headers=headers,
            timeout=HTTP_REQUEST_TIMEOUT,
        )
        results = req.json().get("list")
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
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while trying to get Urban definition for `{term}`: {e.response.content}")
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


def create_wiki_preview(url: str) -> Optional[str]:
    """
    Create a link preview for a Wikipedia URL.

    :param str chat_message: Chat message containing URL to a Wikipedia page.

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
        wiki_preview = "\n\n\n\n"
        page_title = url.split("/")[-1]
        page = wiki.page(page_title)
        html = BeautifulSoup(req.content, "html.parser")
        img_tag = html.find("meta", property="og:image")
        wiki_preview += f"<b>{page.displaytitle}</b>\n\n"
        wiki_preview += f"{page.summary}\n\n"
        wiki_preview += f"{img_tag.get('content')} \n\n" if img_tag is not None else ""
        wiki_preview += f"{page.sections[0].text[0:500]}\n\n" if page.sections_by_title else "\n\n"
        wiki_preview += (
            "- " + "\n- ".join([section._title for section in page.sections if section._title != "See also"]) + "\n\n"
        )
        return wiki_preview
    except Exception as e:
        LOGGER.exception(f"Unexpected error while creating Wikipedia preview for `{url}`: {e}")
        return None


def get_english_translation(language_symbol: str, language_full_name: str, phrase: str) -> str:
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
        res = requests.request("POST", url, data=data, headers=headers, timeout=30)
        if res.status_code == 429:
            return emojize(
                f":warning: yall translated too much shit this month now google tryna charge me smh :warning:",
                language="en",
            )
        language_emoji = language_full_name.split(" ", 1)[0]
        language_name = language_full_name.split(" ", 1)[1].upper()
        return emojize(
            f'{language_emoji} <b>{language_name} TRANSLATION</b>: {res.json()["data"]["translations"][0]["translatedText"]}',
            language="en",
        )
    except HTTPError as e:
        LOGGER.exception(f"HTTPError while translating `{phrase}`: {e.response.content}")
        return emojize(":warning: wtf you broke the api? SPEAK ENGLISH :warning:", language="en")
    except LookupError as e:
        LOGGER.exception(f"LookupError error while translating `{phrase}`: {e}")
        return emojize(":warning: mfer you broke bot SPEAK ENGLISH :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while translating `{phrase}`: {e}")
        return emojize(":warning: mfer you broke bot SPEAK ENGLISH :warning:", language="en")
