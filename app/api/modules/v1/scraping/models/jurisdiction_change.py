"""JurisdictionChange model for tracking individual field changes.

Tracks each specific change detected within a jurisdiction scrape job,
enabling per-change ticket creation and change acceptance workflow.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import JurisdictionScrapeJob
    from app.api.modules.v1.tickets.models.ticket_model import Ticket
    from app.api.modules.v1.users.models.users_model import User


class JurisdictionChange(SQLModel, table=True):
    """
    Track individual field changes within a jurisdiction scrape job.

    This model enables granular tracking of each detected change,
    allowing users to create tickets for specific changes and
    mark individual changes as accepted/dismissed.
    """

    __tablename__ = "jurisdiction_changes"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    jurisdiction_scrape_job_id: UUID = Field(
        foreign_key="jurisdiction_scrape_jobs.id",
        index=True,
        nullable=False,
        description="The jurisdiction scrape job that detected this change",
    )

    field_name: str = Field(
        nullable=False,
        index=True,
        description="The field that changed (e.g., 'applicable_services')",
    )

    old_value: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Previous value of the field",
    )

    new_value: Optional[str] = Field(
        default=None,
        nullable=True,
        description="New value of the field",
    )

    change_description: str = Field(
        nullable=False,
        description="Human-readable description of the change",
    )

    change_index: int = Field(
        nullable=False,
        description="Position of this change in the changes array (0-indexed)",
    )

    ticket_created: bool = Field(
        default=False,
        nullable=False,
        index=True,
        description="Flag indicating whether a ticket has been created for this specific change",
    )

    change_accepted: bool = Field(
        default=False,
        nullable=False,
        index=True,
        description="Flag indicating whether this change has been accepted/dismissed",
    )

    accepted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When this change was accepted",
    )

    accepted_by_user_id: Optional[UUID] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
        description="User who accepted this change",
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    jurisdiction_scrape_job: "JurisdictionScrapeJob" = Relationship(
        back_populates="jurisdiction_changes"
    )
    accepted_by_user: Optional["User"] = Relationship()
    tickets: list["Ticket"] = Relationship(back_populates="jurisdiction_change")
