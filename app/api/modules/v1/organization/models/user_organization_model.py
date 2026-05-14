import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.roles_model import Role
    from app.api.modules.v1.users.models.users_model import User


class UserOrganization(SQLModel, table=True):
    """
    Join table for many-to-many relationship between users and organizations.
    Each record represents a user's membership in an organization with a specific role.
    """

    __tablename__ = "user_organizations"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)

    organization_id: uuid.UUID = Field(foreign_key="organizations.id", nullable=False, index=True)

    role_id: uuid.UUID = Field(
        foreign_key="roles.id",
        nullable=False,
        index=True,
        description="Role the user has in this organization",
    )

    is_active: bool = Field(
        default=True, nullable=False, description="Whether this membership is active"
    )

    title: Optional[str] = Field(
        None,
        max_length=255,
        description="User's job title in this organization (e.g., 'Administrative Officer')",
    )

    department: Optional[str] = Field(
        None, max_length=100, description="User's department (e.g., 'Compliance team')"
    )

    joined_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the user joined this organization",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    is_deleted: bool = Field(default=False, nullable=False, description="Soft delete flag")

    deleted_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
        description="When the membership was soft deleted",
    )

    user: "User" = Relationship(
        back_populates="organization_memberships", sa_relationship_kwargs={"passive_deletes": True}
    )

    organization: "Organization" = Relationship(
        back_populates="user_memberships", sa_relationship_kwargs={"passive_deletes": True}
    )

    role: "Role" = Relationship(sa_relationship_kwargs={"passive_deletes": True})


Index(
    "ix_user_org_active_memberships",
    UserOrganization.user_id,
    UserOrganization.is_active,
    postgresql_where=UserOrganization.is_deleted.is_(False),
)
