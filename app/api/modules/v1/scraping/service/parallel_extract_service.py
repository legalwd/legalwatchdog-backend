"""Service for extracting web content using Parallel.ai Extract API.

Handles web page and PDF extraction, returning clean markdown content
suitable for AI processing and UI display.
"""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

import httpx
import redis
from parallel import Parallel
from sqlmodel import Session

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    EmptyContentError,
    ParallelExtractionError,
    ParallelRateLimitError,
)
from app.api.db.models.parallel_usage import ParallelUsageLog
from app.api.modules.v1.scraping.storage.minio_storage import upload_raw_content

logger = logging.getLogger(__name__)


class ParallelExtractService:
    """Extracts clean markdown content from URLs using Parallel.ai.

    Parallel.ai Extract API handles JavaScript-heavy pages and PDFs automatically,
    returning LLM-ready markdown without requiring complex extraction pipelines.

    Architecture:
    URL → Parallel.ai Extract → Clean Markdown → MinIO Storage

    Enterprise Features:
    - Distributed rate limiting with Redis
    - Connection pooling and resource reuse
    - Graceful async/sync bridging for Celery workers
    - Comprehensive usage logging for billing/monitoring
    - Automatic retry with exponential backoff
    """

    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the ParallelExtractService with Parallel.ai client.

        Sets up Parallel.ai client with retry configuration, Redis for distributed
        rate limiting across Celery workers, and MinIO for content storage.

        Configures httpx client with cache-busting headers to ensure fresh content
        extraction and prevent stale cached results from being returned.

        Args:
            db_session: Optional database session for usage logging.

        Raises:
            ValueError: If PARALLEL_API_KEY is not set in configuration.
        """
        self.db_session = db_session
        if not settings.PARALLEL_API_KEY:
            raise ValueError("PARALLEL_API_KEY is not set in configuration.")

        cache_busting_headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        http_client = httpx.Client(
            timeout=60.0,
            headers=cache_busting_headers,
            follow_redirects=True,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        )
        self.parallel = Parallel(
            api_key=settings.PARALLEL_API_KEY,
            http_client=http_client,
            max_retries=2,
        )
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        self.rate_limit_key = "parallel_ai:extract:requests"
        self.max_requests_per_minute = 600
        self.rate_limit_window = 60

    def _check_rate_limit(self) -> Dict[str, any]:
        """Check if request is within rate limit using Redis sliding window.

        Implements distributed rate limiting across multiple Celery workers.
        Uses sorted sets to track requests with timestamps and removes expired entries.

        Returns:
            Dict containing:
                - allowed: Whether request is within limit
                - current_count: Current requests in window
                - limit: Maximum requests allowed
                - remaining: Remaining requests in window

        Examples:
            >>> status = await self._check_rate_limit()
            >>> if not status['allowed']:
            >>>     raise ParallelRateLimitError("Rate limit exceeded")
        """
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self.rate_limit_window

        try:
            self.redis_client.zremrangebyscore(
                self.rate_limit_key,
                0,
                window_start,
            )
            count = self.redis_client.zcard(self.rate_limit_key)

            if count >= self.max_requests_per_minute:
                logger.warning(
                    f"Parallel.ai rate limit exceeded: "
                    f"{count}/{self.max_requests_per_minute} "
                    f"requests in last {self.rate_limit_window}s"
                )
                return {
                    "allowed": False,
                    "current_count": count,
                    "limit": self.max_requests_per_minute,
                    "remaining": 0,
                }

            self.redis_client.zadd(
                self.rate_limit_key,
                {str(now): now},
            )
            self.redis_client.expire(
                self.rate_limit_key,
                self.rate_limit_window * 2,
            )
            current_count = count + 1
            remaining = self.max_requests_per_minute - current_count
            return {
                "allowed": True,
                "current_count": current_count,
                "limit": self.max_requests_per_minute,
                "remaining": remaining,
            }

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}. Allowing request.")
            return {
                "allowed": True,
                "current_count": 0,
                "limit": self.max_requests_per_minute,
                "remaining": self.max_requests_per_minute,
            }

    def _add_cache_buster(self, url: str) -> str:
        """Add timestamp query parameter to URL for cache busting.

        Appends a _cache_bust parameter with current timestamp to force
        CDN and intermediate caches to fetch fresh content.

        Args:
            url: The original URL

        Returns:
            str: URL with cache-busting parameter added

        Examples:
            >>> service._add_cache_buster("https://example.com/page")
            'https://example.com/page?_cache_bust=1702820400'
            >>> service._add_cache_buster("https://example.com/page?foo=bar")
            'https://example.com/page?foo=bar&_cache_bust=1702820400'
        """
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        timestamp = int(datetime.now(timezone.utc).timestamp())
        query_params["_cache_bust"] = [str(timestamp)]

        new_query = urlencode(query_params, doseq=True)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )

    def _log_usage(
        self,
        user_id: Optional[UUID],
        organization_id: Optional[UUID],
        project_id: Optional[UUID],
        url: str,
        endpoint_name: str,
        success: bool,
        latency_ms: int,
        content_size_bytes: int = 0,
        cost: Decimal = Decimal("0"),
        error_message: Optional[str] = None,
    ) -> None:
        """Log Parallel.ai usage to database for monitoring and billing.

        Creates a usage log entry tracking extraction requests, costs,
        performance, and errors for admin dashboard visibility.

        Args:
            user_id: User who initiated the extraction.
            organization_id: Organization context (if applicable).
            project_id: Project context for cost attribution (if applicable).
            url: Target URL that was extracted.
            endpoint_name: API endpoint that triggered extraction.
            success: Whether extraction succeeded.
            latency_ms: Request latency in milliseconds.
            content_size_bytes: Size of extracted content.
            cost: Estimated API cost in USD.
            error_message: Error details if extraction failed.

        Examples:
            >>> await service._log_usage(
            ...     user_id=user.id,
            ...     organization_id=org.id,
            ...     project_id=project.id,
            ...     url="https://example.com",
            ...     endpoint_name="scrape_source",
            ...     success=True,
            ...     latency_ms=1200,
            ...     content_size_bytes=15000,
            ...     cost=Decimal("0.001")
            ... )
        """
        if not self.db_session:
            logger.warning("Database session not provided, skipping usage logging")
            return

        try:
            usage_log = ParallelUsageLog(
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                url_extracted=url[:2048],
                endpoint_name=endpoint_name,
                success=success,
                cost=cost,
                latency_ms=latency_ms,
                content_size_bytes=content_size_bytes,
                error_message=error_message[:1000] if error_message else None,
            )
            self.db_session.add(usage_log)
            self.db_session.commit()
            logger.debug(
                f"Logged Parallel.ai usage: {endpoint_name} - "
                f"{'success' if success else 'failure'} - {url}"
            )
        except Exception as e:
            logger.error(f"Failed to log Parallel.ai usage: {e}")
            self.db_session.rollback()

    def extract_and_save(
        self,
        url: str,
        clean_bucket: str,
        clean_key: str,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
        endpoint_name: str = "extract",
        objective: Optional[str] = None,
    ) -> Dict[str, str]:
        """Extract content from URL and save to MinIO.

        Implements distributed rate limiting, graceful 429 error handling,
        and comprehensive metrics logging for monitoring.

        Args:
            url: The URL to extract content from.
            clean_bucket: MinIO bucket name for clean content storage.
            clean_key: Object key for the clean markdown file.
            user_id: User initiating the extraction (for usage tracking).
            organization_id: Organization context (for usage tracking).
            project_id: Project context for cost attribution (for usage tracking).
            endpoint_name: API endpoint triggering extraction (for usage tracking).
            objective: Optional natural language objective to focus extraction.

        Returns:
            Dict containing:
                - full_text: The extracted markdown content
                - clean_key: MinIO object key where content was saved
                - title: Page title (if available)
                - source: "parallel"
                - rate_limit_remaining: Requests remaining in window

        Raises:
            ParallelRateLimitError: If rate limit is exceeded (local or 429).
            ParallelExtractionError: If extraction fails or returns no content.
        """
        start_time = time.time()
        rate_limit_status = self._check_rate_limit()

        if not rate_limit_status["allowed"]:
            raise ParallelRateLimitError(
                f"Rate limit exceeded: "
                f"{rate_limit_status['current_count']}/{rate_limit_status['limit']} "
                f"requests in last {self.rate_limit_window}s"
            )

        logger.info(
            f"Parallel.ai Extract: "
            f"{rate_limit_status['current_count']}/{rate_limit_status['limit']} "
            f"({rate_limit_status['remaining']} remaining) - Extracting from {url}"
        )

        cache_bust_url = self._add_cache_buster(url)
        if cache_bust_url != url:
            logger.debug(f"Cache-busting URL: {cache_bust_url}")

        try:
            result = self.parallel.beta.extract(
                urls=[cache_bust_url],
                objective=objective,
                full_content=True,
                excerpts=False,
            )

            if not result.results or len(result.results) == 0:
                logger.warning(
                    f"Parallel.ai returned 0 results for URL: {url}, "
                    f"objective: '{objective}' "
                    f"(likely anti-bot blocking or page structure mismatch)"
                )
                raise EmptyContentError(
                    f"Parallel AI returned no content for {url}. "
                    f"The site may be blocking automated access or the page is empty."
                ) from None

            extracted = result.results[0]

            if not extracted.full_content:
                logger.warning(
                    f"Parallel.ai returned empty full_content for URL: {url}, "
                    f"title: '{extracted.title}' (page may be blocked or JavaScript-rendered)"
                )
                raise EmptyContentError(
                    f"Parallel AI returned no extractable content for {url}. "
                    f"The site may be blocking automated access."
                ) from None

            markdown_content = extracted.full_content

            upload_raw_content(
                file_data=markdown_content.encode("utf-8"),
                bucket_name=clean_bucket,
                object_name=clean_key,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            content_size = len(markdown_content.encode("utf-8"))
            estimated_cost = Decimal("0.001")

            self._log_usage(
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                url=url,
                endpoint_name=endpoint_name,
                success=True,
                latency_ms=latency_ms,
                content_size_bytes=content_size,
                cost=estimated_cost,
            )

            logger.info(
                f"Successfully extracted {len(markdown_content)} chars from {url}, "
                f"saved to {clean_bucket}/{clean_key}"
            )

            return {
                "full_text": markdown_content,
                "clean_key": clean_key,
                "title": extracted.title or "Untitled",
                "source": "parallel",
                "rate_limit_remaining": rate_limit_status["remaining"],
            }

        except EmptyContentError:
            raise

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_str = str(e).lower()

            self._log_usage(
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                url=url,
                endpoint_name=endpoint_name,
                success=False,
                latency_ms=latency_ms,
                content_size_bytes=0,
                cost=Decimal("0"),
                error_message=str(e),
            )

            if "429" in str(e) or "rate limit" in error_str or "ratelimit" in error_str:
                logger.error(f"Parallel.ai API rate limit error (429) for {url}: {e}")
                raise ParallelRateLimitError(
                    "Parallel AI rate limit exceeded. Try again later."
                ) from e

            if "timeout" in error_str or "timed out" in error_str:
                logger.error(f"Parallel.ai timeout error for {url}: {e}")
                raise ParallelExtractionError(
                    "Parallel AI extraction timed out. Please try again later."
                ) from e

            if "401" in str(e) or "authentication" in error_str or "unauthorized" in error_str:
                logger.error(f"Parallel.ai authentication error for {url}: {e}")
                raise ParallelExtractionError(
                    "Parallel AI authentication failed. Contact administrator."
                ) from e

            logger.error(f"Parallel.ai extraction failed for {url}: {e}")
            raise ParallelExtractionError(
                "Parallel AI extraction failed. Please try again later."
            ) from e

    def close(self) -> None:
        """Close HTTP client and Redis connections.

        Should be called when service is no longer needed to properly release resources.

        Examples:
            >>> service = ParallelExtractService()
            >>> try:
            >>>     result = service.extract_and_save(...)
            >>> finally:
            >>>     service.close()
        """
        if hasattr(self.parallel, "_http_client"):
            self.parallel._http_client.close()
        self.redis_client.close()
