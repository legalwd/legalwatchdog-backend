import json
import uuid
from importlib import import_module
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_cache_and_get_search_session_success(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    search_data = {"query": "employment law", "sources": ["https://example.com"]}

    session_id = await redis_utils.cache_search_session(
        user_id=user_id, search_data=search_data.copy()
    )

    assert session_id is not None
    expected_key_prefix = f"suggested_sources:{str(user_id)}:"

    redis_mock.setex.assert_awaited()
    called_key = redis_mock.setex.call_args[0][0]
    assert called_key.startswith(expected_key_prefix)

    stored = {**search_data, "_user_id": str(user_id)}
    redis_mock.get.return_value = json.dumps(stored)

    result = await redis_utils.get_search_session(user_id=user_id, session_id=session_id)
    assert result is not None
    assert result.get("query") == "employment law"

    assert "_user_id" not in result


@pytest.mark.asyncio
async def test_cache_search_session_serialization_error(monkeypatch, mock_redis):
    user_id = uuid.uuid4()

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    bad_data = {"bad": {1, 2, 3}}

    with pytest.raises(ValueError):
        await redis_utils.cache_search_session(user_id=user_id, search_data=bad_data)


@pytest.mark.asyncio
async def test_get_search_session_user_mismatch(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    stored = {"query": "x", "_user_id": str(uuid.uuid4())}
    redis_mock.get.return_value = json.dumps(stored)

    result = await redis_utils.get_search_session(user_id=user_id, session_id="some-session")
    assert result is None


@pytest.mark.asyncio
async def test_get_search_session_corrupted_json_deletes(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    redis_mock.get = AsyncMock(return_value="not-json")

    result = await redis_utils.get_search_session(user_id=user_id, session_id="s")
    assert result is None

    redis_mock.delete.assert_called()


@pytest.mark.asyncio
async def test_get_search_session_expires_in(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    redis_mock.ttl = AsyncMock(return_value=90)
    ttl = await redis_utils.get_search_session_expires_in(user_id=user_id, session_id="s")
    assert ttl == 90

    redis_mock.ttl = AsyncMock(return_value=-1)
    ttl = await redis_utils.get_search_session_expires_in(user_id=user_id, session_id="s")
    assert ttl is None


class DummyPipeline:
    def __init__(self, cached_serialized, delete_result):
        self._cached_serialized = cached_serialized
        self._delete_result = delete_result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, key):
        return None

    def delete(self, key):
        return None

    async def execute(self):
        return [self._cached_serialized]


@pytest.mark.asyncio
async def test_consume_search_session_success(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis
    payload = {"query": "q", "sources": [{"url": "https://a.example"}], "_user_id": str(user_id)}
    serialized = json.dumps(payload)

    def make_pipeline(transaction=True):
        return DummyPipeline(serialized, 1)

    redis_mock.pipeline = lambda transaction=True: DummyPipeline(serialized, 1)

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    result = await redis_utils.consume_search_session(
        user_id=user_id, session_id="sess", accepted_urls=[]
    )
    assert result is not None
    assert isinstance(result.get("sources"), list)
    assert result.get("sources")[0].get("url") == "https://a.example"


@pytest.mark.asyncio
async def test_consume_search_session_no_data(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    def make_pipeline(transaction=True):
        return DummyPipeline(None, 0)

    redis_mock.pipeline = lambda transaction=True: DummyPipeline(None, 0)

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    result = await redis_utils.consume_search_session(
        user_id=user_id, session_id="sess", accepted_urls=[]
    )
    assert result is None


@pytest.mark.asyncio
async def test_delete_search_session_true_false(monkeypatch, mock_redis):
    user_id = uuid.uuid4()
    redis_mock = mock_redis

    redis_utils = import_module("app.api.core.source_search_redis_utils")

    redis_mock.delete = AsyncMock(return_value=1)
    assert await redis_utils.delete_search_session(user_id=user_id, session_id="s") is True

    redis_mock.delete = AsyncMock(return_value=0)
    assert await redis_utils.delete_search_session(user_id=user_id, session_id="s2") is False
