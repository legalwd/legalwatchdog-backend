from typing import AsyncGenerator

from redis.asyncio import Redis

from app.api.core.config import settings


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Get Redis client dependency using REDIS_URL.

    Yields:
        Redis: Redis client instance
    """
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis_client
    finally:
        await redis_client.close()
