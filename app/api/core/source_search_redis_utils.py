import json
import logging
import uuid
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from app.api.core.config import settings
from app.api.core.dependencies.redis_service import get_redis_client

logger = logging.getLogger("app")

SEARCH_SESSION_TTL = settings.SEARCH_SESSION_TTL


async def cache_search_session(user_id: uuid.UUID, search_data: Dict[str, Any]) -> str:
    """
    Cache a search session with suggested sources.

    Args:
        user_id: The UUID of the user initiating the search
        search_data: Dictionary containing search results and metadata

    Returns:
        str: The session_id (UUID) for retrieving the cached data

    Raises:
        ValueError: If user_id is invalid or search_data is invalid
        RedisError: If Redis operation fails

    Example:
        from uuid import UUID

        session_id = await cache_search_session(
            user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            search_data={
                "query": "employment law",
                "sources": [...],
                "timestamp": "2024-01-01T00:00:00"
            }
        )
    """
    if not user_id:
        raise ValueError("user_id cannot be empty")

    if not isinstance(search_data, dict):
        raise ValueError("search_data must be a dictionary")

    try:
        redis = await get_redis_client()
    except Exception as e:
        logger.exception(
            "Failed to get Redis client for caching search session for user %s", user_id
        )
        raise RedisError(f"Could not connect to Redis: {str(e)}") from e

    search_data["_user_id"] = str(user_id)
    session_id = str(uuid.uuid4())
    cache_key = f"suggested_sources:{str(user_id)}:{session_id}"

    try:
        serialized_data = json.dumps(search_data)
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize search data for user %s: %s", user_id, str(e))
        raise ValueError(f"Search data is not JSON serializable: {str(e)}") from e

    try:
        await redis.setex(cache_key, SEARCH_SESSION_TTL, serialized_data)
        logger.info(
            "Cached search session %s for user %s (key=%s, ttl=%ds)",
            session_id,
            user_id,
            cache_key,
            SEARCH_SESSION_TTL,
        )
    except RedisError as e:
        logger.exception(
            "Redis error while caching search session %s for user %s (key=%s)",
            session_id,
            user_id,
            cache_key,
        )
        raise RedisError(f"Failed to cache search session: {str(e)}") from e
    except Exception:
        logger.exception(
            "Unexpected error caching search session %s for user %s (key=%s)",
            session_id,
            user_id,
            cache_key,
        )
        raise

    return session_id


async def get_search_session(user_id: uuid.UUID, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached search session.

    Args:
        user_id: The UUID of the user who created the session
        session_id: The UUID string of the search session

    Returns:
        Optional[Dict[str, Any]]: The cached search data, or None if not found/expired

    Example:
        from uuid import UUID

        search_data = await get_search_session(
            user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
        if search_data:
            sources = search_data.get("sources", [])
    """
    if not user_id:
        logger.warning(
            "User ID is empty when retrieving search session (session_id=%s)", session_id
        )
        return None

    if not session_id or not session_id.strip():
        logger.warning("Session ID is empty when retrieving search session for user %s", user_id)
        return None

    try:
        redis = await get_redis_client()
    except Exception:
        logger.exception(
            "Failed to get Redis client for retrieving search session for user %s (session_id=%s)",
            user_id,
            session_id,
        )
        return None

    cache_key = f"suggested_sources:{str(user_id)}:{session_id.strip()}"

    try:
        cached_data = await redis.get(cache_key)
    except RedisError:
        logger.exception("Redis error while reading cached search session for key %s", cache_key)
        return None
    except Exception:
        logger.exception(
            "Unexpected error reading cached search session from Redis for key %s", cache_key
        )
        return None

    if cached_data is None:
        logger.info(
            "No cached search session found for user %s session %s (key=%s)",
            user_id,
            session_id,
            cache_key,
        )
        return None

    try:
        result = json.loads(cached_data)
        logger.info(
            "Retrieved cached search session %s for user %s (key=%s)",
            session_id,
            user_id,
            cache_key,
        )
        cached_user_id = result.get("_user_id")
        if cached_user_id and cached_user_id != str(user_id):
            logger.error(
                "User ID mismatch! Requested by %s but session belongs to %s",
                user_id,
                cached_user_id,
            )
            return None

        result.pop("_user_id", None)
        return result
    except json.JSONDecodeError as e:
        logger.error("Failed to decode cached JSON for key %s: %s", cache_key, str(e))
        try:
            await redis.delete(cache_key)
            logger.info("Deleted corrupted cache entry: %s", cache_key)
        except Exception:
            logger.exception("Failed to delete corrupted cache entry: %s", cache_key)
        return None


async def get_search_session_expires_in(
    user_id: uuid.UUID, session_id: str, prefix: str = "suggested_sources"
) -> Optional[int]:
    """
    Returns the remaining TTL (in seconds) for a cached key in Redis.

    Args:
        user_id: The ID of the user who owns the session.
        session_id: The session UUID.
        prefix: Cache key prefix (default: "suggested_sources").

    Returns:
        int: Remaining TTL in seconds, or None if key not found / expired.
    """
    cache_key = f"{prefix}:{user_id}:{session_id}"
    try:
        redis = await get_redis_client()
        ttl_seconds = await redis.ttl(cache_key)
        if ttl_seconds is None or ttl_seconds < 0:
            return None
        return ttl_seconds
    except Exception as e:
        logger.exception("Failed to fetch TTL for cache key %s: %s", cache_key, e)
        return None


async def consume_search_session(
    user_id: uuid.UUID,
    session_id: str,
    accepted_urls: list[str],
) -> Optional[Dict[str, Any]]:
    """
    Fetch a cached search session and consume only the accepted sources.
    Deletes the session only when all sources are consumed.
    """

    if not user_id:
        logger.warning(
            "User ID is empty when consuming search session (session_id=%s)",
            session_id,
        )
        return None

    if not session_id or not session_id.strip():
        logger.warning(
            "Session ID is empty when consuming search session for user %s",
            user_id,
        )
        return None

    try:
        redis = await get_redis_client()
    except Exception as e:
        logger.exception(
            "Failed to get Redis client for consuming search session "
            "for user %s (session_id=%s): %s",
            user_id,
            session_id,
            str(e),
        )
        return None

    cache_key = f"suggested_sources:{str(user_id)}:{session_id.strip()}"

    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.get(cache_key)
            (cached_data,) = await pipe.execute()
    except RedisError as e:
        logger.exception(
            "Redis error while fetching search session %s for user %s (key=%s): %s",
            session_id,
            user_id,
            cache_key,
            str(e),
        )
        return None
    except Exception as e:
        logger.exception(
            "Unexpected error while fetching search session %s for user %s (key=%s): %s",
            session_id,
            user_id,
            cache_key,
            str(e),
        )
        return None

    if not cached_data:
        logger.info(
            "No cached search session to consume for user %s session %s (key=%s)",
            user_id,
            session_id,
            cache_key,
        )
        return None

    try:
        result = json.loads(cached_data)
    except json.JSONDecodeError as e:
        logger.error(
            "Failed to decode cached JSON while consuming key %s: %s",
            cache_key,
            str(e),
        )
        try:
            await redis.delete(cache_key)
            logger.info(
                "Deleted corrupted cache entry during consume: %s",
                cache_key,
            )
        except Exception:
            logger.exception(
                "Failed to delete corrupted cache entry during consume: %s",
                cache_key,
            )
        return None

    cached_user_id = result.get("_user_id")
    if cached_user_id and cached_user_id != str(user_id):
        logger.error(
            "User ID mismatch during consume! Requested by %s but session belongs to %s",
            user_id,
            cached_user_id,
        )
        return None

    sources = result.get("sources", [])
    remaining_sources = [s for s in sources if s.get("url") not in accepted_urls]

    if not remaining_sources:
        await redis.delete(cache_key)
        logger.info(
            "All sources consumed; deleted search session (key=%s)",
            cache_key,
        )
    else:
        result["sources"] = remaining_sources
        await redis.set(cache_key, json.dumps(result))
        logger.info(
            "Partially consumed search session (key=%s), %d sources remaining",
            cache_key,
            len(remaining_sources),
        )

    result.pop("_user_id", None)
    return {"sources": remaining_sources}


async def delete_search_session(user_id: uuid.UUID, session_id: str) -> bool:
    """
    Delete a cached search session (optional utility for cleanup).

    Args:
        user_id: The UUID of the user who created the session
        session_id: The UUID string of the search session

    Returns:
        bool: True if the session was deleted, False if it didn't exist

    Example:
        from uuid import UUID

        was_deleted = await delete_search_session(
            user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            session_id="550e8400-e29b-41d4-a716-446655440000"
        )
    """
    if not user_id:
        logger.warning("User ID is empty when deleting search session (session_id=%s)", session_id)
        return False

    if not session_id or not session_id.strip():
        logger.warning("Session ID is empty when deleting search session for user %s", user_id)
        return False

    try:
        redis = await get_redis_client()
    except Exception:
        logger.exception(
            "Failed to get Redis client for deleting search session for user %s (session_id=%s)",
            user_id,
            session_id,
        )
        return False

    cache_key = f"suggested_sources:{str(user_id)}:{session_id.strip()}"

    try:
        result = await redis.delete(cache_key)
    except RedisError:
        logger.exception("Redis error while deleting cached search session for key %s", cache_key)
        return False
    except Exception:
        logger.exception("Unexpected error deleting cached search session for key %s", cache_key)
        return False

    if result > 0:
        logger.info(
            "Deleted cached search session %s for user %s (key=%s)", session_id, user_id, cache_key
        )
        return True

    logger.info(
        "No cached search session to delete for user %s session %s (key=%s)",
        user_id,
        session_id,
        cache_key,
    )
    return False
