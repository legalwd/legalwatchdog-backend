import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.organization.models import Organization
    from app.api.modules.v1.users.models import User


class Role(SQLModel, table=True):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_org_role_name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    organization_id: uuid.UUID = Field(foreign_key="organizations.id", nullable=False, index=True)

    name: str = Field(max_length=50, nullable=False, index=True)

    description: Optional[str] = Field(default=None, max_length=500)

    permissions: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: "Organization" = Relationship(back_populates="roles")
    users: list["User"] = Relationship(back_populates="role")
