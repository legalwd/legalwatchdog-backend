"""
Unit tests for HTTPClientService.

Tests the tiered fetching logic, fast path with Cloudscraper, and fallback to Playwright.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.scraping.service.cloudscrapper_service import HTTPClientService


@pytest.fixture
def service():
    """Fixture for HTTPClientService instance."""
    return HTTPClientService()


@pytest.mark.asyncio
async def test_fetch_content_fast_path_success(service):
    """Test successful fast path fetching."""
    mock_content = b"<html>Test content</html>"
    with patch.object(service, "_fetch_fast_path", new_callable=AsyncMock) as mock_fast:
        mock_fast.return_value = mock_content
        result = await service.fetch_content("https://example.com")
        assert result == mock_content
        mock_fast.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_fetch_content_fallback_on_fast_path_failure(service):
    """Test fallback to Playwright when fast path fails."""
    mock_content = b"Playwright content"
    with (
        patch.object(service, "_fetch_fast_path", side_effect=Exception("JS-wall")),
        patch.object(service.browser, "scrape", new_callable=AsyncMock) as mock_scrape,
    ):
        mock_scrape.return_value = mock_content
        result = await service.fetch_content("https://example.com", auth_creds={"cookies": []})
        assert result == mock_content
        mock_scrape.assert_called_once_with("https://example.com", creds={"cookies": []})


@pytest.mark.asyncio
async def test_fetch_fast_path_calls_sync_request(service):
    """Test _fetch_fast_path calls _sync_request via asyncio.to_thread."""
    mock_content = b"Content"
    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.return_value = mock_content
        result = await service._fetch_fast_path("https://example.com")
        assert result == mock_content
        mock_to_thread.assert_called_once_with(service._sync_request, "https://example.com")


def test_sync_request_success(service):
    """Test successful synchronous request."""
    mock_response = MagicMock()
    mock_response.content = b"PDF content"
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.raise_for_status = MagicMock()
    mock_response.text = "Some text"

    with patch.object(service.scraper, "get", return_value=mock_response):
        result = service._sync_request("https://example.com")
        assert result == b"PDF content"


def test_sync_request_detects_js_wall(service):
    """Test detection of JS-wall in HTML content."""
    mock_response = MagicMock()
    mock_response.content = b"<html>Enable JavaScript</html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_response.raise_for_status = MagicMock()
    mock_response.text = "enable javascript loading"

    with patch.object(service.scraper, "get", return_value=mock_response):
        with pytest.raises(ValueError, match="Detected likely JS-wall"):
            service._sync_request("https://example.com")


def test_sync_request_timeout_or_error(service):
    """Test handling of request exceptions."""
    with patch.object(service.scraper, "get", side_effect=Exception("Timeout")):
        with pytest.raises(Exception):
            service._sync_request("https://example.com")
