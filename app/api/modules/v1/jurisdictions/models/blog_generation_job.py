"""BlogGenerationJob model for tracking blog generation operations.

Tracks the lifecycle of blog generation requests from creation
through completion or failure, enabling frontend polling for status.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Index, Text
from sqlmodel import Column, Field, SQLModel


class BlogGenerationJobStatus(str, Enum):
    """Enumeration of blog generation job statuses."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProjectBulkBlogJobStatus(str, Enum):
    """Enumeration of project-level bulk blog generation job statuses."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class BlogGenerationJob(SQLModel, table=True):
    """
    BlogGenerationJob entity for tracking blog generation operations.

    Tracks the lifecycle of a manual blog generation trigger from creation
    through completion or failure. Includes concurrency control via partial
    unique index on jurisdiction_id for active jobs.
    """

    __tablename__ = "blog_generation_jobs"
    __table_args__ = (
        Index(
            "ix_blog_generation_jobs_jurisdiction_active",
            "jurisdiction_id",
            unique=True,
            postgresql_where="status IN ('PENDING', 'IN_PROGRESS')",
        ),
    )

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    jurisdiction_id: uuid.UUID = Field(foreign_key="jurisdictions.id", index=True, nullable=False)

    status: BlogGenerationJobStatus = Field(default=BlogGenerationJobStatus.PENDING)

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    triggered_by: Optional[uuid.UUID] = Field(
        default=None,
        description="User ID who triggered the generation (optional)",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    started_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # Optional linkage to parent bulk job
    bulk_job_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="project_bulk_blog_jobs.id", index=True
    )


class ProjectBulkBlogJob(SQLModel, table=True):
    """
    ProjectBulkBlogJob entity for tracking bulk blog generation operations
    across an entire project's jurisdictions. Supports continue-on-error.
    """

    __tablename__ = "project_bulk_blog_jobs"
    __table_args__ = (
        Index(
            "ix_project_bulk_blog_jobs_project_active",
            "project_id",
            unique=True,
            postgresql_where="status IN ('PENDING', 'IN_PROGRESS')",
        ),
    )

    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    project_id: uuid.UUID = Field(foreign_key="projects.id", index=True, nullable=False)

    status: ProjectBulkBlogJobStatus = Field(default=ProjectBulkBlogJobStatus.PENDING)

    totals: int = Field(default=0, description="Total jurisdictions to process")
    processed: int = Field(default=0, description="Number successfully processed")
    failed: int = Field(default=0, description="Number failed")
    skipped: int = Field(default=0, description="Number skipped (hash unchanged or placeholder)")

    publish_requested: bool = Field(
        default=False, description="Whether to publish posts after generation"
    )

    error_summary: Optional[str] = Field(default=None, sa_column=Column(Text))

    triggered_by: Optional[uuid.UUID] = Field(
        default=None,
        description="User ID who triggered the bulk generation",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    started_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
