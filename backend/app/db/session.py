"""
ResolveAI — Async Database Engine & Session Factory

Creates a production-grade async engine with connection pooling and
exposes an ``async_sessionmaker`` plus a FastAPI-compatible dependency
(``get_db``) with proper transaction semantics.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Engine ───────────────────────────────────────────────────────────────────
engine_kwargs: dict[str, Any] = {"echo": settings.DEBUG}
if "sqlite" not in str(settings.DATABASE_URL):
    engine_kwargs.update(
        {
            "pool_size": 20,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "pool_timeout": 30,
        }
    )

engine: AsyncEngine = create_async_engine(
    url=settings.async_database_url,
    **engine_kwargs,
)

# ── Session factory ──────────────────────────────────────────────────────────
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── FastAPI dependency ───────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an ``AsyncSession`` with request-scoped transaction management.

    * On success the transaction is **committed**.
    * On any exception the transaction is **rolled back** and the error
      is re-raised so that FastAPI's exception handlers can deal with it.
    * The session is **always** closed, returning the connection to the
      pool.
    """
    session: AsyncSession = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception as exc:
        logger.warning("db_session_rollback_triggered", error=str(exc))
        try:
            await session.rollback()
        except Exception as rollback_err:
            logger.error("db_session_rollback_failed", error=str(rollback_err))
        raise
    finally:
        await session.close()
