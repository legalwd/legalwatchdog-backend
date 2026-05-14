import logging

from app.api.core.config import settings
from app.api.core.dependencies.redis_service import add_token_to_denylist, get_redis_client
from app.api.core.logger import setup_logging
from app.api.utils.jwt import calculate_token_ttl, get_token_jti

setup_logging()
logger = logging.getLogger("app")

ENVIRONMENT = settings.ENVIRONMENT.lower()


async def logout_user(token: str) -> bool:
    """
    Helper function to logout user by adding their JWT to the Redis denylist.

    Args:
        token: JWT access token to revoke

    Returns:
        True if logout successful
    """
    jti = get_token_jti(token)

    if not jti:
        logger.error("Failed to extract jti from token during logout")
        return False

    ttl = calculate_token_ttl(token)

    success = await add_token_to_denylist(jti, ttl)

    if success:
        logger.info(f"Token {jti} denylisted successfully")
        return True
    else:
        logger.error(f"Failed to denylist token {jti} during logout")
        return False


async def logout_all_sessions(user_id: str) -> bool:
    """
    Logout user from all devices/sessions by invalidating all their refresh tokens.

    Args:
        user_id: User UUID

    Returns:
        True if successful
    """
    try:
        redis_client = await get_redis_client()

        pattern = f"{ENVIRONMENT}:refresh_token:{user_id}:*"

        keys = []
        async for key in redis_client.scan_iter(pattern):
            keys.append(key)

        if keys:
            await redis_client.delete(*keys)
            logger.info(
                f"Logged out user {user_id} from all sessions - invalidated {len(keys)} tokens"
            )

        return True
    except Exception as e:
        logger.error(f"Failed to logout all sessions for user {user_id}: {str(e)}")
        return False
