"""
Mock ExtractorService Tests

This module contains unit tests for the TextExtractorService class, which is responsible for
extracting text from raw content (HTML, etc.), cleaning it, and managing MinIO uploads.
It mocks the MinIO interactions to avoid external dependencies during testing.
"""

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.api.modules.v1.scraping.service.extractor_service import (
    TextExtractorService,
)


@pytest.mark.asyncio
async def test_extract_from_minio_success():
    """Test that extract_from_minio extracts text from HTML content."""
    service = TextExtractorService()
    fake_html = b"<html><body><p>Hello world</p></body></html>"

    with patch.object(service, "_fetch_bytes_sync", return_value=fake_html):
        result = await service.extract_from_minio("bucket", "file.html")

    assert "Hello world" in result


@pytest.mark.asyncio
async def test_extract_from_minio_empty():
    """Test that extract_from_minio returns empty string for empty content."""
    service = TextExtractorService()

    with patch.object(service, "_fetch_bytes_sync", return_value=b""):
        result = await service.extract_from_minio("bucket", "file.html")

    assert result == ""


@pytest.mark.asyncio
async def test_process_pipeline_success():
    """Test the main process_pipeline method for full extraction and upload."""
    service = TextExtractorService()
    fake_html = (
        b"<html><body><p>Hello world! This is a longer text to ensure "
        b"extraction works properly.</p></body></html>"
    )
    source_id = "source-123"
    revision_id = uuid4()

    with (
        patch.object(service, "_upload_bytes_sync", return_value="raw.html"),
        patch.object(service, "_fetch_bytes_sync", return_value=fake_html),
    ):
        result = await service.process_pipeline_markdown(
            raw_content=fake_html,
            raw_bucket="raw-bucket",
            raw_key="test.html",
            clean_bucket="clean-bucket",
            source_id=source_id,
            revision_id=revision_id,
        )

    assert "Hello world" in result["markdown_content"]
    assert result["raw_key"] == "test.html"
    assert "markdown/" in result["markdown_key"]
    assert result["revision_id"] == str(revision_id)
    assert result["char_count"] > 0


@pytest.mark.asyncio
async def test_process_pipeline_upload_failure():
    """Test that process_pipeline handles upload failures gracefully."""
    service = TextExtractorService()
    fake_html = b"<html><body><p>Test</p></body></html>"
    source_id = "source-123"

    with patch.object(service, "_upload_bytes_sync", side_effect=Exception("MinIO error")):
        with pytest.raises(Exception, match="MinIO error"):
            await service.process_pipeline_markdown(
                raw_content=fake_html,
                raw_bucket="raw-bucket",
                raw_key="test.html",
                clean_bucket="clean-bucket",
                source_id=source_id,
            )


@pytest.mark.asyncio
async def test_process_pipeline_empty_content():
    """Test that process_pipeline handles empty content appropriately."""
    service = TextExtractorService()
    source_id = "source-123"

    with patch.object(service, "_upload_bytes_sync", return_value="raw.html"):
        result = await service.process_pipeline_markdown(
            raw_content=b"      ",
            raw_bucket="raw-bucket",
            raw_key="test.html",
            clean_bucket="clean-bucket",
            source_id=source_id,
        )

    # Empty content should still process without errors
    assert result["markdown_content"] == ""
    assert result["char_count"] == 0


def test_generate_clean_key():
    """Test that _generate_clean_key generates proper MinIO keys."""
    service = TextExtractorService()
    source_id = "source-123"
    revision_id = uuid4()

    key = service._generate_markdown_key(source_id, revision_id)

    assert key.startswith(f"markdown/{source_id}/")
    assert key.endswith(f"{revision_id}.md")
    assert len(key.split("/")) == 3
