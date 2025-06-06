"""Clients & SDKs for interacting with third-party services."""

import lyricsgenius
import praw
from redis import Redis
import wikipediaapi
from rq_scheduler import Scheduler

from imdb import Cinemagoer
from twilio.rest import Client

from config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_CHART_BASE_URL,
    ALPHA_VANTAGE_PRICE_BASE_URL,
    GOOGLE_BUCKET_NAME,
    GOOGLE_BUCKET_URL,
    IEX_API_BASE_URL,
    IEX_API_TOKEN,
    IP_DATA_KEY,
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_PASSWORD,
    REDDIT_USERNAME,
    REDIS_USERNAME,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    PLAYSTATION_SSO_TOKEN,
)

from .crypto import CryptoChartHandler
from .gcs import GCS
from .geo import GeoIP
from .stock import StockChartHandler
from .psn import PlaystationClient

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
wiki = wikipediaapi.Wikipedia(
    "BroiestBot/1.0 (https://github.com/toddbirchard/broiestbot; broiestbot@eample.com)", "en"
)

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
