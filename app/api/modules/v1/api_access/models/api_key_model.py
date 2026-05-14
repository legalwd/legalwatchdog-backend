from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.api_access.models.api_key_token import APIKey, APIKeyOnboardingToken
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.users_model import User


class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"  # type: ignore
    __table_args__ = (UniqueConstraint("organization_id", "key_name", name="uq_org_keyname"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    key_name: str = Field(nullable=False)
    organization_id: UUID = Field(foreign_key="organizations.id", nullable=False, index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    receiver_email: Optional[str] = Field(
        default=None, nullable=True, description="Email of external recipient"
    )
    hashed_key: str = Field(
        nullable=False, unique=True, description="Hashed representation of the raw API key"
    )
    scope: str = Field(nullable=False, description="Comma-separated permissions for this API key")
    generated_by: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last successful usage of this API key"
    )
    expires_at: datetime = Field(nullable=False, description="Expiration datetime for this API key")

    rotation_enabled: bool = Field(
        default=False, nullable=False, description="If true, key is auto-rotated"
    )
    rotation_interval_days: Optional[int] = Field(
        default=None, nullable=True, description="Rotate when expiry is within this many days"
    )
    last_rotated_at: Optional[datetime] = Field(
        default=None, nullable=True, description="Timestamp when the key was last rotated"
    )

    organization: "Organization" = Relationship(back_populates="api_keys")
    owner_user: Optional["User"] = Relationship(
        back_populates="owned_api_keys",
        sa_relationship_kwargs={
            "foreign_keys": ("[app.api.modules.v1.api_access.models.api_key_model.APIKey.user_id]"),
        },
    )
    generated_by_user: Optional["User"] = Relationship(
        back_populates="generated_api_keys",
        sa_relationship_kwargs={
            "foreign_keys": (
                "[app.api.modules.v1.api_access.models.api_key_model.APIKey.generated_by]"
            ),
        },
    )
    onboarding_token: Optional["APIKeyOnboardingToken"] = Relationship(
        back_populates="api_key", sa_relationship_kwargs={"uselist": False}
    )
