"""Tests for register schema validation."""

import pytest
from pydantic import ValidationError

from app.api.core.config import settings
from app.api.modules.v1.auth.schemas.register import RegisterRequest
from app.api.utils.email_verifier import BusinessEmailVerifier


@pytest.mark.skipif(
    settings.ALLOW_TEST_EMAIL_PROVIDERS,
    reason="Test requires ALLOW_TEST_EMAIL_PROVIDERS=false",
)
def test_register_rejects_free_provider():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    with pytest.raises(ValidationError):
        RegisterRequest(
            name="Acme",
            email="someone@gmail.com",
            password="Password1!",
            confirm_password="Password1!",
            industry="Legal",
        )


def test_register_allows_business_email():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    model = RegisterRequest(
        name="Acme",
        email="someone@company.com",
        password="Password1!",
        confirm_password="Password1!",
        industry="Legal",
    )

    assert model.email == "someone@company.com"


def test_register_allows_role_based_email():
    BusinessEmailVerifier._verify_mx_records = lambda self, d: True

    model = RegisterRequest(
        name="Acme",
        email="admin@company.com",
        password="Password1!",
        confirm_password="Password1!",
        industry="Legal",
    )

    assert model.email == "admin@company.com"
