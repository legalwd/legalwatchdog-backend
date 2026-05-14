from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.users.models.users_model import User


class SpecialistHire(SQLModel, table=True):
    """
    Database model for storing specialist hire requests.

    Tracks company information and specialist requirements for
    immigration and global mobility services.
    """

    __tablename__ = "specialist_hires"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_name: str = Field(nullable=False, max_length=255)
    company_email: str = Field(nullable=False, max_length=255)
    industry: str = Field(nullable=False, max_length=255)
    brief_description: str = Field(nullable=False)

    project_id: Optional[UUID] = Field(default=None, foreign_key="projects.id")
    jurisdiction_id: Optional[UUID] = Field(default=None, foreign_key="jurisdictions.id")
    user_id: UUID = Field(nullable=False, foreign_key="users.id")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    is_active: bool = Field(default=True, nullable=False)
    deactivated_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )

    user: "User" = Relationship(back_populates="specialist_hires")
    project: Optional["Project"] = Relationship(back_populates="specialist_hires")
    jurisdiction: Optional["Jurisdiction"] = Relationship(back_populates="specialist_hires")

    def __repr__(self):
        return f"<SpecialistHire(company={self.company_name}, industry={self.industry})>"
