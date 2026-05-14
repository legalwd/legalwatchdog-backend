"""
Unit tests for Notification routes: /notifications
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from main import app


@pytest.fixture
def mock_user():
    """Create a mock user for testing"""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_notification():
    """Create a mock notification for testing"""
    return Notification(
        notification_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        notification_type=NotificationType.MENTION,
        title="Test Notification",
        message="This is a test notification",
        status=NotificationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client(mock_user):
    """Create test client with overridden dependencies"""
    from app.api.core.dependencies.auth import get_current_user

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestGetNotifications:
    """Test suite for GET /notifications endpoint"""

    @pytest.mark.asyncio
    async def test_get_notifications_success(self, client, mock_user, mock_notification):
        """Test successfully retrieving notifications with default pagination"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [mock_notification],
                "total": 1,
                "page": 1,
                "limit": 50,
                "unread_count": 1,
            },
        ):
            response = client.get("/api/v1/notifications")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert "data" in response_data
            assert "notifications" in response_data["data"]
            assert response_data["data"]["total"] == 1
            assert response_data["message"] == "Notifications retrieved successfully"

    @pytest.mark.asyncio
    async def test_get_notifications_with_filters(self, client, mock_user, mock_notification):
        """Test retrieving notifications with filters applied"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [mock_notification],
                "total": 1,
                "page": 1,
                "limit": 20,
                "unread_count": 1,
            },
        ):
            response = client.get(
                "/api/v1/notifications",
                params={
                    "page": 1,
                    "limit": 20,
                    "status_filter": "PENDING",
                    "notification_type": "MENTION",
                    "is_read": False,
                },
            )

            assert response.status_code == status.HTTP_200_OK
            assert len(response.json()["data"]["notifications"]) == 1

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(self, client, mock_user):
        """Test pagination parameters are correctly applied"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [],
                "total": 100,
                "page": 2,
                "limit": 25,
                "unread_count": 10,
            },
        ) as mock_service:
            response = client.get("/api/v1/notifications", params={"page": 2, "limit": 25})

            assert response.status_code == status.HTTP_200_OK
            call_args = mock_service.call_args
            assert call_args.kwargs["skip"] == 25
            assert call_args.kwargs["limit"] == 25


class TestGetNotificationStats:
    """Test suite for GET /notifications/stats endpoint"""

    @pytest.mark.asyncio
    async def test_get_notification_stats_success(self, client, mock_user):
        """Test successfully retrieving notification statistics"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_notification_stats",
            new_callable=AsyncMock,
            return_value={
                "total_notifications": 10,
                "unread_count": 3,
                "pending_count": 2,
                "by_type": {
                    "MENTION": 5,
                    "DATA_REVISION": 5,
                },
            },
        ):
            response = client.get("/api/v1/notifications/stats")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["data"]["total_notifications"] == 10
            assert response_data["data"]["unread_count"] == 3
            assert response_data["message"] == "Notification statistics retrieved successfully"


class TestMarkNotificationsRead:
    """Test suite for POST /notifications/mark-read endpoint"""

    @pytest.mark.asyncio
    async def test_mark_notifications_read_success(self, client, mock_user):
        """Test successfully marking multiple notifications as read"""
        notification_ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.mark_as_read",
            new_callable=AsyncMock,
            return_value=3,
        ):
            response = client.post(
                "/api/v1/notifications/mark-read",
                json={"notification_ids": notification_ids},
            )

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert "Marked 3 notification(s) as read" in response_data["message"]
            assert response_data["data"]["count"] == 3

    @pytest.mark.asyncio
    async def test_mark_single_notification_read(self, client, mock_user):
        """Test marking a single notification as read"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.mark_as_read",
            new_callable=AsyncMock,
            return_value=1,
        ):
            response = client.post(
                "/api/v1/notifications/mark-read",
                json={"notification_ids": [str(uuid.uuid4())]},
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["data"]["count"] == 1


class TestMarkAllRead:
    """Test suite for POST /notifications/mark-all-read endpoint"""

    @pytest.mark.asyncio
    async def test_mark_all_read_success(self, client, mock_user):
        """Test successfully marking all notifications as read"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.mark_all_as_read",
            new_callable=AsyncMock,
            return_value=5,
        ):
            response = client.post("/api/v1/notifications/mark-all-read")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert "Marked 5 notification(s) as read" in response_data["message"]
            assert response_data["data"]["count"] == 5

    @pytest.mark.asyncio
    async def test_mark_all_read_no_unread(self, client, mock_user):
        """Test marking all as read when there are no unread notifications"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.mark_all_as_read",
            new_callable=AsyncMock,
            return_value=0,
        ):
            response = client.post("/api/v1/notifications/mark-all-read")

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["data"]["count"] == 0


class TestGetNotification:
    """Test suite for GET /notifications/{notification_id} endpoint"""

    @pytest.mark.asyncio
    async def test_get_notification_success(self, client, mock_user, mock_notification):
        """Test successfully retrieving a single notification"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_notification_by_id",
            new_callable=AsyncMock,
            return_value=mock_notification,
        ):
            response = client.get(f"/api/v1/notifications/{mock_notification.notification_id}")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["message"] == "Notification retrieved successfully"
            assert "data" in response_data

    @pytest.mark.asyncio
    async def test_get_notification_not_found(self, client, mock_user):
        """Test getting a notification that doesn't exist"""
        from app.api.core.custom_exceptions.exceptions import NotFoundError

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_notification_by_id",
            new_callable=AsyncMock,
            side_effect=NotFoundError(message="Notification not found for the user"),
        ):
            response = client.get(f"/api/v1/notifications/{uuid.uuid4()}")

            assert response.status_code == 404
            assert "notification" in response.json()["message"].lower()


class TestGetNotificationWithContext:
    """Test suite for GET /notifications/{notification_id}/context endpoint"""

    @pytest.mark.asyncio
    async def test_get_notification_with_context_success(
        self, client, mock_user, mock_notification
    ):
        """Test successfully retrieving notification with full context"""
        mock_context = {
            "notification": mock_notification,
            "source": {"id": str(uuid.uuid4()), "name": "Test Source"},
            "organization": {"id": str(uuid.uuid4()), "name": "Test Org"},
        }

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_notification_with_context",
            new_callable=AsyncMock,
            return_value=mock_context,
        ):
            response = client.get(
                f"/api/v1/notifications/{mock_notification.notification_id}/context"
            )

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["message"] == "Notification context retrieved successfully"
            assert "notification" in response_data["data"]


class TestUpdateNotification:
    """Test suite for PATCH /notifications/{notification_id} endpoint"""

    @pytest.mark.asyncio
    async def test_update_notification_success(self, client, mock_user, mock_notification):
        """Test successfully updating a notification"""
        updated_notification = mock_notification
        updated_notification.status = NotificationStatus.READ

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.update_notification",
            new_callable=AsyncMock,
            return_value=updated_notification,
        ):
            response = client.patch(
                f"/api/v1/notifications/{mock_notification.notification_id}",
                json={"status": NotificationStatus.READ.value},
            )

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["message"] == "Notification updated successfully"

    @pytest.mark.asyncio
    async def test_update_notification_read_status(self, client, mock_user, mock_notification):
        """Test updating notification read status"""
        read_time = datetime.now(timezone.utc)
        updated_notification = mock_notification
        updated_notification.read_at = read_time

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.update_notification",
            new_callable=AsyncMock,
            return_value=updated_notification,
        ):
            response = client.patch(
                f"/api/v1/notifications/{mock_notification.notification_id}",
                json={"read_at": read_time.isoformat()},
            )

            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_update_notification_not_owned(self, client, mock_user):
        """Test updating a notification not owned by the user"""
        from app.api.core.custom_exceptions.exceptions import NotFoundError

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.update_notification",
            new_callable=AsyncMock,
            side_effect=NotFoundError(message="Notification not found for the user"),
        ):
            response = client.patch(
                f"/api/v1/notifications/{uuid.uuid4()}",
                json={"status": NotificationStatus.READ.value},
            )

            assert response.status_code == 404
            assert "notification" in response.json()["message"].lower()


class TestDeleteNotification:
    """Test suite for DELETE /notifications/{notification_id} endpoint"""

    @pytest.mark.asyncio
    async def test_delete_notification_success(self, client, mock_user, mock_notification):
        """Test successfully deleting a notification"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.delete_notification",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.delete(f"/api/v1/notifications/{mock_notification.notification_id}")

            assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_notification_not_found(self, client, mock_user):
        """Test deleting a notification that doesn't exist"""
        from app.api.core.custom_exceptions.exceptions import NotFoundError

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.delete_notification",
            new_callable=AsyncMock,
            side_effect=NotFoundError(message="Notification not found for the user"),
        ):
            response = client.delete(f"/api/v1/notifications/{uuid.uuid4()}")

            assert response.status_code == 404
            assert "notification" in response.json()["message"].lower()


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_get_notifications_empty_result(self, client, mock_user):
        """Test retrieving notifications when none exist"""
        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [],
                "total": 0,
                "page": 1,
                "limit": 50,
                "unread_count": 0,
            },
        ):
            response = client.get("/api/v1/notifications")

            assert response.status_code == status.HTTP_200_OK
            response_data = response.json()
            assert response_data["data"]["total"] == 0
            assert len(response_data["data"]["notifications"]) == 0

    @pytest.mark.asyncio
    async def test_mark_read_empty_list(self, client, mock_user):
        """Test marking notifications as read with empty list"""
        from app.api.core.custom_exceptions.exceptions import PermissionDeniedError

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.mark_as_read",
            new_callable=AsyncMock,
            side_effect=PermissionDeniedError(message="No notification IDs provided"),
        ):
            response = client.post("/api/v1/notifications/mark-read", json={"notification_ids": []})

            assert response.status_code == 403
            assert "no notification ids provided" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_get_notifications_with_organization_filter(self, client, mock_user):
        """Test filtering notifications by organization"""
        org_id = uuid.uuid4()

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [],
                "total": 0,
                "page": 1,
                "limit": 50,
                "unread_count": 0,
            },
        ):
            response = client.get("/api/v1/notifications", params={"organization_id": str(org_id)})

            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_notifications_with_source_filter(self, client, mock_user):
        """Test filtering notifications by source"""
        source_id = uuid.uuid4()

        with patch(
            "app.api.modules.v1.notifications.routes.notification_route.NotificationService.get_user_notifications",
            new_callable=AsyncMock,
            return_value={
                "notifications": [],
                "total": 0,
                "page": 1,
                "limit": 50,
                "unread_count": 0,
            },
        ):
            response = client.get("/api/v1/notifications", params={"source_id": str(source_id)})

            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_invalid_notification_id_format(self, client, mock_user):
        """Test endpoint with invalid UUID format"""
        response = client.get("/api/v1/notifications/invalid-uuid-format")

        assert response.status_code == 422
