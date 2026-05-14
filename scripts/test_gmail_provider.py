"""Test script to verify Gmail can be added as an accepted mail provider for testing.

This script demonstrates how the ALLOW_TEST_EMAIL_PROVIDERS configuration
allows Gmail (and other free providers) to be accepted for testing purposes.

Usage:
    # To enable Gmail as a test provider, set in .env:
    ALLOW_TEST_EMAIL_PROVIDERS=true
    TEST_EMAIL_PROVIDERS=gmail.com

    Then run: python scripts/test_gmail_provider.py
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.core.config import Settings  # noqa: E402
from app.api.modules.v1.auth.service.validators import (  # noqa: E402
    is_company_email,
)
from app.api.utils.email_verifier import BusinessEmailVerifier  # noqa: E402


def test_email_verification():
    """Test email verification with and without test provider configuration."""
    print("=" * 70)
    print("Email Verification Test - Gmail as Test Provider")
    print("=" * 70)

    settings = Settings()
    verifier = BusinessEmailVerifier()

    print("\nConfiguration:")
    print(f"  ALLOW_TEST_EMAIL_PROVIDERS: {settings.ALLOW_TEST_EMAIL_PROVIDERS}")
    print(f"  TEST_EMAIL_PROVIDERS: {settings.TEST_EMAIL_PROVIDERS}")

    # Test emails
    test_emails = [
        "john.doe@gmail.com",
        "jane.smith@company.com",
        "test@example.com",
    ]

    print("\n" + "-" * 70)
    print("BusinessEmailVerifier Results:")
    print("-" * 70)

    for email in test_emails:
        result = verifier.verify_email(email)
        print(f"\nEmail: {email}")
        print(f"  Valid: {result.is_valid}")
        print(f"  Type: {result.email_type.value}")
        print(f"  Is Free Provider: {result.is_free_provider}")
        print(f"  Has MX Records: {result.has_mx_records}")
        print(f"  Confidence Score: {result.confidence_score:.2f}")

    print("\n" + "-" * 70)
    print("is_company_email() Validator Results:")
    print("-" * 70)

    for email in test_emails:
        is_company = is_company_email(email)
        domain = email.split("@")[1]
        print(f"\nEmail: {email} (domain: {domain})")
        print(f"  Is Company Email: {is_company}")

        # Show if it's a test provider
        if settings.ALLOW_TEST_EMAIL_PROVIDERS:
            test_providers = {p.strip().lower() for p in settings.TEST_EMAIL_PROVIDERS.split(",")}
            if domain in test_providers:
                print("  Note: This domain is in TEST_EMAIL_PROVIDERS")


def main():
    """Run all tests."""
    print("\n")
    test_email_verification()
    print("\n" + "=" * 70)
    print("Test Complete!")
    print("=" * 70)

    print("\n📝 To enable Gmail as a test provider:")
    print("   1. Add to your .env file:")
    print("      ALLOW_TEST_EMAIL_PROVIDERS=true")
    print("      TEST_EMAIL_PROVIDERS=gmail.com")
    print("")
    print("   2. Optionally, add multiple providers:")
    print("      TEST_EMAIL_PROVIDERS=gmail.com,yahoo.com,outlook.com")
    print("")
    print("   3. Restart your application for changes to take effect")
    print("\n")


if __name__ == "__main__":
    main()
