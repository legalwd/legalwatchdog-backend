"""Database utility functions for the application.

This module provides helper functions and context managers for database interactions.

.. deprecated::
    ``get_isolated_async_session`` is deprecated. Use ``AsyncSessionLocal`` from
    ``app.api.db.database`` instead. The ``syncify()`` bridge already creates a
    fresh event loop per Celery task call, so ``AsyncSessionLocal`` is safe.
"""

import warnings
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.api.core.config import settings


@asynccontextmanager
async def get_isolated_async_session() -> AsyncGenerator[AsyncSession, None]:
    """DEPRECATED: Use ``AsyncSessionLocal`` from ``app.api.db.database`` instead.

    This function creates a new engine with NullPool per call, which does not
    scale at campaign volume (10K+ jurisdictions). ``syncify()`` already creates
    a fresh event loop per call, so ``AsyncSessionLocal`` works correctly in
    Celery tasks without the "Future attached to different loop" issue.

    Yields:
        AsyncSession: A fresh SQLAlchemy async session.
    """
    warnings.warn(
        "get_isolated_async_session is deprecated. "
        "Use AsyncSessionLocal from app.api.db.database instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    db_url = str(settings.DATABASE_URL)

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, poolclass=NullPool, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

    await engine.dispose()
