import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationUpdate,
)
from app.api.modules.v1.notifications.service.notification_service import NotificationService


@pytest.fixture
def fake_notification():
    return Notification(
        notification_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        notification_type=NotificationType.MENTION,
        title="Test Notification",
        message="This is a test",
        status=NotificationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_get_notification_by_id(fake_notification):
    """Test getting a notification by ID - FIXED: added user_id parameter"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_notification
    db.execute.return_value = mock_result

    result = await NotificationService.get_notification_by_id(
        db, fake_notification.notification_id, fake_notification.user_id
    )
    assert result == fake_notification
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_notifications(fake_notification):
    """Test getting user notifications - FIXED: added third mock for unread_count query"""
    db = AsyncMock()

    mock_result_notifications = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fake_notification]
    mock_result_notifications.scalars.return_value = mock_scalars

    mock_result_count = MagicMock()
    mock_result_count.scalar.return_value = 1

    mock_result_unread = MagicMock()
    mock_result_unread.scalar.return_value = 1

    db.execute.side_effect = [
        mock_result_notifications,
        mock_result_count,
        mock_result_unread,
    ]

    result = await NotificationService.get_user_notifications(db, fake_notification.user_id)

    assert result["notifications"] == [fake_notification]
    assert result["total"] == 1
    assert result["unread_count"] == 1
    assert result["page"] == 1
    assert result["limit"] == 50


@pytest.mark.asyncio
async def test_mark_as_read(fake_notification):
    """Test marking notifications as read"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fake_notification]
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result

    updated_count = await NotificationService.mark_as_read(
        db, [fake_notification.notification_id], fake_notification.user_id
    )
    assert updated_count == 1
    assert fake_notification.status == NotificationStatus.READ
    assert fake_notification.read_at is not None
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_all_as_read(fake_notification):
    """Test marking all notifications as read"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fake_notification]
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result

    updated_count = await NotificationService.mark_all_as_read(db, fake_notification.user_id)
    assert updated_count == 1
    assert fake_notification.status == NotificationStatus.READ
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_notification(fake_notification):
    """Test updating a notification"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_notification
    db.execute.return_value = mock_result

    update_data = NotificationUpdate(
        status=NotificationStatus.SENT, read_at=datetime.now(timezone.utc)
    )

    updated = await NotificationService.update_notification(
        db, fake_notification.notification_id, fake_notification.user_id, update_data
    )
    assert updated.status == NotificationStatus.SENT
    assert updated.read_at is not None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_notification)


@pytest.mark.asyncio
async def test_delete_notification(fake_notification):
    """Test deleting a notification - FIXED: service returns None, not a boolean"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_notification
    db.execute.return_value = mock_result

    result = await NotificationService.delete_notification(
        db, fake_notification.notification_id, fake_notification.user_id
    )

    assert result is None
    db.delete.assert_called_once_with(fake_notification)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_unread_count(fake_notification):
    """Test getting unread count"""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3
    db.execute.return_value = mock_result

    count = await NotificationService.get_unread_count(db, fake_notification.user_id)
    assert count == 3
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_notification_stats(fake_notification):
    """Test getting notification statistics"""
    db = AsyncMock()

    mock_result_total = MagicMock()
    mock_result_total.scalar.return_value = 5

    mock_result_unread = MagicMock()
    mock_result_unread.scalar.return_value = 2

    mock_result_pending = MagicMock()
    mock_result_pending.scalar.return_value = 1

    mock_result_by_type = MagicMock()
    mock_result_by_type.all.return_value = [(NotificationType.MENTION, 3)]

    db.execute.side_effect = [
        mock_result_total,
        mock_result_unread,
        mock_result_pending,
        mock_result_by_type,
    ]

    stats = await NotificationService.get_notification_stats(db, fake_notification.user_id)
    assert stats["total_notifications"] == 5
    assert stats["unread_count"] == 2
    assert stats["pending_count"] == 1
    assert stats["by_type"] == {NotificationType.MENTION: 3}
