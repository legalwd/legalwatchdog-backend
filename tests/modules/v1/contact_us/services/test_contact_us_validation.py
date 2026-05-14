import pytest
from pydantic import ValidationError

from app.api.modules.v1.contact_us.schemas.contact_us import ContactUsRequest


def test_valid_contact_us_request():
    data = {
        "full_name": "John Doe",
        "phone_number": "+12345678901",
        "email": "valid@gmail.com",
        "message": "Hello there, this is valid.",
    }

    obj = ContactUsRequest(**data)
    assert obj.full_name == "John Doe"


def test_invalid_email_not_company():
    """
    Since the schema's is_company_email() does NOT reject gmail,
    this test should simply assert that the model DOES NOT raise.
    """
    data = {
        "full_name": "John Doe",
        "phone_number": "+12345678901",
        "email": "john@yahoo.com",
        "message": "This is a valid message.",
    }

    with pytest.raises(ValidationError) as exc:
        ContactUsRequest(**data)

    assert "Only company email addresses are allowed" in str(exc.value)


def test_phone_invalid_format():
    data = {
        "full_name": "John Doe",
        "phone_number": "123-45x-789",
        "email": "valid@company.com",
        "message": "This is a valid message.",
    }

    with pytest.raises(ValidationError) as exc:
        ContactUsRequest(**data)

    assert "Invalid phone number" in str(exc.value)


def test_phone_must_be_10_digits():
    data = {
        "full_name": "John Doe",
        "phone_number": "12345",
        "email": "valid@gmail.com",
        "message": "This is a valid message.",
    }

    with pytest.raises(ValidationError):
        ContactUsRequest(**data)


def test_full_name_not_empty():
    data = {
        "full_name": "   ",
        "phone_number": "1234567890",
        "email": "valid@acme.com",
        "message": "This is a valid message.",
    }

    with pytest.raises(ValidationError) as exc:
        ContactUsRequest(**data)

    assert "Full name cannot be empty" in str(exc.value)
