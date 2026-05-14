import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.utils.role_hierarchy import RoleHierarchy, RoleLevel, validate_role_hierarchy


class TestRoleHierarchyGetLevel:
    """Test RoleHierarchy.get_role_level() method."""

    def test_get_owner_level(self):
        """Test that Owner role returns correct level."""
        assert RoleHierarchy.get_role_level("Owner") == RoleLevel.OWNER
        assert RoleHierarchy.get_role_level("Owner") == 4

    def test_get_admin_level(self):
        """Test that Admin role returns correct level."""
        assert RoleHierarchy.get_role_level("Admin") == RoleLevel.ADMIN
        assert RoleHierarchy.get_role_level("Admin") == 3

    def test_get_manager_level(self):
        """Test that Manager role returns correct level."""
        assert RoleHierarchy.get_role_level("Manager") == RoleLevel.MANAGER
        assert RoleHierarchy.get_role_level("Manager") == 2

    def test_get_member_level(self):
        """Test that Member role returns correct level."""
        assert RoleHierarchy.get_role_level("Member") == RoleLevel.MEMBER
        assert RoleHierarchy.get_role_level("Member") == 1

    def test_get_unknown_role_defaults_to_member(self):
        """Test that unknown roles default to Member level."""
        assert RoleHierarchy.get_role_level("UnknownRole") == RoleLevel.MEMBER
        assert RoleHierarchy.get_role_level("CustomRole") == 1


class TestRoleHierarchyCanManage:
    """Test can_manage_role with hierarchy levels."""

    """Test can_manage_role with hierarchy levels."""

    def test_owner_can_manage_admin(self):
        """Owner (4) can manage Admin (3)."""
        assert RoleHierarchy.can_manage_role(4, 3) is True
        """Owner (4) can manage Admin (3)."""
        assert RoleHierarchy.can_manage_role(4, 3) is True

    def test_admin_can_manage_manager(self):
        """Admin (3) can manage Manager (2)."""
        assert RoleHierarchy.can_manage_role(3, 2) is True

    def test_admin_can_manage_member(self):
        """Admin (3) can manage Member (1)."""
        assert RoleHierarchy.can_manage_role(3, 1) is True

    def test_manager_can_manage_member(self):
        """Manager (2) can manage Member (1)."""
        assert RoleHierarchy.can_manage_role(2, 1) is True

    def test_admin_cannot_manage_owner(self):
        """Admin (3) cannot manage Owner (4)."""
        assert RoleHierarchy.can_manage_role(3, 4) is False

    def test_manager_cannot_manage_admin(self):
        """Manager (2) cannot manage Admin (3)."""
        assert RoleHierarchy.can_manage_role(2, 3) is False

    def test_cannot_manage_same_level(self):
        """Admin (3) cannot manage Admin (3)."""
        assert RoleHierarchy.can_manage_role(3, 3) is False

    def test_member_cannot_manage_anyone(self):
        """Test that Member cannot manage any role."""
        assert RoleHierarchy.can_manage_role(1, 1) is False
        assert RoleHierarchy.can_manage_role(1, 2) is False
        assert RoleHierarchy.can_manage_role(1, 3) is False
        assert RoleHierarchy.can_manage_role(1, 4) is False


class TestRoleHierarchyCanAssign:
    """Test can_assign_role with hierarchy levels."""

    """Test can_assign_role with hierarchy levels."""

    def test_owner_can_assign_owner(self):
        """Owner (4) can assign Owner role (4)."""
        assert RoleHierarchy.can_assign_role("Owner", "Owner") is True

    def test_owner_can_assign_admin(self):
        """Owner (4) can assign Admin role (3)."""
        assert RoleHierarchy.can_assign_role("Owner", "Admin") is True

    def test_owner_can_assign_manager(self):
        """Owner (4) can assign Manager role (2)."""
        assert RoleHierarchy.can_assign_role("Owner", "Manager") is True

    def test_owner_can_assign_member(self):
        """Owner (4) can assign Member role (1)."""
        assert RoleHierarchy.can_assign_role("Owner", "Member") is True

    def test_admin_can_assign_manager(self):
        """Admin (3) can assign Manager role (2)."""
        assert RoleHierarchy.can_assign_role("Admin", "Manager") is True

    def test_admin_can_assign_member(self):
        """Admin (3) can assign Member role (1)."""
        assert RoleHierarchy.can_assign_role("Admin", "Member") is True

    def test_manager_can_assign_member(self):
        """Manager (2) can assign Member role (1)."""
        assert RoleHierarchy.can_assign_role("Manager", "Member") is True


@pytest.mark.asyncio
class TestValidateRoleHierarchy:
    """Test validate_role_hierarchy() function."""

    async def test_missing_new_role_name_for_assign_action(self):
        """Test that assign_role action requires new_role_name."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="assign_role",
                    new_role_name=None,
                )

            assert "New role name is required" in str(exc.value)

    async def test_user_not_member_of_organization(self):
        """Test that ValueError is raised when user is not a member."""
        db = AsyncMock()

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.return_value = None

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="manage",
                )

            assert "not a member of this organization" in str(exc.value)

    async def test_invalid_action(self):
        """Test that ValueError is raised for unknown action."""
        db = AsyncMock()

        user_membership = MagicMock()
        user_membership.role_id = uuid.uuid4()

        user_role = MagicMock()
        user_role.name = "Admin"
        user_role.id = user_membership.role_id

        target_membership = MagicMock()
        target_membership.role_id = uuid.uuid4()

        target_role = MagicMock()
        target_role.name = "Member"
        target_role.id = target_membership.role_id

        with patch(
            "app.api.modules.v1.organization.service.user_organization_service.UserOrganizationCRUD.get_user_organization"
        ) as mock_get_membership:
            mock_get_membership.side_effect = [user_membership, target_membership]

            db.get.side_effect = [user_role, target_role]

            with pytest.raises(ValueError) as exc:
                await validate_role_hierarchy(
                    db=db,
                    current_user_id=str(uuid.uuid4()),
                    target_user_id=str(uuid.uuid4()),
                    organization_id=str(uuid.uuid4()),
                    action="unknown_action",
                )

            assert "Unknown action" in str(exc.value)
