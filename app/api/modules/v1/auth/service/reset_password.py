"""Password Reset Service"""

import logging
import secrets

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AccountInactiveError,
    InvalidResetCodeError,
    NotFoundError,
    PasswordReuseError,
    ProcessingError,
    ResetTokenExpiredError,
)
from app.api.core.dependencies.redis_service import get_redis_client
from app.api.core.dependencies.send_reset_password import (
    send_password_reset_email,
)
from app.api.core.logger import setup_logging
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password, verify_password

setup_logging()
logger = logging.getLogger("app")

# Redis key prefixes and TTL
RESET_CODE_PREFIX = "password_reset_code:"
RESET_TOKEN_PREFIX = "password_reset_token:"
CODE_TTL_MINUTES = 15  # Reset code expires in 15 minutes
TOKEN_TTL_MINUTES = 30  # Reset token expires in 30 minutes


def generate_reset_code() -> str:
    """Generate a 6-digit reset code"""
    return str(secrets.randbelow(1000000)).zfill(6)


def generate_reset_token() -> str:
    """Generate a secure reset token"""
    return secrets.token_urlsafe(32)


async def store_reset_code(
    email: str, reset_code: str, ttl_minutes: int = CODE_TTL_MINUTES
) -> bool:
    """
    Store password reset code in Redis with TTL.

    Args:
        email: User's email address
        reset_code: 6-digit reset code
        ttl_minutes: Time-to-live in minutes

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_CODE_PREFIX}{email}"
        await client.setex(key, ttl_minutes * 60, reset_code)
        logger.info(f"Stored reset code for {email} with {ttl_minutes}min TTL")
        return True
    except Exception as e:
        logger.error(f"Failed to store reset code: {str(e)}")
        raise ProcessingError(
            message=(
                "Unable to process your password reset request at this time. "
                "Please try again later."
            )
        )


async def verify_reset_code_redis(email: str, code: str) -> bool:
    """
    Verify reset code from Redis and delete if valid (one-time use).

    Args:
        email: User's email address
        code: Reset code to verify

    Returns:
        True if code is valid
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_CODE_PREFIX}{email}"
        stored_code = await client.get(key)

        if stored_code and stored_code == code:
            # Delete code after successful verification (one-time use)
            await client.delete(key)
            logger.info(f"Reset code verified and deleted for {email}")
            return True

        logger.warning(f"Reset code verification failed for {email}")
        return False
    except Exception as e:
        logger.error(f"Reset code verification error: {str(e)}")
        raise ProcessingError(
            message="Unable to verify your reset code at this time. Please try again later."
        )


async def store_reset_token(
    reset_token: str, user_id: str, ttl_minutes: int = TOKEN_TTL_MINUTES
) -> bool:
    """
    Store reset token in Redis with user_id as value.

    Args:
        reset_token: Generated reset token
        user_id: User UUID
        ttl_minutes: Time-to-live in minutes

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_TOKEN_PREFIX}{reset_token}"
        await client.setex(key, ttl_minutes * 60, user_id)
        logger.info(f"Stored reset token for user_id={user_id} with {ttl_minutes}min TTL")
        return True
    except Exception as e:
        logger.error(f"Failed to store reset token: {str(e)}")
        raise ProcessingError(
            message=(
                "We're having trouble processing your password reset request. "
                "Please try again in a moment."
            )
        )


async def get_user_from_reset_token(reset_token: str) -> str | None:
    """
    Get user_id from reset token and delete token (one-time use).

    Args:
        reset_token: Reset token to verify

    Returns:
        User ID if token is valid, None otherwise
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_TOKEN_PREFIX}{reset_token}"
        user_id = await client.get(key)

        if user_id:
            await client.delete(key)
            logger.info(f"Reset token verified and deleted for user {user_id}")
            return user_id

        logger.warning(f"Reset token not found or expired: {reset_token}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving user from reset token: {str(e)}")
        raise ProcessingError(
            message=(
                "We're unable to verify your reset code right now. "
                "Please try again or request a new code."
            )
        )


async def delete_reset_code(email: str) -> bool:
    """
    Delete reset code from Redis.

    Args:
        email: User's email address

    Returns:
        True if successful
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_CODE_PREFIX}{email}"
        await client.delete(key)
        logger.info(f"Deleted reset code for {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete reset code: {str(e)}")
        raise ProcessingError(
            message="We encountered an issue processing your request. Please try again."
        )


async def request_password_reset(
    db: AsyncSession,
    email: str,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    """
    Generate reset code, store in Redis, and send email.

    Args:
        db: Database session
        email: Email address requesting password reset
        background_tasks: FastAPI background tasks (optional)

    Returns:
        Dict with user email

    Raises:
        NotFoundError: If user not found
        AccountInactiveError: If user account is inactive
        ProcessingError: If reset request fails
    """
    try:
        user = await db.scalar(select(User).where(User.email == email))
        if not user:
            logger.warning(f"Password reset requested for non-existent email={email}")
            raise NotFoundError(
                message=(
                    "We couldn't find an account with that email address. "
                    "Please check and try again."
                )
            )

        if not user.is_active:
            logger.warning(f"Password reset requested for inactive user: email={email}")
            raise AccountInactiveError()

        reset_code = generate_reset_code()

        await store_reset_code(user.email, reset_code, ttl_minutes=CODE_TTL_MINUTES)

        email_context = {
            "user_email": user.email,
            "user_name": user.name,
            "reset_code": reset_code,
            "frontend_url": settings.FRONTEND_URL,
            "app_url": settings.APP_URL,
            "expiry_minutes": CODE_TTL_MINUTES,
        }

        if background_tasks is not None:
            background_tasks.add_task(send_password_reset_email, email_context)
            logger.info(f"Scheduled password reset email to be sent to: {user.email}")
        else:
            await send_password_reset_email(email_context)
            logger.info(f"Sent password reset email to: {user.email}")

        logger.info(f"Password reset code generated for user_id={user.id}, email={user.email}")
        return {"email": user.email}

    except Exception:
        logger.exception(f"Failed to generate reset code for email={email}")
        raise


async def verify_reset_code(
    db: AsyncSession,
    email: str,
    code: str,
) -> str | None:
    """
    Verify reset code and return a temporary reset token.

    Args:
        db: Database session
        email: User's email
        code: Reset code to verify

    Returns:
        Reset token if code is valid, None otherwise
    """
    try:
        user = await db.scalar(select(User).where(User.email == email))
        if not user:
            logger.warning(f"Reset code verification attempted for non-existent email={email}")
            raise NotFoundError(
                message=(
                    "We couldn't find your account. Please try logging in again or contact support."
                )
            )

        is_valid = await verify_reset_code_redis(email, code)

        if not is_valid:
            logger.warning(f"Invalid reset code for email={email}, user_id={user.id}")
            raise InvalidResetCodeError()

        reset_token = generate_reset_token()

        await store_reset_token(reset_token, str(user.id), ttl_minutes=TOKEN_TTL_MINUTES)

        logger.info(f"Reset code verified for email={email}, user_id={user.id}")
        return reset_token

    except Exception:
        logger.exception(f"Error verifying reset code for email={email}")
        raise


async def reset_password(
    db: AsyncSession,
    reset_token: str,
    new_password: str,
) -> bool:
    """
    Reset user password using reset token.
    """
    try:
        client = await get_redis_client()
        key = f"{RESET_TOKEN_PREFIX}{reset_token}"
        user_id = await client.get(key)

        if not user_id:
            logger.warning("Invalid or expired reset token")
            raise ResetTokenExpiredError()

        user = await db.get(User, user_id)
        if not user:
            logger.error(f"User not found for user_id={user_id}")
            await client.delete(key)
            raise NotFoundError(
                message=(
                    "We couldn't find your account. "
                    "Please try again or contact support if this continues."
                )
            )

        if verify_password(new_password, user.hashed_password):
            logger.warning(f"User {user.id} attempted to reuse old password")
            raise PasswordReuseError("New password cannot be the same as your old password")

        await client.delete(key)
        logger.info(f"Reset token consumed for user {user_id}")

        user.hashed_password = hash_password(new_password)
        db.add(user)
        await db.commit()

        await delete_reset_code(user.email)

        logger.info(f"Password reset successful for user_id={user.id}")
        return True

    except PasswordReuseError:
        raise
    except Exception:
        logger.exception("Error resetting password")
        await db.rollback()
        raise
