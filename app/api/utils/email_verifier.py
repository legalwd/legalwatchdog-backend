import time
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Dict, Optional, Tuple

import dns.resolver

from app.api.core.config import settings

_TEST_EMAIL_PROVIDERS = set()
if settings.ALLOW_TEST_EMAIL_PROVIDERS:
    _TEST_EMAIL_PROVIDERS = {p.strip().lower() for p in settings.TEST_EMAIL_PROVIDERS.split(",")}


class EmailType(Enum):
    BUSINESS = "business"
    PERSONAL = "personal"
    ROLE_BASED = "role_based"
    DISPOSABLE = "disposable"
    INVALID = "invalid"


@dataclass
class EmailVerificationResult:
    email: str
    is_valid: bool
    email_type: EmailType
    domain: str
    has_mx_records: bool
    is_free_provider: bool
    is_disposable: bool
    is_reserved: bool
    is_role_based: bool
    confidence_score: float
    details: Dict[str, any]
    error_message: Optional[str] = None

    """Holds the results of an email verification attempt.

    Attributes:
        email: Original email passed to the verifier.
        is_valid: Whether the email passes a minimal 'valid' check (MX and not disposable/reserved).
        email_type: One of EmailType values.
        domain: Domain extracted from the email.
        has_mx_records: Whether the domain returned MX records.
        is_free_provider: Whether the domain is in the free providers list.  # noqa: E501
        is_disposable: Whether the domain is known disposable.
        is_reserved: Whether the domain is reserved/example.
        is_role_based: Whether the local-part looks like a role-based address.
        confidence_score: A heuristic confidence score (0.0 - 1.0).
        details: A dictionary with additional details.
        error_message: Optional error text when verification failed early.
    """


class BusinessEmailVerifier:
    """Class responsible for classifying an email address.

    The verifier implements simple but production-minded checks. It is not a
    substitute for an external email validation provider but provides
    deterministic, testable logic for server-side registration.
    """

    FREE_EMAIL_PROVIDERS = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "live.com",
        "msn.com",
        "googlemail.com",
        "protonmail.com",
        "proton.me",
        "zoho.com",
        "gmx.com",
        "yandex.com",
        "mail.ru",
    }

    DISPOSABLE_EMAIL_DOMAINS = {
        "mailinator.com",
        "guerrillamail.com",
        "temp-mail.org",
        "10minutemail.com",
    }

    # Reserved/example domains that should not be considered valid business emails
    RESERVED_DOMAINS = {
        "example.com",
        "example.org",
        "example.net",
        "test.com",
        "test.org",
        "localhost",
        "invalid",
    }

    ROLE_BASED_PREFIXES = {
        "admin",
        "administrator",
        "info",
        "support",
        "sales",
        "contact",
        "help",
    }

    def __init__(self, dns_timeout: float = 5.0, rate_limit_delay: float = 0.1):
        """Create a new verifier.

        Args:
            dns_timeout: DNS query timeout in seconds.
            rate_limit_delay: Minimum time in seconds between DNS queries
                in order to avoid being rate-limited by resolvers.
        """
        # Resolver configuration
        self.resolver = dns.resolver.Resolver()
        # Use Google DNS servers
        self.resolver.nameservers = ["8.8.8.8", "8.8.4.4"]
        self.resolver.timeout = dns_timeout
        self.resolver.lifetime = dns_timeout
        self.rate_limit_delay = rate_limit_delay
        self.last_dns_query_time = 0

    def verify_email(self, email: str) -> EmailVerificationResult:
        """Verify an email and return a detailed result.

        Steps performed:
        1. Syntax validation
        2. Disposable provider check
        3. Free-provider check
        4. Role-based local-part detection
        5. DNS MX lookup

        Args:
            email: Email address to verify.

        Returns:
            EmailVerificationResult object describing the classification.
        """
        email = email.strip().lower()
        ok, err = self._validate_email_syntax(email)
        if not ok:
            return EmailVerificationResult(
                email,
                False,
                EmailType.INVALID,
                "",
                False,
                False,
                False,
                False,
                False,
                0.0,
                {},
                error_message=err,
            )

        local_part, domain = email.rsplit("@", 1)
        is_disposable = self._is_disposable_email(domain)
        is_reserved = self._is_reserved_domain(domain)
        is_free_provider = self._is_free_email_provider(domain)
        is_role_based = self._is_role_based_email(local_part)
        has_mx_records = self._verify_mx_records(domain)

        email_type, confidence = self._classify_email(
            is_free_provider=is_free_provider,
            is_disposable=is_disposable,
            is_reserved=is_reserved,
            is_role_based=is_role_based,
            has_mx_records=has_mx_records,
        )

        details = {
            "local_part": local_part,
            "syntax_valid": True,
            "dns_verified": has_mx_records,
        }
        is_valid = has_mx_records and not is_disposable and not is_reserved

        return EmailVerificationResult(
            email=email,
            is_valid=is_valid,
            email_type=email_type,
            domain=domain,
            has_mx_records=has_mx_records,
            is_free_provider=is_free_provider,
            is_disposable=is_disposable,
            is_reserved=is_reserved,
            is_role_based=is_role_based,
            confidence_score=confidence,
            details=details,
        )

    def _validate_email_syntax(self, email: str) -> Tuple[bool, Optional[str]]:
        """Perform a pragmatic email syntax check.

        This method is intentionally pragmatic; it is not a full RFC-compliant
        validator, but it ensures the email has a local part, domain and reasonable
        maximum lengths.

        Args:
            email: Full email string to validate.

        Returns:
            Tuple where the first element is boolean success, and second is
            an optional error string when falsy.
        """
        if "@" not in email:
            return False, "Missing @ symbol"
        try:
            local, domain = email.rsplit("@", 1)
        except Exception:
            return False, "Invalid format"
        if len(local) > 64:
            return False, "Local part too long"
        if len(domain) > 255 or "." not in domain:
            return False, "Invalid domain format"
        return True, None

    def _is_free_email_provider(self, domain: str) -> bool:
        """Return whether domain belongs to a known public free provider.

        Args:
            domain: Domain portion of an email address.

        Returns:
            True when domain is in FREE_EMAIL_PROVIDERS, unless it's an allowed test provider.
        """
        # Allow test email providers if configured
        if settings.ALLOW_TEST_EMAIL_PROVIDERS and domain in _TEST_EMAIL_PROVIDERS:
            return False
        return domain in self.FREE_EMAIL_PROVIDERS

    def _is_disposable_email(self, domain: str) -> bool:
        """Check whether domain is a known disposable email provider.

        Args:
            domain: Domain portion of an email address.

        Returns:
            True if domain is disposable.
        """
        return domain in self.DISPOSABLE_EMAIL_DOMAINS

    def _is_reserved_domain(self, domain: str) -> bool:
        """Check whether domain is a reserved/example domain.

        Args:
            domain: Domain portion of an email address.

        Returns:
            True if domain is reserved and should not be considered valid.
        """
        return domain in self.RESERVED_DOMAINS

    def _is_role_based_email(self, local_part: str) -> bool:
        """Detect if the local part corresponds to a role-based address.

        Role-based addresses are like 'support@company.com' or
        'support+tag@company.com'. Those addresses commonly represent shared
        inboxes and are often not acceptable for user registration.

        Args:
            local_part: Local part of an email address.

        Returns:
            True when local_part is role-like.
        """
        low = local_part.lower()
        return any(low == r or low.startswith(r + "+") for r in self.ROLE_BASED_PREFIXES)

    @lru_cache(maxsize=1024)
    def _verify_mx_records(self, domain: str) -> bool:
        """Verify that the domain has an MX record.

        Queries the DNS and returns True when MX records exist. Caches
        responses and applies a rate-limit between queries.

        Args:
            domain: The domain to query.

        Returns:
            True if one or more MX records are found, False otherwise.
        """
        now = time.time()
        since = now - self.last_dns_query_time
        if since < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - since)
        try:
            self.last_dns_query_time = time.time()
            answers = self.resolver.resolve(domain, "MX")
            return bool(answers)
        except Exception:
            return False

    def _classify_email(
        self,
        is_free_provider: bool,
        is_disposable: bool,
        is_reserved: bool,
        is_role_based: bool,
        has_mx_records: bool,
    ) -> Tuple[EmailType, float]:
        """Return a coarse classification with a confidence score.

        Args:
            is_free_provider: Whether the domain is a known free provider.
            is_disposable: Whether the domain is known disposable.
            is_reserved: Whether the domain is reserved/example.
            is_role_based: Whether the local part is role-based.
            has_mx_records: Whether MX records were found for the domain.

        Returns:
            (EmailType, confidence) describing the assumed email type.
        """
        if is_disposable:
            return EmailType.DISPOSABLE, 1.0
        if is_reserved:
            return EmailType.INVALID, 1.0
        if not has_mx_records:
            return EmailType.INVALID, 0.0
        if is_free_provider:
            return EmailType.PERSONAL, 0.95
        if is_role_based:
            return EmailType.ROLE_BASED, 0.8
        return EmailType.BUSINESS, 0.9

    def batch_verify(self, emails: list[str]) -> list[EmailVerificationResult]:
        """Verify multiple emails at once.

        Args:
            emails: List of email addresses to verify.

        Returns:
            List of EmailVerificationResult objects.
        """
        return [self.verify_email(email) for email in emails]
