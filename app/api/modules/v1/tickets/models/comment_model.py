import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Column, DateTime, Index, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket
    from app.api.modules.v1.users.models.users_model import User


class Comment(SQLModel, table=True):
    """
    Comment model for storing comments from both internal users and external participants.

    Comments can be made by:
    1. Internal users (user_id is set, participant_id is null)
    2. External participants (participant_id is set, user_id is null)

    Attributes:
        comment_id: Unique identifier for the comment
        user_id: Internal user who created the comment (nullable)
        participant_id: External participant who created the comment (nullable)
        content: The comment text content (optional if attachments are provided)
        mentioned_user_ids: List of internal user IDs mentioned in the comment
        mentioned_participant_ids: List of external participant IDs mentioned in the comment
        ticket_id: Link to ticket
        created_at: When comment was created
        updated_at: When comment was last updated
        deleted_at: Soft delete timestamp
    """

    __tablename__ = "comments"

    comment_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="Internal user who created the comment (null if external participant)",
    )

    participant_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="external_participants.id",
        index=True,
        nullable=True,
        description="External participant who created the comment (null if internal user)",
    )

    content: Optional[str] = Field(
        default=None,
        sa_column=sa.Column(Text, nullable=True),
        description="Comment text content (optional if attachments provided)",
    )

    attachments: Optional[List[dict]] = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
        description="List of attached files/photos with metadata (url, type, name, size, etc.)",
    )

    mentioned_user_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
        description="List of internal user IDs mentioned in this comment",
    )

    mentioned_participant_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
        description="List of external participant IDs mentioned in this comment",
    )

    ticket_id: uuid.UUID = Field(
        foreign_key="tickets.id",
        index=True,
        nullable=False,
        description="Link to ticket",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When the comment was last updated",
    )

    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Soft delete timestamp",
    )

    user: Optional["User"] = Relationship(back_populates="comments")
    participant: Optional["ExternalParticipant"] = Relationship(back_populates="comments")
    ticket: "Ticket" = Relationship(back_populates="comments")


Index("ix_comments_user_created", Comment.user_id, Comment.created_at.desc())
Index("ix_comments_participant_created", Comment.participant_id, Comment.created_at.desc())
Index("ix_comments_ticket", Comment.ticket_id)
Index("ix_comments_active", Comment.comment_id, postgresql_where=Comment.deleted_at.is_(None))
