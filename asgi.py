"""ASGI entry point — runs the bot inside uvicorn's event loop via lifespan."""

import asyncio
from typing import List

from logger import LOGGER

from broiestbot.bot import Bot
from database import init_db
from config import (
    CHATANGO_ROOMS,
    CHATANGO_TEST_ROOM,
    CHATANGO_USERS,
    ENVIRONMENT,
)

_bot_task: asyncio.Task = None


async def _run_bot(rooms: List[str]) -> None:
    bot = Bot(
        username=CHATANGO_USERS["BROIESTBOT"]["USERNAME"],
        password=CHATANGO_USERS["BROIESTBOT"]["PASSWORD"],
        rooms=rooms,
    )
    try:
        await bot.run(forever=True)
    except asyncio.CancelledError:
        bot.stop()
        raise
    except Exception as e:
        LOGGER.exception(f"Unexpected exception while running bot: {e}")
        bot.stop()


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        await _handle_lifespan(receive, send)
    elif scope["type"] == "http":
        await _handle_http(send)


async def _handle_lifespan(receive, send) -> None:
    global _bot_task
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await init_db()
            rooms = CHATANGO_ROOMS if ENVIRONMENT == "production" else [CHATANGO_TEST_ROOM]
            LOGGER.info(f'Starting bot in {ENVIRONMENT} mode, joining: {", ".join(rooms)}')
            _bot_task = asyncio.create_task(_run_bot(rooms))
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            if _bot_task and not _bot_task.done():
                _bot_task.cancel()
                try:
                    await _bot_task
                except asyncio.CancelledError:
                    pass
            await send({"type": "lifespan.shutdown.complete"})
            return


async def _handle_http(send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"broiestbot is running",
        }
    )
