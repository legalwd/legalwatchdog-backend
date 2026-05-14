"""Schemas for superadmin organization management endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OrganizationOwnerSchema(BaseModel):
    """Schema for organization owner details (nullable when no owner exists)."""

    id: Optional[UUID] = Field(None, description="Owner user ID")
    name: Optional[str] = Field(None, description="Owner name")
    email: Optional[str] = Field(None, description="Owner email address")
    is_approved: Optional[bool] = Field(
        None, description="Whether the owner is approved by superadmin"
    )
    is_active: Optional[bool] = Field(None, description="Whether the owner account is active")
    is_verified: Optional[bool] = Field(None, description="Whether the owner email is verified")
    approved_at: Optional[datetime] = Field(None, description="Timestamp when owner was approved")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when owner account was created"
    )
    last_login: Optional[datetime] = Field(None, description="Owner's last login timestamp")
    last_active: Optional[datetime] = Field(None, description="Owner's last activity timestamp")

    model_config = ConfigDict(from_attributes=True)


class OrganizationWithOwnerSchema(BaseModel):
    """Schema for organization with owner details."""

    id: UUID = Field(..., description="Organization ID")
    name: str = Field(..., description="Organization name")
    industry: Optional[str] = Field(None, description="Organization industry")
    location: Optional[str] = Field(None, description="Organization location")
    country: Optional[str] = Field(None, description="Organization country")
    email: Optional[str] = Field(None, description="Organization contact email")
    company_size: Optional[str] = Field(None, description="Organization company size")
    org_type: Optional[str] = Field(None, description="Organization type")
    plan: Optional[str] = Field(None, description="Subscription plan")
    logo_url: Optional[str] = Field(None, description="Organization logo URL")
    is_active: bool = Field(..., description="Whether the organization is active")
    created_at: datetime = Field(..., description="Organization creation timestamp")
    updated_at: datetime = Field(..., description="Organization last update timestamp")
    owner: Optional[OrganizationOwnerSchema] = Field(
        None, description="Organization owner details (null if no owner)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Acme Corporation",
                "industry": "Legal",
                "location": "United Kingdom",
                "country": "UK",
                "email": "contact@acme.com",
                "company_size": "51-200",
                "org_type": "Law Firm",
                "plan": "Professional",
                "logo_url": "https://example.com/logo.png",
                "is_active": True,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-02-10T15:30:00Z",
                "owner": {
                    "id": "456e7890-e89b-12d3-a456-426614174001",
                    "name": "John Doe",
                    "email": "john@acme.com",
                    "is_approved": True,
                    "is_active": True,
                    "is_verified": True,
                    "approved_at": "2024-01-16T09:00:00Z",
                    "created_at": "2024-01-15T10:00:00Z",
                    "last_login": "2024-02-10T15:30:00Z",
                    "last_active": "2024-02-10T15:35:00Z",
                },
            }
        },
    )


class PaginationMeta(BaseModel):
    """Schema for pagination metadata."""

    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(
        json_schema_extra={"example": {"total": 100, "page": 1, "limit": 20, "total_pages": 5}}
    )


class OrganizationListResponse(BaseModel):
    """Schema for paginated organization list response."""

    organizations: list[OrganizationWithOwnerSchema] = Field(
        ..., description="List of organizations with owner details"
    )
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "organizations": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Acme Corporation",
                        "industry": "Legal",
                        "is_active": True,
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-02-10T15:30:00Z",
                        "owner": {
                            "id": "456e7890-e89b-12d3-a456-426614174001",
                            "name": "John Doe",
                            "email": "john@acme.com",
                            "is_approved": True,
                        },
                    }
                ],
                "meta": {"total": 1, "page": 1, "limit": 20, "total_pages": 1},
            }
        },
    )
