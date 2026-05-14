import logging
import tempfile
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger(__name__)


class PDFService:
    """
    Service for extracting text content from PDF files.
    Handles PDF processing logic separately from scraping concerns.
    """

    def __init__(self):
        if pdfplumber is None:
            logger.warning("pdfplumber not installed. PDF extraction will not be available.")

    def extract_text(self, pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes using pdfplumber.

        Args:
            pdf_bytes: Raw PDF content as bytes

        Returns:
            Extracted text from all PDF pages joined together

        Raises:
            ValueError: If pdfplumber not installed or PDF is invalid
        """
        if pdfplumber is None:
            raise ValueError("pdfplumber not installed. Install with: pip install pdfplumber")

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                tmp_path = tmp.name

            extracted_text = []
            with pdfplumber.open(tmp_path) as pdf:
                logger.info(f"PDF has {len(pdf.pages)} pages")
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        extracted_text.append(text)
                    logger.debug(f"  Page {page_num}: {len(text)} chars extracted")

            return "\n\n".join(extracted_text)
        except Exception as e:
            logger.error(f"PDF extraction failed: {type(e).__name__}: {e}", exc_info=True)
            raise ValueError(
                "We couldn't extract text from this PDF file. "
                "The file might be corrupted or password-protected."
            )

    def is_pdf(self, content: bytes, content_type: Optional[str] = None) -> bool:
        """
        Determine if content is a PDF based on content-type header or magic bytes.

        Args:
            content: Raw content bytes
            content_type: Content-Type header value

        Returns:
            True if content appears to be PDF
        """
        if content_type and "pdf" in content_type.lower():
            return True

        if len(content) >= 4 and content[:4] == b"%PDF":
            return True

        return False
