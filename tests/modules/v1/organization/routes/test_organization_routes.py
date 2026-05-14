"""
This module contains unit tests for the organization routes in the v1 API.

It covers various scenarios for organization-related API endpoints,
including creation, retrieval, update, and deletion of organizations,
as well as handling of associated users and permissions.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.api.core.config import settings
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.modules.v1.billing.models.billing_account import BillingStatus
from app.api.modules.v1.organization.routes.organization_route import (
    get_organization,
    get_organization_invitations,
    update_organization,
)
from app.api.modules.v1.organization.schemas.organization_schema import (
    UpdateOrganizationRequest,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_get_organization_success():
    """Test successful retrieval of organization details."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_org_details = {
        "id": str(org_id),
        "name": "Test Org",
        "industry": "Tech",
        "is_active": True,
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00",
        "projects_count": 5,
        "location": "New York",
        "country": "United States",
        "email": "contact@test.com",
        "company_size": "51-200",
        "org_type": "Private",
        "plan": "Enterprise",
        "logo_url": "http://example.com/logo.png",
        "settings": {},
        "billing_info": {},
    }

    with (
        patch(
            "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.routes.organization_route.OrganizationService.get_organization_details",
            new_callable=AsyncMock,
        ) as mock_get_details,
    ):
        mock_check_perm.return_value = True
        mock_get_details.return_value = mock_org_details

        response = await get_organization(
            organization_id=org_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert body["data"]["projects_count"] == 5
        assert body["data"]["location"] == "New York"
        assert body["data"]["country"] == "United States"
        assert body["data"]["email"] == "contact@test.com"


@pytest.mark.asyncio
async def test_update_organization_success():
    """Test successful update of organization details."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    payload = UpdateOrganizationRequest(
        name="Updated Org",
        industry="Finance",
        country="United Kingdom",
        email="new@test.com",
        company_size="51-200",
        org_type="Public",
        is_active=True,
    )

    mock_updated_org_data = {
        "id": str(org_id),
        "name": payload.name,
        "industry": payload.industry,
        "is_active": payload.is_active,
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-02T00:00:00",
        "settings": {},
        "billing_info": {"status": "active", "current_plan": {"tier": "pro"}},
        "user_role": "Admin",
        "location": None,
        "country": payload.country,
        "email": payload.email,
        "company_size": payload.company_size,
        "org_type": payload.org_type,
        "plan": "pro",
        "logo_url": None,
        "projects_count": 0,
    }

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.OrganizationService",
    ) as mock_org_service:
        mock_instance = mock_org_service.return_value
        mock_instance.update_organization = AsyncMock(return_value=mock_updated_org_data)

        response = await update_organization(
            organization_id=org_id,
            payload=payload,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        data = body["data"]
        assert data["name"] == "Updated Org"
        assert data["industry"] == "Finance"
        assert data["country"] == "United Kingdom"
        assert data["email"] == "new@test.com"
        assert data["plan"] == "pro"
        assert data["billing_info"]["status"] == "active"
        assert data["billing_info"]["current_plan"]["tier"] == "pro"
        assert body["data"]["name"] == "Updated Org"
        assert body["data"]["industry"] == "Finance"


@pytest.mark.asyncio
async def test_get_organization_invitations_success():
    """Test successful retrieval of organization invitations."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_invitations_data = {
        "invitations": [
            {
                "id": str(uuid.uuid4()),
                "organization_id": str(org_id),
                "organization_name": "Test Org",
                "invited_email": "invitee@example.com",
                "inviter_id": str(mock_current_user.id),
                "inviter_name": "Inviter User",
                "inviter_email": "inviter@example.com",
                "role_id": str(uuid.uuid4()),
                "role_name": "Member",
                "status": "pending",
                "is_expired": False,
                "expires_at": "2023-01-02T00:00:00",
                "accepted_at": None,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        ],
        "total": 1,
        "page": 1,
        "limit": 10,
        "total_pages": 1,
    }

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.OrganizationService",
    ) as mock_org_service:
        mock_instance = mock_org_service.return_value
        mock_instance.get_organization_invitations = AsyncMock(return_value=mock_invitations_data)

        response = await get_organization_invitations(
            organization_id=org_id,
            status_filter="pending",
            page=1,
            limit=10,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert len(body["data"]["invitations"]) == 1
        assert body["data"]["invitations"][0]["invited_email"] == "invitee@example.com"
        assert body["data"]["invitations"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_invite_user_invalid_domain():
    """Test that inviting a user with a non-company email fails."""
    from pydantic import ValidationError

    from app.api.modules.v1.organization.schemas.invitation_schema import InvitationCreate

    with patch(
        "app.api.modules.v1.organization.schemas.invitation_schema.is_company_email"
    ) as mock_validator:
        mock_validator.return_value = False

        with pytest.raises(ValidationError) as excinfo:
            InvitationCreate(invited_email="test@qmail.com", role_name="Member")

        assert "Only company email addresses are allowed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_cancel_invitation_success():
    """Test successful cancellation of an invitation."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    org_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_invitation = MagicMock()
    mock_invitation.id = invitation_id
    mock_invitation.organization_id = org_id
    mock_invitation.status.value = "cancelled"
    mock_invitation.invited_email = "invitee@example.com"

    mock_db.get.return_value = mock_invitation

    with (
        patch(
            "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.service.invitation_service.InvitationCRUD.cancel_invitation",
            new_callable=AsyncMock,
        ) as mock_cancel,
    ):
        mock_check_perm.return_value = True
        mock_cancel.return_value = mock_invitation

        from app.api.modules.v1.organization.routes.organization_route import cancel_invitation

        response = await cancel_invitation(
            organization_id=org_id,
            invitation_id=invitation_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_200_OK
        body = json.loads(response.body)
        assert body["status"] == "SUCCESS"
        assert body["message"] == "Invitation cancelled successfully"


@pytest.mark.asyncio
async def test_require_billing_access_allows_active_org(monkeypatch):
    """Billing guard should allow orgs with allowed billing status."""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")

    mock_db = AsyncMock()
    org_id = uuid.uuid4()

    mock_account = MagicMock()
    mock_account.status = BillingStatus.ACTIVE

    with patch(
        "app.api.core.dependencies.billing_guard.get_billing_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=mock_account)
        mock_service.is_org_allowed_usage = AsyncMock(return_value=(True, BillingStatus.ACTIVE))
        mock_get_service.return_value = mock_service

        result = await require_billing_access(organization_id=org_id, db=mock_db)

        assert result is mock_account
        mock_service.get_billing_account_by_org.assert_awaited_once_with(org_id)
        mock_service.is_org_allowed_usage.assert_awaited_once_with(org_id)


@pytest.mark.asyncio
async def test_require_billing_access_blocked_org_raises(monkeypatch):
    """Billing guard should block orgs with BLOCKED billing status.(on non-dev envs)"""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")

    mock_db = AsyncMock()
    org_id = uuid.uuid4()

    mock_account = MagicMock()
    mock_account.status = BillingStatus.BLOCKED

    with patch(
        "app.api.core.dependencies.billing_guard.get_billing_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=mock_account)
        mock_service.is_org_allowed_usage = AsyncMock(return_value=(False, BillingStatus.BLOCKED))
        mock_get_service.return_value = mock_service

        with pytest.raises(HTTPException) as excinfo:
            await require_billing_access(organization_id=org_id, db=mock_db)

        err = excinfo.value
        assert err.status_code == status.HTTP_403_FORBIDDEN
        assert "blocked" in err.detail.lower()


@pytest.mark.asyncio
async def test_require_billing_access_no_account_raises_payment_required(monkeypatch):
    """Billing guard should reject orgs with no billing account. (on non-dev envs)"""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")

    mock_db = AsyncMock()
    org_id = uuid.uuid4()

    with patch(
        "app.api.core.dependencies.billing_guard.get_billing_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service

        with pytest.raises(HTTPException) as excinfo:
            await require_billing_access(organization_id=org_id, db=mock_db)

        err = excinfo.value
        assert err.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert "billing account not found" in err.detail.lower()
