import asyncio
import logging
from typing import Any, Dict, Optional

import cloudscraper

from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


class HTTPClientService:
    """Tiered fetching service for web content.

    This service provides a two-tier approach to fetching web content:
    1. Fast Path: Uses Cloudscraper (Requests wrapper) for static content/PDFs.
    2. Slow Path: Falls back to Playwright for JS-heavy sites or strict bot protection.
    """

    def __init__(self):
        """Initialize the HTTPClientService.

        Sets up Cloudscraper with a desktop browser profile and initializes the PlaywrightService.

        Args:
            None

        Returns:
            None

        Raises:
            None

        Examples:
            >>> service = HTTPClientService()
        """
        # Initialize Cloudscraper with a desktop browser profile to look legit
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        self.browser = PlaywrightService()

    async def fetch_content(self, url: str, auth_creds: Optional[Dict[str, Any]] = None) -> bytes:
        """Fetch web content using a tiered approach.

        Attempts to fetch content efficiently via Cloudscraper,
        falling back to Playwright if needed.

        Args:
            url (str): The URL to fetch content from.
            auth_creds (Optional[Dict[str, Any]]): Optional auth credentials
                for Playwright fallback.

        Returns:
            bytes: The fetched content as bytes.

        Raises:
            RequestException: If the request fails in the fast path.
            ValueError: If suspicious content is detected in the fast path.
            Exception: For other errors during fetching.

        Examples:
            >>> content = await service.fetch_content('https://example.com')
            >>> print(len(content))
            1234
        """
        try:
            return await self._fetch_fast_path(url)
        except Exception as e:
            logger.warning(f"Fast path failed for {url}: {str(e)}. Escalating to Playwright.")
            return await self.browser.scrape(url, creds=auth_creds)

    async def _fetch_fast_path(self, url: str) -> bytes:
        """Fetch content using Cloudscraper in a separate thread.

        Executes the blocking Cloudscraper call asynchronously to avoid freezing the event loop.

        Args:
            url (str): The URL to fetch content from.

        Returns:
            bytes: The fetched content as bytes.

        Raises:
            RequestException: If the HTTP request fails.
            ValueError: If suspicious content (e.g., JS-wall) is detected.

        Examples:
            >>> content = await service._fetch_fast_path('https://example.com')
            >>> print(content[:10])
            b'<!DOCTYPE'
        """
        return await asyncio.to_thread(self._sync_request, url)

    def _sync_request(self, url: str) -> bytes:
        """Perform synchronous HTTP request using Cloudscraper.

        Makes a GET request with timeout and checks for suspicious content.

        Args:
            url (str): The URL to request.

        Returns:
            bytes: The response content as bytes.

        Raises:
            RequestException: If the request fails (e.g., timeout, bad status).
            ValueError: If the content appears to be a loading shell or JS-wall.

        Examples:
            >>> content = service._sync_request('https://example.com')
            >>> print(len(content))
            5678
        """

        response = self.scraper.get(url, timeout=15)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        content = response.content

        if "text/html" in content_type and len(content) < 800:
            text_sample = response.text.lower()
            suspicious_terms = ["javascript", "enable", "loading", "wait"]
            if any(term in text_sample for term in suspicious_terms):
                raise ValueError("Detected likely JS-wall or Loading shell")

        logger.info(f"Fast fetch successful: {url} ({content_type}) - {len(content)} bytes")
        return content
