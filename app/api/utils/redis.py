import json
import logging
from typing import Any, Dict, Optional

from redis.asyncio.client import Redis

from app.api.core.config import settings

logger = logging.getLogger(__name__)

ENVIRONMENT = settings.ENVIRONMENT.lower()


async def store_user_credentials(
    redis_client: Redis, email: str, registration_data: Dict[str, Any], ttl_seconds: int = 600
) -> bool:
    """
    Store user registration credentials in Redis with TTL.

    Args:
        redis_client: Async Redis client instance
        email: User email (used as key)
        registration_data: Dictionary containing all registration data
            Expected keys: name, email, industry, hashed_password, otp_code
        ttl_seconds: Time to live in seconds (default: 600 = 10 minutes)

    Returns:
        bool: True if stored successfully, False otherwise

    Raises:
        Exception: If Redis operation fails
    """
    try:
        key = f"{ENVIRONMENT}:pending_registration:{email}"

        data_json = json.dumps(registration_data)

        await redis_client.setex(name=key, time=ttl_seconds, value=data_json)

        logger.info(
            "Stored registration credentials for email=%s with TTL=%d seconds",
            email,
            ttl_seconds,
        )
        return True

    except Exception as e:
        logger.error("Failed to store credentials for email=%s: %s", email, str(e), exc_info=True)
        raise Exception("Failed to store registration data")


async def get_user_credentials(redis_client: Redis, email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user registration credentials from Redis.

    Args:
        redis_client: Async Redis client instance
        email: User email to retrieve credentials for

    Returns:
        Optional[Dict[str, Any]]: Registration data dictionary if exists, None otherwise
            Contains: name, email, industry, hashed_password, otp_code

    Raises:
        Exception: If Redis operation fails
    """
    try:
        key = f"{ENVIRONMENT}:pending_registration:{email}"

        data_json = await redis_client.get(key)

        if not data_json:
            logger.debug("No pending registration found for email=%s", email)
            return None

        registration_data = json.loads(data_json)

        logger.debug("Retrieved registration credentials for email=%s", email)
        return registration_data

    except json.JSONDecodeError as e:
        logger.error("Failed to decode JSON for email=%s: %s", email, str(e), exc_info=True)
        return None
    except Exception as e:
        logger.error(
            "Failed to retrieve credentials for email=%s: %s",
            email,
            str(e),
            exc_info=True,
        )
        raise Exception("Failed to retrieve registration data")


async def delete_user_credentials(redis_client: Redis, email: str) -> bool:
    """
    Delete user registration credentials from Redis.

    Typically called after successful OTP verification or registration completion.

    Args:
        redis_client: Async Redis client instance
        email: User email to delete credentials for

    Returns:
        bool: True if deleted successfully, False if key didn't exist

    Raises:
        Exception: If Redis operation fails
    """
    try:
        key = f"{ENVIRONMENT}:pending_registration:{email}"

        result = await redis_client.delete(key)

        if result > 0:
            logger.info("Deleted registration credentials for email=%s", email)
            return True
        else:
            logger.debug("No credentials found to delete for email=%s", email)
            return False

    except Exception as e:
        logger.error(
            "Failed to delete credentials for email=%s: %s",
            email,
            str(e),
            exc_info=True,
        )
        raise Exception("Failed to delete registration data")


async def verify_and_get_credentials(
    redis_client: Redis, email: str, otp_code: str
) -> Optional[Dict[str, Any]]:
    """
    Verify OTP and retrieve registration credentials if valid.

    Args:
        redis_client: Async Redis client instance
        email: User email
        otp_code: OTP code to verify

    Returns:
        Optional[Dict[str, Any]]: Registration data if OTP is valid, None otherwise

    Raises:
        Exception: If Redis operation fails
    """
    try:
        credentials = await get_user_credentials(redis_client, email)

        if not credentials:
            logger.warning("No pending registration found for email=%s", email)
            return None

        stored_otp = credentials.get("otp_code")
        if stored_otp != otp_code:
            logger.warning(
                "OTP mismatch for email=%s. Expected=%s, Provided=%s",
                email,
                stored_otp,
                otp_code,
            )
            return None

        logger.info("OTP verified successfully for email=%s", email)
        return credentials

    except Exception as e:
        logger.error("Failed to verify OTP for email=%s: %s", email, str(e), exc_info=True)
        raise Exception("Failed to verify OTP")
