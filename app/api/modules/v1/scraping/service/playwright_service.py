import asyncio
import logging
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class PlaywrightService:
    """Wrapper for Playwright.

    This class provides a service for web scraping using Playwright, handling
    automatic PDF detection, SPA hydration waits, basic bot evasion techniques,
    and resource cleanup.
    """

    BROWSER_ARGS = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
        "--disable-blink-features=AutomationControlled",
    ]

    async def scrape(self, url: str, creds: Optional[Dict[str, Any]] = None) -> bytes:
        logger.info(f"Starting scrape for URL: {url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=self.BROWSER_ARGS)
            logger.info("Browser launched successfully.")

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                accept_downloads=True,
                viewport={"width": 1920, "height": 1080},
            )

            if creds and "cookies" in creds:
                await context.add_cookies(creds["cookies"])
                logger.info("Auth cookies injected.")

            page = await context.new_page()
            logger.info("Browser context and page created.")

            download_future = asyncio.Future()

            def on_download(download):
                if not download_future.done():
                    download_future.set_result(download)

            page.on("download", on_download)

            try:
                logger.info(f"Navigating to: {url}")

                try:
                    goto_task = asyncio.create_task(
                        page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    )

                    done, pending = await asyncio.wait(
                        [goto_task, download_future], return_when=asyncio.FIRST_COMPLETED
                    )

                    if download_future in done:
                        logger.info("Download detected immediately.")
                        download = download_future.result()
                        return await self._handle_download_stream(download)

                    await goto_task
                    logger.info("Page navigation completed.")
                    if download_future.done():
                        return await self._handle_download_stream(download_future.result())

                    logger.info("Waiting for page content to load.")
                    try:
                        await page.wait_for_function(
                            "document.body.innerText.length > 0", timeout=5000
                        )
                    except Exception:
                        logger.warning("Page body appears empty or timed out waiting for text.")

                    content = await page.content()
                    logger.info(f"Content extracted, length: {len(content)}")
                    return content.encode("utf-8")

                except Exception as e:
                    if "Download is starting" in str(e) or download_future.done():
                        logger.info("Navigation cancelled by download.")
                        download = await download_future
                        return await self._handle_download_stream(download)
                    raise e

            except Exception as e:
                logger.error(f"Scrape failed for {url}: {str(e)}")
                raise e
            finally:
                await context.close()
                await browser.close()
                logger.info("Browser resources cleaned up.")

    async def _handle_download_stream(self, download) -> bytes:
        """Helper to stream download to memory without temp files if possible.

        This method waits for a Playwright download to complete, reads the
        downloaded file into memory as bytes, and returns it. It avoids using
        temporary files by directly reading from the download path.

        Args:
            download (playwright.async_api.Download): The Playwright download
                object representing the file being downloaded.

        Returns:
            bytes: The content of the downloaded file as a byte string.

        Raises:
            Exception: If the download fails, is cancelled, or the file cannot
                be read.

        Examples:
            >>> # Assuming a download object from Playwright
            >>> data = await service._handle_download_stream(download)
            >>> print(len(data))
            1024
        """
        logger.info("Handling download stream.")
        try:
            path = await download.path()
            if not path:
                raise Exception("Download failed or was cancelled")

            #
            with open(path, "rb") as f:
                data = f.read()

            logger.info(f"Downloaded file: {download.suggested_filename} ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.error(f"Failed to process download: {e}")
            raise e
