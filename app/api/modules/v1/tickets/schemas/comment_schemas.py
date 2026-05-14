"""
Comment Schemas
Pydantic schemas for comment-related API operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Image validation constants
MAX_IMAGES_PER_COMMENT = 5
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Comment content constraints
MAX_COMMENT_LENGTH = 3000  # ~500 words (average 6 chars per word)


class AttachmentInfo(BaseModel):
    """Schema for attachment metadata."""

    url: str = Field(..., description="URL of the attached file/photo")
    name: Optional[str] = Field(None, description="Original filename")
    type: Optional[str] = Field(None, description="MIME type (e.g., image/png, image/jpeg)")
    size: Optional[int] = Field(None, description="File size in bytes")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata (width, height for images, etc.)"
    )

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    """
    Schema for creating a new comment.

    Note: This is used for validation when content-type is application/json.
    For file uploads, use multipart/form-data with Form fields.
    """

    content: Optional[str] = Field(
        default=None,
        max_length=MAX_COMMENT_LENGTH,
        description="Comment text content (optional if images provided). "
        "Max 500 words (~3,000 characters).",
    )


class CommentUpdate(BaseModel):
    """
    Schema for updating an existing comment.

    Note: This is used for validation when content-type is application/json.
    For file uploads, use multipart/form-data with Form fields.
    """

    content: Optional[str] = Field(
        default=None,
        max_length=MAX_COMMENT_LENGTH,
        description="Updated comment text content. Max 500 words (~3,000 characters).",
    )


class UserSummary(BaseModel):
    """Minimal user info for comment responses."""

    id: UUID
    name: str
    email: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ParticipantSummary(BaseModel):
    """Minimal external participant info for comment responses."""

    id: UUID
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Schema for comment response."""

    comment_id: UUID
    ticket_id: UUID
    content: Optional[str] = None
    attachments: Optional[List[AttachmentInfo]] = None
    user_id: Optional[UUID] = None
    participant_id: Optional[UUID] = None
    mentioned_user_ids: Optional[List[UUID]] = None
    mentioned_participant_ids: Optional[List[UUID]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    user: Optional[UserSummary] = None
    participant: Optional[ParticipantSummary] = None

    # Computed fields for easy frontend consumption
    author_name: Optional[str] = Field(
        default=None, description="Display name (user.name or participant email/Guest)"
    )
    author_email: Optional[str] = Field(
        default=None, description="Email address (user.email or participant.email)"
    )
    author_avatar_url: Optional[str] = Field(
        default=None, description="Avatar URL (user.avatar_url or None for guest)"
    )
    is_guest: bool = Field(
        default=False, description="True if comment is from external participant"
    )

    # Formatted timestamp fields for frontend display
    date: Optional[str] = Field(
        default=None, description="Formatted date (DD/MM/YYYY) extracted from created_at"
    )
    time: Optional[str] = Field(
        default=None, description="Formatted time (HH:MM:SS) extracted from created_at"
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_comment(cls, comment) -> "CommentResponse":
        """Create response from Comment model with computed fields."""
        # Determine author info
        if comment.user:
            author_name = comment.user.name
            author_email = comment.user.email
            author_avatar_url = comment.user.avatar_url
            is_guest = False
        elif comment.participant:
            # External participants show as "Guest"
            author_name = "Guest"
            author_email = comment.participant.email
            author_avatar_url = None  # Frontend should show default guest avatar
            is_guest = True
        else:
            author_name = "Unknown"
            author_email = None
            author_avatar_url = None
            is_guest = False

        # Format date and time from created_at timestamp
        # Format: DD/MM/YYYY for date, HH:MM:SS for time
        date_str = comment.created_at.strftime("%d/%m/%Y")
        time_str = comment.created_at.strftime("%H:%M:%S")

        return cls(
            comment_id=comment.comment_id,
            ticket_id=comment.ticket_id,
            content=comment.content,
            attachments=comment.attachments,
            user_id=comment.user_id,
            participant_id=comment.participant_id,
            mentioned_user_ids=comment.mentioned_user_ids,
            mentioned_participant_ids=comment.mentioned_participant_ids,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
            user=UserSummary.model_validate(comment.user) if comment.user else None,
            participant=ParticipantSummary.model_validate(comment.participant)
            if comment.participant
            else None,
            author_name=author_name,
            author_email=author_email,
            author_avatar_url=author_avatar_url,
            is_guest=is_guest,
            date=date_str,
            time=time_str,
        )
