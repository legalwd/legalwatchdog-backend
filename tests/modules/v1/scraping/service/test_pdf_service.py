"""
Unit tests for PDFService.

Tests PDF text extraction and detection logic.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.api.modules.v1.scraping.service.pdf_service import PDFService


@pytest.fixture
def service():
    """Fixture for PDFService instance."""
    return PDFService()


def test_extract_text_success(service):
    """Test successful text extraction from PDF."""
    mock_pdf = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Page 1 text"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Page 2 text"
    mock_pdf.pages = [mock_page1, mock_page2]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=None)

    with (
        patch(
            "app.api.modules.v1.scraping.service.pdf_service.pdfplumber.open", return_value=mock_pdf
        ),
        patch("tempfile.NamedTemporaryFile") as mock_temp,
    ):
        mock_temp.return_value.__enter__.return_value.write = MagicMock()
        mock_temp.return_value.__enter__.return_value.flush = MagicMock()
        mock_temp.return_value.__enter__.return_value.name = "/tmp/test.pdf"
        result = service.extract_text(b"%PDF test")
        assert result == "Page 1 text\n\nPage 2 text"


def test_extract_text_pdfplumber_not_installed(service):
    """Test error when pdfplumber is not available."""
    with patch("app.api.modules.v1.scraping.service.pdf_service.pdfplumber", None):
        with pytest.raises(ValueError, match="pdfplumber not installed"):
            service.extract_text(b"dummy")


def test_extract_text_extraction_failure(service):
    """Test handling of extraction errors."""
    with patch("pdfplumber.open", side_effect=Exception("Invalid PDF")):
        with pytest.raises(ValueError, match="extract text from this PDF"):
            service.extract_text(b"%PDF invalid")


def test_is_pdf_by_content_type(service):
    """Test PDF detection by content-type header."""
    assert service.is_pdf(b"dummy", "application/pdf") is True
    assert service.is_pdf(b"dummy", "text/html") is False


def test_is_pdf_by_magic_bytes(service):
    """Test PDF detection by magic bytes."""
    assert service.is_pdf(b"%PDF-1.4") is True
    assert service.is_pdf(b"Not PDF") is False
    assert service.is_pdf(b"") is False
