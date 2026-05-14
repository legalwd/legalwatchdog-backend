import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.users.models.users_model import User


class ProjectUser(SQLModel, table=True):
    """
    Table linking projects to users.
    """

    __tablename__ = "project_users"

    user_id: uuid.UUID = Field(foreign_key="users.id", primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="projects.id", primary_key=True, ondelete="CASCADE")
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    project: Optional["Project"] = Relationship(back_populates="project_users")
    user: Optional["User"] = Relationship(back_populates="project_users")
