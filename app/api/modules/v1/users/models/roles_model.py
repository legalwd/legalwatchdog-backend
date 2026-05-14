import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.organization_model import Organization


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_role_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    organization_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="organizations.id",
        nullable=True,
        index=True,
        description="Null for global roles, UUID for organization-specific roles",
    )

    name: str = Field(max_length=50, nullable=False, index=True)

    description: Optional[str] = Field(default=None, max_length=500)

    permissions: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    hierarchy_level: int = Field(
        default=1, ge=1, le=10, description="Role hierarchy level (1=lowest, 10=highest)"
    )

    template_name: Optional[str] = Field(
        default=None, max_length=50, description="Name of template used to create this role"
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: "Organization" = Relationship(back_populates="roles")
    invitations: list["Invitation"] = Relationship(
        back_populates="role", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
