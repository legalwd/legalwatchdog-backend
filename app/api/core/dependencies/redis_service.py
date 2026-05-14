import asyncio
import logging
from typing import Optional

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

from app.api.core.config import settings
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app")

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None
_connection_pool: Optional[ConnectionPool] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client instance.

    Returns:
        Redis client instance

    Raises:
        ValueError: If REDIS_URL is not configured
    """
    global _redis_client, _connection_pool
    if _redis_client is None:
        if not settings.REDIS_URL:
            raise ValueError(
                "REDIS_URL is not configured. Please set REDIS_URL in your .env file "
                "with a valid Redis URL (e.g., redis://localhost:6379/0)"
            )

        # Create connection pool with optimized settings
        _connection_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=10,
            socket_keepalive=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        _redis_client = redis.Redis(connection_pool=_connection_pool)
        logger.info(f"Redis client initialized with URL: {settings.REDIS_URL}")
    return _redis_client


async def close_redis_client():
    """Close the Redis client connection and pool."""
    global _redis_client, _connection_pool
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    if _connection_pool:
        await _connection_pool.disconnect()
        _connection_pool = None
        logger.info("Redis client and connection pool closed")


# ==================== JWT DENYLIST ====================


async def add_token_to_denylist(jti: str, ttl: int) -> bool:
    """
    Add a JWT ID (jti) to the denylist in Redis.
    Used during logout to revoke tokens.

    Args:
        jti: JWT ID to denylist
        ttl: Time-to-live in seconds (should match token expiry)

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"jwt:denylist:{jti}"
        await client.setex(key, ttl, "revoked")
        logger.info(f"Added JWT {jti} to denylist with TTL {ttl}s")
        return True
    except Exception as e:
        logger.error(f"Failed to add JWT to denylist: {str(e)}")
        return False


async def is_token_denylisted(jti: str) -> bool:
    """
    Check if a JWT ID is in the denylist.

    Args:
        jti: JWT ID to check

    Returns:
        True if token is denylisted (revoked)
    """
    try:
        client = await get_redis_client()
        key = f"jwt:denylist:{jti}"
        exists = await client.exists(key)
        return bool(exists)
    except Exception as e:
        logger.error(f"Failed to check JWT denylist: {str(e)}")
        # Fail secure: if Redis is down, deny access
        return True


# ==================== RATE LIMITING ====================


async def check_rate_limit(
    identifier: str, max_attempts: int = 5, window_seconds: int = 60
) -> bool:
    """
    Check if identifier (IP or email) has exceeded rate limit.
    Used for login attempt throttling.

    Args:
        identifier: IP address or email to check
        max_attempts: Maximum attempts allowed in window
        window_seconds: Time window in seconds

    Returns:
        True if rate limit NOT exceeded (request allowed)
        False if rate limit exceeded (request blocked)
    """
    try:
        client = await get_redis_client()
        key = f"rate_limit:{identifier}"

        # Increment counter
        current = await client.incr(key)

        # Set expiry on first attempt
        if current == 1:
            await client.expire(key, window_seconds)

        if current > max_attempts:
            logger.warning(f"Rate limit exceeded for {identifier}: {current}/{max_attempts}")
            return False

        return True
    except Exception as e:
        logger.error(f"Rate limit check failed: {str(e)}")
        # Fail open: if Redis is down, allow request
        return True


async def get_remaining_attempts(identifier: str, max_attempts: int = 5) -> int:
    """
    Get remaining login attempts for identifier.

    Args:
        identifier: IP address or email
        max_attempts: Maximum attempts allowed

    Returns:
        Number of remaining attempts
    """
    try:
        client = await get_redis_client()
        key = f"rate_limit:{identifier}"
        current = await client.get(key)

        if current is None:
            return max_attempts

        remaining = max_attempts - int(current)
        return max(remaining, 0)
    except Exception as e:
        logger.error(f"Failed to get remaining attempts: {str(e)}")
        return 0


async def reset_rate_limit(identifier: str) -> bool:
    """
    Reset rate limit for identifier (e.g., after successful login).

    Args:
        identifier: IP address or email to reset

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"rate_limit:{identifier}"
        await client.delete(key)
        logger.info(f"Reset rate limit for {identifier}")
        return True
    except Exception as e:
        logger.error(f"Failed to reset rate limit: {str(e)}")
        return False


# ==================== OTP STORAGE ====================


async def store_otp(user_id: str, otp_code: str, ttl_minutes: int = 10) -> bool:
    """
    Store OTP in Redis with TTL.

    Args:
        user_id: User UUID
        otp_code: 6-digit OTP code
        ttl_minutes: Time-to-live in minutes

    Returns:
        True if successful
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            client = await get_redis_client()
            key = f"otp:{user_id}"
            await client.setex(key, ttl_minutes * 60, otp_code)
            logger.info(f"Stored OTP for user {user_id} with {ttl_minutes}min TTL")
            return True
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(
                    "Failed to store OTP (attempt %s/%s): %s",
                    retry_count,
                    max_retries,
                    str(e),
                )
                return False
            logger.warning(
                "Store OTP attempt %s/%s failed, retrying: %s",
                retry_count,
                max_retries,
                str(e),
            )
            # Wait before retry (exponential backoff)
            await asyncio.sleep(0.5 * retry_count)


async def verify_otp(user_id: str, otp_code: str) -> bool:
    """
    Verify OTP from Redis and delete if valid (one-time use).

    Args:
        user_id: User UUID
        otp_code: OTP code to verify

    Returns:
        True if OTP is valid
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            client = await get_redis_client()
            key = f"otp:{user_id}"
            stored_otp = await client.get(key)

            if stored_otp and stored_otp == otp_code:
                # Delete OTP after successful verification (one-time use)
                await client.delete(key)
                logger.info(f"OTP verified and deleted for user {user_id}")
                return True

            logger.warning(f"OTP verification failed for user {user_id}")
            return False
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                logger.error(
                    "OTP verification error (attempt %s/%s): %s",
                    retry_count,
                    max_retries,
                    str(e),
                )
                return False
            logger.warning(
                "OTP verification attempt %s/%s failed, retrying: %s",
                retry_count,
                max_retries,
                str(e),
            )
            # Wait before retry (exponential backoff)
            await asyncio.sleep(0.5 * retry_count)


async def delete_otp(user_id: str) -> bool:
    """
    Delete OTP from Redis.

    Args:
        user_id: User UUID

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"otp:{user_id}"
        await client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Failed to delete OTP: {str(e)}")
        return False
