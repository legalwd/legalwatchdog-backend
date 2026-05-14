"""URL validation utilities for source creation.

Provides comprehensive URL validation including format checks, domain blocklisting,
and reachability verification to ensure only valid sources are created.
"""

import ipaddress
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from pydantic import HttpUrl


class URLValidationError(Exception):
    """Base exception for URL validation failures.

    Attributes:
        message (str): User-friendly error message.
        error_code (str): Machine-readable error code.
    """

    def __init__(self, message: str, error_code: str):
        """Initialize URLValidationError.

        Args:
            message (str): User-friendly error message.
            error_code (str): Machine-readable error code.
        """
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class URLValidator:
    """Validates URLs for source creation with comprehensive checks.

    Implements multi-layer validation including:
    - Format and structure validation
    - Domain blocklist checking (localhost, reserved IPs, test domains)
    - Reachability verification via HTTP requests
    """

    BLOCKED_DOMAINS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "test.org",
        "invalid",
        "local",
    }

    BLOCKED_TLDS = {
        "test",
        "localhost",
        "invalid",
        "example",
        "local",
    }

    PRIVATE_IP_PATTERNS = [
        r"^10\.",  # 10.0.0.0/8
        r"^172\.(1[6-9]|2[0-9]|3[01])\.",
        r"^192\.168\.",
        r"^169\.254\.",
        r"^fe80:",
        r"^fc00:",
        r"^fd00:",
    ]

    @classmethod
    def validate_url_format(cls, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate URL format and structure.

        Args:
            url (str): The URL to validate.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
                (is_valid, error_message, error_code)

        Examples:
            >>> is_valid, msg, code = URLValidator.validate_url_format("https://example.com")
            >>> print(is_valid)
            False  # example.com is blocked
        """
        try:
            parsed = urlparse(str(url))

            # Must have scheme
            if not parsed.scheme:
                return (
                    False,
                    "URL must include a protocol (http:// or https://)",
                    "MISSING_PROTOCOL",
                )

            # Must be HTTP or HTTPS
            if parsed.scheme not in ["http", "https"]:
                return (
                    False,
                    "Only HTTP and HTTPS protocols are supported for scraping",
                    "INVALID_PROTOCOL",
                )

            # Must have netloc (domain)
            if not parsed.netloc:
                return False, "URL must include a valid domain name", "MISSING_DOMAIN"

            # Extract hostname
            hostname = parsed.hostname
            if not hostname:
                return False, "Could not extract a valid hostname from the URL", "INVALID_HOSTNAME"

            return True, None, None

        except Exception as e:
            return False, f"The URL format is invalid: {str(e)}", "MALFORMED_URL"

    @classmethod
    def validate_domain(cls, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if domain is blocked or reserved.

        Args:
            url (str): The URL to check.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
                (is_valid, error_message, error_code)

        Examples:
            >>> is_valid, msg, code = URLValidator.validate_domain("http://localhost:8000")
            >>> print(code)
            BLOCKED_DOMAIN
        """
        try:
            parsed = urlparse(str(url))
            hostname = parsed.hostname

            if not hostname:
                return False, "Could not extract hostname from URL", "INVALID_HOSTNAME"

            # Check against blocked domains
            if hostname in cls.BLOCKED_DOMAINS:
                return (
                    False,
                    f"Cannot scrape from '{hostname}' - this domain is reserved "
                    "for testing or local use",
                    "BLOCKED_DOMAIN",
                )

            # Check TLD
            if "." in hostname:
                tld = hostname.split(".")[-1].lower()
                if tld in cls.BLOCKED_TLDS:
                    return (
                        False,
                        f"Cannot scrape from '.{tld}' domains - this is a "
                        "reserved top-level domain",
                        "BLOCKED_DOMAIN",
                    )

            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return (
                        False,
                        f"Cannot scrape from private or local IP address '{hostname}'",
                        "BLOCKED_DOMAIN",
                    )
            except ValueError:
                pass

            for pattern in cls.PRIVATE_IP_PATTERNS:
                if re.match(pattern, hostname):
                    return (
                        False,
                        f"Cannot scrape from private network address '{hostname}'",
                        "BLOCKED_DOMAIN",
                    )

            return True, None, None

        except Exception as e:
            return False, f"Domain validation failed: {str(e)}", "DOMAIN_VALIDATION_ERROR"

    @classmethod
    async def check_url_reachability(
        cls,
        url: str,
        timeout: int = 10,
        allow_redirects: bool = True,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Verify that the URL is reachable via HTTP request.

        Args:
            url (str): The URL to check.
            timeout (int): Request timeout in seconds. Default is 10.
            allow_redirects (bool): Whether to follow redirects. Default is True.

        Returns:
            Tuple[bool, Optional[str], Optional[str]]:
                (is_reachable, error_message, error_code)

        Raises:
            Exception: On network errors (captured and returned as tuple).

        Examples:
            >>> is_reachable, msg, code = await URLValidator.check_url_reachability("https://google.com")
            >>> print(is_reachable)
            True
        """
        try:
            async with httpx.AsyncClient(
                follow_redirects=allow_redirects,
                timeout=timeout,
                trust_env=False,
            ) as client:
                # Try HEAD request first (faster, doesn't download content)
                try:
                    response = await client.head(str(url))
                    if response.status_code < 400:
                        return True, None, None

                    # If HEAD fails, try GET (some servers don't support HEAD)
                    response = await client.get(str(url))
                    if response.status_code < 400:
                        return True, None, None

                    return (
                        False,
                        f"The URL returned an error status: {response.status_code}. "
                        "Please verify the URL is correct and publicly accessible",
                        "UNREACHABLE_URL",
                    )
                except httpx.HTTPStatusError as e:
                    return (
                        False,
                        f"The server returned an error ({e.response.status_code}). "
                        "Please check if the URL is correct",
                        "UNREACHABLE_URL",
                    )

        except httpx.ConnectTimeout:
            return (
                False,
                "Connection timed out while trying to reach the URL. The server "
                "may be down or unreachable",
                "UNREACHABLE_URL",
            )
        except httpx.ConnectError:
            return (
                False,
                "Could not connect to the URL. Please verify the domain exists and is accessible",
                "UNREACHABLE_URL",
            )
        except httpx.TimeoutException:
            return (
                False,
                "Request timed out. The server is taking too long to respond",
                "UNREACHABLE_URL",
            )
        except Exception as e:
            # Catch-all for other network errors
            error_str = str(e).lower()

            if "ssl" in error_str or "certificate" in error_str:
                return (
                    False,
                    "SSL/TLS certificate error. The website's security certificate "
                    "may be invalid or expired",
                    "UNREACHABLE_URL",
                )
            elif "dns" in error_str or "name or service not known" in error_str:
                return (
                    False,
                    "Domain name could not be resolved. Please verify the URL is correct",
                    "UNREACHABLE_URL",
                )
            else:
                return (
                    False,
                    f"Failed to reach the URL: {str(e)}",
                    "UNREACHABLE_URL",
                )

    @classmethod
    async def validate_url_comprehensive(
        cls,
        url: HttpUrl,
        check_reachability: bool = True,
    ) -> None:
        """Perform comprehensive URL validation.

        Runs all validation checks in sequence and raises on first failure.

        Args:
            url (HttpUrl): Pydantic-validated URL to check.
            check_reachability (bool): Whether to verify URL is reachable. Default is True.

        Returns:
            None: Returns nothing if all validations pass.

        Raises:
            URLValidationError: If any validation check fails, with user-friendly message.

        Examples:
            >>> await URLValidator.validate_url_comprehensive(HttpUrl("https://google.com"))
            >>> # Returns None if valid, raises URLValidationError if invalid
        """
        url_str = str(url)

        # Step 1: Format validation
        is_valid, error_msg, error_code = cls.validate_url_format(url_str)
        if not is_valid:
            raise URLValidationError(error_msg, error_code)

        # Step 2: Domain validation
        is_valid, error_msg, error_code = cls.validate_domain(url_str)
        if not is_valid:
            raise URLValidationError(error_msg, error_code)

        # Step 3: Reachability check (optional, can be disabled for performance)
        if check_reachability:
            is_reachable, error_msg, error_code = await cls.check_url_reachability(url_str)
            if not is_reachable:
                raise URLValidationError(error_msg, error_code)
