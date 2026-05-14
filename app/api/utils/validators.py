import logging
import re

from app.api.utils.email_verifier import BusinessEmailVerifier, EmailType

logger = logging.getLogger("app")


def is_company_email(email: str) -> bool:
    """Return True if an email appears to be from a business/enterprise.

    This function is a small wrapper around :class:`BusinessEmailVerifier`
    used by registration to block free and disposable addresses.

    Args:
        email: The email address to check.

    Returns:
        True if the email is classified as `EmailType.BUSINESS` or `EmailType.ROLE_BASED`
        and not disposable.
    """
    verifier = BusinessEmailVerifier()
    result = verifier.verify_email(email)
    return result.email_type in (EmailType.BUSINESS, EmailType.ROLE_BASED) and result.is_valid


def is_strong_password(password: str) -> str:
    """Check password strength and return a human-readable error message.

    This function validates the password against several common rules and
    returns a concatenated message describing the missing requirements. If the
    password satisfies all checks, an empty string is returned (so it can be
    used in Pydantic validators as the absence of an error).

    Args:
        password: The plaintext password to validate.

    Returns:
        An empty string on success, or a message describing the failures.
    """
    errors: list[str] = []

    # Minimum length
    if len(password) < 8:
        errors.append("at least 8 characters")
    # Uppercase
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    # Lowercase
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    # Digit
    if not re.search(r"[0-9]", password):
        errors.append("one digit")
    # Special character
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("one special character")

    if errors:
        return "Password must contain: " + ", ".join(errors) + "."
    return ""
