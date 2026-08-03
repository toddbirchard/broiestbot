"""Fetch crypto or stock market data."""

from aiohttp import ClientError
from emoji import emojize
from http_client import get_http_session
from logger import LOGGER

from clients import cch, sch
from config import COINMARKETCAP_API_KEY, COINMARKETCAP_LATEST_ENDPOINT


async def get_crypto_chart(symbol: str) -> str:
    """
    Fetch crypto price and generate 60-day performance chart.

    :param str symbol: Crypto symbol to fetch prices for.

    :returns: str
    """
    try:
        return await cch.get_crypto_chart(symbol)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching crypto price for `{symbol}`: {e}")
        return emojize(f":warning: omg the internet died AAAAA :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching crypto price for `{symbol}`: {e}")
        return emojize(
            ":warning: jfc stop abusing the crypto commands u fgts, you exceeded the API limit :@ :warning:",
            language="en",
        )


async def get_crypto_price(symbol: str, endpoint) -> str:
    """
    Fetch crypto price for a given coin symbol.

    :param str symbol: Crypto symbol to fetch price performance for.
    :param str endpoint: Endpoint for the requested crypto.

    :returns: str
    """
    try:
        return await cch.get_coin_price(symbol, endpoint)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching crypto price for `{symbol}`: {e}")
        return emojize(":warning: omg the internet died AAAAA :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching crypto price for `{symbol}`: {e}")
        return emojize(
            ":warning: jfc stop abusing the crypto commands u fgts, you exceeded the API limit :@ :warning:",
            language="en",
        )


async def get_stock(symbol: str) -> str:
    """
    Fetch stock price and generate 30-day performance chart.

    :param str symbol: Stock symbol to fetch prices for.

    :returns: str
    """
    try:
        # chart = sch.get_chart(symbol)
        return await sch.get_price(symbol)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching stock price for `{symbol}`: {e}")
        return emojize(":warning: ough nough da site i get stocks from died :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected error while fetching stock price for `{symbol}`: {e}")
        return emojize(":warning: i broke bc im a shitty bot :warning:", language="en")


async def get_top_crypto() -> str:
    """
    Fetch top 10 crypto coin performance.

    :returns: str
    """
    try:
        params = {"start": "1", "limit": "10", "convert": "USD"}
        headers = {
            "Accepts": "application/json",
            "X-CMC_PRO_API_KEY": COINMARKETCAP_API_KEY,
        }
        session = await get_http_session()
        async with session.get(COINMARKETCAP_LATEST_ENDPOINT, params=params, headers=headers) as resp:
            if resp.status == 200:
                coins = (await resp.json(content_type=None)).get("data")
                return format_top_crypto_response(coins)
    except ClientError as e:
        LOGGER.exception(f"ClientError while fetching top coins: {e}")
        return emojize(":warning: FUCK the bot broke :warning:", language="en")
    except Exception as e:
        LOGGER.exception(f"Unexpected exception while fetching top coins: {e}")
        return emojize(":warning: FUCK the bot broke :warning:", language="en")


def format_top_crypto_response(coins: dict):
    """
    Format a response depicting top-10 coin performance by market cap.

    :params dict coins: Performance of top 10 cryptocurrencies.

    :returns: dict
    """
    try:
        top_coins = "\n\n\n"
        for i, coin in enumerate(coins):
            top_coins += f"<b>{coin['name']} ({coin['symbol']})</b> ${'{:.3f}'.format(coin['quote']['USD']['price'])}\n"
            top_coins += f"1d change of {'{:.2f}'.format(coin['quote']['USD']['percent_change_24h'])}%\n"
            top_coins += f"7d change of {'{:.2f}'.format(coin['quote']['USD']['percent_change_7d'])}%\n"
            if i < len(coins):
                top_coins += "\n"
        return top_coins
    except KeyError as e:
        LOGGER.exception(f"KeyError while formatting top cryptocurrencies: {e}")
    except Exception as e:
        LOGGER.exception(f"Unexpected exception while formatting top cryptocurrencies: {e}")
