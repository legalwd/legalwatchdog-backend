import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD


@pytest.mark.asyncio
async def test_add_user_to_organization_success():
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    role_id = uuid.uuid4()

    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=None)

    result = await UserOrganizationCRUD.add_user_to_organization(db, user_id, org_id, role_id)

    assert result.user_id == user_id
    assert result.organization_id == org_id
    assert result.role_id == role_id
    db.add.assert_called_once_with(result)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(result)


@pytest.mark.asyncio
async def test_add_user_to_organization_already_exists():
    db = MagicMock()
    existing_membership = UserOrganization(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role_id=uuid.uuid4()
    )
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=existing_membership)

    with pytest.raises(ValueError):
        await UserOrganizationCRUD.add_user_to_organization(
            db,
            existing_membership.user_id,
            existing_membership.organization_id,
            existing_membership.role_id,
        )


@pytest.mark.asyncio
async def test_get_user_organization_returns_membership():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    expected_membership = UserOrganization(
        user_id=user_id, organization_id=org_id, role_id=uuid.uuid4()
    )

    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=expected_membership)

    db = AsyncMock()

    result = await UserOrganizationCRUD.get_user_organization(db, user_id, org_id)

    assert result.user_id == expected_membership.user_id
    assert result.organization_id == expected_membership.organization_id


@pytest.mark.asyncio
async def test_update_user_role_in_organization_success():
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    old_role_id = uuid.uuid4()
    new_role_id = uuid.uuid4()

    membership = UserOrganization(user_id=user_id, organization_id=org_id, role_id=old_role_id)
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=membership)

    result = await UserOrganizationCRUD.update_user_role_in_organization(
        db, user_id, org_id, new_role_id
    )

    assert result.role_id == new_role_id
    db.add.assert_called_once_with(membership)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(membership)


@pytest.mark.asyncio
async def test_update_user_role_in_organization_not_found():
    db = MagicMock()
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=None)

    with pytest.raises(ValueError):
        await UserOrganizationCRUD.update_user_role_in_organization(
            db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        )


@pytest.mark.asyncio
async def test_set_membership_status_success():
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    membership = UserOrganization(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role_id=uuid.uuid4(), is_active=False
    )
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=membership)

    result = await UserOrganizationCRUD.set_membership_status(
        db, membership.user_id, membership.organization_id, True
    )

    assert result.is_active is True
    db.add.assert_called_once_with(membership)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(membership)


@pytest.mark.asyncio
async def test_soft_delete_member_success():
    db = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()

    membership = UserOrganization(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role_id=uuid.uuid4()
    )

    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=membership)

    await UserOrganizationCRUD.soft_delete_member(
        db, membership.user_id, membership.organization_id
    )

    assert membership.is_deleted is True
    assert membership.deleted_at is not None
    db.add.assert_called_once_with(membership)
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_soft_delete_member_not_found():
    db = AsyncMock()
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="not a member"):
        await UserOrganizationCRUD.soft_delete_member(db, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_soft_delete_member_already_deleted():
    db = AsyncMock()
    membership = UserOrganization(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        is_deleted=True,
    )
    UserOrganizationCRUD.get_user_organization = AsyncMock(return_value=membership)

    with pytest.raises(ValueError, match="already been deleted"):
        await UserOrganizationCRUD.soft_delete_member(
            db, membership.user_id, membership.organization_id
        )
