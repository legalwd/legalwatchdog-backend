"""JurisdictionScrapeJob model for tracking consolidated scraping operations.

Tracks the batch scraping process for all sources within a jurisdiction.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Text
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange


class JurisdictionScrapeJobStatus(str, Enum):
    """Status of a jurisdiction scrape job."""

    PENDING = "PENDING"
    SCRAPING = "SCRAPING"
    CONSOLIDATING = "CONSOLIDATING"
    FILTERING = "FILTERING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JurisdictionScrapeJob(SQLModel, table=True):
    """
    Tracks consolidated scraping jobs for jurisdictions.

    A JurisdictionScrapeJob represents a batch scraping operation that:
    1. Scrapes all sources in a jurisdiction
    2. Consolidates the content
    3. Filters relevant sources
    4. Analyzes changes across the jurisdiction
    5. Generates tickets for detected changes
    """

    __tablename__ = "jurisdiction_scrape_jobs"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    jurisdiction_id: UUID = Field(foreign_key="jurisdictions.id", index=True)

    status: JurisdictionScrapeJobStatus = Field(default=JurisdictionScrapeJobStatus.PENDING)

    total_sources: int = Field(default=0)
    successful_sources: int = Field(default=0)
    filtered_sources: int = Field(default=0)

    consolidated_content_key: Optional[str] = Field(default=None)

    content_hash: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Combined SHA-256 hash of all source content hashes + prompt",
    )

    extracted_data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    started_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    jurisdiction_changes: list["JurisdictionChange"] = Relationship(
        back_populates="jurisdiction_scrape_job"
    )
