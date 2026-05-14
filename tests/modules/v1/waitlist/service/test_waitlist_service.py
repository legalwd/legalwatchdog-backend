import pytest

from app.api.core.custom_exceptions.exceptions import EmailAlreadyExistsError
from app.api.modules.v1.waitlist.schemas.waitlist_schema import (
    WaitlistResponse,
    WaitlistSignup,
)
from app.api.modules.v1.waitlist.service.waitlist_service import WaitlistService


@pytest.mark.asyncio
async def test_add_to_waitlist_success(pg_async_session):
    """Test adding a new email to the waitlist successfully."""
    session = pg_async_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )
    response: WaitlistResponse = await service.add_to_waitlist(session, waitlist_data)

    assert response.organization_email == "new@company.com"
    assert response.organization_name == "New Company"


@pytest.mark.asyncio
async def test_add_to_waitlist_duplicate(pg_async_session):
    """Test adding a duplicate email to the waitlist raises an error."""
    session = pg_async_session
    service = WaitlistService()

    waitlist_data = WaitlistSignup(
        organization_email="new@company.com", organization_name="New Company"
    )

    await service.add_to_waitlist(session, waitlist_data)

    with pytest.raises(EmailAlreadyExistsError) as exc_info:
        await service.add_to_waitlist(session, waitlist_data)

    assert "Email is already registered" in str(exc_info.value)
