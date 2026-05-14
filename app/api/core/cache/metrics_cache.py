"""Redis caching layer for superadmin metrics."""

import json
import logging
from typing import Any, Callable, Dict, Optional

import redis.asyncio as redis

from app.api.core.config import settings

logger = logging.getLogger(__name__)


class MetricsCache:
    """Redis cache manager for superadmin dashboard metrics."""

    CACHE_TTL = 300  # 5 minutes in seconds
    CACHE_PREFIX = "superadmin:metrics"

    def __init__(self):
        """Initialize Redis connection pool."""
        self.redis_url = settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None

    async def get_redis(self) -> redis.Redis:
        """
        Get or create Redis connection.

        Returns:
            Redis client instance

        Examples:
            >>> cache = MetricsCache()
            >>> client = await cache.get_redis()
        """
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    def _make_key(self, metric_type: str, **params) -> str:
        """
        Generate cache key from metric type and parameters.

        Args:
            metric_type: Type of metric (revenue, users, ai_credits)
            **params: Additional parameters for the cache key

        Returns:
            Cache key string

        Examples:
            >>> cache._make_key("revenue", days=30)
            'superadmin:metrics:revenue:days=30'
        """
        key_parts = [self.CACHE_PREFIX, metric_type]

        # Sort params for consistent key generation
        if params:
            param_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
            key_parts.append(param_str)

        return ":".join(key_parts)

    async def get(self, metric_type: str, **params) -> Optional[Dict[str, Any]]:
        """
        Get cached metric data.

        Args:
            metric_type: Type of metric to retrieve
            **params: Additional parameters for cache lookup

        Returns:
            Cached data dict or None if not found/expired

        Examples:
            >>> data = await cache.get("revenue", days=30)
        """
        try:
            client = await self.get_redis()
            key = self._make_key(metric_type, **params)

            cached_data = await client.get(key)
            if cached_data:
                logger.debug(f"Cache hit for {key}")
                return json.loads(cached_data)

            logger.debug(f"Cache miss for {key}")
            return None

        except Exception as e:
            logger.error(f"Redis get error for {metric_type}: {e}", exc_info=True)
            return None

    async def set(
        self,
        metric_type: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
        **params,
    ) -> bool:
        """
        Store metric data in cache.

        Args:
            metric_type: Type of metric to store
            data: Metric data to cache
            ttl: Time-to-live in seconds (default: 300)
            **params: Additional parameters for cache key

        Returns:
            True if successful, False otherwise

        Examples:
            >>> await cache.set("revenue", {"total": 1000}, days=30)
        """
        try:
            client = await self.get_redis()
            key = self._make_key(metric_type, **params)
            ttl = ttl or self.CACHE_TTL

            serialized = json.dumps(data, default=str)
            await client.setex(key, ttl, serialized)

            logger.debug(f"Cached {key} with TTL {ttl}s")
            return True

        except Exception as e:
            logger.error(f"Redis set error for {metric_type}: {e}", exc_info=True)
            return False

    async def delete(self, metric_type: str, **params):
        """
        Delete cached metric data.

        Args:
            metric_type: Type of metric to delete
            **params: Additional parameters for cache key

        Examples:
            >>> await cache.delete("revenue", days=30)
        """
        try:
            client = await self.get_redis()
            key = self._make_key(metric_type, **params)
            await client.delete(key)
            logger.debug(f"Deleted cache key {key}")

        except Exception as e:
            logger.error(f"Redis delete error for {metric_type}: {e}", exc_info=True)

    async def clear_all_metrics(self):
        """
        Clear all cached metrics.

        Useful for manual cache invalidation or testing.

        Examples:
            >>> await cache.clear_all_metrics()
        """
        try:
            client = await self.get_redis()
            pattern = f"{self.CACHE_PREFIX}:*"

            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted_count += await client.delete(*keys)
                if cursor == 0:
                    break

            logger.info(f"Cleared {deleted_count} cached metrics")

        except Exception as e:
            logger.error(f"Redis clear error: {e}", exc_info=True)

    async def get_or_compute(
        self,
        metric_type: str,
        compute_fn: Callable,
        ttl: Optional[int] = None,
        **params,
    ) -> Dict[str, Any]:
        """
        Get cached data or compute and cache if not found.

        Args:
            metric_type: Type of metric
            compute_fn: Async function to compute metric if not cached
            ttl: Time-to-live in seconds
            **params: Additional parameters for cache key and compute function

        Returns:
            Metric data dict

        Examples:
            >>> async def compute_revenue():
            ...     return {"total": 1000}
            >>> data = await cache.get_or_compute("revenue", compute_revenue, days=30)
        """
        # Try to get from cache
        cached_data = await self.get(metric_type, **params)
        if cached_data is not None:
            return cached_data

        # Compute fresh data
        try:
            logger.debug(f"Computing {metric_type} with params {params}")
            fresh_data = await compute_fn()

            # Cache the result
            await self.set(metric_type, fresh_data, ttl=ttl, **params)

            return fresh_data

        except Exception as e:
            logger.error(f"Error computing {metric_type}: {e}", exc_info=True)
            raise


# Global cache instance
_cache_instance: Optional[MetricsCache] = None


def get_metrics_cache() -> MetricsCache:
    """
    Get singleton metrics cache instance.

    Returns:
        MetricsCache instance

    Examples:
        >>> cache = get_metrics_cache()
        >>> data = await cache.get("revenue", days=30)
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MetricsCache()
    return _cache_instance
