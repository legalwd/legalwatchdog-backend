from unittest.mock import AsyncMock, patch

import pytest

from app.api.core.dependencies.registeration_redis import get_redis


@pytest.mark.asyncio
async def test_get_redis_yields_redis_client():
    """Test that get_redis yields a Redis client and closes it properly."""
    mock_redis_instance = AsyncMock()
    with patch(
        "app.api.core.dependencies.registeration_redis.Redis.from_url",
        return_value=mock_redis_instance,
    ) as mock_from_url:
        gen = get_redis()
        redis_client = await gen.__anext__()

        assert redis_client == mock_redis_instance
        mock_from_url.assert_called_once()

        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

        mock_redis_instance.close.assert_awaited_once()
