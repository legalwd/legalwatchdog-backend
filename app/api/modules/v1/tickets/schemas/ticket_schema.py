"""
Ticket Schemas
Pydantic schemas for ticket-related API operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus


class TicketBase(BaseModel):
    """Base schema for ticket creation and updates.

    Supports both source-level and jurisdiction-level tickets:
    - Source-level: Requires source_id + revision_id
    - Jurisdiction-level: Requires jurisdiction_id + jurisdiction_scrape_job_id
    """

    source_id: Optional[UUID] = Field(
        None,
        description=(
            "Source ID (required for source-level tickets) - identifies the specific source"
        ),
    )
    revision_id: Optional[UUID] = Field(
        None,
        description=(
            "Data Revision ID (required for source-level tickets) - "
            "specific revision that triggered this ticket"
        ),
    )

    jurisdiction_id: Optional[UUID] = Field(
        None,
        description="Jurisdiction ID (required for jurisdiction-level tickets)",
    )
    jurisdiction_scrape_job_id: Optional[UUID] = Field(
        None,
        description=(
            "Jurisdiction Scrape Job ID (required for jurisdiction-level tickets) - "
            "the job that detected changes"
        ),
    )
    jurisdiction_change_id: Optional[UUID] = Field(
        None,
        description=(
            "Jurisdiction Change ID (optional) - specific change within the job "
            "to create ticket for. If provided, creates ticket for this single change. "
            "If omitted, creates ticket for all changes in the job (legacy behavior)"
        ),
    )

    priority: Optional[TicketPriority] = Field(
        None,
        description=(
            "Ticket priority (optional): low, medium, high, or critical. "
            "If not provided, will be inferred from AI confidence scores"
        ),
    )


class TicketCreate(TicketBase):
    """Schema for creating a new ticket."""

    pass


class TicketUpdate(BaseModel):
    """Schema for updating an existing ticket."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    content: Optional[dict] = None
    status: Optional[TicketStatus] = Field(
        None, description="Ticket status (open, in_progress, resolved, closed, cancelled)"
    )
    priority: Optional[TicketPriority] = Field(
        None, description="Ticket priority (low, medium, high, critical)"
    )
    assigned_to_user_id: Optional[UUID] = None
    assigned_by_user_id: Optional[UUID] = None


class TicketInviteUsers(BaseModel):
    """Schema for inviting users to a ticket."""

    user_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of user IDs to invite to the ticket",
    )


class UserDetail(BaseModel):
    """Schema for user information in ticket responses."""

    id: UUID
    email: str
    name: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvitedUserDetail(UserDetail):
    """User detail with invitation timestamp."""

    invited_at: datetime = Field(..., description="When this user was invited to the ticket")


class TicketResponse(BaseModel):
    """Schema for ticket response."""

    id: UUID
    ticket_number: int = Field(
        ..., description="Human-friendly sequential ticket number (e.g., 1024)"
    )
    title: str
    description: Optional[str] = None
    content: Optional[dict] = None
    status: TicketStatus
    priority: TicketPriority
    is_manual: bool
    source_id: Optional[UUID] = None
    data_revision_id: Optional[UUID] = None
    change_diff_id: Optional[UUID] = None
    jurisdiction_id: Optional[UUID] = None
    jurisdiction_scrape_job_id: Optional[UUID] = None
    jurisdiction_change_id: Optional[UUID] = None
    created_by_user_id: Optional[UUID] = None
    assigned_by_user_id: Optional[UUID] = None
    assigned_to_user_id: Optional[UUID] = None
    organization_id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    created_by_user: Optional[UserDetail] = None
    assigned_by_user: Optional[UserDetail] = None
    assigned_to_user: Optional[UserDetail] = None

    comments: Optional[List] = Field(
        default=None, description="Latest comments on this ticket (up to 20)"
    )

    model_config = ConfigDict(from_attributes=True)


class TicketListFilters(BaseModel):
    """Query parameters for filtering tickets."""

    status: Optional[TicketStatus] = Field(None, description="Filter by ticket status")
    priority: Optional[TicketPriority] = Field(None, description="Filter by priority level")
    assigned_to_me: bool = Field(False, description="Show only tickets assigned to current user")
    created_by_me: bool = Field(False, description="Show only tickets created by current user")
    search: Optional[str] = Field(
        None, max_length=255, description="Search in title and description"
    )
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(20, ge=1, le=100, description="Number of items per page")


class TicketListResponse(BaseModel):
    """Schema for paginated ticket list response."""

    data: List[TicketResponse] = Field(
        ...,
        description="List of tickets for the current page",
    )
    total: int = Field(
        ...,
        description="Total number of tickets matching the criteria",
        examples=[42],
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
        examples=[1],
    )
    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page",
        examples=[20],
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages",
        examples=[3],
    )


class TicketDetailResponse(TicketResponse):
    """Schema for detailed ticket response with invited users."""

    invited_users: List[InvitedUserDetail] = Field(
        default=[], description="Users invited to collaborate on this ticket"
    )

    model_config = ConfigDict(from_attributes=True)
