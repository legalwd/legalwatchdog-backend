import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.notifications.models.revision_notification import (
    NotificationStatus,
    NotificationType,
)


class NotificationBase(BaseModel):
    """Base notification schema with common fields."""

    notification_type: NotificationType
    title: str = Field(..., max_length=255)
    message: str

    revision_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None
    jurisdiction_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    change_diff_id: Optional[uuid.UUID] = None

    action_url: Optional[str] = Field(None, max_length=1000)


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""

    status: Optional[NotificationStatus] = None
    read_at: Optional[datetime] = None


class NotificationMarkRead(BaseModel):
    """Schema for marking notification(s) as read."""

    notification_ids: List[uuid.UUID]


class NotificationResponse(NotificationBase):
    """Response schema for a single notification."""

    notification_id: uuid.UUID
    user_id: uuid.UUID
    status: NotificationStatus

    created_at: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Response schema for list of notifications with pagination."""

    notifications: List[NotificationResponse]
    total: int
    page: int
    limit: int
    unread_count: int


class NotificationStats(BaseModel):
    """Statistics about user notifications."""

    total_notifications: int
    unread_count: int
    pending_count: int
    by_type: Dict[str, int]


class NotificationFilter(BaseModel):
    """Filter parameters for querying notifications."""

    status: Optional[NotificationStatus] = None
    notification_type: Optional[NotificationType] = None
    is_read: Optional[bool] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None

    organization_id: Optional[uuid.UUID] = None
    source_id: Optional[uuid.UUID] = None


class NotificationContextResponse(BaseModel):
    """
    Response with notification and full context for navigation.
    Includes related entities for direct navigation.
    """

    notification: NotificationResponse

    revision: Optional[Dict] = None
    source: Optional[Dict] = None
    organization: Optional[Dict] = None
    change_diff: Optional[Dict] = None
