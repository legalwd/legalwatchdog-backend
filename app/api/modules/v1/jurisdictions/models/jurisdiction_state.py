"""Jurisdiction State models for the 'Compliance Ledger' architecture.

These models define the 'Golden Record' or accepted truth for a jurisdiction's regulatory data.
Instead of comparing scrape-to-scrape, we compare fresh scrapes against this persistent state.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
        JurisdictionScrapeJob,
    )
    from app.api.modules.v1.users.models.users_model import User


class JurisdictionState(SQLModel, table=True):
    """
    The 'Golden Record' of confirmed fields for a jurisdiction.

    This represents the Source of Truth that has been explicitly accepted by a user
    (or auto-accepted on Day 1).
    """

    __tablename__ = "jurisdiction_states"
    __table_args__ = (
        UniqueConstraint(
            "jurisdiction_id",
            "field_key",
            name="uq_jurisdiction_field",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    jurisdiction_id: UUID = Field(foreign_key="jurisdictions.id", index=True, nullable=False)
    field_key: str = Field(index=True, nullable=False)
    value: str = Field(sa_column=Column(Text, nullable=False))
    source_evidence: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    confirmed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    confirmed_by_user_id: Optional[UUID] = Field(foreign_key="users.id", nullable=True)
    originating_job_id: Optional[UUID] = Field(
        foreign_key="jurisdiction_scrape_jobs.id",
        nullable=True,
    )

    jurisdiction: "Jurisdiction" = Relationship()
    confirmed_by_user: Optional["User"] = Relationship()
    originating_job: Optional["JurisdictionScrapeJob"] = Relationship()
    history: list["JurisdictionStateHistory"] = Relationship(
        back_populates="state",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class JurisdictionStateHistory(SQLModel, table=True):
    """
    Immutable log of every change to the Golden Record (Audit Trail).
    """

    __tablename__ = "jurisdiction_state_history"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    state_id: UUID = Field(foreign_key="jurisdiction_states.id", index=True, nullable=False)

    previous_value: Optional[str] = Field(sa_column=Column(Text, nullable=True))
    new_value: str = Field(sa_column=Column(Text, nullable=False))

    changed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    changed_by_user_id: Optional[UUID] = Field(foreign_key="users.id", nullable=True)
    change_reason: str = Field(nullable=False)
    state: "JurisdictionState" = Relationship(back_populates="history")
    changed_by_user: Optional["User"] = Relationship()
