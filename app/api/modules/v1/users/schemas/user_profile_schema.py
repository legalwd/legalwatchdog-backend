"""Schemas for user profile operations."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UpdateUserProfileRequest(BaseModel):
    """Schema for updating user profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="User's full name")
    avatar_url: Optional[str] = Field(
        None, max_length=500, description="URL to user's avatar image"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Alicia Smith",
                "avatar_url": "https://storage.example.com/avatars/user123.png",
            }
        }
    )


class UserProfileResponse(BaseModel):
    """Schema for user profile response."""

    id: str
    email: str
    name: str
    avatar_url: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "alicia@legalwatchdog.org",
                "name": "Alicia Smith",
                "avatar_url": "https://storage.example.com/avatars/user123.png",
                "is_active": True,
                "is_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
    )
