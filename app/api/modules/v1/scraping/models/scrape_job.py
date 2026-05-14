"""
ScrapeJob model for tracking asynchronous scrape operations.

Provides status tracking for manual scrape triggers, enabling
the frontend to poll for completion status.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source


class ScrapeJobStatus(str, Enum):
    """Enumeration of scrape job statuses."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def now_utc_aware():
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(timezone.utc)


class ScrapeJob(SQLModel, table=True):
    """
    ScrapeJob entity for tracking asynchronous scrape operations.

    Tracks the lifecycle of a manual scrape trigger from creation
    through completion or failure. Includes concurrency control
    via partial unique index on source_id for active jobs.
    """

    __tablename__ = "scrape_jobs"
    __table_args__ = (
        Index(
            "ix_scrape_jobs_source_active",
            "source_id",
            unique=True,
            postgresql_where="status IN ('PENDING', 'IN_PROGRESS')",
        ),
    )

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    source_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    jurisdiction_scrape_job_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("jurisdiction_scrape_jobs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    status: ScrapeJobStatus = Field(default=ScrapeJobStatus.PENDING)

    result: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None)

    retry_count: int = Field(default=0, description="Number of times this job has been retried")

    data_revision_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("data_revisions.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )
    is_baseline: bool = Field(default=False)

    created_at: datetime = Field(
        default_factory=now_utc_aware, sa_column=Column(DateTime(timezone=True))
    )
    started_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    timeout_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), index=True),
    )

    source: Optional["Source"] = Relationship()
    data_revision: Optional["DataRevision"] = Relationship()
