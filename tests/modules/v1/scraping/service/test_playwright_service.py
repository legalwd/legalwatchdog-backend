"""
Unit tests for PlaywrightService.

Tests web scraping with Playwright, including downloads and auth.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.scraping.service.playwright_service import PlaywrightService


@pytest.fixture
def service():
    """Fixture for PlaywrightService instance."""
    return PlaywrightService()


@pytest.mark.asyncio
async def test_scrape_successful_content(service):
    """Test successful scraping of page content."""
    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value="<html>Content</html>")
    mock_page.wait_for_function = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    with patch(
        "app.api.modules.v1.scraping.service.playwright_service.async_playwright"
    ) as mock_pw:
        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__.return_value = mock_p
        result = await service.scrape("https://example.com")
        assert result == b"<html>Content</html>"


@pytest.mark.asyncio
async def test_scrape_with_download(service):
    """Test scraping when a download is triggered."""
    mock_download = MagicMock()
    mock_download.path = AsyncMock(return_value="/path/to/file")
    mock_download.suggested_filename = "test.pdf"

    mock_page = MagicMock()
    mock_page.goto = AsyncMock(side_effect=Exception("Download is starting"))
    mock_page.on = MagicMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.add_cookies = AsyncMock()
    mock_context.close = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_future = MagicMock()
    mock_future.done = MagicMock(return_value=True)
    mock_future.result = MagicMock(return_value=mock_download)

    with (
        patch("app.api.modules.v1.scraping.service.playwright_service.async_playwright") as mock_pw,
        patch.object(service, "_handle_download_stream", new_callable=AsyncMock) as mock_handle,
        patch("asyncio.Future", return_value=mock_future),
    ):
        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__.return_value = mock_p
        mock_handle.return_value = b"Downloaded content"
        result = await service.scrape("https://example.com", creds={"cookies": []})
        assert result == b"Downloaded content"


@pytest.mark.asyncio
async def test_scrape_with_auth_cookies(service):
    """Test scraping with authentication cookies."""
    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value="<html>Auth content</html>")
    mock_page.wait_for_function = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.add_cookies = AsyncMock()
    mock_context.close = AsyncMock()
    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    with patch(
        "app.api.modules.v1.scraping.service.playwright_service.async_playwright"
    ) as mock_pw:
        mock_p = MagicMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__.return_value = mock_p
        result = await service.scrape(
            "https://example.com",
            creds={"cookies": [{"name": "session", "value": "abc", "url": "https://example.com"}]},
        )
        mock_context.add_cookies.assert_called_once_with(
            [{"name": "session", "value": "abc", "url": "https://example.com"}]
        )
        assert result == b"<html>Auth content</html>"


@pytest.mark.asyncio
async def test_handle_download_stream_success(service):
    """Test successful download handling."""
    mock_download = MagicMock()
    mock_download.path = AsyncMock(return_value="/tmp/test.pdf")
    mock_download.suggested_filename = "test.pdf"

    with patch("builtins.open", MagicMock()) as mock_open:
        mock_file = MagicMock()
        mock_file.read.return_value = b"File content"
        mock_open.return_value.__enter__.return_value = mock_file
        result = await service._handle_download_stream(mock_download)
        assert result == b"File content"


@pytest.mark.asyncio
async def test_handle_download_stream_failure(service):
    """Test download handling failure."""
    mock_download = MagicMock()
    mock_download.path = AsyncMock(return_value=None)

    with pytest.raises(Exception, match="Download failed"):
        await service._handle_download_stream(mock_download)
