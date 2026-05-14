"""
Tests for the InvitationCRUD service, specifically the duplicate invitation prevention logic.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.organization.models.invitation_model import (
    Invitation,
    InvitationStatus,
)
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD


@pytest.mark.asyncio
async def test_get_pending_invitation_for_email_and_org_found():
    """Test that an existing pending invitation is found."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    email = "invitee@company.com"

    mock_invitation = MagicMock(spec=Invitation)
    mock_invitation.id = uuid.uuid4()
    mock_invitation.organization_id = org_id
    mock_invitation.invited_email = email
    mock_invitation.status = InvitationStatus.PENDING
    mock_invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_invitation
    mock_db.execute.return_value = mock_result

    result = await InvitationCRUD.get_pending_invitation_for_email_and_org(mock_db, email, org_id)

    assert result is mock_invitation
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_pending_invitation_for_email_and_org_not_found():
    """Test that None is returned when no pending invitation exists."""
    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    email = "new_invitee@company.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await InvitationCRUD.get_pending_invitation_for_email_and_org(mock_db, email, org_id)

    assert result is None
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_invitation_blocks_duplicate_pending():
    """Test that sending an invitation fails when a pending invitation already exists."""
    from fastapi import BackgroundTasks

    from app.api.modules.v1.organization.service.organization_service import (
        OrganizationService,
    )

    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    inviter_id = uuid.uuid4()
    invited_email = "duplicate@company.com"
    background_tasks = BackgroundTasks()

    mock_org = MagicMock()
    mock_org.name = "Test Org"
    mock_org.deleted_at = None

    mock_inviter = MagicMock()
    mock_inviter.name = "Inviter Name"

    mock_existing_invitation = MagicMock(spec=Invitation)
    mock_existing_invitation.id = uuid.uuid4()
    mock_existing_invitation.status = InvitationStatus.PENDING

    with (
        patch(
            "app.api.modules.v1.organization.service.organization_service.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.service.organization_service.OrganizationCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_inviter,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get_by_email,
        patch(
            "app.api.modules.v1.organization.service.organization_service.InvitationCRUD.get_pending_invitation_for_email_and_org",
            new_callable=AsyncMock,
        ) as mock_get_pending,
    ):
        mock_check_perm.return_value = True
        mock_get_org.return_value = mock_org
        mock_get_inviter.return_value = mock_inviter
        mock_get_by_email.return_value = None  # User doesn't exist yet
        mock_get_pending.return_value = mock_existing_invitation  # Pending invitation exists

        service = OrganizationService(mock_db)

        with pytest.raises(ValueError) as exc_info:
            await service.send_invitation(
                background_tasks=background_tasks,
                organization_id=org_id,
                invited_email=invited_email,
                inviter_id=inviter_id,
                role_name="Member",
            )

        assert "pending invitation already exists" in str(exc_info.value).lower()
        mock_get_pending.assert_awaited_once_with(mock_db, invited_email, org_id)


@pytest.mark.asyncio
async def test_send_invitation_allows_when_no_pending():
    """Test that sending an invitation succeeds when no pending invitation exists."""
    from fastapi import BackgroundTasks

    from app.api.modules.v1.organization.service.organization_service import (
        OrganizationService,
    )

    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    inviter_id = uuid.uuid4()
    role_id = uuid.uuid4()
    invited_email = "new_user@company.com"
    background_tasks = BackgroundTasks()

    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.name = "Test Org"
    mock_org.deleted_at = None

    mock_inviter = MagicMock()
    mock_inviter.name = "Inviter Name"

    mock_role = MagicMock()
    mock_role.id = role_id
    mock_role.name = "Member"

    mock_new_invitation = MagicMock(spec=Invitation)
    mock_new_invitation.id = uuid.uuid4()
    mock_new_invitation.organization_id = org_id
    mock_new_invitation.invited_email = invited_email
    mock_new_invitation.status = InvitationStatus.PENDING

    with (
        patch(
            "app.api.modules.v1.organization.service.organization_service.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.service.organization_service.OrganizationCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_inviter,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get_by_email,
        patch(
            "app.api.modules.v1.organization.service.organization_service.InvitationCRUD.get_pending_invitation_for_email_and_org",
            new_callable=AsyncMock,
        ) as mock_get_pending,
        patch(
            "app.api.modules.v1.organization.service.organization_service.RoleCRUD.get_role_by_name_and_organization",
            new_callable=AsyncMock,
        ) as mock_get_role,
        patch(
            "app.api.modules.v1.organization.service.organization_service.InvitationCRUD.create_invitation",
            new_callable=AsyncMock,
        ) as mock_create_invitation,
        patch(
            "app.api.modules.v1.organization.service.organization_service.send_email",
        ) as _mock_send_email,
    ):
        mock_check_perm.return_value = True
        mock_get_org.return_value = mock_org
        mock_get_inviter.return_value = mock_inviter
        mock_get_by_email.return_value = None  # User doesn't exist
        mock_get_pending.return_value = None  # No pending invitation
        mock_get_role.return_value = mock_role
        mock_create_invitation.return_value = mock_new_invitation

        service = OrganizationService(mock_db)

        result = await service.send_invitation(
            background_tasks=background_tasks,
            organization_id=org_id,
            invited_email=invited_email,
            inviter_id=inviter_id,
            role_name="Member",
        )

        assert result is mock_new_invitation
        mock_get_pending.assert_awaited_once_with(mock_db, invited_email, org_id)
        mock_create_invitation.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_invitation_allows_for_soft_deleted_member():
    """Test that sending an invitation succeeds for a previously deleted member.

    Scenario:
    - User exists in the system.
    - Their prior membership in the organization has been soft-deleted
      (user_organizations.is_deleted = True).
    - UserOrganizationCRUD.get_user_organization returns None for such
      soft-deleted memberships (see implementation in user_organization_service).
    - In this case, the user should be treated as not a current member and
      a new invitation should be allowed.
    """
    from fastapi import BackgroundTasks

    from app.api.modules.v1.organization.service.organization_service import (
        OrganizationService,
    )

    mock_db = AsyncMock()
    org_id = uuid.uuid4()
    inviter_id = uuid.uuid4()
    role_id = uuid.uuid4()
    invited_email = "former_member@company.com"
    background_tasks = BackgroundTasks()

    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.name = "Test Org"
    mock_org.deleted_at = None

    mock_inviter = MagicMock()
    mock_inviter.name = "Inviter Name"

    mock_existing_user = MagicMock()
    mock_existing_user.id = uuid.uuid4()
    mock_existing_user.email = invited_email

    mock_role = MagicMock()
    mock_role.id = role_id
    mock_role.name = "Member"

    mock_new_invitation = MagicMock(spec=Invitation)
    mock_new_invitation.id = uuid.uuid4()
    mock_new_invitation.organization_id = org_id
    mock_new_invitation.invited_email = invited_email
    mock_new_invitation.status = InvitationStatus.PENDING

    with (
        patch(
            "app.api.modules.v1.organization.service.organization_service.check_user_permission",
            new_callable=AsyncMock,
        ) as mock_check_perm,
        patch(
            "app.api.modules.v1.organization.service.organization_service.OrganizationCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_org,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_inviter,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserCRUD.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get_by_email,
        patch(
            "app.api.modules.v1.organization.service.organization_service.UserOrganizationCRUD.get_user_organization",
            new_callable=AsyncMock,
        ) as mock_get_membership,
        patch(
            "app.api.modules.v1.organization.service.organization_service.InvitationCRUD.get_pending_invitation_for_email_and_org",
            new_callable=AsyncMock,
        ) as mock_get_pending,
        patch(
            "app.api.modules.v1.organization.service.organization_service.RoleCRUD.get_role_by_name_and_organization",
            new_callable=AsyncMock,
        ) as mock_get_role,
        patch(
            "app.api.modules.v1.organization.service.organization_service.InvitationCRUD.create_invitation",
            new_callable=AsyncMock,
        ) as mock_create_invitation,
        patch(
            "app.api.modules.v1.organization.service.organization_service.send_email",
        ) as _mock_send_email,
    ):
        mock_check_perm.return_value = True
        mock_get_org.return_value = mock_org
        mock_get_inviter.return_value = mock_inviter
        mock_get_by_email.return_value = mock_existing_user  # User exists
        # Soft-deleted membership is not returned by get_user_organization
        mock_get_membership.return_value = None
        mock_get_pending.return_value = None  # No pending invitation
        mock_get_role.return_value = mock_role
        mock_create_invitation.return_value = mock_new_invitation

        service = OrganizationService(mock_db)

        result = await service.send_invitation(
            background_tasks=background_tasks,
            organization_id=org_id,
            invited_email=invited_email,
            inviter_id=inviter_id,
            role_name="Member",
        )

        assert result is mock_new_invitation
        mock_get_by_email.assert_awaited_once_with(mock_db, invited_email)
        mock_get_membership.assert_awaited_once_with(
            mock_db, user_id=mock_existing_user.id, organization_id=org_id
        )
        mock_get_pending.assert_awaited_once_with(mock_db, invited_email, org_id)
        mock_create_invitation.assert_awaited_once()
