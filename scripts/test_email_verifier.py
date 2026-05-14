import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if __name__ == "__main__":
    from app.api.utils.email_verifier import BusinessEmailVerifier, EmailType

    verifier = BusinessEmailVerifier()

    test_emails = [
        "john.doe@company.com",
        "user@gmail.com",
        "support@company.com",
        "temp@mailinator.com",
        "invalid-email",
        "admin@startup.io",
        "contact@microsoft.com",
        "admin@hng.tech",
    ]

    print("=" * 80)
    print("EMAIL VERIFICATION RESULTS")
    print("=" * 80)

    for email in test_emails:
        result = verifier.verify_email(email)

        print(f"\nEmail: {result.email}")
        print(f"Valid: {result.is_valid}")
        print(f"Type: {result.email_type.value}")
        print(f"Domain: {result.domain}")
        print(f"MX Records: {result.has_mx_records}")
        print(f"Free Provider: {result.is_free_provider}")
        print(f"Disposable: {result.is_disposable}")
        print(f"Role-based: {result.is_role_based}")
        print(f"Confidence: {result.confidence_score:.2%}")

        if result.error_message:
            print(f"Error: {result.error_message}")

        print("-" * 80)

    print("\n" + "=" * 80)
    print("BATCH VERIFICATION")
    print("=" * 80)

    batch_results = verifier.batch_verify(test_emails[:3])
    business_emails = [r for r in batch_results if r.email_type == EmailType.BUSINESS]

    print(f"\nTotal verified: {len(batch_results)}")
    print(f"Business emails found: {len(business_emails)}")

    for result in business_emails:
        print(f"  - {result.email} (confidence: {result.confidence_score:.2%})")
