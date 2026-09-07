"""Create SQLAlchemy database sessions (sync and async)."""

import re
import ssl
import sys

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from config import (
    DATABASE_ARGS,
    DATABASE_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    SQLALCHEMY_DATABASE_URI,
)

# aiomysql requires an ssl.SSLContext; pymysql accepts the raw {"ca": ...} dict.
_ca_cert: str = DATABASE_ARGS["ssl"]["ca"]
_ssl_ctx = ssl.create_default_context(cafile=_ca_cert)

# An aiomysql connection is bound to the event loop which opened it, so a pooled connection
# can't be handed to a different loop. The bot runs on a single loop for its whole lifetime
# and pools happily; the test suite drives each case through its own `asyncio.run(...)`, so
# there it falls back to NullPool rather than checking out connections from a dead loop.
_UNDER_PYTEST = "pytest" in sys.modules

# Async engine (aiomysql) — used by async functions called directly from the event loop.
# Every chat message costs several round trips (user lookup, chat log insert, phrase lookup),
# so connections are pooled: without it each query pays a fresh TCP + TLS handshake.
_async_uri = re.sub(r"^mysql(\+\w+)?://", "mysql+aiomysql://", SQLALCHEMY_DATABASE_URI)
_async_pool_args = (
    {"poolclass": NullPool}
    if _UNDER_PYTEST
    else {
        "pool_size": DATABASE_POOL_SIZE,
        "max_overflow": DATABASE_MAX_OVERFLOW,
        "pool_recycle": DATABASE_POOL_RECYCLE,
        # Supported by aiomysql as of SQLAlchemy 2.0; guards against connections the server
        # dropped between checkouts.
        "pool_pre_ping": True,
    }
)
async_engine = create_async_engine(
    _async_uri,
    connect_args={"ssl": _ssl_ctx},
    echo=False,
    **_async_pool_args,
)
async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine (pymysql) — used by functions dispatched via asyncio.to_thread
# (e.g. create_message command handlers that also make blocking HTTP requests).
engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    connect_args=DATABASE_ARGS,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
)
Session = sessionmaker(bind=engine, autoflush=True, autobegin=True)


async def init_db() -> None:
    """Create all tables defined in models if they don't yet exist."""
    from database.models import Base  # noqa: avoid circular import at module load time

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Dispose of the async engine's connection pool.

    Called on lifespan shutdown so pooled connections are closed politely rather than
    left for the server to time out.

    :returns: None
    """
    await async_engine.dispose()
