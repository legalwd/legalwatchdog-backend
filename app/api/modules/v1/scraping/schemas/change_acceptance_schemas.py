"""
Change Acceptance Schemas

Pydantic schemas for change acceptance API operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JurisdictionChangeResponse(BaseModel):
    """Schema for jurisdiction change response."""

    id: UUID
    jurisdiction_scrape_job_id: UUID
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    change_description: str
    change_index: int
    ticket_created: bool
    change_accepted: bool
    accepted_at: Optional[datetime] = None
    accepted_by_user_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkAcceptChangesRequest(BaseModel):
    """Request schema for bulk accepting jurisdiction changes."""

    change_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of change IDs to accept (max 50)",
    )


class FailedChange(BaseModel):
    """Schema for a failed change in bulk accept."""

    change_id: str
    error: str


class BulkAcceptChangesResponse(BaseModel):
    """Response schema for bulk accept changes operation."""

    accepted_count: int = Field(..., description="Number of successfully accepted changes")
    failed_changes: List[FailedChange] = Field(
        default_factory=list, description="List of changes that failed to be accepted"
    )
    accepted_changes: List[JurisdictionChangeResponse] = Field(
        default_factory=list, description="List of successfully accepted changes"
    )
