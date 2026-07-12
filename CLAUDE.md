# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

BroiestBot is a Python chatbot for the [Chatango](https://www.chatango.com/) platform. It uses a custom `ch.py` WebSocket framework (`chatango/`) to join rooms and respond to user messages. The bot handles two interaction types: `!command`-prefixed chat triggers (looked up from a MySQL database) and freeform phrase matching (also stored in the DB).

## Commands

```bash
make install    # Create .venv and install from requirements.txt
make run        # Run via gunicorn (binds to a UNIX socket)
make lint       # flake8 (errors + undefined names only: E9,F63,F7,F82)
make format     # isort + black
make test       # pytest with coverage, opens HTML report
make clean      # Remove caches, logs, .venv, poetry.lock
```

Run a single test file:
```bash
.venv/bin/python -m pytest broiestbot/commands/footy/tests/test_liveodds.py -v
```

The bot is not a web server — `gunicorn` here is used purely as a process manager. `wsgi:app` calls `start_bot()`, which blocks on `broiestbot.main()` (the Chatango event loop).

## Architecture

### Message Flow

1. `chatango/ch.py` delivers `on_message(room, user, message)` to `broiestbot/bot.py:Bot`.
2. `Bot.on_message` runs moderation checks, persists data, then routes based on message content:
   - `?<query>` → YouTube search
   - `!<cmd>` → `_process_command` → DB lookup → `create_message` → `room.message()`
   - YouTube/Twitter/Wikipedia URLs → auto-generate link previews
   - `@bro <message>` → LLM response via Anthropic Claude
   - Everything else → `_process_phrase` → DB phrase match
3. `create_message` is a large `if/elif` dispatch on `cmd_type` (the `type` column of the `commands` DB table), calling the appropriate function from `broiestbot/commands/`.

### Package Layout

- **`broiestbot/bot.py`** — Core `Bot(RoomManager)` class; all message routing lives here.
- **`broiestbot/commands/`** — One module per domain (footy, nba, nfl, weather, images, llm, etc.). All public command functions are re-exported through `broiestbot/commands/__init__.py`.
- **`broiestbot/data/`** — Persists chat logs and user geo/IP data to the DB after every message.
- **`broiestbot/moderation/`** — Ban/mute logic for blacklisted users, IPs, and specific phrases.
- **`clients/__init__.py`** — Single module that instantiates all third-party SDK clients at import time (Redis, Twilio, GCS, Wikipedia, IMDB, Reddit, Genius, PSN, Anthropic). Import from here rather than re-instantiating.
- **`database/__init__.py`** — Creates the SQLAlchemy `engine` and `session`; imported wherever DB access is needed.
- **`database/models.py`** — ORM models: `Command`, `Phrase`, `Chat`, `ChatangoUser`, `Weather`, `PollResult`, `Sport`, `League`.
- **`config.py`** — All configuration and constants loaded from `.env`. Includes hundreds of league/team IDs and API endpoints. Import constants from here; never hardcode them.
- **`chatango/`** — Vendored ch.py framework; do not modify unless fixing a WebSocket/platform bug.

### Adding a New Command

1. Add a row to the `commands` DB table with a unique `command`, a `type` string, and an optional `response` value.
2. Implement the handler function in the relevant `broiestbot/commands/<domain>.py`.
3. Export it from `broiestbot/commands/__init__.py`.
4. Add an `elif cmd_type == "<your_type>"` branch in `Bot.create_message` (`broiestbot/bot.py`).

### LLM Integration

`@bro <message>` in chat triggers `_respond_llm_prompt`, which calls `generate_llm_response` → `clients/llm.py:LLMClient`. The client uses `claude-opus-4-6` via the Anthropic SDK with a custom system prompt defining the bot's persona. Chat history from the room (`room._history`) is formatted as a structured `messages` list.

### Active Leagues / Features

Many features in `config.py` (`FOOTY_LEAGUES`, `FOOTY_LIVE_SCORED_LEAGUES`, etc.) are defined as dicts with most entries commented out. Only the uncommented entries are active. This is intentional seasonal configuration — comment/uncomment entries to enable leagues rather than deleting them.

## Code Style

- **Line length**: 120 characters (`black`, `pyproject.toml`).
- **Import sorting**: `isort` with `profile = "black"`.
- **Type hints**: Used throughout; mypy targets Python 3.12.
- **Logging**: Always use `from logger import LOGGER` (Loguru-backed). Never use `print` in production paths.
- **Environment**: `ENVIRONMENT=production` joins real rooms; anything else joins only `CHATANGO_TEST_ROOM`.

## Environment Variables

A `.env` file is required. Required keys:
- `CHATANGO_BOT_USERNAME`, `CHATANGO_BOT_PASSWORD`, `CHATANGO_BRO_USERNAME`, `CHATANGO_BRO_PASSWORD`
- `SQLALCHEMY_DATABASE_URI` (MySQL with SSL; cert at `creds/ca-certificate.crt`)
- Room names: `CHATANGO_SIXERS_ROOM`, `CHATANGO_FLYERS_ROOM`, `CHATANGO_ALT_ROOM`, `CHATANGO_OBI_ROOM`, `CHATANGO_LMAO_ROOM`, `CHATANGO_TEST_ROOM`

Optional keys enable specific features (GCS images, Twitch, Twilio SMS, weather, crypto, PSN, Anthropic LLM, etc.). See `README.md` for the full list.
