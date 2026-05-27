"""Campaign domain models."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction


class CampaignStatus(str, Enum):
    """Lifecycle states for a Campaign."""

    DRAFT = "DRAFT"
    GENERATING_TAXONOMY = "GENERATING_TAXONOMY"
    TAXONOMY_READY = "TAXONOMY_READY"
    HYDRATING = "HYDRATING"
    DISCOVERING_SOURCES = "DISCOVERING_SOURCES"
    SCRAPING = "SCRAPING"
    PUBLISHING = "PUBLISHING"
    MONITORING = "MONITORING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CampaignTargetDepth(str, Enum):
    """Geographic target depth for jurisdiction discovery."""

    COUNTRY = "COUNTRY"
    STATE = "STATE"
    CITY = "CITY"


class CampaignMonitorBackend(str, Enum):
    """Backend used for periodic campaign monitoring."""

    CELERY_BEAT = "CELERY_BEAT"


class Campaign(SQLModel, table=True):
    """
    Represents a regulatory monitoring campaign spanning multiple jurisdictions.

    A Campaign orchestrates taxonomy generation, source discovery, scraping, and
    AI-processing for a given industry and geographic scope. It transitions through
    a well-defined lifecycle from DRAFT to ACTIVE/COMPLETED.

    Attributes:
        id: UUID primary key.
        organization_id: FK to the owning organization.
        project_id: Optional FK to a linked project.
        name: Human-readable campaign title.
        industry: Industry vertical this campaign monitors.
        domain_description: Freeform explanation of the monitoring domain.
        target_depth: Deepest geographic unit to model (COUNTRY/STATE/CITY).
        monitor_backend: Scheduling backend (currently CELERY_BEAT only).
        monitor_cadence: Cron-style or named cadence string.
        sources_per_jurisdiction: How many sources to discover per jurisdiction (1–20).
        max_jurisdictions: Upper bound on jurisdiction count (min 1).
        status: Current lifecycle state.
        taxonomy_json: JSONB taxonomy tree produced during TAXONOMY_READY phase.
        stats: JSONB aggregate statistics updated during execution.
        created_by: UUID of the user who created this campaign.
        taxonomy_approved_by: UUID of the approver.
        taxonomy_approved_at: Timestamp of taxonomy approval.
        launched_by: UUID of the user who launched execution.
        generation_model: LLM model identifier used for taxonomy generation.
        generation_config_snapshot: JSONB snapshot of generation configuration.
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC).
    """

    __tablename__ = "campaigns"  # type: ignore
    __table_args__ = (
        Index("ix_campaigns_organization_id", "organization_id"),
        Index("ix_campaigns_status", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    organization_id: uuid.UUID = Field(foreign_key="organizations.id")
    project_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="projects.id",
        index=True,
        nullable=True,
    )

    name: str = Field(max_length=255)
    industry: str = Field(max_length=255)
    domain_description: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )

    target_depth: CampaignTargetDepth = Field(default=CampaignTargetDepth.COUNTRY)
    monitor_backend: CampaignMonitorBackend = Field(
        default=CampaignMonitorBackend.CELERY_BEAT,
    )
    monitor_cadence: Optional[str] = Field(default=None, max_length=100)
    sources_per_jurisdiction: int = Field(default=5, ge=1, le=20)
    max_jurisdictions: int = Field(default=15000, ge=1)
    target_countries: Optional[list[str]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    target_states: Optional[list[str]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    status: CampaignStatus = Field(default=CampaignStatus.DRAFT)
    taxonomy_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    stats: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    created_by: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )
    taxonomy_approved_by: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )
    taxonomy_approved_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    launched_by: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="users.id",
        nullable=True,
    )
    generation_model: Optional[str] = Field(default=None, max_length=255)
    generation_config_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    execution_logs: list["CampaignExecutionLog"] = Relationship(
        back_populates="campaign",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    jurisdictions: list["Jurisdiction"] = Relationship(back_populates="campaign")


class CampaignExecutionLog(SQLModel, table=True):
    """
    Records the progress and outcome of a single execution phase within a Campaign.

    Attributes:
        id: UUID primary key.
        campaign_id: FK to the parent Campaign.
        phase: Identifier for the execution phase (e.g. 'TAXONOMY', 'SCRAPING').
        started_at: Timestamp when this phase started.
        completed_at: Timestamp when this phase finished.
        total_items: Total number of items to process in this phase.
        completed_items: Items successfully processed.
        failed_items: Items that failed processing.
        error_log: JSONB bag of error details per failed item.
    """

    __tablename__ = "campaign_execution_logs"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    campaign_id: uuid.UUID = Field(
        foreign_key="campaigns.id",
        index=True,
        ondelete="CASCADE",
    )
    phase: str = Field(max_length=100)
    started_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    total_items: int = Field(default=0)
    completed_items: int = Field(default=0)
    failed_items: int = Field(default=0)
    error_log: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    campaign: Campaign = Relationship(back_populates="execution_logs")
