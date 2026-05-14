from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.api.modules.v1.organization.service.organization_repository import OrganizationCRUD


@pytest.mark.asyncio
async def test_create_organization_success():
    """Test successful creation of an organization."""

    db = AsyncMock()

    with patch(
        "app.api.modules.v1.organization.service.organization_repository.Organization"
    ) as MockOrg:
        mock_org_instance = AsyncMock()
        mock_org_instance.id = "123"
        mock_org_instance.name = "TestOrg"
        mock_org_instance.industry = "Tech"
        mock_org_instance.is_active = True
        mock_org_instance.settings = {}
        mock_org_instance.billing_info = {}
        mock_org_instance.created_at = datetime.now(timezone.utc)
        mock_org_instance.updated_at = datetime.now(timezone.utc)
        mock_org_instance.user_memberships = []
        mock_org_instance.roles = []
        mock_org_instance.projects = []

        MockOrg.return_value = mock_org_instance

        result = await OrganizationCRUD.create_organization(
            db=db,
            name="TestOrg",
            industry="Tech",
        )

    db.add.assert_called_once_with(mock_org_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited()

    assert result.name == "TestOrg"
    assert result.industry == "Tech"
    assert result.is_active is True
    assert isinstance(result.settings, dict)
    assert isinstance(result.billing_info, dict)
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)


@pytest.mark.asyncio
async def test_create_organization_failure():
    """Test that an exception is raised when DB operations fail."""

    db = AsyncMock()
    db.flush.side_effect = Exception("DB failure")

    with pytest.raises(Exception) as exc:
        await OrganizationCRUD.create_organization(
            db=db,
            name="FailOrg",
        )

    assert "Failed to create organization" in str(exc.value)
