import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.service.organization_repository import OrganizationCRUD


@pytest.mark.asyncio
async def test_create_organization_success():
    db = AsyncMock()

    with patch(
        "app.api.modules.v1.organization.service.organization_repository.Organization"
    ) as MockOrg:
        mock_org_instance = MockOrg.return_value
        mock_org_instance.id = uuid.uuid4()
        mock_org_instance.name = "TestOrg"
        mock_org_instance.industry = "Tech"
        mock_org_instance.is_active = True
        mock_org_instance.created_at = datetime.now(timezone.utc)
        mock_org_instance.updated_at = datetime.now(timezone.utc)

        result = await OrganizationCRUD.create_organization(db, name="TestOrg", industry="Tech")

    db.add.assert_called_once_with(mock_org_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(mock_org_instance)

    assert result.name == "TestOrg"
    assert result.industry == "Tech"
    assert result.is_active is True


@pytest.mark.asyncio
async def test_get_by_id_returns_organization():
    db = AsyncMock()
    org_id = uuid.uuid4()
    expected_org = Organization(id=org_id, name="Org1", industry="IT")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = expected_org
    db.execute.return_value = mock_result

    result = await OrganizationCRUD.get_by_id(db, org_id)

    assert result == expected_org
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_name_returns_organization():
    db = AsyncMock()
    org_name = "Org1"
    expected_org = Organization(id=uuid.uuid4(), name=org_name, industry="IT")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = expected_org
    db.execute.return_value = mock_result

    result = await OrganizationCRUD.get_by_name(db, org_name)

    assert result == expected_org
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_organization_success():
    db = AsyncMock()
    org_id = uuid.uuid4()
    existing_org = Organization(id=org_id, name="OldName", industry="OldIndustry", is_active=True)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_org
    db.execute.return_value = mock_result

    updated_org = await OrganizationCRUD.update(
        db,
        organization_id=org_id,
        name="NewName",
        industry="NewIndustry",
        is_active=False,
    )

    assert updated_org.name == "NewName"
    assert updated_org.industry == "NewIndustry"
    assert updated_org.is_active is False
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(existing_org)
