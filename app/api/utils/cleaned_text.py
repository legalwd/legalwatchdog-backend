import logging
import re

try:
    from bs4 import BeautifulSoup, Comment

    _HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    _HAS_BS4 = False


logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize a text string by collapsing and cleaning whitespace.

    This function:
    - Collapses multiple whitespace characters (spaces, tabs, newlines) into a single space.
    - Replaces non-breaking spaces (\\xa0) with regular spaces.
    - Strips leading and trailing whitespace.

    Args:
        text (str): The input text to normalize. Can be empty or None-like.

    Returns:
        str: A clean, whitespace-normalized string. Returns an empty
        string if the input is falsy.
    """

    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    return text.strip()


def cleaned_html(raw_bytes: bytes) -> str:
    """
    Clean raw HTML bytes and extract readable text content.

    This function:
    - Decodes raw HTML bytes (UTF-8 with fallback to Latin-1).
    - Parses the HTML using BeautifulSoup.
    - Removes junk elements such as:
        * <script>, <style>, <meta>, <header>, <footer>, <nav>, forms, SVG, ads
    - Removes HTML comments.
    - Removes elements whose IDs or classes contain keywords like:
      "cookie", "banner", "popup", "ads", "tracking", "newsletter", etc.
    - Extracts only meaningful visible text.
    - Normalizes whitespace using `normalize_text`.

    Args:
        raw_bytes (bytes): Raw HTML content to clean and extract text from.
            Passing empty bytes returns an empty string.

    Returns:
        str: Cleaned, human-readable text extracted from the HTML. Returns an
        empty string if BeautifulSoup is not installed or if processing fails.
    """
    if not raw_bytes:
        return ""

    if not _HAS_BS4:
        logger.error(
            "BeautifulSoup is not installed. Install `beautifulsoup4` to enable HTML cleaning."
        )
        return ""

    try:
        try:
            html_str = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            html_str = raw_bytes.decode("latin-1", errors="replace")

        soup = BeautifulSoup(html_str, "html.parser")

        junk_tags = [
            "script",
            "style",
            "meta",
            "noscript",
            "header",
            "footer",
            "nav",
            "iframe",
            "svg",
            "path",
            "link",
            "button",
            "input",
            "form",
            "select",
            "option",
            "aside",
            "ad",
            "banner",
        ]
        for tag_name in junk_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()

        junk_keywords = [
            "cookie",
            "popup",
            "modal",
            "banner",
            "footer",
            "header",
            "ads",
            "tracking",
            "subscribe",
            "newsletter",
            "consent",
        ]
        pattern = re.compile("|".join(junk_keywords), re.IGNORECASE)

        elements_to_remove = []
        for element in soup.find_all(True):
            if not hasattr(element, "get"):
                continue
            elem_id = element.get("id", "")
            elem_class = " ".join(element.get("class", []))
            if pattern.search(elem_id) or pattern.search(elem_class):
                elements_to_remove.append(element)

        for element in elements_to_remove:
            element.decompose()

        lines = [
            normalize_text(line)
            for line in soup.get_text(separator="\n").splitlines()
            if line.strip()
        ]
        readable_text = "\n".join(lines)

        if len(readable_text) < 50:
            logger.warning(
                "Extracted text is very short (<50 chars). Source content may be blocked."
            )

        return readable_text

    except Exception as err:
        logger.error(f"Failed to clean HTML content: {err}")
        return ""
