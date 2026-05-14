from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.api.modules.v1.organization.schemas.organization_schema import (
    CreateOrganizationRequest,
    UpdateOrganizationRequest,
)
from app.api.utils.organization_validations import (
    validate_no_pending_registration,
    validate_organization_email_available,
)


@pytest.mark.asyncio
async def test_validate_organization_email_available_passes():
    """Passes when email is not registered"""
    db_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_by_email",
        new=AsyncMock(return_value=None),
    ):
        await validate_organization_email_available(db_mock, "test@example.com")


@pytest.mark.asyncio
async def test_validate_organization_email_available_fails():
    """Raises ValueError when email is already registered"""
    db_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_organization_by_email",
        new=AsyncMock(return_value={"id": 1}),
    ):
        with pytest.raises(ValueError) as exc:
            await validate_organization_email_available(db_mock, "test@example.com")
        assert str(exc.value) == "An organization with this email already exists."


@pytest.mark.asyncio
async def test_validate_no_pending_registration_passes():
    """Passes when no pending registration exists"""
    redis_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_user_credentials",
        new=AsyncMock(return_value=None),
    ):
        await validate_no_pending_registration(redis_mock, "test@example.com")


@pytest.mark.asyncio
async def test_validate_no_pending_registration_fails():
    """Raises ValueError when pending registration exists"""
    redis_mock = AsyncMock()
    with patch(
        "app.api.utils.organization_validations.get_user_credentials",
        new=AsyncMock(return_value={"otp_code": "123456"}),
    ):
        with pytest.raises(ValueError) as exc:
            await validate_no_pending_registration(redis_mock, "test@example.com")
        assert str(exc.value) == (
            "A registration with this email is already pending OTP verification."
        )


def test_create_organization_rejects_too_short_name():
    with pytest.raises(ValidationError) as exc:
        CreateOrganizationRequest(name="A", industry="Tech")

    assert "at least 2 characters" in str(exc.value)


def test_create_organization_accepts_valid_name_and_industry():
    req = CreateOrganizationRequest(name="Acme Corp", industry="Technology")
    assert req.name == "Acme Corp"
    assert req.industry == "Technology"


def test_update_organization_rejects_invalid_industry():
    with pytest.raises(ValidationError) as exc:
        UpdateOrganizationRequest(industry="12345")

    assert "must not contain numbers" in str(exc.value)


def test_update_organization_accepts_partial_valid_payload():
    req = UpdateOrganizationRequest(
        name="Updated Org",
        industry="Finance",
        location="London",
    )
    assert req.name == "Updated Org"
    assert req.industry == "Finance"
    assert req.location == "London"
