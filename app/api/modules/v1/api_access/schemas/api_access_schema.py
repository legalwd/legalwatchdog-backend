from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.api.core.config import settings


class APIKeyCreateSchema(BaseModel):
    key_name: str
    organization_id: UUID
    user_id: Optional[UUID] = None
    receiver_email: Optional[EmailStr] = None
    scope: str
    generated_by: UUID
    is_active: bool = True
    expires_at: datetime

    @field_validator("scope")
    def scope_must_not_be_empty(cls, v):
        if not v and not v.strip():
            raise ValueError("Scope must not be empty")
        return v

    @field_validator("expires_at")
    def api_key_default_expiration(cls, v):
        if not v:
            return datetime.now(timezone.utc) + timedelta(
                days=settings.API_KEY_DEFAULT_EXPIRATION_DAYS
            )
        return v

    @field_validator("expires_at")
    def check_max_expiration(cls, v):
        max_exp = datetime.now(timezone.utc) + timedelta(days=settings.API_KEY_MAX_EXPIRATION_DAYS)
        if v > max_exp:
            raise ValueError(
                f"Expiration cannot exceed {settings.API_KEY_MAX_EXPIRATION_DAYS} days from now"
            )
        return v


class APIKeyOutSchema(BaseModel):
    key_name: str
    organization_name: str
    user_name: Optional[str]
    receiver_email: Optional[EmailStr] = None
    api_key: str
    scope: str
    generated_by: str
    is_active: bool = True
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    rotation_enabled: bool = False
    rotation_interval_days: Optional[int] = None
    last_rotated_at: Optional[datetime] = None


class ScopeOut(BaseModel):
    value: str
    label: str


class PaginatedAPIKeys(BaseModel):
    items: List[APIKeyOutSchema]
    pagination: dict
