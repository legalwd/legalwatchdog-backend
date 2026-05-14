"""Rate limiting service for authentication operations."""

import logging
from typing import Optional

from app.api.core.custom_exceptions.exceptions import RateLimitExceededError
from app.api.core.dependencies.redis_service import check_rate_limit

logger = logging.getLogger(__name__)


class RateLimitService:
    """Service for managing rate limits across authentication endpoints."""

    def __init__(
        self,
        max_email_attempts: int,
        max_ip_attempts: int,
        rate_limit_window: int,
    ):
        """
        Initialize rate limit service.

        Args:
            max_email_attempts: Maximum attempts allowed per email.
            max_ip_attempts: Maximum attempts allowed per IP.
            rate_limit_window: Time window in seconds for rate limits.

        Examples:
            >>> service = RateLimitService(
            ...     max_email_attempts=3,
            ...     max_ip_attempts=9,
            ...     rate_limit_window=3600,
            ... )
        """
        self.max_email_attempts = max_email_attempts
        self.max_ip_attempts = max_ip_attempts
        self.rate_limit_window = rate_limit_window

    async def check_email_rate_limit(self, email: str, key_prefix: str) -> None:
        """
        Check rate limit for email address.

        Args:
            email: Email address to check.
            key_prefix: Redis key prefix (e.g., "password_reset", "otp_verify").

        Raises:
            RateLimitExceededError: If rate limit exceeded.

        Examples:
            >>> await service.check_email_rate_limit(
            ...     "user@example.com",
            ...     "password_reset"
            ... )
        """
        allowed = await check_rate_limit(
            f"{key_prefix}:email:{email}",
            max_attempts=self.max_email_attempts,
            window_seconds=self.rate_limit_window,
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {key_prefix} email: {email}")
            raise RateLimitExceededError(
                message=f"Too many {key_prefix} attempts for this email. "
                f"Please retry in {self.rate_limit_window // 3600} hour(s)."
            )

    async def check_ip_rate_limit(self, ip_address: str, key_prefix: str) -> None:
        """
        Check rate limit for IP address.

        Args:
            ip_address: IP address to check.
            key_prefix: Redis key prefix (e.g., "password_reset", "otp_verify").

        Raises:
            RateLimitExceededError: If rate limit exceeded.

        Examples:
            >>> await service.check_ip_rate_limit(
            ...     "192.168.1.1",
            ...     "password_reset"
            ... )
        """
        allowed = await check_rate_limit(
            f"{key_prefix}:ip:{ip_address}",
            max_attempts=self.max_ip_attempts,
            window_seconds=self.rate_limit_window,
        )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {key_prefix} IP: {ip_address}")
            raise RateLimitExceededError(
                message=f"Too many {key_prefix} attempts from this IP. "
                f"Please retry in {self.rate_limit_window // 3600} hour(s)."
            )

    async def check_combined_limits(
        self, email: str, ip_address: Optional[str], key_prefix: str
    ) -> None:
        """
        Check both email and IP rate limits.

        Args:
            email: Email address to check.
            ip_address: IP address to check (optional).
            key_prefix: Redis key prefix.

        Raises:
            RateLimitExceededError: If either limit exceeded.

        Examples:
            >>> await service.check_combined_limits(
            ...     "user@example.com",
            ...     "192.168.1.1",
            ...     "password_reset"
            ... )
        """
        await self.check_email_rate_limit(email, key_prefix)

        if ip_address:
            await self.check_ip_rate_limit(ip_address, key_prefix)
