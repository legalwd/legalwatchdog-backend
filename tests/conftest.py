import importlib
import os
import pkgutil
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import bcrypt
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.core.config import settings


def _load_all_model_modules() -> None:
    """Import all v1 model modules so SQLModel metadata is fully populated."""
    base_package = importlib.import_module("app.api.modules.v1")
    prefix = f"{base_package.__name__}."

    for module_info in pkgutil.walk_packages(base_package.__path__, prefix):
        if ".models." not in module_info.name:
            continue
        if module_info.ispkg:
            continue
        importlib.import_module(module_info.name)


def get_worker_id():
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def get_test_database_url(async_driver: bool = True) -> str:
    """
    Build test database URL using current settings.

    This is computed lazily to ensure .env.test values are loaded first.
    """
    driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
    return (
        f"{driver}://{settings.DB_USER}:{settings.DB_PASS}@"
        f"{settings.DB_HOST}:{settings.DB_PORT}/watchdog_test"
    )


TEST_DATABASE_URL = None
SYNC_TEST_DATABASE_URL = None


@pytest.fixture(scope="session", autouse=True)
def setup_patches():
    """Session-wide patches for cryptography and app config."""
    mock_fernet = MagicMock()
    mock_fernet.encrypt.return_value.decode.return_value = "mock_encrypted_value"
    mock_fernet.decrypt.return_value.decode.return_value = (
        '{"username": "test", "password": "secret"}'
    )

    p1 = patch("cryptography.fernet.Fernet", return_value=mock_fernet)
    p2 = patch("app.api.core.config.get_cipher_suite", return_value=mock_fernet)

    p1.start()
    p2.start()

    yield

    p1.stop()
    p2.stop()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_db_engine():
    """Session-scoped async engine for schema setup."""
    engine = create_async_engine(get_test_database_url(async_driver=True), echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Function-scoped async engine for tests."""
    engine = create_async_engine(
        get_test_database_url(async_driver=True),
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def sync_db_engine():
    """Session-scoped sync engine."""
    engine = create_engine(get_test_database_url(async_driver=False), echo=False)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_schema(session_db_engine):
    """Create the schema once per session."""
    try:
        _load_all_model_modules()
        async with session_db_engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.run_sync(SQLModel.metadata.create_all)
        yield
        async with session_db_engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    except OSError as e:
        print(
            f"WARNING: DB Connection failed, skipping schema setup. "
            f"Tests requiring real DB will fail. Error: {e}"
        )
        yield


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Function-scoped session that rolls back changes."""
    connection = await db_engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(bind=connection, expire_on_commit=False)

    await connection.begin_nested()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture(scope="function")
async def pg_async_session(db_session):
    """Alias for db_session."""
    yield db_session


@pytest_asyncio.fixture(scope="function")
async def test_engine(db_engine):
    """Deprecated: Prefer db_session."""
    yield db_engine


@pytest.fixture(scope="function")
def pg_sync_session(sync_db_engine):
    """Function-scoped sync session that rolls back changes."""
    connection = sync_db_engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection, expire_on_commit=False)
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def patch_global_db_engine(sync_db_engine, pg_sync_session, monkeypatch):
    """Patch global database engine/session to use the test session."""
    monkeypatch.setattr("app.api.db.database.sync_engine", sync_db_engine)

    mock_session_cls = MagicMock()
    mock_session_cls.return_value = pg_sync_session

    monkeypatch.setattr("app.api.db.database.SyncSessionLocal", mock_session_cls)
    monkeypatch.setattr(
        "app.api.modules.v1.scraping.service.tasks.SyncSessionLocal", mock_session_cls
    )


@pytest.fixture(autouse=True)
def mock_encryption(monkeypatch):
    """Set a valid encryption key for testing"""
    valid_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", valid_key)


@pytest.fixture(autouse=True)
def mock_bcrypt_speed(monkeypatch):
    """Speed up bcrypt by reducing rounds for testing."""
    original_gensalt = bcrypt.gensalt

    def fast_gensalt(rounds=12, prefix=b"2b"):
        return original_gensalt(rounds=4, prefix=prefix)

    monkeypatch.setattr(bcrypt, "gensalt", fast_gensalt)


@pytest.fixture
def mock_encrypt_auth_details():
    """Mock the encrypt_auth_details utility function."""
    with patch("app.api.modules.v1.scraping.service.source_service.encrypt_auth_details") as mock:
        mock.return_value = "mock_encrypted_value"
        yield mock


@pytest.fixture(autouse=True, scope="function")
def mock_redis(monkeypatch):
    """Mock Redis client for all tests to avoid connection errors."""
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")

    redis_store = {}
    mock_redis_client = AsyncMock()

    async def mock_get(key):
        return redis_store.get(key)

    async def mock_set(key, value, **kwargs):
        redis_store[key] = str(value)
        return True

    async def mock_setex(key, seconds, value):
        redis_store[key] = str(value)
        return True

    async def mock_delete(*keys):
        count = 0
        for key in keys:
            if key in redis_store:
                del redis_store[key]
                count += 1
        return count

    async def mock_incr(key):
        current = int(redis_store.get(key, 0))
        new_value = current + 1
        redis_store[key] = str(new_value)
        return new_value

    async def mock_expire(key, seconds):
        return True

    async def mock_ttl(key):
        if key in redis_store:
            if "lockout" in key:
                return 15 * 60
            return 300
        return -1

    async def mock_exists(key):
        return 1 if key in redis_store else 0

    mock_redis_client.get.side_effect = mock_get
    mock_redis_client.set.side_effect = mock_set
    mock_redis_client.setex.side_effect = mock_setex
    mock_redis_client.delete.side_effect = mock_delete
    mock_redis_client.incr.side_effect = mock_incr
    mock_redis_client.expire.side_effect = mock_expire
    mock_redis_client.ttl.side_effect = mock_ttl
    mock_redis_client.exists.side_effect = mock_exists
    mock_redis_client.close.return_value = None

    mock_pool = MagicMock()
    mock_pool.disconnect = AsyncMock()

    with (
        patch("redis.asyncio.connection.ConnectionPool.from_url", return_value=mock_pool),
        patch("redis.asyncio.Redis", return_value=mock_redis_client),
    ):
        import app.api.core.dependencies.redis_service as redis_module

        redis_module._redis_client = None
        redis_module._connection_pool = None
        yield mock_redis_client
        redis_module._redis_client = None
        redis_module._connection_pool = None


@pytest_asyncio.fixture
async def mocked_async_session():
    """Provide a mocked async PostgreSQL session for unit tests."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.flush = AsyncMock()

    mock_scalars = Mock()
    mock_scalars.all = Mock(return_value=[])
    mock_scalars.first = Mock(return_value=None)

    mock_result = Mock()
    mock_result.scalars = Mock(return_value=mock_scalars)
    mock_result.scalar = Mock(return_value=None)
    mock_result.scalar_one_or_none = Mock(return_value=None)
    mock_result.all = Mock(return_value=[])
    mock_result.first = Mock(return_value=None)

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.get = AsyncMock(return_value=None)

    yield mock_session


@pytest.fixture(autouse=True)
def mock_url_validator(monkeypatch):
    """Mock URLValidator."""
    from app.api.modules.v1.scraping.validators.url_validator import URLValidator

    mock_reachability = AsyncMock(return_value=(True, None, None))
    monkeypatch.setattr(URLValidator, "check_url_reachability", mock_reachability)

    def mock_validate_format(url):
        return (True, None, None)

    def mock_validate_domain(url):
        return (True, None, None)

    monkeypatch.setattr(URLValidator, "validate_url_format", staticmethod(mock_validate_format))
    monkeypatch.setattr(URLValidator, "validate_domain", staticmethod(mock_validate_domain))


@pytest_asyncio.fixture
async def test_session(db_engine):
    """Create tables for SQLite test session."""
    connection = await db_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    await connection.begin_nested()
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
def celery_eager(db_engine, sync_db_engine, monkeypatch):
    """Enable Celery eager mode with DB sessions redirected to the test database.

    This fixture patches:
    1. ``AsyncSessionLocal`` in both ``database.py`` and ``campaign_tasks.py``
       → bound to the test async engine so async tasks hit the test PG.
    2. ``SyncSessionLocal`` in ``campaign_tasks.py``
       → bound to the test sync engine so sync tasks hit the test PG.
    3. ``_publish_progress`` → no-op (module-level sync Redis unavailable).
    4. ``_make_async_redis_client`` → mock (source discovery Redis).
    5. ``sitemap_rebuild_debounced`` → mock (avoid enqueueing unrelated task).
    6. Enables ``task_always_eager`` + ``task_eager_propagates``.
    """
    from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.orm import sessionmaker
    from sqlmodel import Session

    from app.celery_app import celery_app

    # --- Async session factory bound to test engine ---
    test_async_session_factory = async_sessionmaker(
        bind=db_engine,
        class_=SAAsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # --- Sync session factory bound to test engine ---
    test_sync_session_factory = sessionmaker(
        bind=sync_db_engine,
        class_=Session,
        expire_on_commit=False,
        autoflush=False,
    )

    from app.api.db import database as db_module

    # Patch at source (database.py) so get_db() also uses test engine
    monkeypatch.setattr(db_module, "AsyncSessionLocal", test_async_session_factory)
    monkeypatch.setattr(db_module, "SyncSessionLocal", test_sync_session_factory)

    # Patch at import site (campaign_tasks) where the names were imported
    tasks_mod = "app.api.modules.v1.campaigns.tasks.campaign_tasks"
    monkeypatch.setattr(f"{tasks_mod}.AsyncSessionLocal", test_async_session_factory)
    monkeypatch.setattr(f"{tasks_mod}.SyncSessionLocal", test_sync_session_factory)

    # _publish_progress → no-op (module-level sync Redis unavailable in tests)
    monkeypatch.setattr(f"{tasks_mod}._publish_progress", lambda *a, **kw: None)

    # _make_async_redis_client → mock
    mock_async_redis = MagicMock()
    mock_async_redis.aclose = AsyncMock()
    monkeypatch.setattr(f"{tasks_mod}._make_async_redis_client", lambda: mock_async_redis)

    # sitemap_rebuild_debounced.delay → no-op
    monkeypatch.setattr(f"{tasks_mod}.sitemap_rebuild_debounced", MagicMock())

    # Preserve existing Celery eager configuration so we can restore it.
    prev_task_always_eager = celery_app.conf.task_always_eager
    prev_task_eager_propagates = celery_app.conf.task_eager_propagates

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery_app.conf.update(
        task_always_eager=prev_task_always_eager,
        task_eager_propagates=prev_task_eager_propagates,
    )
