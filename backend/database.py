# backend/database.py
"""Async SQLAlchemy engine + session factory for the ArticleWriter Postgres backend.

Three switches cooperate to keep `python run.py` working in any environment:

- `DATABASE_URL`   : if missing/empty, the engine is None and `init_db()` is a no-op.
- `DB_BACKEND`     : `null` (default) → repositories use NullArticleRepository (B5).
                     `postgres` → repositories use PostgresArticleRepository (B4).
                     The repository layer reads this; this module just ensures the
                     engine is available when DATABASE_URL is set.

The engine is created lazily so importing this module never tries to connect.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str | None:
    """Return DATABASE_URL from env, or None when unset/empty.

    Read here (not in Secrets) because this is a runtime infrastructure switch,
    not a credential. Secrets layer can also surface it if a project prefers.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    return url or None


def get_db_backend() -> str:
    """`postgres` or `null`. Default: `null` so a fresh checkout works without Docker."""
    return os.environ.get("DB_BACKEND", "null").strip().lower() or "null"


def get_engine() -> AsyncEngine | None:
    """Lazy engine. Returns None when DATABASE_URL is unset (run.py without DB)."""
    global _engine, _session_maker
    if _engine is not None:
        return _engine
    url = get_database_url()
    if url is None:
        return None
    _engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession] | None:
    """Returns the session factory once `get_engine()` has been called, else None."""
    if _session_maker is None:
        get_engine()
    return _session_maker


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    """Context-managed AsyncSession. Caller is responsible for commit on success.

    Raises RuntimeError if DATABASE_URL is unset — call sites should guard with
    `get_db_backend() == "postgres"` first, or use the repository layer which has
    its own null implementation.
    """
    sm = get_session_maker()
    if sm is None:
        raise RuntimeError(
            "DATABASE_URL is not configured. Either set DATABASE_URL or use a "
            "repository implementation that does not require a database session."
        )
    async with sm() as s:
        yield s


async def init_db() -> None:
    """Verify DB connectivity at startup. No-op when DB_BACKEND=null or DATABASE_URL unset.

    Intended to be called from FastAPI's `lifespan` startup. Not used by `run.py`
    (which can run with or without DB depending on DB_BACKEND).
    """
    if get_db_backend() != "postgres":
        return
    engine = get_engine()
    if engine is None:
        raise RuntimeError(
            "DB_BACKEND=postgres requires DATABASE_URL to be set. "
            "Either set DATABASE_URL in .env or set DB_BACKEND=null."
        )
    # Probe connection.
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Dispose of the engine on shutdown. Safe to call when engine was never created."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
