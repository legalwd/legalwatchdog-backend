import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, text
from sqlmodel import Field, Relationship, SQLModel

from app.api.core.config import settings


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.roles_model import Role
    from app.api.modules.v1.users.models.users_model import User


class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    organization_id: uuid.UUID = Field(foreign_key="organizations.id", index=True, nullable=False)
    organization_name: str = Field(max_length=255, index=True, nullable=True)
    invited_email: str = Field(max_length=255, index=True, nullable=False)
    inviter_id: uuid.UUID = Field(foreign_key="users.id", index=True, nullable=False)
    token: str = Field(max_length=255, unique=True, index=True, nullable=False)
    role_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="roles.id", index=True, nullable=True
    )

    status: InvitationStatus = Field(default=InvitationStatus.PENDING, nullable=False)

    role_name: Optional[str] = Field(
        default=None,
        max_length=50,
        nullable=True,
        description="Name of the role assigned to the invited user",
    )

    accepted_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True), default=None
    )

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: (
            datetime.now(timezone.utc) + timedelta(minutes=settings.INVITATION_TOKEN_EXPIRE_MINUTES)
        ),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
        ),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: "Organization" = Relationship(
        back_populates="invitations", sa_relationship_kwargs={"passive_deletes": True}
    )

    inviter: "User" = Relationship(
        back_populates="sent_invitations", sa_relationship_kwargs={"passive_deletes": True}
    )

    role: Optional["Role"] = Relationship(
        back_populates="invitations", sa_relationship_kwargs={"passive_deletes": True}
    )
