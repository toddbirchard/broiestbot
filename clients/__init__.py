"""Clients & SDKs for interacting with third-party services."""

import lyricsgenius
import praw
import wikipediaapi
from imdb import Cinemagoer
from redis import Redis
from rq_scheduler import Scheduler
from twilio.rest import Client

from config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_CHART_BASE_URL,
    ALPHA_VANTAGE_PRICE_BASE_URL,
    ANTHROPIC_API_KEY,
    GOOGLE_BUCKET_NAME,
    GOOGLE_BUCKET_URL,
    IEX_API_BASE_URL,
    IEX_API_TOKEN,
    IP_DATA_KEY,
    PLAYSTATION_SSO_TOKEN,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_PASSWORD,
    REDDIT_USERNAME,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USERNAME,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
)

from .crypto import CryptoChartHandler
from .gcs import GCS
from .geo import GeoIP
from .llm import LLMClient
from .psn import PlaystationClient
from .stock import StockChartHandler

# Google Cloud Storage
gcs = GCS(GOOGLE_BUCKET_NAME, GOOGLE_BUCKET_URL)

# IEX Charts
sch = StockChartHandler(token=IEX_API_TOKEN, endpoint=IEX_API_BASE_URL)

# Crypto Charts
cch = CryptoChartHandler(
    token=ALPHA_VANTAGE_API_KEY,
    price_endpoint=ALPHA_VANTAGE_PRICE_BASE_URL,
    chart_endpoint=ALPHA_VANTAGE_CHART_BASE_URL,
)

# Wikipedia API Python SDK
WIKI_USER_AGENT = "BroiestBot/1.0 (https://github.com/toddbirchard/broiestbot; broiestbot@eample.com)"

# Blocking client, for the handlers dispatched through `asyncio.to_thread`.
wiki = wikipediaapi.Wikipedia(WIKI_USER_AGENT, language="en")

# Non-blocking client (httpx.AsyncClient under the hood), for handlers awaited on the event
# loop. A `WikipediaPage` fetches lazily on attribute access, so a page held by the blocking
# client blocks the loop wherever its attributes are read — use this one from `async def`.
async_wiki = wikipediaapi.AsyncWikipedia(WIKI_USER_AGENT, language="en")

# Twilio SMS Client
sms = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# IMDB Client
ia = Cinemagoer()

# Reddit API Python SDK
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent="bot",
)

# IP Data Client
geo = GeoIP(IP_DATA_KEY)

# Rap Genius
genius = lyricsgenius.Genius()
genius.remove_section_headers = True

# Redis
r = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, password=REDIS_PASSWORD)
redis_scheduler = Scheduler(connection=r)

# Playstation
psn = PlaystationClient(PLAYSTATION_SSO_TOKEN)

# Anthropic LLM Client
claude = LLMClient()

# Redgifs: `redgifs.aio.API` opens an `aiohttp.ClientSession` in its constructor, so it needs a
# running event loop and cannot be built here at import time. See `commands/afterdark.py`.
