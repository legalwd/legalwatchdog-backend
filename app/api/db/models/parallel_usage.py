"""Parallel.ai usage tracking models for monitoring and billing."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class ParallelUsageLog(SQLModel, table=True):
    """Track Parallel.ai Extract API usage for monitoring and cost analysis.

    Records each Parallel.ai extraction request including success/failure,
    costs, performance metrics, and error details for comprehensive monitoring.

    Attributes:
        id: Unique identifier for the usage log entry.
        user_id: User who initiated the extraction request.
        organization_id: Organization context for the request (if applicable).
        project_id: Project context for cost attribution (if applicable).
        url_extracted: Target URL that was extracted.
        endpoint_name: API endpoint that triggered the extraction (e.g., "scrape_source").
        success: Whether the extraction succeeded (True) or failed (False).
        cost: Estimated or actual API cost in USD for this request.
        latency_ms: Time taken for the extraction request in milliseconds.
        content_size_bytes: Size of the extracted markdown content in bytes.
        error_message: Error details if the extraction failed.
        created_at: Timestamp when the extraction was performed (UTC).

    Examples:
        >>> log = ParallelUsageLog(
        ...     user_id=user.id,
        ...     organization_id=org.id,
        ...     url_extracted="https://example.com/page",
        ...     endpoint_name="scrape_source",
        ...     success=True,
        ...     cost=Decimal("0.001"),
        ...     latency_ms=1250,
        ...     content_size_bytes=15000
        ... )
        >>> db.add(log)
        >>> await db.commit()
    """

    __tablename__ = "parallel_usage_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    organization_id: Optional[UUID] = Field(
        default=None, foreign_key="organizations.id", index=True
    )
    project_id: Optional[UUID] = Field(default=None, foreign_key="projects.id", index=True)
    url_extracted: str = Field(max_length=2048, index=False)
    endpoint_name: str = Field(max_length=100, index=True)
    success: bool = Field(default=False, index=True)
    cost: Decimal = Field(
        default=Decimal("0"),
        max_digits=10,
        decimal_places=6,
        description="Cost in USD",
    )
    latency_ms: int = Field(default=0, ge=0, description="Request latency in milliseconds")
    content_size_bytes: int = Field(
        default=0, ge=0, description="Size of extracted content in bytes"
    )
    error_message: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True),
        description="Timestamp of extraction (UTC)",
    )
