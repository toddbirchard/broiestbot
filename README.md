# BroiestBot

![Python](https://img.shields.io/badge/python-^3.12-blue.svg?longCache=true&style=flat-square&colorA=4c566a&colorB=5e81ac&logo=Python&logoColor=white)
![Chatango](https://img.shields.io/badge/chatango--lib-async-blue.svg?longCache=true&style=flat-square&colorA=4c566a&colorB=5e81ac&logo=ChatBot&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-^0.34.0-red.svg?longCache=true&style=flat-square&colorA=4c566a&colorB=5e81ac&logo=gunicorn&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-^2.0-red.svg?longCache=true&style=flat-square&logo=scala&logoColor=white&colorA=4c566a&colorB=bf616a)
![Anthropic](https://img.shields.io/badge/Anthropic-^0.100.0-red.svg?longCache=true&style=flat-square&colorA=4c566a&colorB=bf616a&logo=Anthropic&logoColor=white)
![GitHub Last Commit](https://img.shields.io/github/last-commit/toddbirchard/broiestbot.svg?style=flat-square&colorA=4c566a&logo=GitHub&colorB=a3be8c)
[![GitHub Issues](https://img.shields.io/github/issues/toddbirchard/broiestbot.svg?style=flat-square&colorA=4c566a&logo=GitHub&colorB=ebcb8b)](https://github.com/toddbirchard/broiestbot/issues)
[![GitHub Stars](https://img.shields.io/github/stars/toddbirchard/broiestbot.svg?style=flat-square&colorA=4c566a&logo=GitHub&colorB=ebcb8b)](https://github.com/toddbirchard/broiestbot/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/toddbirchard/broiestbot.svg?style=flat-square&colorA=4c566a&logo=GitHub&colorB=ebcb8b)](https://github.com/toddbirchard/broiestbot/network)

The baddest bot in the game right now. An async Python bot which joins [Chatango](https://www.chatango.com/) rooms via the [chatango-lib](https://github.com/toddbirchard/chatango-lib) framework and responds to user messages.

## Features

Every message the bot sees is checked against a handful of triggers:

* **`!command`**: Fires a function depending on the command's type. A directory of all commands can be found [here](http://broiestbro.com/table/commands).
* **`!!query`**: Skips commands entirely and returns an image search result.
* **`?query`**: Returns the top YouTube video result.
* **`@bro ...`**: Generates a response via Anthropic's Claude, using recent room history as context.
* **Links**: YouTube, X, and Wikipedia URLs are expanded into rich previews.
* **Phrases**: Non-command chats are matched against a table of trigger phrases.

Moderation (banning blacklisted users, anons, and IPs) and persistence of chat logs and user geo data happen on every message.

### Commands

Chat commands are rows in a database table with 3 properties:

* **Command name**: Text which triggers a command (ie: `!test`)
* **Response**: Value returned by a command, either sent directly as a chat, or processed further depending on command type.
* **Type**: Determines logic associated with a command.

Command handlers live in `broiestbot/commands/`, grouped by domain: footy, F1, NBA, NFL, MLB, sumo, betting odds, weather, images, movies, lyrics, crypto & stocks, PlayStation, polls, and more.

## Getting Started

### Installation

```shell
git clone https://github.com/toddbirchard/broiestbot.git
cd broiestbot
make install
make run
```

`make run` serves the ASGI app in `asgi.py` under uvicorn, bound to a local UNIX socket. The bot itself is started from the ASGI lifespan event — uvicorn is a process manager here, not a web server. Use `make kill` to stop a running instance.

Other useful targets:

```shell
make format   # isort + black
make lint     # flake8
make test     # pytest with an HTML coverage report
make update   # poetry update & regenerate requirements.txt
make clean    # remove caches, logs, & the virtualenv
```

### Configuration

Create a `.env` file with your Chatango configuration. These variables are required:

```env
ENVIRONMENT=production

# Bot accounts
CHATANGO_BOT_USERNAME=yourChatangoBotUsername
CHATANGO_BOT_PASSWORD=yourChatangoBotPassword
CHATANGO_BRO_USERNAME=yourSecondaryChatangoUsername
CHATANGO_BRO_PASSWORD=yourSecondaryChatangoPassword

# Rooms to join (see `CHATANGO_ROOMS` in config.py)
CHATANGO_LMAO_ROOM=yourChatangoRoom
CHATANGO_TEST_ROOM=yourChatangoTestRoom

# MySQL connection string; SSL cert expected at creds/ca-certificate.crt
SQLALCHEMY_DATABASE_URI=yourSqlDatabaseUri
```

`ENVIRONMENT=production` joins the rooms listed in `CHATANGO_ROOMS`; any other value joins only `CHATANGO_TEST_ROOM`.

These variables are optional to enable different services, such as pulling images from Google Cloud or fetching stock prices:

```env
# Data persistence toggles
PERSIST_CHAT_DATA=true
PERSIST_USER_DATA=true

# Moderation (comma-separated)
CHATANGO_SPECIAL_USERS=user1,user2
CHATANGO_BLACKLISTED_USERS=user1,user2
CHATANGO_IGNORED_USERS=user1,user2
CHATANGO_IGNORED_IPS=1.2.3.4
CHATANGO_BANNED_IPS=1.2.3.4

# LLM responses via `@bro`
ANTHROPIC_API_KEY=yourAnthropicApiKey

# Fetching .gifs
KLIPY_API_KEY=yourKlipyApiKey
GIPHY_API_KEY=yourGiphyApiKey
REDGIFS_ACCESS_KEY=yourRedgifsKey

# Fetching images from Google Cloud Storage
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_BUCKET_NAME=nameOfGcsBucket
GOOGLE_BUCKET_URL=urlOfGcsBucket

# Third party API keys/tokens
RAPID_API_KEY=yourRapidApiKey          # footy, F1, sumo, NFL, MLB
NBA_API_KEY=yourApiBasketballKey
SPORTSGAMEODDS_API_KEY=yourOddsApiKey
SLEEPER_LEAGUE_ID=yourSleeperLeagueId
IEX_API_TOKEN=yourIexApiToken
ALPHA_VANTAGE_API_KEY=yourAlphaVantageApiKey
COINMARKETCAP_API_KEY=yourCoinMarketCapKey
WEATHERSTACK_API_KEY=yourWeatherstackApiKey
IP_DATA_KEY=yourIpDataKey
OMDB_API_KEY=yourOmdbApiKey
YOUTUBE_API_KEY=yourYoutubeApiKey
GOOGLE_TRANSLATE_API_KEY=yourGoogleTranslateKey
PLAYSTATION_SSO_TOKEN=yourPsnSsoToken

# Chart generation
PLOTLY_API_KEY=yourPlotlyApiKey
PLOTLY_USERNAME=yourPlotlyUsername

# Text notifications
TWILIO_ACCOUNT_SID=yourTwilioAccountSid
TWILIO_AUTH_TOKEN=yourTwilioToken
TWILIO_SENDER_PHONE=123456789
TWILIO_BRO_PHONE_NUMBER=123456789      # one var per SMS recipient

# Song lyrics
GENIUS_KEY_ID=yourLyricsGeniusKey
GENIUS_KEY_SECRET=yourLyricsGeniusSecret

# Reddit images
REDDIT_CLIENT_ID=yourRedditClientId
REDDIT_CLIENT_SECRET=yourRedditClientSecret
REDDIT_USERNAME=yourRedditUsername

# Twitch stream alerts
TWITCH_CLIENT_ID=yourTwitchClientId
TWITCH_CLIENT_SECRET=yourTwitchClientSecret
TWITCH_BRO_USERNAME=yourTwitchUsername  # one username/id pair per tracked streamer
TWITCH_BRO_ID=yourTwitchUserId

# Redis cache
REDIS_HOST=yourRedisHost
REDIS_USERNAME=yourRedisUsername
REDIS_PASSWORD=yourRedisPassword
REDIS_PORT=yourRedisPort
REDIS_DB=yourRedisDb

# Datadog logging
DDOG_API_KEY=yourDatadogApiKey
DDOG_APP_KEY=yourDatadogAppKey
```

`config.py` is the authoritative list of supported environment variables.
