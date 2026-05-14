import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.auth.models.oauth_models import OAuthLoginEvent, RefreshTokenMetadata

logger = logging.getLogger(__name__)


class OAuthCRUD:
    """
    CRUD operations for OAuth-related database models.

    Handles token metadata, login events, and audit logging for OAuth flows.
    """

    @staticmethod
    async def create_token_metadata(
        db: AsyncSession,
        user_id: uuid.UUID,
        jti: str,
        provider: str,
        provider_token_exp: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> RefreshTokenMetadata:
        """
        Create and store refresh token metadata.

        Records details about a newly issued refresh token for audit and
        revocation purposes.

        Args:
            db: Async database session
            user_id: User this token belongs to
            jti: JWT Token ID (unique identifier)
            provider: OAuth provider or 'local'
            provider_token_exp: Unix timestamp of provider token expiry
            ip_address: Client IP address
            user_agent: Client user agent string
            expires_at: When this token expires (default: 30 days from now)

        Returns:
            Created RefreshTokenMetadata instance

        Raises:
            Exception: If database operation fails

        Examples:
            >>> metadata = await OAuthCRUD.create_token_metadata(
            ...     db=db,
            ...     user_id=user_id,
            ...     jti=refresh_token_jti,
            ...     provider="google",
            ...     ip_address="192.168.1.1",
            ...     user_agent="Mozilla/5.0..."
            ... )
        """
        try:
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            if expires_at is None:
                expires_at = now + timedelta(days=30)

            metadata = RefreshTokenMetadata(
                user_id=user_id,
                jti=jti,
                provider=provider,
                provider_token_exp=provider_token_exp,
                issued_at=now,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                is_revoked=False,
            )

            db.add(metadata)
            await db.flush()
            await db.refresh(metadata)

            logger.info(f"Created token metadata for user {user_id} from provider {provider}")
            return metadata

        except Exception as e:
            logger.error(
                f"Failed to create token metadata for user {user_id}: {str(e)}",
                exc_info=True,
            )
            raise ProcessingError(
                message="Unable to complete authentication request. Please try again later."
            )

    @staticmethod
    async def get_token_metadata(db: AsyncSession, jti: str) -> Optional[RefreshTokenMetadata]:
        """
        Retrieve token metadata by JTI.

        Args:
            db: Async database session
            jti: JWT Token ID

        Returns:
            RefreshTokenMetadata if found, None otherwise

        Examples:
            >>> metadata = await OAuthCRUD.get_token_metadata(db, jti)
            >>> if metadata and not metadata.is_revoked:
            ...     # Token is valid
        """
        try:
            stmt = select(RefreshTokenMetadata).where(RefreshTokenMetadata.jti == jti)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to retrieve token metadata for jti {jti}: {str(e)}")
            return None

    @staticmethod
    async def revoke_token(
        db: AsyncSession, jti: str, reason: Optional[str] = None
    ) -> Optional[RefreshTokenMetadata]:
        """
        Revoke a refresh token.

        Marks token as revoked and records revocation timestamp for audit trail.

        Args:
            db: Async database session
            jti: JWT Token ID
            reason: Optional reason for revocation

        Returns:
            Updated RefreshTokenMetadata if found and updated

        Examples:
            >>> await OAuthCRUD.revoke_token(db, jti, reason="user_logout")
        """
        try:
            metadata = await OAuthCRUD.get_token_metadata(db, jti)
            if not metadata:
                logger.warning(f"Attempted to revoke non-existent token: {jti}")
                return None

            metadata.is_revoked = True
            metadata.revoked_at = datetime.now(timezone.utc)

            db.add(metadata)
            await db.flush()
            await db.refresh(metadata)

            logger.info(f"Revoked token {jti} (reason: {reason or 'unspecified'})")
            return metadata

        except Exception as e:
            logger.error(f"Failed to revoke token {jti}: {str(e)}", exc_info=True)
            raise ProcessingError(
                message="Unable to complete logout at this time. Please try again."
            )

    @staticmethod
    async def get_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> list[RefreshTokenMetadata]:
        """
        Get all active (non-revoked) refresh tokens for a user.

        Useful for tracking active sessions and forcing logout from all devices.

        Args:
            db: Async database session
            user_id: User ID

        Returns:
            List of active RefreshTokenMetadata records

        Examples:
            >>> tokens = await OAuthCRUD.get_user_tokens(db, user_id)
            >>> for token in tokens:
            ...     await OAuthCRUD.revoke_token(db, token.jti, reason="force_logout")
        """
        try:
            stmt = (
                select(RefreshTokenMetadata)
                .where(RefreshTokenMetadata.user_id == user_id)
                .where(not RefreshTokenMetadata.is_revoked)
            )
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to retrieve user tokens for {user_id}: {str(e)}")
            return []

    @staticmethod
    async def log_oauth_event(
        db: AsyncSession,
        provider: str,
        status: str,
        email: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        failure_reason: Optional[str] = None,
        error_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> OAuthLoginEvent:
        """
        Log an OAuth authentication event.

        Records all OAuth login attempts (success/failure) for audit and
        security monitoring.

        Args:
            db: Async database session
            provider: OAuth provider ('google', 'microsoft', 'apple')
            status: Result status ('success', 'failed', 'blocked', 'error')
            email: Email address attempted (for failed attempts)
            user_id: Authenticated user ID (for successful attempts)
            failure_reason: Reason for failure
            error_code: Machine-readable error code
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Created OAuthLoginEvent instance

        Raises:
            Exception: If database operation fails

        Examples:
            >>> event = await OAuthCRUD.log_oauth_event(
            ...     db=db,
            ...     provider="google",
            ...     status="success",
            ...     user_id=user_id,
            ...     ip_address="192.168.1.1"
            ... )
        """
        try:
            event = OAuthLoginEvent(
                provider=provider,
                status=status,
                email=email,
                user_id=user_id,
                failure_reason=failure_reason,
                error_code=error_code,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            db.add(event)
            await db.flush()
            await db.refresh(event)

            logger.debug(
                f"Logged OAuth event: provider={provider}, status={status}, user={user_id or email}"
            )
            return event

        except Exception as e:
            logger.error(f"Failed to log OAuth event: {str(e)}", exc_info=True)
            raise ProcessingError(message="An internal error occurred during authentication.")

    @staticmethod
    async def get_oauth_events(
        db: AsyncSession,
        user_id: Optional[uuid.UUID] = None,
        provider: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[OAuthLoginEvent]:
        """
        Query OAuth login events for audit/monitoring.

        Allows filtering by user, provider, or status for security analysis.

        Args:
            db: Async database session
            user_id: Filter by user ID
            provider: Filter by provider
            status: Filter by status
            limit: Maximum results to return

        Returns:
            List of OAuthLoginEvent records

        Examples:
            >>> failed_events = await OAuthCRUD.get_oauth_events(
            ...     db=db,
            ...     provider="google",
            ...     status="failed",
            ...     limit=100
            ... )
            >>> for event in failed_events:
            ...     print(f"{event.email}: {event.failure_reason}")
        """
        try:
            stmt = select(OAuthLoginEvent)

            if user_id:
                stmt = stmt.where(OAuthLoginEvent.user_id == user_id)
            if provider:
                stmt = stmt.where(OAuthLoginEvent.provider == provider)
            if status:
                stmt = stmt.where(OAuthLoginEvent.status == status)

            stmt = stmt.order_by(OAuthLoginEvent.timestamp.desc()).limit(limit)

            result = await db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to query OAuth events: {str(e)}")
            return []

    @staticmethod
    async def revoke_user_tokens(
        db: AsyncSession, user_id: uuid.UUID, reason: Optional[str] = None
    ) -> int:
        """
        Revoke all active tokens for a user (logout from all devices).

        Args:
            db: Async database session
            user_id: User ID
            reason: Reason for revocation

        Returns:
            Number of tokens revoked

        Examples:
            >>> revoked_count = await OAuthCRUD.revoke_user_tokens(
            ...     db=db,
            ...     user_id=user_id,
            ...     reason="security_alert"
            ... )
            >>> print(f"Revoked {revoked_count} tokens")
        """
        try:
            tokens = await OAuthCRUD.get_user_tokens(db, user_id)
            count = 0

            for token in tokens:
                await OAuthCRUD.revoke_token(db, token.jti, reason=reason)
                count += 1

            logger.info(f"Revoked {count} tokens for user {user_id} (reason: {reason})")
            return count

        except Exception as e:
            logger.error(f"Failed to revoke user tokens for {user_id}: {str(e)}")
            raise ProcessingError(
                message="We couldn't complete your logout from all devices. Please try again later."
            )
