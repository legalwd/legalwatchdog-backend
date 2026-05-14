import logging
import ssl
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool, QueuePool
from sqlmodel import Session, SQLModel

from app.api.core.config import settings
from app.api.db.model_registry import ensure_model_modules_loaded

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_USER = settings.DB_USER
DB_PASS = settings.DB_PASS
DB_NAME = settings.DB_NAME
DB_TYPE = settings.DB_TYPE

ensure_model_modules_loaded()


def get_db_url(test_mode: bool = False, sync: bool = False) -> str:
    """Construct database URL for SQLModel engines.

    Args:
        test_mode: If True, uses test database.
        sync: If True, returns sync driver URL (for Celery tasks).

    Returns:
        Database connection URL.
    """
    if DB_TYPE == "sqlite":
        db_file = "test.db" if test_mode else "db.sqlite3"
        driver = "sqlite" if sync else "sqlite+aiosqlite"
        return f"{driver}:///{BASE_DIR}/{db_file}"

    driver = "postgresql" if sync else "postgresql+asyncpg"
    db_name = f"{DB_NAME}_test" if test_mode else DB_NAME
    return f"{driver}://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_name}"


# Async engine for FastAPI endpoints
DATABASE_URL = get_db_url()

if DB_TYPE == "postgresql":
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Connection pool sizing is env-driven to respect RDS connection limits.
    # With a 30-connection RDS limit:
    #   FastAPI pool: 5 base + 5 overflow = 10 max
    #   Celery pool:  5 base + 5 overflow = 10 max
    #   Beat: ~1
    #   Reserve: ~9 for headroom, admin connections, and bursts
    engine = create_async_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=True,
        connect_args={"ssl": ctx},
    )

    logger.info(
        "Async DB engine pool: size=%d, max_overflow=%d, max=%d",
        settings.DB_POOL_SIZE,
        settings.DB_MAX_OVERFLOW,
        settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW,
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Sync engine for Celery tasks (fallback/testing only)
SYNC_DATABASE_URL = get_db_url(sync=True)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=QueuePool if DB_TYPE == "postgresql" else NullPool,
    pool_size=settings.CELERY_DB_POOL_SIZE,
    max_overflow=settings.CELERY_DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_timeout=settings.CELERY_DB_POOL_TIMEOUT,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

logger.info(
    "Sync DB engine pool (Celery): size=%d, max_overflow=%d, max=%d",
    settings.CELERY_DB_POOL_SIZE,
    settings.CELERY_DB_MAX_OVERFLOW,
    settings.CELERY_DB_POOL_SIZE + settings.CELERY_DB_MAX_OVERFLOW,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


celery_async_engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    poolclass=NullPool,
    pool_pre_ping=True,
    connect_args={"ssl": ctx},
)

CeleryAsyncSessionLocal = async_sessionmaker(
    bind=celery_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = SQLModel


async def get_db():
    """Get async database session for FastAPI endpoints.

    Yields:
        AsyncSession: SQLAlchemy async session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db():
    """Get sync database session for Celery tasks (fallback only).

    Yields:
        Session: SQLAlchemy sync session.
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
