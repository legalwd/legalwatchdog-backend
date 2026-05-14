from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TicketCloseRequest(BaseModel):
    """Request schema for closing a ticket."""

    closing_notes: Optional[str] = Field(
        default=None,
        min_length=0,
        max_length=1000,
        description="Optional notes explaining why the ticket was closed",
    )


class TicketResponse(BaseModel):
    """Response schema for ticket operations."""

    id: UUID
    ticket_number: int = Field(..., description="Human-friendly sequential ticket number")
    title: str
    description: Optional[str]
    content: Optional[dict]
    status: str
    priority: str
    is_manual: bool
    data_revision_id: Optional[UUID]
    source_id: Optional[UUID]
    created_by_user_id: Optional[UUID]
    assigned_by_user_id: Optional[UUID]
    assigned_to_user_id: Optional[UUID]
    organization_id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True
