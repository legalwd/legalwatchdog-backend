import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_user_model import ProjectUser
    from app.api.modules.v1.tickets.models.ticket_model import Ticket


class Project(SQLModel, table=True):
    """
    Main Project table - represents a high-level container for monitoring.
    """

    __tablename__ = "projects"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    org_id: uuid.UUID = Field(
        foreign_key="organizations.id",
        index=True,
        description="Organization that owns this project",
    )
    title: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    master_prompt: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="High-level AI prompt for the entire project",
    )
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    organization: Optional["Organization"] = Relationship(back_populates="projects")
    project_users: List["ProjectUser"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    jurisdictions: List["Jurisdiction"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    tickets: List["Ticket"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    specialist_hires: List["SpecialistHire"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
