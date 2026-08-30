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

   These branches are mutually exclusive: the `?<query>` and `!<cmd>` branches `return` once
   handled, so a command never also pays for the link-preview checks or a `phrases` lookup it
   could never match. `broiestbot/tests/test_message_routing.py` locks that in.
3. `create_message` is a large **async** `if/elif` dispatch on `cmd_type` (the `type` column of the `commands` table), calling the appropriate function from `broiestbot/commands/`.

### Sync/Async Boundary

Handlers which talk to an HTTP API are **coroutines** built on `aiohttp`, and `create_message` awaits them directly. The LLM handler is likewise a coroutine, built on the Anthropic SDK's `AsyncAnthropic` client, and the redgifs handler on `redgifs.aio.API`. Handlers still backed by a blocking third-party SDK (GCS, Twilio, IMDb, PSN, Genius, `praw`, `youtube_search`, `pandas.read_html`) stay synchronous and are dispatched with `asyncio.to_thread(...)` so they never block the event loop.

Two traps when deciding whether something is safe to await:

- **Lazy SDKs defeat `to_thread`.** A `wikipediaapi` page does no I/O when it is built — it fetches on *attribute access*, so `to_thread(wiki.page, …)` offloads nothing and every later `.summary` / `.sections` read blocks the loop. `clients/__init__.py` exposes both `wiki` (blocking, for `to_thread` handlers) and `async_wiki` (`AsyncWikipedia`, whose equivalents are awaitables) — use the latter from any `async def`.
- **`to_thread` hides serial I/O.** Offloading keeps the loop free but the work inside the thread is still sequential, so a wrapper making N calls in a loop stays N round trips. Prefer removing the redundant calls (see `playstation.py`, which carries each friend's presence payload rather than re-fetching it) over widening the thread.

- **`http_client.py`** owns the process-wide `aiohttp.ClientSession`. Call `get_http_session()` inside a handler rather than creating a session per request; `asgi.py` closes it on lifespan shutdown. Pass `request_timeout(n)` per request only when overriding the session-wide `HTTP_REQUEST_TIMEOUT`.
- Decode bodies with `await resp.json(content_type=None)` — several of these APIs serve JSON under the wrong content type.
- Catch `aiohttp.ClientError` (and `ClientResponseError` before it, when the status matters) where `requests.exceptions.HTTPError` used to be caught.

`database/__init__.py` exposes both engines to match:
- `async_session` (aiomysql) — for `await`ed DB access on the event loop; used by `bot.py`'s command/phrase lookups and by any async handler (`footy/util.py`, `weather.py`).
- `Session` (pymysql) — for the synchronous handlers running inside `to_thread` (e.g. `polls/`).

The async engine pools its connections (`DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` /
`DATABASE_POOL_RECYCLE` in `config.py`), because every chat message costs several round trips
and an unpooled query pays a fresh TCP + TLS handshake each time — measured at ~523ms against
~111ms pooled. An aiomysql connection belongs to the event loop which opened it, so the engine
falls back to `NullPool` under pytest, where each test drives its own `asyncio.run(...)`;
`asgi.py` disposes the pool via `close_db()` on lifespan shutdown.

### Package Layout

- **`broiestbot/bot.py`** — Core `Bot(chatango.Client)` class; all message routing lives here.
- **`broiestbot/commands/`** — One module or package per domain (`footy/`, `f1/`, `nba/`, `nfl/`, `mlb/`, `sumo/`, `odds/`, `polls/`, `images/`, plus flat modules like `llm.py`, `weather.py`, `movies.py`). All public command functions are re-exported through `broiestbot/commands/__init__.py`.
- **`broiestbot/data/`** — Persists chat logs and user geo/IP data to the DB after every message.
- **`broiestbot/moderation/`** — Ban/mute logic for blacklisted users, anon accounts, IPs, and specific phrases. Every entry point is gated on `privileges.py:bot_is_moderator(room)` — see "Room Privileges" below.
- **`clients/__init__.py`** — Instantiates all third-party SDK clients at import time (Redis, Twilio, GCS, Wikipedia sync + async, IMDB, Reddit, Genius, PSN, Anthropic). Import from here rather than re-instantiating. The exception is redgifs: `redgifs.aio.API` opens an `aiohttp.ClientSession` in its constructor, so it needs a running loop and is built lazily by `commands/afterdark.py:get_redgifs_client` (which also caches its auth token) and closed on lifespan shutdown.
- **`database/models.py`** — ORM models: `Command`, `Phrase`, `Chat`, `ChatangoUser`, `Weather`, `PollResult`, `Sport`, `League`.
- **`config.py`** — All configuration and constants loaded from `.env`. Includes hundreds of league/team IDs and API endpoints. Import constants from here; never hardcode them.
- **`http_client.py`** — Shared `aiohttp` session (`get_http_session`, `request_timeout`, `close_http_session`) used by every HTTP-backed command.

Tests live beside the code they cover (`broiestbot/commands/<domain>/tests/`), with DB-level tests in the top-level `tests/`. Async code is driven with `asyncio.run(...)` rather than a pytest asyncio plugin; `tests/aiohttp_mocks.py` provides `patch_http_session` / `FakeResponse` for faking a command module's HTTP calls.

### Adding a New Command

1. Add a row to the `commands` DB table with a unique `command`, a `type` string, and an optional `response` value.
2. Implement the handler in the relevant `broiestbot/commands/<domain>` module: `async def` using `get_http_session()` if it calls an HTTP API, otherwise a plain `def`.
3. Export it from `broiestbot/commands/__init__.py`.
4. Add an `elif cmd_type == "<your_type>"` branch in `Bot.create_message` (`broiestbot/bot.py`) — `await` an async handler, or `await asyncio.to_thread(...)` a blocking one.

`type = "reserved"` is a sentinel meaning "another bot owns this command" — it is matched and ignored, never responded to.

### LLM Integration

`@bro <message>` triggers `_respond_llm_prompt` → `generate_llm_response` → `clients/llm.py:LLMClient`, which awaits Claude via the Anthropic SDK's `AsyncAnthropic` client with a persona system prompt. Room history (`room.history`) is formatted into a structured `messages` list, and the markdown reply is converted to HTML before being sent. `asgi.py` closes the client on lifespan shutdown.

The call goes through `client.beta.messages.create` because it opts into server-side refusal fallbacks (`fallbacks="default"` plus the `SERVER_SIDE_FALLBACK_BETA` header): if Claude's safety classifiers decline the prompt, Anthropic re-runs it on a fallback model within the same request. Two consequences worth knowing:

- Reply text must be selected by block type (`block.type == "text"`) — `content[0]` may be a thinking or `fallback` block.
- If the whole chain still declines, `generate_response` raises `LLMRefusalError` and `generate_llm_response` returns an in-persona brush-off rather than staying silent.

#### Reading links (`web_fetch`)

The LLM can read a link, using Anthropic's server-side `web_fetch` tool, but **only when the message tagging the bot carries that link itself**. `LLMClient.fetchable_hosts` strips quoted text (a quoted link is not the sender's own ask) and returns the hosts of any URLs left; `generate_response` then attaches the tool scoped to those hosts via `allowed_domains`. With no link in the prompt the tool is omitted from the request entirely, so links merely sitting in `room.history` can never be fetched — this is why `_respond_llm_prompt` takes the triggering `chat_message` separately from the history.

Consequences for anyone editing this path:

- Reply text is whatever follows the **last non-text block** (`LLMClient._reply_text`), not the first text block: a turn that used a tool opens with a throwaway preamble before the tool call, and the answer comes after the results.
- Dynamic filtering runs code execution server-side, so responses contain `code_execution_tool_result` blocks. Do **not** also declare a `code_execution` tool — a second execution environment confuses the model.
- A tool loop which hits its iteration cap stops with `stop_reason == "pause_turn"`; the turn is re-sent unchanged (no extra user message) up to `MAX_PAUSE_TURN_RESUMES` times.
- A blocked host comes back as a `web_fetch_tool_result` whose content is `web_fetch_tool_result_error` with `error_code: "url_not_allowed"` — an ordinary HTTP 200, not a raised exception.

### Room Privileges

Chatango grants moderator powers **per room**, so the bot must not assume it can moderate everywhere. `broiestbot/moderation/privileges.py` exposes `bot_privilege_level(room)` and `bot_is_moderator(room)`, both reading `Room.get_level()` and failing closed (`PrivilegeLevel.USER`) when the level can't be determined.

In a room where the bot is a plain user:

- `check_blacklisted_users`, `ban_daddy_anons` and `ban_word` return immediately. This matters mostly because each of them **taunts the offending user in chat** — without the guard the bot announces bans it has no power to carry out.
- Even as a mod, taunts are sent only after the privileged call reports success: `room.ban_message()`, `room.ban_user()` and `room.delete_message()` all return `bool` rather than raising, and `chatango-lib` returns `False` instead of erroring when the bot lacks the power.
- `RoomMessage.ip` is an empty string — Chatango discloses IPs to mods only. `persist_user_data` already treats a missing IP as "nothing to persist", so `chatango_users` rows simply aren't written for that room. Chat logs are unaffected.
- A missing IP is expected rather than anomalous, so `_log_message` logs it at INFO instead of WARNING.

`Bot.on_inited`, `on_mod_added` and `on_mod_remove` log the bot's level per room on join and whenever it changes, so degraded rooms are visible in the logs rather than silent.

### Active Rooms / Leagues

`CHATANGO_ROOMS` and many league dicts in `config.py` (`FOOTY_LEAGUES`, `FOOTY_LIVE_SCORED_LEAGUES`, etc.) keep most entries commented out. Only uncommented entries are active. This is intentional seasonal configuration — comment/uncomment entries rather than deleting them.

Some active leagues are only worth surfacing for a handful of clubs. `FOOTY_LEAGUE_TEAM_FILTERS` maps a league ID to the team IDs a fixture must feature to be shown (club friendlies → `FOOTY_FRIENDLY_CLUBS`; the Primeira Liga → Benfica; Eliteserien → Aalesund); every other league passes through unfiltered. `footy/util.py:filter_league_fixtures` applies it to every fetched fixture list, so all fixture-backed commands inherit it — including the `liveodds` and `footystats` types, which fetch through `live.py:fetch_live_fixtures`. Adding a league to the dict is the whole change; there is no per-command wiring.

The one exception is the upcoming-fixtures path: a team-filtered league can't use the `next=N` parameter, since the soonest N league-wide fixtures rarely include the clubs being filtered for. `upcoming.py` routes those leagues to `fetch_upcoming_fixtures_by_date_range` (a `from`/`to` request spanning `UPCOMING_FIXTURE_WINDOW_DAYS`) instead, so the fixtures survive long enough to be filtered.

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
