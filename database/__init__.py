"""Create SQLAlchemy database sessions (sync and async)."""

import re
import ssl

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from config import DATABASE_ARGS, SQLALCHEMY_DATABASE_URI

# aiomysql requires an ssl.SSLContext; pymysql accepts the raw {"ca": ...} dict.
_ca_cert: str = DATABASE_ARGS["ssl"]["ca"]
_ssl_ctx = ssl.create_default_context(cafile=_ca_cert)

# Async engine (aiomysql) — used by async functions called directly from the event loop.
# NullPool avoids aiomysql ping() compatibility issues and prevents stale connections
# when multiple asyncio event loops are used (e.g. in tests via asyncio.run()).
_async_uri = re.sub(r"^mysql(\+\w+)?://", "mysql+aiomysql://", SQLALCHEMY_DATABASE_URI)
async_engine = create_async_engine(
    _async_uri,
    connect_args={"ssl": _ssl_ctx},
    poolclass=NullPool,
    echo=False,
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
