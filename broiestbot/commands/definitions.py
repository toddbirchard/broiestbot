"""Lookup definitions via Wikipedia, Urban Dictionary, etc"""
import requests
from emoji import emojize
from requests.exceptions import HTTPError

from clients import wiki
from config import RAPID_API_KEY
from logger import LOGGER


def get_urban_definition(term: str) -> str:
    """
    Fetch Urban Dictionary definition for a given phrase or word.

    :param term: Word or phrase to fetch UD definition for.
    :type term: str
    :returns: str
    """
    params = {"term": term}
    headers = {"Content-Type": "application/json"}
    try:
        req = requests.get(
            "http://api.urbandictionary.com/v0/define", params=params, headers=headers
        )
        results = req.json().get("list")
        if results:
            word = term.upper()
            results = sorted(results, key=lambda i: i["thumbs_down"], reverse=True)
            definition = (
                str(results[0].get("definition")).replace("[", "").replace("]", "")
            )[0:1500]
            example = results[0].get("example")
            if example:
                example = str(example).replace("[", "").replace("]", "")[0:250]
                return f"{word}:\n\n {definition} \n\n EXAMPLE: {example}"
            return f"{word}:\n\n {definition}"
        return emojize(
            ":warning: idk wtf ur trying to search for tbh :warning:", use_aliases=True
        )
    except HTTPError as e:
        LOGGER.error(
            f"HTTPError while trying to get Urban definition for `{term}`: {e.response.content}"
        )
        return emojize(
            f":warning: wtf urban dictionary is down :warning:", use_aliases=True
        )
    except KeyError as e:
        LOGGER.error(f"KeyError error when fetching Urban definition for `{term}`: {e}")
        return emojize(":warning: mfer you broke bot :warning:", use_aliases=True)
    except IndexError as e:
        LOGGER.error(
            f"IndexError error when fetching Urban definition for `{term}`: {e}"
        )
        return emojize(":warning: mfer you broke bot :warning:", use_aliases=True)
    except Exception as e:
        LOGGER.error(
            f"Unexpected error when fetching Urban definition for `{term}`: {e}"
        )
        return emojize(":warning: mfer you broke bot :warning:", use_aliases=True)


def wiki_summary(query: str) -> str:
    """
    Fetch Wikipedia summary for a given query.

    :param query: Query to fetch corresponding Wikipedia page.
    :type query: str
    :returns: str
    """
    try:
        wiki_page = wiki.page(query)
        if wiki_page.exists():
            return f"{wiki_page.title.upper()}: {wiki_page.summary[0:1500]}"
        return emojize(
            f":warning: bruh i couldnt find shit for `{query}` :warning:",
            use_aliases=True,
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while fetching wiki summary for `{query}`: {e}")
        return emojize(
            f":warning: BRUH YOU BROKE THE BOT WTF IS `{query}`?! :warning:",
            use_aliases=True,
        )


def get_english_translation(language: str, phrase: str):
    """
    Translate a phrase between languages.

    :param language: Language to translate from into English
    :type language: str
    :param phrase: Message to be translated.
    :type phrase: str
    :return: str
    """
    try:
        url = "https://google-translate1.p.rapidapi.com/language/translate/v2"
        data = {
            "q": phrase,
            "target": "en",
            "source": language,
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "accept-encoding": "application/gzip",
            "x-rapidapi-key": RAPID_API_KEY,
            "x-rapidapi-host": "google-translate1.p.rapidapi.com",
        }
        res = requests.request("POST", url, data=data, headers=headers)
        return (
            f'TRANSLATION: `{res.json()["data"]["translations"][0]["translatedText"]}`'
        )
    except HTTPError as e:
        LOGGER.error(f"HTTPError while translating `{phrase}`: {e.response.content}")
        return emojize(
            f":warning: wtf you broke the api? SPEAK ENGLISH :warning:",
            use_aliases=True,
        )
    except KeyError as e:
        LOGGER.error(f"KeyError error while translating `{phrase}`: {e}")
        return emojize(
            ":warning: mfer you broke bot SPEAK ENGLISH :warning:", use_aliases=True
        )
    except IndexError as e:
        LOGGER.error(f"IndexError error while translating `{phrase}`: {e}")
        return emojize(
            ":warning: mfer you broke bot SPEAK ENGLISH :warning:", use_aliases=True
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error while translating `{phrase}`: {e}")
        return emojize(
            ":warning: mfer you broke bot SPEAK ENGLISH :warning:", use_aliases=True
        )
