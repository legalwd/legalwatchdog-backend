import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Index, String
from sqlmodel import Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.users.models.users_model import User


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    READ = "READ"


class NotificationType(str, Enum):
    """Types of notifications for different source contexts."""

    MENTION = "MENTION"
    CHANGE_DETECTED = "CHANGE_DETECTED"
    SCRAPE_FAILED = "SCRAPE_FAILED"
    SPECIALIST_REQUEST = "SPECIALIST_REQUEST"


class Notification(SQLModel, table=True):
    """
    Notification model for storing user notifications with full context.

    Attributes:
        notification_id: Unique identifier for the notification
        user_id: User who receives this notification
        notification_type: Type of notification (revision, change, etc.)
        title: Short title/subject of the notification
        message: Detailed notification message
        status: Current status (PENDING, SENT, FAILED, READ)

        revision_id: Optional link to data revision
        source_id: Optional link to source
        organization_id: Optional link to organization
        change_diff_id: Optional link to change diff
        specialist_hire_id: Optional link to specialist hire

        action_url: Direct URL to navigate to relevant context

        # Timestamps
        created_at: When notification was created
        sent_at: When notification was sent
        read_at: When notification was read
    """

    __tablename__ = "revision_notifications"

    # SQLModel handles the UUID primary key automatically
    notification_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    revision_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("data_revisions.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        description="Link to data revision if applicable",
    )
    user_id: uuid.UUID = Field(foreign_key="users.id")

    message: str

    status: NotificationStatus = Field(
        sa_column=sa.Column(String, nullable=False, index=True), default=NotificationStatus.PENDING
    )

    title: str = Field(max_length=255, nullable=False, description="Short notification title")

    source_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="sources.id",
        index=True,
        description="Link to source if applicable",
    )

    notification_type: NotificationType = Field(
        sa_column=sa.Column(
            sa.Enum(NotificationType, name="notificationtype"),
            nullable=False,
        ),
        description="Type of notification for categorization",
    )

    organization_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="organizations.id",
        index=True,
        description="Link to organization if applicable",
    )

    jurisdiction_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="jurisdictions.id",
        index=True,
        description="Link to jurisdiction if applicable",
    )

    change_diff_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="change_diff.diff_id",
        index=True,
        description="Link to change diff if applicable",
    )

    specialist_hire_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="specialist_hires.id",
        index=True,
        description="Link to specialist hire if applicable",
    )

    action_url: Optional[str] = Field(
        default=None, max_length=1000, description="Direct URL to navigate to the relevant context"
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    sent_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the notification was sent",
    )

    read_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the notification was read",
    )

    user: Optional["User"] = Relationship(
        back_populates="notifications", sa_relationship_kwargs={"lazy": "joined"}
    )


Index(
    "ix_notifications_user_status",
    Notification.user_id,
    Notification.status,
    postgresql_where=Notification.read_at.is_(None),
)

Index("ix_notifications_user_created", Notification.user_id, Notification.created_at.desc())

Index(
    "ix_notifications_type_created", Notification.notification_type, Notification.created_at.desc()
)

Index(
    "ix_notifications_unread", Notification.user_id, postgresql_where=Notification.read_at.is_(None)
)
