"""Database models for LLM usage tracking and monitoring."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel


class LLMUsageLog(SQLModel, table=True):
    """Tracks all LLM API requests for cost monitoring and admin dashboard.

    Stores comprehensive metrics for each LLM request including tokens used,
    cost, latency, success/failure status, and user/organization attribution.
    Used by admin dashboard for usage analytics, cost tracking, and billing.

    Attributes:
        id (UUID): Primary key.
        request_id (str): Unique identifier for the request.
        model (str): Model identifier used (e.g., 'anthropic/claude-3.5-sonnet').
        provider (str): LLM provider (e.g., 'openrouter', 'gemini').
        user_id (UUID): User who made the request (nullable).
        organization_id (UUID): Organization owning the request (nullable).
        project_id (UUID): Project associated with the request (nullable).
        jurisdiction_id (UUID): Jurisdiction associated with the request (nullable).
        input_tokens (int): Number of input tokens consumed.
        output_tokens (int): Number of output tokens generated.
        total_tokens (int): Total tokens (input + output).
        cost_usd (float): Estimated cost in USD.
        latency_ms (float): Request latency in milliseconds.
        success (bool): Whether request succeeded.
        error_message (str): Error message if failed (nullable).
        retry_count (int): Number of retries attempted.
        endpoint (str): API endpoint that triggered the request (nullable).
        ip_address (str): Client IP address (nullable).
        created_at (datetime): Request timestamp.

    Examples:
        >>> log = LLMUsageLog(
        ...     request_id="abc123",
        ...     model="anthropic/claude-3.5-sonnet",
        ...     provider="openrouter",
        ...     user_id=user.id,
        ...     organization_id=org.id,
        ...     project_id=project.id,
        ...     input_tokens=1500,
        ...     output_tokens=300,
        ...     total_tokens=1800,
        ...     cost_usd=0.0088,
        ...     latency_ms=1234.5,
        ...     success=True
        ... )
        >>> db.add(log)
        >>> await db.commit()
    """

    __tablename__ = "llm_usage_logs"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    request_id: str = Field(max_length=255, index=True)
    model: str = Field(max_length=255, index=True)
    provider: str = Field(max_length=50, index=True)

    user_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    )
    organization_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    )
    project_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    )
    jurisdiction_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(PG_UUID(as_uuid=True), index=True, nullable=True)
    )

    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)

    cost_usd: float = Field(default=0.0)
    latency_ms: float = Field(default=0.0)

    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    retry_count: int = Field(default=0)

    endpoint: Optional[str] = Field(default=None, max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=45)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )

    def __repr__(self) -> str:
        """String representation of LLM usage log.

        Returns:
            str: Human-readable representation.

        Examples:
            >>> log = LLMUsageLog(model="claude-3.5-sonnet", cost_usd=0.0088)
            >>> print(log)
            <LLMUsageLog model=claude-3.5-sonnet cost=$0.0088 success=True>
        """
        return f"<LLMUsageLog model={self.model} cost=${self.cost_usd:.4f} success={self.success}>"


class LLMProviderStatus(SQLModel, table=True):
    """Tracks real-time health and status of LLM providers.

    Monitors provider availability, rate limits, error rates, and performance
    metrics for routing decisions and admin dashboard monitoring.

    Attributes:
        id (UUID): Primary key.
        provider (str): Provider identifier (e.g., 'openrouter', 'gemini').
        model (str): Model identifier (nullable for provider-level status).
        is_available (bool): Whether provider is currently available.
        error_rate (float): Recent error rate (0.0-1.0).
        avg_latency_ms (float): Average latency in milliseconds.
        requests_last_hour (int): Number of requests in last hour.
        rate_limit_remaining (int): Remaining rate limit quota (nullable).
        rate_limit_reset_at (datetime): Rate limit reset timestamp (nullable).
        last_error (str): Most recent error message (nullable).
        last_success_at (datetime): Timestamp of last successful request.
        last_error_at (datetime): Timestamp of last failed request.
        updated_at (datetime): Last status update timestamp.

    Examples:
        >>> status = LLMProviderStatus(
        ...     provider="openrouter",
        ...     model="anthropic/claude-3.5-sonnet",
        ...     is_available=True,
        ...     error_rate=0.02,
        ...     avg_latency_ms=1200.0
        ... )
        >>> db.add(status)
        >>> await db.commit()
    """

    __tablename__ = "llm_provider_status"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    provider: str = Field(max_length=50, index=True)
    model: Optional[str] = Field(default=None, max_length=255, index=True)

    is_available: bool = Field(default=True)
    error_rate: float = Field(default=0.0)
    avg_latency_ms: float = Field(default=0.0)
    requests_last_hour: int = Field(default=0)

    rate_limit_remaining: Optional[int] = Field(default=None)
    rate_limit_reset_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    last_error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    last_success_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_error_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    def __repr__(self) -> str:
        """String representation of provider status.

        Returns:
            str: Human-readable representation.

        Examples:
            >>> status = LLMProviderStatus(provider="openrouter", is_available=True)
            >>> print(status)
            <LLMProviderStatus provider=openrouter available=True>
        """
        return f"<LLMProviderStatus provider={self.provider} available={self.is_available}>"
