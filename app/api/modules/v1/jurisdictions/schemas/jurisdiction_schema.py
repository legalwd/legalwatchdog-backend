"""Schemas For Jurisdiction Request and Responses"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class JurisdictionCreateSchema(BaseModel):
    """Schema for creating a Jurisdiction"""

    project_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class JurisdictionResponseSchema(BaseModel):
    """Schema used for returning Jurisdiction objects in responses"""

    id: UUID
    project_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    is_deleted: bool = False

    children: Optional[List["JurisdictionResponseSchema"]] = None

    model_config = ConfigDict(from_attributes=True)


JurisdictionResponseSchema.model_rebuild()


class JurisdictionUpdateSchema(BaseModel):
    """Schema for updating a jurisdiction: all fields optional except id"""

    parent_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    scrape_output: Optional[Dict[str, Any]] = None
    is_deleted: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("parent_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v


class JurisdictionScrapeHistoryItem(BaseModel):
    """Schema for individual scrape job history item."""

    id: UUID
    status: str
    total_sources: int = 0
    successful_sources: int = 0
    filtered_sources: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    changes_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class JurisdictionScrapeHistoryResponse(BaseModel):
    """Schema for paginated scrape history response for a jurisdiction."""

    jobs: List[JurisdictionScrapeHistoryItem]
    pagination: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
