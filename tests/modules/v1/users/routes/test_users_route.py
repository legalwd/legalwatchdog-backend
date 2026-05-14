"""Tests for user profile routes."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.routes.users_route import (
    update_user_profile,
    upload_user_profile_picture,
)
from app.api.modules.v1.users.schemas.user_profile_schema import UpdateUserProfileRequest


@pytest.mark.asyncio
async def test_update_user_profile_success():
    """Test successful user profile update."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "test@example.com"
    mock_current_user.name = "Old Name"
    mock_current_user.avatar_url = None

    payload = UpdateUserProfileRequest(name="New Name", avatar_url="https://example.com/avatar.png")

    mock_result = {
        "id": str(mock_current_user.id),
        "email": mock_current_user.email,
        "name": "New Name",
        "avatar_url": "https://example.com/avatar.png",
        "is_active": True,
        "is_verified": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

    with patch(
        "app.api.modules.v1.users.service.user.UserCRUD.update_user_profile",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_update.return_value = mock_result

        response = await update_user_profile(
            payload=payload, current_user=mock_current_user, db=mock_db
        )

        assert response.status_code == status.HTTP_200_OK
        data = json.loads(response.body.decode())
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Profile updated successfully"
        assert data["data"]["name"] == "New Name"
        assert data["data"]["avatar_url"] == "https://example.com/avatar.png"


@pytest.mark.asyncio
async def test_update_user_profile_no_fields():
    """Test update with no fields provided."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    payload = UpdateUserProfileRequest(name=None, avatar_url=None)

    from app.api.core.custom_exceptions.exceptions import NoFieldsToUpdateError

    with patch(
        "app.api.modules.v1.users.service.user.UserCRUD.update_user_profile",
        new_callable=AsyncMock,
    ) as mock_update:
        mock_update.side_effect = NoFieldsToUpdateError(message="No fields to update")

        with pytest.raises(NoFieldsToUpdateError) as exc:
            await update_user_profile(payload=payload, current_user=mock_current_user, db=mock_db)

        assert "No fields to update" in str(exc.value)
        assert exc.value.code == "NO_FIELDS_TO_UPDATE"


@pytest.mark.asyncio
async def test_upload_user_profile_picture_success():
    """Test successful profile picture upload."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    # Mock file upload
    mock_file = MagicMock()
    mock_file.filename = "test.jpg"
    mock_file.content_type = "image/jpeg"
    mock_file.read = AsyncMock(return_value=b"fake image data")

    expected_url = f"http://localhost:9001/legalwatch-staging-profile/{mock_current_user.id}/12345678-1234-5678-9012-123456789012.jpg"
    mock_result = {"profile_picture_url": expected_url}

    with patch(
        "app.api.modules.v1.users.service.user.UserCRUD.upload_profile_picture",
        new_callable=AsyncMock,
    ) as mock_upload:
        mock_upload.return_value = mock_result

        response = await upload_user_profile_picture(
            file=mock_file, current_user=mock_current_user, db=mock_db
        )

        assert response.status_code == status.HTTP_200_OK
        data = json.loads(response.body.decode())
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Profile picture uploaded successfully"
        assert "profile_picture_url" in data["data"]

        mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_upload_profile_picture_invalid_type():
    """Test upload with invalid file type."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)

    mock_file = MagicMock()
    mock_file.content_type = "text/plain"
    mock_file.read = AsyncMock(return_value=b"fake image data")  # Make read awaitable

    from app.api.core.custom_exceptions.exceptions import InvalidFileTypeError

    with patch(
        "app.api.modules.v1.users.service.user.UserCRUD.upload_profile_picture",
        new_callable=AsyncMock,
    ) as mock_upload:
        # Service now handles validation, so we mock it to raise the exception
        mock_upload.side_effect = InvalidFileTypeError(
            message="Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed."
        )

        with pytest.raises(InvalidFileTypeError) as exc:
            await upload_user_profile_picture(
                file=mock_file, current_user=mock_current_user, db=mock_db
            )

    assert "Invalid file type" in str(exc.value)
    assert exc.value.code == "INVALID_FILE_TYPE"
