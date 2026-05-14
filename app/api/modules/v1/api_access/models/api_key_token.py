from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from app.api.modules.v1.api_access.models.api_key_model import APIKey


class APIKeyOnboardingToken(SQLModel, table=True):
    __tablename__ = "api_key_onboarding_tokens"  # type: ignore

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    api_key_id: UUID = Field(foreign_key="api_keys.id", nullable=False, index=True)
    token: str = Field(default_factory=lambda: str(uuid4()), nullable=False, unique=True)
    expires_at: datetime = Field(nullable=False)
    used: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    api_key: "APIKey" = Relationship(back_populates="onboarding_token")
