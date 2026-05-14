"""Tests for organization member routes."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.modules.v1.organization.routes.organization_route import (
    delete_member,
    update_member_details,
)
from app.api.modules.v1.organization.schemas.member_schema import UpdateMemberRequest
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_update_member_details_success():
    """Test successful member details update."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    payload = UpdateMemberRequest(
        name="New Name",
        email="new@example.com",
        department="Engineering",
        title="Senior Engineer",
    )

    updated_user = MagicMock(spec=User)
    updated_user.id = user_id
    updated_user.name = payload.name
    updated_user.email = payload.email

    updated_membership = MagicMock()
    updated_membership.department = payload.department
    updated_membership.title = payload.title

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = True

        with patch(
            "app.api.modules.v1.organization.routes.organization_route.validate_role_hierarchy",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = (True, "", MagicMock(), MagicMock())

            with patch(
                "app.api.modules.v1.organization.routes.organization_route.UserOrganizationCRUD.update_member_details",
                new_callable=AsyncMock,
            ) as mock_update:
                mock_update.return_value = (updated_user, updated_membership)

                response = await update_member_details(
                    organization_id=org_id,
                    user_id=user_id,
                    payload=payload,
                    current_user=mock_current_user,
                    db=mock_db,
                )

                body = json.loads(response.body)
                assert body["status"] == "SUCCESS"
                assert body["message"] == "Member details updated successfully"
                assert body["data"]["name"] == "New Name"
                assert body["data"]["email"] == "new@example.com"
                assert body["data"]["department"] == "Engineering"
                assert body["data"]["title"] == "Senior Engineer"

                mock_update.assert_called_once()
                call_args = mock_update.call_args[1]
                assert call_args["organization_id"] == org_id
                assert call_args["user_id"] == user_id
                assert call_args["user_updates"] == {
                    "name": "New Name",
                    "email": "new@example.com",
                }
                assert call_args["membership_updates"] == {
                    "department": "Engineering",
                    "title": "Senior Engineer",
                }


@pytest.mark.asyncio
async def test_update_member_details_permission_denied():
    """Test update member details without permission."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = UpdateMemberRequest(name="New Name")

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = False

        response = await update_member_details(
            organization_id=org_id,
            user_id=user_id,
            payload=payload,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "do not have permission" in response.body.decode()


@pytest.mark.asyncio
async def test_update_member_details_no_fields():
    """Test update with no fields provided."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = UpdateMemberRequest()

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = True

        with patch(
            "app.api.modules.v1.organization.routes.organization_route.validate_role_hierarchy",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = (True, "", MagicMock(), MagicMock())

            response = await update_member_details(
                organization_id=org_id,
                user_id=user_id,
                payload=payload,
                current_user=mock_current_user,
                db=mock_db,
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "No fields provided" in response.body.decode()


@pytest.mark.asyncio
async def test_delete_member_success():
    """Test successful member deletion."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = True

        with patch(
            "app.api.modules.v1.organization.routes.organization_route.validate_role_hierarchy",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = (True, "", MagicMock(), MagicMock())

            with patch(
                "app.api.modules.v1.organization.routes.organization_route.UserOrganizationCRUD.soft_delete_member",
                new_callable=AsyncMock,
            ) as mock_delete:
                response = await delete_member(
                    organization_id=org_id,
                    user_id=user_id,
                    current_user=mock_current_user,
                    db=mock_db,
                )

                assert response.status_code == status.HTTP_204_NO_CONTENT
                mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_member_permission_denied():
    """Test delete member without permission."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = False

        response = await delete_member(
            organization_id=org_id,
            user_id=user_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_delete_member_self_deletion():
    """Test that users cannot delete themselves."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    org_id = uuid.uuid4()

    with patch(
        "app.api.modules.v1.organization.routes.organization_route.check_user_permission",
        new_callable=AsyncMock,
    ) as mock_check_perm:
        mock_check_perm.return_value = True

        response = await delete_member(
            organization_id=org_id,
            user_id=mock_current_user.id,
            current_user=mock_current_user,
            db=mock_db,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "cannot delete yourself" in response.body.decode().lower()
