from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
)
from app.api.modules.v1.users.service.user import UserCRUD


@pytest.mark.asyncio
async def test_create_admin_user_success():
    """Test that admin user is created successfully."""

    db = AsyncMock()

    mock_user_instance = MagicMock()
    mock_user_instance.id = uuid4()
    mock_user_instance.email = "admin@example.com"
    mock_user_instance.organization_id = uuid4()

    with patch(
        "app.api.modules.v1.users.service.user.User",
        return_value=mock_user_instance,
    ):
        result = await UserCRUD.create_admin_user(
            db=db,
            email="admin@example.com",
            name="Admin User",
            hashed_password="hashed",
            organization_id=uuid4(),
            role_id=uuid4(),
        )

    db.add.assert_called_once_with(mock_user_instance)
    db.flush.assert_awaited()
    db.refresh.assert_awaited_with(mock_user_instance)

    assert result is mock_user_instance
    assert result.email == "admin@example.com"


@pytest.mark.asyncio
async def test_create_admin_user_failure():
    """Test ProcessingError is raised when DB operation fails."""

    db = AsyncMock()
    db.flush.side_effect = Exception("DB error")

    with pytest.raises(ProcessingError) as exc:
        await UserCRUD.create_admin_user(
            db=db,
            email="admin@example.com",
            name="Admin User",
            hashed_password="hashed",
            organization_id=uuid4(),
            role_id=uuid4(),
        )

    assert "unable to create the admin account" in str(exc.value).lower()
    assert exc.value.code == "PROCESSING_ERROR"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_user_active_status_not_found():
    """Test NotFoundError is raised when user does not exist."""
    db = AsyncMock()
    db.get.return_value = None

    with pytest.raises(NotFoundError) as exc:
        await UserCRUD.set_user_active_status(db, uuid4(), True)

    assert "doesn't exist" in str(exc.value)
    assert exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_user_role_org_mismatch():
    """Test PermissionDeniedError is raised on organization mismatch."""
    db = AsyncMock()

    mock_user = MagicMock()
    mock_user.organization_id = uuid4()

    mock_role = MagicMock()
    mock_role.organization_id = uuid4()  # Different org

    db.get.side_effect = [mock_user, mock_role]

    with pytest.raises(PermissionDeniedError) as exc:
        await UserCRUD.update_user_role(db, uuid4(), uuid4())

    assert "different organization" in str(exc.value)
    assert exc.value.code == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_get_user_profile_not_found():
    """Test NotFoundError in get_user_profile."""
    db = AsyncMock()
    service = UserCRUD(db)

    with patch(
        "app.api.modules.v1.users.service.user.UserCRUD.get_by_id", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        with pytest.raises(NotFoundError) as exc:
            await service.get_user_profile(uuid4())

        assert "profile could not be found" in str(exc.value)
        assert exc.value.code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_upload_profile_picture_success():
    """Test successful profile picture upload."""
    db = AsyncMock()
    service = UserCRUD(db)
    user_id = uuid4()

    file_content = b"fake image content"
    filename = "profile.jpg"
    content_type = "image/jpeg"

    # Patch source modules because imports are local to the function
    with patch(
        "app.api.modules.v1.scraping.storage.minio_storage.upload_profile_picture"
    ) as mock_minio_upload:
        with patch(
            "app.api.modules.v1.users.service.user.UserCRUD.update_user", new_callable=AsyncMock
        ) as mock_update:
            with patch("app.api.core.config.settings") as mock_settings:
                mock_settings.MINIO_PROFILE_BUCKET = "profiles"
                mock_settings.MINIO_PUBLIC_URL = "http://minio.local"
                mock_settings.MINIO_SECURE = False
                mock_settings.MINIO_ENDPOINT = "localhost:9000"

                result = await service.upload_profile_picture(
                    user_id=user_id,
                    file_content=file_content,
                    filename=filename,
                    content_type=content_type,
                )

                assert result["profile_picture_url"].startswith("http")
                mock_minio_upload.assert_called_once()
                mock_update.assert_called_once()
                db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_profile_picture_invalid_type():
    """Test InvalidFileTypeError in upload_profile_picture."""
    db = AsyncMock()
    service = UserCRUD(db)

    from app.api.core.custom_exceptions.exceptions import InvalidFileTypeError

    with pytest.raises(InvalidFileTypeError) as exc:
        await service.upload_profile_picture(
            user_id=uuid4(), file_content=b"content", filename="file.txt", content_type="text/plain"
        )

    assert "Invalid file type" in str(exc.value)
    assert exc.value.code == "INVALID_FILE_TYPE"


@pytest.mark.asyncio
async def test_upload_profile_picture_too_large():
    """Test FileTooLargeError in upload_profile_picture."""
    db = AsyncMock()
    service = UserCRUD(db)

    from app.api.core.custom_exceptions.exceptions import FileTooLargeError

    # Create content larger than 5MB
    large_content = b"x" * (5 * 1024 * 1024 + 1)

    with pytest.raises(FileTooLargeError) as exc:
        await service.upload_profile_picture(
            user_id=uuid4(),
            file_content=large_content,
            filename="large.jpg",
            content_type="image/jpeg",
        )

    assert "File too large" in str(exc.value)
    assert exc.value.code == "FILE_TOO_LARGE"
