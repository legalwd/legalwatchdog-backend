from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, Enum, Index, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import JSON, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.tickets.models.ticket_model import Ticket

    from .source_model import Source


class ExtractionStatus:
    """Extraction processing status for Stage 2 pipeline tracking."""

    PENDING_EXTRACTION = "pending_extraction"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    EXTRACTION_FAILED = "extraction_failed"


class DataRevision(SQLModel, table=True):
    """
    DataRevision model
    Represents a specific revision of scraped data,
    including its content, metadata, and AI-generated summaries.
    """

    __tablename__ = "data_revisions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(index=True, foreign_key="sources.id")
    minio_object_key: str = Field(nullable=False)
    content_hash: Optional[str] = Field(default=None, nullable=True, index=True)
    extraction_status: str = Field(
        default=ExtractionStatus.PENDING_EXTRACTION,
        sa_column=Column(
            Enum(
                ExtractionStatus.PENDING_EXTRACTION,
                ExtractionStatus.EXTRACTING,
                ExtractionStatus.COMPLETED,
                ExtractionStatus.EXTRACTION_FAILED,
                name="extraction_status_enum",
            ),
            nullable=False,
            server_default="pending_extraction",
        ),
    )
    extracted_data: Optional[Dict] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=True),
    )
    ai_summary: Optional[str] = Field(default=None)
    ai_markdown_summary: Optional[str] = Field(default=None)
    ai_confidence_score: Optional[float] = Field(default=None)
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    was_change_detected: bool = Field(default=False)
    is_baseline: bool = Field(default=False)
    ticket_created: bool = Field(
        default=False,
        nullable=False,
        description="Flag indicating whether a ticket has been created for this revision",
    )

    search_vector: Optional[str] = Field(
        default=None, sa_column=Column(TSVECTOR, nullable=True, server_default=text("NULL"))
    )

    tickets: list["Ticket"] = Relationship(back_populates="data_revision")

    __table_args__ = (
        Index("idx_data_revisions_search_vector", "search_vector", postgresql_using="gin"),
    )

    source: Optional["Source"] = Relationship(back_populates="data_revisions")
