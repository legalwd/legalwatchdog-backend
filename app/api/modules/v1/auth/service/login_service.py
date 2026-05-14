import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    AccountUnverifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    ProcessingError,
    RateLimitExceededError,
    TokenExpiredError,
)
from app.api.core.dependencies.redis_service import (
    add_token_to_denylist,
    check_rate_limit,
    get_redis_client,
    reset_rate_limit,
)
from app.api.core.logger import setup_logging
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import calculate_token_ttl, create_access_token, get_token_jti
from app.api.utils.password import verify_password

setup_logging()
logger = logging.getLogger("app")

# Constants for rate limiting
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW_SECONDS = 60
ENVIRONMENT = settings.ENVIRONMENT.lower()


class LoginService:
    """
    Login service implementing secure authentication with:
    - Rate limiting
    - Account lockout
    - Token rotation
    - RBAC support
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str, ip_address: Optional[str] = None) -> dict:
        """
        Authenticate user and return tokens.

        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP for rate limiting

        Returns:
            Dictionary with tokens and user data
        """
        return await self._authenticate_user(email, password, ip_address)

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """
        Rotate tokens using refresh token.

        Args:
            refresh_token: Current refresh token (can be None if not provided)

        Returns:
            Dictionary with new tokens

        Raises:
            InvalidTokenError: If token is None or invalid
            TokenExpiredError: If token has expired
        """
        from app.api.utils.jwt import decode_token

        if not refresh_token:
            raise InvalidTokenError(message="Your session has expired. Please log in again.")

        try:
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")

            if not user_id:
                raise InvalidTokenError()

            return await self._refresh_access_token(user_id, refresh_token)
        except (InvalidTokenError, TokenExpiredError, NotFoundError, AccountInactiveError):
            raise
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise ProcessingError(message="Unable to refresh your session. Please log in again.")

    async def _authenticate_user(
        self, email: str, password: str, ip_address: Optional[str] = None
    ) -> dict:
        """
        Authenticate user with comprehensive security measures:
        - Rate limiting (5 failed attempts)
        - 15-minute account lockout after max failed attempts
        - Secure password verification
        - Token rotation with refresh tokens
        - Role-based access control context

        Args:
            db: Database session
            email: User email
            password: Plain text password
            ip_address: Client IP address for rate limiting

        Returns:
            Dictionary with access_token, refresh_token, and user data

        Raises:
            HTTPException: 429 if account locked or rate limit exceeded
            HTTPException: 401 if credentials invalid
            HTTPException: 403 if account inactive or unverified
        """

        lockout_ttl = await self._check_account_lockout(email)
        if lockout_ttl:
            minutes_remaining = lockout_ttl // 60
            logger.warning(f"Login blocked: account {email} is locked")
            raise AccountLockedError(
                message=f"Account locked due to too many failed login attempts. "
                f"Try again in {minutes_remaining} minutes."
            )

        if ip_address:
            ip_allowed = await check_rate_limit(
                f"login:ip:{ip_address}",
                max_attempts=10,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )

            if not ip_allowed:
                logger.warning(f"Rate limit exceeded for IP: {ip_address}")
                raise RateLimitExceededError(
                    message="Too many login attempts from this IP. Please try again later."
                )

        user = await self.db.scalar(select(User).where(User.email == email))

        if not user:
            await self._increment_failed_attempts(email)
            logger.warning(f"Login failed: user not found for email {email}")
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            failed_count = await self._increment_failed_attempts(email)
            remaining = MAX_LOGIN_ATTEMPTS - failed_count

            logger.warning(
                f"Login failed: invalid password for {email}. "
                f"Failed attempts: {failed_count}/{MAX_LOGIN_ATTEMPTS}"
            )

            if failed_count >= MAX_LOGIN_ATTEMPTS:
                raise AccountLockedError(
                    message=f"Your account has been temporarily locked for security reasons. "
                    f"Please try again in {LOCKOUT_DURATION_MINUTES} minutes."
                )

            raise InvalidCredentialsError(
                message=(
                    f"The email or password you entered is incorrect. "
                    f"You have {remaining} attempts remaining before your account "
                    f"is temporarily locked."
                )
            )

        if not user.is_active:
            logger.warning(f"Login blocked: inactive account {email}")
            raise AccountInactiveError()

        if not user.is_verified:
            logger.warning(f"Login blocked: unverified account {email}")
            raise AccountUnverifiedError()

        memberships = await self.db.execute(
            select(UserOrganization).where(
                UserOrganization.user_id == user.id, UserOrganization.is_active
            )
        )
        active_memberships = list(memberships.scalars().all())

        organizations = []
        for membership in active_memberships:
            role = await self.db.get(Role, membership.role_id)
            if role:
                organizations.append(
                    {
                        "organization_id": str(membership.organization_id),
                        "role_id": str(membership.role_id),
                        "role_name": role.name,
                        "permissions": role.permissions,
                        "joined_at": membership.joined_at.isoformat(),
                    }
                )

        # successful authentication, reset failed attempts
        await self._reset_failed_attempts(email)
        if ip_address:
            await reset_rate_limit(f"login:ip:{ip_address}")

        # Update last_login timestamp
        from datetime import datetime, timezone

        user.last_login = datetime.now(timezone.utc)
        self.db.add(user)
        await self.db.commit()

        access_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=2),
        )

        refresh_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=30),
        )

        refresh_token_jti = get_token_jti(refresh_token)
        # store refresh token in Redis for rotation
        await self._store_refresh_token(str(user.id), refresh_token_jti, ttl_days=30)

        logger.info(f"Successful login: {user.email}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 172800,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "is_verified": user.is_verified,
                "is_active": user.is_active,
                "organizations": organizations,
                "has_organizations": len(organizations) > 0,
            },
        }

    async def _refresh_access_token(self, user_id: str, old_refresh_token: str) -> dict:
        """
        Token rotation: Generate new access + refresh tokens, revoke old refresh token.
        Implements automatic token rotation for enhanced security.

        Args:
            user_id: User UUID
            old_refresh_token: Current refresh token to rotate

        Returns:
            Dictionary with new access_token and refresh_token

        Raises:
            HTTPException: 401 if refresh token invalid or revoked
            HTTPException: 404 if user not found
            HTTPException: 403 if user inactive
        """
        old_token_jti = get_token_jti(old_refresh_token)
        if not old_token_jti:
            logger.warning(f"Invalid refresh token format for user {user_id}")
            raise InvalidTokenError(
                message="Your session is invalid. Please log in again to continue."
            )

        is_valid = await self._verify_refresh_token(user_id, old_token_jti)
        if not is_valid:
            logger.warning(f"Refresh token validation failed for user {user_id}")
            raise TokenExpiredError(
                message="Your session has expired or been revoked. Please log in again."
            )

        user = await self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            logger.warning(f"Token refresh failed: user {user_id} not found")
            raise NotFoundError(message="Your account could not be found. Please log in again.")

        if not user.is_active:
            logger.warning(f"Token refresh blocked: user {user.email} is inactive")
            raise AccountInactiveError(
                message="Your account has been deactivated. Please contact support for assistance."
            )

        await self._revoke_refresh_token(user_id, old_token_jti)
        ttl = calculate_token_ttl(old_refresh_token)
        await add_token_to_denylist(old_token_jti, ttl)

        new_access_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=2),
        )

        new_refresh_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=30),
        )
        new_refresh_token_jti = get_token_jti(new_refresh_token)

        await self._store_refresh_token(str(user.id), new_refresh_token_jti, ttl_days=30)

        logger.info(f"Token rotated for user: {user.email} (old jti: {old_token_jti[:8]}...)")

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 172800,
        }

    async def _check_account_lockout(self, email: str) -> Optional[int]:
        """
        Check if account is locked due to failed login attempts.

        Args:
            email: User email

        Returns:
            Remaining lockout time in seconds, or None if not locked
        """
        try:
            redis_client = await get_redis_client()
            lockout_key = f"{ENVIRONMENT}:login:lockout:{email}"
            ttl = await redis_client.ttl(lockout_key)

            if ttl > 0:
                return ttl
            return None
        except Exception as e:
            logger.error(f"Failed to check account lockout: {str(e)}")
            return None

    async def _increment_failed_attempts(self, email: str) -> int:
        """
        Increment failed login attempts counter.
        After MAX_LOGIN_ATTEMPTS, lock account for LOCKOUT_DURATION_MINUTES.

        Args:
            email: User email

        Returns:
            Current failed attempt count
        """
        try:
            redis_client = await get_redis_client()
            attempts_key = f"login:failed:{email}"

            attempts = await redis_client.incr(attempts_key)

            if attempts == 1:
                await redis_client.expire(attempts_key, LOCKOUT_DURATION_MINUTES * 60)

            if attempts >= MAX_LOGIN_ATTEMPTS:
                lockout_key = f"{ENVIRONMENT}:login:lockout:{email}"
                await redis_client.setex(lockout_key, LOCKOUT_DURATION_MINUTES * 60, str(attempts))
                logger.warning(
                    f"Account locked for {email}: {attempts} failed attempts. "
                    f"Locked for {LOCKOUT_DURATION_MINUTES} minutes."
                )

            return attempts
        except Exception as e:
            logger.error(f"Failed to increment failed attempts: {str(e)}")
            return 0

    async def _reset_failed_attempts(self, email: str) -> bool:
        """
        Reset failed login attempts after successful login.

        Args:
            email: User email

        Returns:
            True if successful
        """
        try:
            redis_client = await get_redis_client()
            attempts_key = f"login:failed:{email}"
            lockout_key = f"login:lockout:{email}"

            await redis_client.delete(attempts_key)
            await redis_client.delete(lockout_key)

            logger.info(f"Reset failed attempts for {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to reset attempts: {str(e)}")
            return False

    async def _store_refresh_token(
        self, user_id: str, refresh_token: str, ttl_days: int = 30
    ) -> bool:
        """
        Store refresh token in Redis for token rotation.

        Args:
            user_id: User UUID
            refresh_token: Refresh token string (jti)
            ttl_days: Time-to-live in days

        Returns:
            True if successful
        """
        try:
            redis_client = await get_redis_client()
            key = f"{ENVIRONMENT}:refresh_token:{user_id}:{refresh_token}"
            await redis_client.setex(key, ttl_days * 24 * 3600, "valid")
            logger.info(f"Stored refresh token for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store refresh token: {str(e)}")
            return False

    async def _verify_refresh_token(self, user_id: str, refresh_token: str) -> bool:
        """
        Verify if refresh token is valid and not blacklisted.

        Args:
            user_id: User UUID
            refresh_token: Refresh token string (jti)

        Returns:
            True if valid
        """
        try:
            redis_client = await get_redis_client()
            key = f"{ENVIRONMENT}:refresh_token:{user_id}:{refresh_token}"
            exists = await redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to verify refresh token: {str(e)}")
            return False

    async def _revoke_refresh_token(self, user_id: str, refresh_token: str) -> bool:
        """
        Revoke a refresh token (token rotation).

        Args:
            user_id: User UUID
            refresh_token: Refresh token string (jti)

        Returns:
            True if successful
        """
        try:
            redis_client = await get_redis_client()
            key = f"{ENVIRONMENT}:refresh_token:{user_id}:{refresh_token}"
            await redis_client.delete(key)
            logger.info(f"Revoked refresh token for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {str(e)}")
            return False

    async def logout(self, user_id: str, token: str = None) -> dict:
        """
        Logout user and invalidate their tokens.

        Args:
            user_id: User UUID
            token: Current access token to invalidate (optional but recommended)

        Returns:
            Logout confirmation
        """
        try:
            user = await self.db.scalar(select(User).where(User.id == user_id))

            if user:
                await self._reset_failed_attempts(user.email)

            if token:
                jti = get_token_jti(token)
                if jti:
                    ttl = calculate_token_ttl(token)
                    await add_token_to_denylist(jti, ttl)
                    logger.info(f"Token {jti} added to denylist for user {user_id}")

            await self._invalidate_user_refresh_tokens(user_id)

            logger.info(f"User {user_id} logged out successfully")

            return {"message": "Logged out successfully", "success": True}

        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise ProcessingError(
                message="Unable to log you out at this time. Please try again in a moment."
            )

    async def _invalidate_user_refresh_tokens(self, user_id: str) -> bool:
        """
        Invalidate all refresh tokens for a user.
        This prevents token refresh after logout.

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
                logger.info(f"Invalidated {len(keys)} refresh tokens for user {user_id}")

            return True
        except Exception as e:
            logger.error(f"Failed to invalidate refresh tokens: {str(e)}")
            return False
