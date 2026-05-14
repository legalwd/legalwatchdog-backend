"""
Source model for scraping configuration.

Defines the database schema for sources to be monitored and scraped.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import DateTime
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.tickets.models.ticket_model import Ticket

    from .data_revision import DataRevision


class SourceType(str, Enum):
    """Enumeration of supported source types."""

    WEB = "web"
    PDF = "pdf"
    API = "api"


class ScrapeFrequency(str, Enum):
    """Enumeration of supported scrape frequencies."""

    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


def now_utc_aware():
    return datetime.now(timezone.utc)


class Source(SQLModel, table=True):
    """
    Source entity for web scraping configuration.
    All datetime fields are now timezone-aware.
    """

    __tablename__ = "sources"
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    jurisdiction_id: uuid.UUID = Field(foreign_key="jurisdictions.id", index=True)

    name: Optional[str] = None
    url: str
    source_type: SourceType = Field(default=SourceType.WEB)

    scrape_frequency: ScrapeFrequency = Field(default=ScrapeFrequency.DAILY)
    next_scrape_time: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False, index=True)
    auto_create_tickets: bool = Field(default=False)

    auth_details_encrypted: Optional[str] = Field(default=None)
    scraping_rules: Dict = Field(default={}, sa_column=Column(JSON))

    last_scraped_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    last_error: Optional[str] = Field(default=None)

    verification_status: Optional[str] = Field(
        default="unverified_retryable",
        description=(
            "Last known reachability status (verified, unverified_retryable, "
            "unverified_permanent, blocked_by_bot_protection, timeout, unreachable)"
        ),
    )
    verification_attempts: int = Field(
        default=0,
        description="Number of verification attempts made",
    )
    last_verification_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="Timestamp of last verification attempt",
    )

    created_at: datetime = Field(
        default_factory=now_utc_aware, sa_column=Column(DateTime(timezone=True))
    )

    jurisdiction: Optional["Jurisdiction"] = Relationship(back_populates="sources")

    data_revisions: List["DataRevision"] = Relationship(
        back_populates="source", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    tickets: list["Ticket"] = Relationship(
        back_populates="source", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
