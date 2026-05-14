# tests/modules/v1/users/service/test_role_service.py

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.users.service.role import RoleCRUD
from app.api.modules.v1.users.service.role_template_service import RoleTemplateCRUD


@pytest.mark.asyncio
async def test_create_admin_role_success():
    """Test successful creation of admin role from template."""

    db = AsyncMock()
    org_id = uuid4()
    role_id = uuid4()

    # Mock the template
    mock_template = MagicMock()
    mock_template.display_name = "Admin"
    mock_template.description = "Administrator with full permissions"
    mock_template.permissions = {"manage_users": True, "view_projects": True}
    mock_template.hierarchy_level = 3

    # Mock the created role
    mock_role = MagicMock()
    mock_role.id = role_id
    mock_role.name = "Admin"
    mock_role.organization_id = org_id
    mock_role.hierarchy_level = 3
    mock_role.template_name = "admin"
    mock_role.permissions = mock_template.permissions.copy()

    # Patch at the correct import location
    with patch(
        "app.api.modules.v1.users.service.role.RoleTemplateCRUD.get_template_by_name"
    ) as mock_get_template:
        mock_get_template.return_value = mock_template

        with patch("app.api.modules.v1.users.service.role.Role") as mock_role_class:
            mock_role_class.return_value = mock_role

            result = await RoleCRUD.create_admin_role(
                db=db,
                organization_id=org_id,
            )

    # Verify get_template_by_name was called correctly
    mock_get_template.assert_awaited_once_with(db, "admin")

    # Verify Role was instantiated correctly
    mock_role_class.assert_called_once()
    call_kwargs = mock_role_class.call_args[1]
    assert call_kwargs["name"] == "Admin"
    assert call_kwargs["organization_id"] == org_id
    assert call_kwargs["hierarchy_level"] == 3
    assert call_kwargs["template_name"] == "admin"

    # Verify database operations
    db.add.assert_called_once_with(mock_role)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(mock_role)

    # Verify result
    assert result is mock_role
    assert result.name == "Admin"
    assert result.hierarchy_level == 3


@pytest.mark.asyncio
async def test_create_admin_role_failure():
    """Test that an exception is raised when DB operations fail."""

    db = AsyncMock()
    org_id = uuid4()

    # Mock template
    mock_template = MagicMock()
    mock_template.name = "admin"
    mock_template.display_name = "Admin"
    mock_template.description = "Administrator with full permissions"
    mock_template.permissions = {"manage_users": True, "invite_users": True}
    mock_template.hierarchy_level = 3

    # Mock Role constructor
    mock_role_instance = MagicMock()
    with patch.object(RoleTemplateCRUD, "get_template_by_name", return_value=mock_template):
        with patch("app.api.modules.v1.users.service.role.Role", return_value=mock_role_instance):
            # Make flush fail
            db.flush.side_effect = Exception("DB crash")
    org_id = uuid4()

    # Mock template
    mock_template = MagicMock()
    mock_template.name = "admin"
    mock_template.display_name = "Admin"
    mock_template.description = "Administrator with full permissions"
    mock_template.permissions = {"manage_users": True, "invite_users": True}
    mock_template.hierarchy_level = 3

    # Mock Role constructor
    mock_role_instance = MagicMock()
    with patch.object(RoleTemplateCRUD, "get_template_by_name", return_value=mock_template):
        with patch("app.api.modules.v1.users.service.role.Role", return_value=mock_role_instance):
            # Make flush fail
            db.flush.side_effect = Exception("DB crash")

            with pytest.raises(Exception) as exc:
                await RoleCRUD.create_admin_role(
                    db=db,
                    organization_id=org_id,
                )
            with pytest.raises(Exception) as exc:
                await RoleCRUD.create_admin_role(
                    db=db,
                    organization_id=org_id,
                )

    # Check the error message matches what your code actually raises
    assert "Failed to create role from template 'admin'" in str(exc.value)
    # Check the error message matches what your code actually raises
    assert "Failed to create role from template 'admin'" in str(exc.value)
