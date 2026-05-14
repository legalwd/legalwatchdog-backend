import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class RefreshTokenMetadata(SQLModel, table=True):
    """
    Tracks refresh token metadata for token rotation and audit logging.

    Stores information about refresh tokens issued to users, including provider
    information, token expiry, and revocation status.

    Attributes:
        id: Unique identifier for this token metadata record
        user_id: Reference to the user this token belongs to
        jti: JWT Token ID (unique identifier from the token itself)
        provider: Authentication provider ('local', 'google', 'microsoft', etc.)
        provider_token_exp: Provider-level token expiry timestamp (if applicable)
        issued_at: When this token was issued
        expires_at: When this token will expire
        revoked_at: When this token was revoked (if applicable)
        ip_address: IP address of the client that obtained the token
        user_agent: User agent of the client that obtained the token
        is_revoked: Whether this token has been revoked
    """

    __tablename__ = "refresh_token_metadata"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)

    jti: str = Field(index=True, unique=True, nullable=False)

    provider: str = Field(max_length=50, nullable=False, default="local")

    provider_token_exp: Optional[int] = Field(
        default=None, description="Unix timestamp of provider token expiry"
    )

    issued_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    revoked_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )

    ip_address: Optional[str] = Field(default=None, max_length=45)

    user_agent: Optional[str] = Field(default=None, max_length=500)

    is_revoked: bool = Field(default=False, nullable=False)


class OAuthLoginEvent(SQLModel, table=True):
    """
    Audit log for all OAuth authentication attempts.

    Records every OAuth login attempt (success or failure) with context information
    for security monitoring and debugging.

    Attributes:
        id: Unique identifier for this event
        user_id: Reference to the user (if login succeeded)
        provider: OAuth provider ('google', 'microsoft', 'apple', etc.)
        status: Result status ('success', 'failed', 'blocked', 'error')
        failure_reason: Human-readable reason for failure
        error_code: Machine-readable error code
        ip_address: Client IP address
        user_agent: Client user agent
        email: Email used in the attempt (for failed attempts)
        timestamp: When the event occurred
    """

    __tablename__ = "oauth_login_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    user_id: Optional[uuid.UUID] = Field(
        foreign_key="users.id", nullable=True, index=True, default=None
    )

    provider: str = Field(max_length=50, nullable=False)

    status: str = Field(
        max_length=20,
        nullable=False,
        description="success, failed, blocked, error",
    )

    failure_reason: Optional[str] = Field(default=None, max_length=500)

    error_code: Optional[str] = Field(default=None, max_length=100)

    ip_address: Optional[str] = Field(default=None, max_length=45)

    user_agent: Optional[str] = Field(default=None, max_length=500)

    email: Optional[str] = Field(default=None, max_length=255, index=True)

    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
        default_factory=lambda: datetime.now(timezone.utc),
    )
