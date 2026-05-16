"""Database session factory for async SQLAlchemy."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings


class _LazySessionmaker:
    """Defers engine + sessionmaker creation until first call.

    Importing this module during unit-test collection does not trigger
    create_async_engine, so tests that mock the DB session can collect
    without a DATABASE_URL being set.
    """

    def __init__(self, poolclass: Any = None) -> None:
        self._poolclass = poolclass
        self._maker: async_sessionmaker[AsyncSession] | None = None

    def _build(self) -> async_sessionmaker[AsyncSession]:
        kwargs: dict[str, Any] = {}
        if self._poolclass is not None:
            kwargs["poolclass"] = self._poolclass
        else:
            kwargs["pool_pre_ping"] = True
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20
            kwargs["echo"] = settings.environment == "development"
        engine = create_async_engine(settings.database_url, **kwargs)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    def __call__(self) -> AsyncSession:
        if self._maker is None:
            self._maker = self._build()
        return self._maker()


# Pooled factory for FastAPI — lives in a single long-lived event loop.
AsyncSessionLocal = _LazySessionmaker()

# Unpooled factory for Celery tasks — each task runs in its own event loop.
# NullPool creates a fresh connection per session and closes it immediately,
# so no asyncio primitives are shared across event loop boundaries.
CeleryAsyncSessionLocal = _LazySessionmaker(poolclass=NullPool)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
