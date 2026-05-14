"""Tests for validators."""

import pytest

from app.api.core.config import settings
from app.api.utils.validators import is_company_email, is_strong_password


@pytest.mark.skipif(
    settings.ALLOW_TEST_EMAIL_PROVIDERS,
    reason="Test requires ALLOW_TEST_EMAIL_PROVIDERS=false",
)
@pytest.mark.parametrize(
    "email,expected",
    [
        ("user@company.com", True),
        ("user@gmail.com", False),
        ("user@yahoo.com", False),
        (
            "admin@company.com",
            True,
        ),
        ("someone@mailinator.com", False),
        ("employee@enterprise.org", True),
        ("admin@outlook.com", False),
    ],
)
def test_is_company_email(email, expected):
    from app.api.utils.email_verifier import BusinessEmailVerifier

    # Mock MX record verification
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    # Test without mocking - use actual settings from .env
    # Tests run with ALLOW_TEST_EMAIL_PROVIDERS=false in CI
    assert is_company_email(email) == expected


@pytest.mark.parametrize(
    "password,expected",
    [
        ("Password1!", ""),  # Empty string means valid
        ("password", "not_empty"),  # Any non-empty string means invalid
        ("PASSWORD1!", "not_empty"),
        ("Password!", "not_empty"),
        ("Password1", "not_empty"),
        ("Pass1!", "not_empty"),
        ("StrongPass123$", ""),  # Empty string means valid
    ],
)
def test_is_strong_password(password, expected):
    """Test password strength validation.

    is_strong_password returns an empty string if valid, or an error message if invalid.
    """
    result = is_strong_password(password)
    if expected == "":
        assert result == "", f"Expected valid password but got: {result}"
    else:
        assert result != "", "Expected invalid password but got valid"
