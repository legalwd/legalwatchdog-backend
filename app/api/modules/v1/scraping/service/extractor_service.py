"""
Text Extractor Service.

This module provides the TextExtractorService class, which handles the extraction of text
from raw content (HTML, PDF, etc.). It manages the entire pipeline of uploading raw content
to MinIO, cleaning the content to extract meaningful text, and uploading the cleaned text
back to MinIO. It supports fallback mechanisms using readability-lxml if primary extraction fails.
"""

import io
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool
from markdownify import markdownify as md
from readability import Document

from app.api.core.config import settings
from app.api.utils.cleaned_text import cleaned_html, normalize_text

try:
    from bs4 import BeautifulSoup, Comment

    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    _HAS_BS4 = False

try:
    from minio import Minio
    from minio.error import S3Error

    _HAS_MINIO = True
except ImportError:
    Minio = None
    S3Error = Exception
    _HAS_MINIO = False

logger = logging.getLogger(__name__)
EXTRACTOR_VERSION = "1.4.0"


class TextExtractorService:
    """
    Unified service for storage and text extraction.

    Responsibilities:
    1. Uploading Raw Content (HTML/PDF bytes) to MinIO.
    2. Extracting & Cleaning Text from those bytes.
    3. Uploading Cleaned Text to MinIO.
    4. Returning the clean text for AI processing.
    """

    def __init__(self):
        self.minio_client = self._init_minio_client()

    def _init_minio_client(self) -> Optional[Any]:
        """Initialize MinIO client based on settings."""
        if not _HAS_MINIO:
            logger.warning("MinIO SDK not installed.")
            return None

        try:
            client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            return client
        except Exception as e:
            logger.critical(f"Failed to initialize MinIO client: {e}")
            return None

    # --- Core MinIO Operations (Internal Sync methods for Threadpool) ---

    def _upload_bytes_sync(self, file_data: bytes, bucket_name: str, object_name: str) -> str:
        """Blocking upload method to be run in threadpool."""
        if not self.minio_client:
            raise Exception("MinIO client not available.")

        try:
            # Check/Create Bucket (Idempotent-ish)
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)
        except Exception as e:
            # Ignore harmless race conditions on bucket creation or permission warnings
            logger.warning(f"Bucket check/create warning for '{bucket_name}': {e}")

        # Upload
        try:
            data_stream = io.BytesIO(file_data)
            self.minio_client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=len(file_data),
                content_type="application/octet-stream",
            )
            return object_name
        except Exception as e:
            logger.error(f"MinIO Upload Error ({bucket_name}/{object_name}): {e}")
            raise e

    def _fetch_bytes_sync(self, bucket_name: str, object_name: str) -> Optional[bytes]:
        """Blocking fetch method."""
        if not self.minio_client:
            return None
        try:
            response = self.minio_client.get_object(bucket_name, object_name)
            content = response.read()
            response.close()
            return content
        except Exception as e:
            logger.error(f"MinIO Fetch Error: {e}")
            return None

    # --- Pipeline Methods ---

    async def process_pipeline(
        self,
        raw_content: bytes,
        raw_bucket: str,
        raw_key: str,
        clean_bucket: str,
        source_id: str,
        revision_id: UUID = None,
    ) -> Dict[str, Any]:
        """
        Master method for the Scraping Pipeline.

        Steps:
        1. Upload Raw Content to MinIO (Raw Bucket).
        2. Clean Content (Bytes -> Clean String).
        3. Upload Clean Content to MinIO (Clean Bucket).
        4. Return Full Text and Metadata for the AI Service.

        Args:
            raw_content (bytes): The raw HTML or PDF bytes.
            raw_bucket (str): Bucket name for raw files.
            raw_key (str): Object key for the raw file.
            clean_bucket (str): Bucket name for cleaned text files.
            source_id (str): ID of the source (for file naming).
            revision_id (UUID, optional): ID of the revision.

        Returns:
            Dict: Contains 'full_text', 'raw_key', 'clean_key', 'revision_id'.
        """
        revision_id = revision_id or uuid4()

        try:
            await run_in_threadpool(self._upload_bytes_sync, raw_content, raw_bucket, raw_key)
        except Exception as e:
            logger.error(f"Failed to upload raw content: {e}")
            raise e

        try:
            extracted_text = cleaned_html(raw_content)

            if len(extracted_text) < 50:
                try:
                    html_str = raw_content.decode("utf-8", errors="ignore")
                    extracted_text = normalize_text(Document(html_str).summary(html=False))
                except Exception:
                    pass

            extracted_text = normalize_text(extracted_text)

        except Exception as fallback_err:
            logger.error(f"All extraction methods failed: {fallback_err}")
            raise

        clean_key = self._generate_clean_key(source_id, revision_id)
        if extracted_text:
            try:
                await run_in_threadpool(
                    self._upload_bytes_sync, extracted_text.encode("utf-8"), clean_bucket, clean_key
                )
                logger.info(f"Uploaded markdown to {clean_bucket}/{clean_key}")
            except Exception as e:
                logger.warning(f"Failed to upload clean text (non-fatal): {e}")

            return {
                "full_text": extracted_text,
                "raw_key": raw_key,
                "clean_key": clean_key,
                "revision_id": str(revision_id),
                "char_count": len(extracted_text),
            }

    async def process_pipeline_markdown(
        self,
        raw_content: bytes,
        raw_bucket: str,
        raw_key: str,
        clean_bucket: str,
        source_id: str,
        revision_id: UUID = None,
    ) -> Dict[str, Any]:
        """
        Pipeline optimized for human-readable documents.
        Converts HTML to structured markdown for frontend display.

        Args:
            raw_content (bytes): Raw HTML content
            raw_bucket (str): Bucket for raw HTML storage
            raw_key (str): Object key for raw HTML
            markdown_bucket (str): Bucket for markdown storage
            source_id (str): Source identifier
            revision_id (UUID, optional): Revision ID

        Returns:
            Dict: Contains 'markdown_content', 'raw_key', 'markdown_key',
              'revision_id', 'char_count'
        """
        revision_id = revision_id or uuid4()

        try:
            await run_in_threadpool(self._upload_bytes_sync, raw_content, raw_bucket, raw_key)
            logger.info(f"Uploaded raw HTML to {raw_bucket}/{raw_key}")
        except Exception as e:
            logger.error(f"Failed to upload raw content: {e}")
            raise e

        try:
            markdown_text = await self._html_to_markdown(raw_content)
        except Exception as e:
            logger.warning(f"Markdown conversion failed: {e}, falling back to plain text")
            markdown_text = cleaned_html(raw_content)

        markdown_key = self._generate_markdown_key(source_id, revision_id)
        if markdown_text:
            await run_in_threadpool(
                self._upload_bytes_sync, markdown_text.encode("utf-8"), clean_bucket, markdown_key
            )

        return {
            "markdown_content": markdown_text,
            "raw_key": raw_key,
            "markdown_key": markdown_key,
            "revision_id": str(revision_id),
            "char_count": len(markdown_text),
            "content_type": "markdown",
        }

    async def _html_to_markdown(self, html_bytes: bytes) -> str:
        """
        Convert HTML bytes to clean markdown format.

        Args:
            html_bytes: Raw HTML content

        Returns:
            str: Cleaned markdown text
        """
        html_str = html_bytes.decode("utf-8", errors="ignore")

        if _HAS_BS4:
            soup = BeautifulSoup(html_str, "html.parser")

            for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
                element.decompose()

            for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
                comment.extract()

            html_str = str(soup)

        markdown_text = md(
            html_str,
            heading_style="ATX",
            bullets="-",
            code_language="",
            strip=["script", "style"],
            escape_asterisks=False,
            escape_underscores=False,
        )

        lines = []
        for line in markdown_text.split("\n"):
            line = line.rstrip()
            lines.append(line)

        markdown_text = "\n".join(lines)

        markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text)

        markdown_text = normalize_text(markdown_text)

        return markdown_text

    def _generate_clean_key(self, source_id: str, revision_id: UUID) -> str:
        """Generates a standard key for cleaned text files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"clean/{source_id}/{timestamp}_{revision_id}.txt"

    def _generate_markdown_key(self, source_id: str, revision_id: UUID) -> str:
        """Generates a standard key for markdown files."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"markdown/{source_id}/{timestamp}_{revision_id}.md"

    async def extract_from_minio(self, bucket: str, object_name: str) -> str:
        """Fetch raw HTML from MinIO and return cleaned string (Legacy support)."""
        html_bytes = await run_in_threadpool(self._fetch_bytes_sync, bucket, object_name)

        if not html_bytes or len(html_bytes.strip()) < 20:
            return ""

        extracted = cleaned_html(html_bytes)
        return normalize_text(extracted)
