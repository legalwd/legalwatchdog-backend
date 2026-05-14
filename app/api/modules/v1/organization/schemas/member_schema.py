"""Schemas for organization member operations."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UpdateMemberRequest(BaseModel):
    """Schema for updating member details."""

    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Member's full name"
    )
    email: Optional[str] = Field(None, description="Member's email address")
    department: Optional[str] = Field(None, max_length=100, description="Member's department")
    title: Optional[str] = Field(None, max_length=255, description="Member's job title")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format."""
        if v is not None and "@" not in v:
            raise ValueError("Invalid email format")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Kylie Morgan",
                "email": "kyliemorgan@charteredinc.com",
                "department": "Compliance team",
                "title": "Senior Compliance Officer",
            }
        }
    )
