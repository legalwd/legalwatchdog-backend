import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class RoleTemplate(SQLModel, table=True):
    """
    Role templates stored in database.
    These serve as blueprints for creating organization-specific roles.
    """

    __tablename__ = "role_templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    name: str = Field(
        max_length=50,
        nullable=False,
        unique=True,
        index=True,
        description="Unique template name (e.g., 'owner', 'admin', 'manager', 'member')",
    )

    display_name: str = Field(
        max_length=100, nullable=False, description="Human-readable name for display"
    )

    description: Optional[str] = Field(
        default=None, max_length=500, description="Template description"
    )

    permissions: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
        description="Permission set for this role template",
    )

    is_system: bool = Field(
        default=True,
        nullable=False,
        description="Whether this is a system-defined template (cannot be deleted)",
    )

    hierarchy_level: int = Field(
        default=1,
        nullable=False,
        description="Role hierarchy level. Owner=4, Admin=3, Manager=2, Member=1",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
