# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

BroiestBot is an async Python chatbot for the [Chatango](https://www.chatango.com/) platform. It joins rooms via the external `chatango-lib` package and responds to user messages. The bot handles two interaction types: `!command`-prefixed chat triggers (looked up from a MySQL database) and freeform phrase matching (also stored in the DB).

## Commands

```bash
make install    # Create .venv and install from requirements.txt
make run        # Run via uvicorn (binds to a UNIX socket)
make kill       # Kill the running bot process
make lint       # flake8 (errors + undefined names only: E9,F63,F7,F82)
make format     # isort + black
make test       # pytest with coverage, opens HTML report
make update     # poetry update + regenerate requirements.txt
make clean      # Remove caches, logs, .venv, poetry.lock
```

Run a single test file:
```bash
.venv/bin/python -m pytest broiestbot/commands/footy/tests/test_liveodds.py -v
```

The bot is not a web server — uvicorn is used purely as a process manager. `asgi.py` is the sole entrypoint: it starts the bot from the ASGI **lifespan** startup event (`init_db()`, then `Bot.run(forever=True)` as a background task) and serves a trivial health response on HTTP.

## Architecture

### Message Flow

1. `chatango-lib` delivers `async on_message(room, message)` to `broiestbot/bot.py:Bot` (a `chatango.Client` subclass).
2. `Bot.on_message` runs moderation checks, persists chat/user data, then routes on message content:
   - `?<query>` → YouTube search
   - `!<cmd>` → `_process_command` → DB lookup → `create_message` → `room.send_message()`
   - `!!<query>` → skip the DB, go straight to the image-search fallback
   - YouTube/X/Wikipedia URLs → auto-generate link previews
   - `@bro` → LLM response via Anthropic Claude
   - Everything else → `_process_phrase` → DB phrase match
3. `create_message` is a large **synchronous** `if/elif` dispatch on `cmd_type` (the `type` column of the `commands` table), calling the appropriate function from `broiestbot/commands/`.

### Sync/Async Boundary

Command handlers are blocking (`requests`, SDK calls) and must never run on the event loop directly. `Bot` dispatches them with `asyncio.to_thread(...)` — `create_message`, link previews, and `generate_llm_response` all go through it. Keep new handlers synchronous and let the caller thread them.

`database/__init__.py` exposes both engines to match:
- `async_session` (aiomysql, `NullPool`) — for `await`ed DB access on the event loop, e.g. the command/phrase lookups in `bot.py`.
- `Session` (pymysql) — for the synchronous handlers running inside `to_thread`.

### Package Layout

- **`broiestbot/bot.py`** — Core `Bot(chatango.Client)` class; all message routing lives here.
- **`broiestbot/commands/`** — One module or package per domain (`footy/`, `f1/`, `nba/`, `nfl/`, `mlb/`, `sumo/`, `odds/`, `polls/`, `images/`, plus flat modules like `llm.py`, `weather.py`, `movies.py`). All public command functions are re-exported through `broiestbot/commands/__init__.py`.
- **`broiestbot/data/`** — Persists chat logs and user geo/IP data to the DB after every message.
- **`broiestbot/moderation/`** — Ban/mute logic for blacklisted users, anon accounts, IPs, and specific phrases.
- **`clients/__init__.py`** — Instantiates all third-party SDK clients at import time (Redis, Twilio, GCS, Wikipedia, IMDB, Reddit, Genius, PSN, Anthropic, Redgifs). Import from here rather than re-instantiating.
- **`database/models.py`** — ORM models: `Command`, `Phrase`, `Chat`, `ChatangoUser`, `Weather`, `PollResult`, `Sport`, `League`.
- **`config.py`** — All configuration and constants loaded from `.env`. Includes hundreds of league/team IDs and API endpoints. Import constants from here; never hardcode them.

Tests live beside the code they cover (`broiestbot/commands/<domain>/tests/`), with DB-level tests in the top-level `tests/`.

### Adding a New Command

1. Add a row to the `commands` DB table with a unique `command`, a `type` string, and an optional `response` value.
2. Implement a **synchronous** handler in the relevant `broiestbot/commands/<domain>` module.
3. Export it from `broiestbot/commands/__init__.py`.
4. Add an `elif cmd_type == "<your_type>"` branch in `Bot.create_message` (`broiestbot/bot.py`).

`type = "reserved"` is a sentinel meaning "another bot owns this command" — it is matched and ignored, never responded to.

### LLM Integration

`@bro <message>` triggers `_respond_llm_prompt` → `generate_llm_response` → `clients/llm.py:LLMClient`, which calls Claude via the Anthropic SDK with a persona system prompt. Room history (`room.history`) is formatted into a structured `messages` list, and the markdown reply is converted to HTML before being sent.

### Active Rooms / Leagues

`CHATANGO_ROOMS` and many league dicts in `config.py` (`FOOTY_LEAGUES`, `FOOTY_LIVE_SCORED_LEAGUES`, etc.) keep most entries commented out. Only uncommented entries are active. This is intentional seasonal configuration — comment/uncomment entries rather than deleting them.

## Code Style

- **Line length**: 120 characters (`black`, `pyproject.toml`).
- **Import sorting**: `isort` with `profile = "black"`.
- **Type hints**: Used throughout; mypy targets Python 3.12.
- **Docstrings**: reST-style `:param:` / `:returns:` on non-trivial functions.
- **Emoji**: always `emojize(..., language="en")` from the `emoji` package.
- **Logging**: Always use `from logger import LOGGER` (Loguru-backed). Never use `print` in production paths.
- **Environment**: `ENVIRONMENT=production` joins `CHATANGO_ROOMS`; anything else joins only `CHATANGO_TEST_ROOM`.

## Environment Variables

A `.env` file is required. Required keys:
- `CHATANGO_BOT_USERNAME`, `CHATANGO_BOT_PASSWORD`, `CHATANGO_BRO_USERNAME`, `CHATANGO_BRO_PASSWORD`
- `SQLALCHEMY_DATABASE_URI` (MySQL with SSL; cert at `creds/ca-certificate.crt`)
- Room names — one `CHATANGO_*_ROOM` var per room referenced in `config.py`, including `CHATANGO_TEST_ROOM`

Optional keys enable specific features (GCS images, Klipy/Giphy, Twitch, Twilio SMS, weather, crypto, PSN, Redgifs, Anthropic LLM, etc.). See `config.py` for the authoritative list.
