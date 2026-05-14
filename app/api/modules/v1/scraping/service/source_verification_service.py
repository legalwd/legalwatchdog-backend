"""
Source URL verification with intelligent retry and categorization.

Handles 403s, timeouts, and accessibility issues gracefully during batch
operations like campaign launch. Distinguishes between temporary failures
(403, timeout) and permanent failures (DNS, format) to enable recovery strategies.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("app")


class VerificationStatus(str, Enum):
    """Source reachability status after verification."""

    VERIFIED = "verified"  # URL confirmed accessible
    UNVERIFIED_RETRYABLE = "unverified_retryable"  # 403, timeout, server error
    UNVERIFIED_PERMANENT = "unverified_permanent"  # DNS, format error
    BLOCKED_BY_BOT_PROTECTION = "blocked_by_bot_protection"  # 403 or 429
    TIMEOUT = "timeout"  # Connection timed out
    UNREACHABLE = "unreachable"  # Generic unreachable


@dataclass
class VerificationResult:
    """Result of URL verification attempt.

    Attributes:
        status: VerificationStatus enum indicating reachability status.
        http_status: Optional HTTP status code returned (internal use only).
        error_message: Internal error details for logging only (NOT for user exposure).
        retry_recommended: Whether retry is recommended for this failure type.
        user_message: User-friendly message for API responses (safe to expose).
    """

    status: VerificationStatus
    http_status: Optional[int] = None
    error_message: Optional[str] = None  # Internal only - DO NOT expose to users
    retry_recommended: bool = False
    user_message: Optional[str] = None  # Safe to expose - always use this for user responses


class SourceVerificationService:
    """
    Intelligent URL verification for source discovery.

    Distinguishes between temporary (403, timeout) and permanent failures,
    enabling recovery strategies during batch operations. Used during
    automatic campaign source discovery to create sources even if URLs
    are temporarily unreachable.
    """

    # User agents to rotate through for retries
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    ]

    @classmethod
    async def verify_single(
        cls,
        url: str,
        attempt_count: int = 1,
        timeout: int = 8,
    ) -> VerificationResult:
        """Verify one URL using a user-agent selected for the retry attempt.

        Args:
            url: URL to verify.
            attempt_count: 1-based verification attempt count used to rotate
                user-agents across retries.
            timeout: Request timeout in seconds.

        Returns:
            VerificationResult: Categorized verification outcome.
        """
        user_agent_index = max(attempt_count - 1, 0)
        return await cls._verify_single(
            url=url,
            timeout=timeout,
            user_agent_index=user_agent_index,
        )

    @classmethod
    async def verify_bulk(
        cls,
        urls: list[str],
        timeout: int = 8,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> dict[str, VerificationResult]:
        """Verify multiple URLs with intelligent retry logic.

        Args:
            urls: List of URLs to verify.
            timeout: Request timeout in seconds (default 8).
            max_retries: Number of retry attempts for 403/timeout (default 2).
            retry_delay: Delay between retries in seconds (default 1.0).

        Returns:
            Dict mapping URL to VerificationResult.

        Examples:
            >>> results = await SourceVerificationService.verify_bulk(
            ...     ["https://example.com", "https://blocked.gov"]
            ... )
            >>> results["https://blocked.gov"].status
            VerificationStatus.BLOCKED_BY_BOT_PROTECTION
        """
        results = {}

        for url in urls:
            result = await cls._verify_with_retries(
                url,
                timeout=timeout,
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
            results[url] = result
            logger.debug(f"Verified {url}: {result.status}")

        return results

    @classmethod
    async def _verify_with_retries(
        cls,
        url: str,
        timeout: int = 8,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> VerificationResult:
        """Try URL with exponential backoff on retryable errors (403, timeout).

        Args:
            url: URL to verify.
            timeout: Request timeout in seconds.
            max_retries: Number of retry attempts.
            retry_delay: Initial delay between retries in seconds.

        Returns:
            VerificationResult with status and optional retry recommendation.
        """
        result = None

        for attempt in range(max_retries + 1):
            result = await cls._verify_single(
                url,
                timeout,
                user_agent_index=attempt,
            )

            # Don't retry on permanent failures
            if result.status == VerificationStatus.UNVERIFIED_PERMANENT:
                return result

            # Retry on temporary failures (403, timeout, etc.)
            if result.status in (
                VerificationStatus.BLOCKED_BY_BOT_PROTECTION,
                VerificationStatus.TIMEOUT,
                VerificationStatus.UNVERIFIED_RETRYABLE,
            ):
                if attempt < max_retries:
                    backoff = retry_delay * (2**attempt)
                    logger.debug(
                        f"Retrying {url} after {backoff}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)
                    continue
                else:
                    # Mark as retryable after exhausting attempts
                    result.retry_recommended = True
                    return result

            # Success or other status - return as is
            return result

        return result or VerificationResult(
            status=VerificationStatus.UNREACHABLE,
            error_message="Verification attempts exhausted",
            user_message=(
                "Unable to verify this source after multiple attempts. We'll try again later."
            ),
        )

    @classmethod
    async def _verify_single(
        cls,
        url: str,
        timeout: int = 8,
        user_agent_index: int = 0,
    ) -> VerificationResult:
        """Single verification attempt with categorized response handling.

        Args:
            url: URL to verify.
            timeout: Request timeout in seconds.
            user_agent_index: Zero-based index used to rotate request headers.

        Returns:
            VerificationResult with specific status for decision making.

        Examples:
            >>> result = await SourceVerificationService._verify_single(
            ...     "https://blocked-site.gov"
            ... )
            >>> result.status
            VerificationStatus.BLOCKED_BY_BOT_PROTECTION
        """
        try:
            headers = {
                "User-Agent": cls.USER_AGENTS[user_agent_index % len(cls.USER_AGENTS)],
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    # Try HEAD first (faster, doesn't download content)
                    response = await client.head(url, headers=headers, follow_redirects=True)
                except httpx.RequestError:
                    # Some servers don't support HEAD, try GET
                    response = await client.get(
                        url, headers=headers, follow_redirects=True, timeout=timeout
                    )

                if response.status_code < 400:
                    # Success (2xx-3xx)
                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        http_status=response.status_code,
                    )
                elif response.status_code == 403:
                    # Forbidden - likely bot protection or geo-blocking
                    return VerificationResult(
                        status=VerificationStatus.BLOCKED_BY_BOT_PROTECTION,
                        http_status=403,
                        error_message=(
                            "HTTP 403 Forbidden (bot protection, geo-blocking, "
                            "or access restrictions)"
                        ),
                        user_message=(
                            "This source is temporarily blocked. We'll retry automatically."
                        ),
                        retry_recommended=True,
                    )
                elif response.status_code == 429:
                    # Rate limited
                    return VerificationResult(
                        status=VerificationStatus.BLOCKED_BY_BOT_PROTECTION,
                        http_status=429,
                        error_message="HTTP 429 Too Many Requests (rate limited)",
                        user_message=(
                            "This source is temporarily rate-limited. We'll retry automatically."
                        ),
                        retry_recommended=True,
                    )
                elif response.status_code >= 500:
                    # Server error - retryable
                    return VerificationResult(
                        status=VerificationStatus.UNVERIFIED_RETRYABLE,
                        http_status=response.status_code,
                        error_message=f"HTTP {response.status_code} Server Error",
                        user_message=(
                            "The source server is temporarily unavailable. "
                            "We'll retry automatically."
                        ),
                        retry_recommended=True,
                    )
                else:
                    # Other 4xx - permanent
                    return VerificationResult(
                        status=VerificationStatus.UNVERIFIED_PERMANENT,
                        http_status=response.status_code,
                        error_message=f"HTTP {response.status_code}",
                        user_message=(
                            "This source could not be accessed. Please verify the URL is correct."
                        ),
                    )

        except httpx.TimeoutException:
            # Timeout - retryable (network may be slow)
            return VerificationResult(
                status=VerificationStatus.TIMEOUT,
                error_message="Connection timeout (network may be slow)",
                user_message="Connection timed out. We'll retry with a longer timeout.",
                retry_recommended=True,
            )
        except httpx.ConnectError as e:
            # DNS or connection failure - check if permanent
            error_msg = str(e).lower()
            if (
                "name or service not known" in error_msg
                or "no address associated" in error_msg
                or "nodename nor servname provided" in error_msg
            ):
                # DNS failure - permanent
                logger.warning(f"DNS resolution failed for URL: {error_msg}")
                return VerificationResult(
                    status=VerificationStatus.UNVERIFIED_PERMANENT,
                    error_message=f"DNS resolution failed: {error_msg}",
                    user_message=(
                        "The domain name could not be found. Please verify the URL is correct."
                    ),
                )
            # Connection refused or other - could be temporary
            logger.warning(f"Connection error for URL: {error_msg}")
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED_RETRYABLE,
                error_message=f"Connection error: {error_msg}",
                user_message="Connection error occurred. We'll retry automatically.",
                retry_recommended=True,
            )
        except Exception as e:
            # Unexpected error - log internally, don't expose
            logger.error(f"Unexpected error during URL verification: {type(e).__name__}: {str(e)}")
            return VerificationResult(
                status=VerificationStatus.UNREACHABLE,
                error_message=f"{type(e).__name__}: {str(e)}",
                user_message="Unable to verify this source at this time. Please try again later.",
            )
