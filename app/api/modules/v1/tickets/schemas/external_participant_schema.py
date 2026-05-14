from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, Field


class InviteParticipantsRequest(BaseModel):
    """Request schema for inviting participants (internal users + external) to a ticket"""

    emails: List[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of email addresses to invite (internal users or external participants)",
    )


class InternalUserInvitationResponse(BaseModel):
    """Response for internal user notification (they log in normally)"""

    user_id: str
    email: str
    name: str | None
    is_internal: bool = True
    invited_at: datetime

    class Config:
        from_attributes = True


class ExternalParticipantResponse(BaseModel):
    """Response schema for an invited external participant (guest access)"""

    participant_id: str
    email: str
    role: str
    is_internal: bool = False
    invited_at: datetime
    expires_at: datetime | None
    magic_link: str | None = Field(
        None,
        description="The magic link sent to the participant (only returned on creation)",
    )

    class Config:
        from_attributes = True


class InviteParticipantsResponse(BaseModel):
    """Response schema for inviting participants (both internal and external)"""

    internal_users: List[InternalUserInvitationResponse] = Field(
        ..., description="Internal users notified (they'll log in normally)"
    )
    external_participants: List[ExternalParticipantResponse] = Field(
        ..., description="External participants with guest access (magic link)"
    )
    already_invited: List[str] = Field(..., description="Email addresses that were already invited")
    not_in_project: List[str] = Field(
        default_factory=list,
        description="Internal user emails that cannot be invited "
        "because they're not in the project. Add them to the project first, then re-invite.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "internal_users": [
                    {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "john@company.com",
                        "name": "John Doe",
                        "is_internal": True,
                        "invited_at": "2025-12-05T10:30:00Z",
                    }
                ],
                "external_participants": [
                    {
                        "participant_id": "123e4567-e89b-12d3-a456-426614174001",
                        "email": "counsel@lawfirm.com",
                        "role": "Guest",
                        "is_internal": False,
                        "invited_at": "2025-12-05T10:30:00Z",
                        "expires_at": "2025-12-12T10:30:00Z",
                        "magic_link": "https://app.legalwatchdog.com/guest/access?token=eyJ...&client=local",
                    }
                ],
                "already_invited": ["existing@company.com"],
                "not_in_project": ["user@company.com"],
            }
        }


class GuestTicketAccessResponse(BaseModel):
    """Response schema for guest ticket access (limited view)"""

    ticket_id: str
    title: str
    description: str | None
    priority: str
    status: str
    created_at: datetime
    project_name: str | None

    # Guest-specific info
    participant_email: str
    participant_role: str
    access_expires_at: datetime | None

    class Config:
        json_schema_extra = {
            "example": {
                "ticket_id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Legal Review Required for Contract Amendment",
                "description": "We need external counsel to review...",
                "priority": "high",
                "status": "open",
                "created_at": "2025-12-05T10:00:00Z",
                "project_name": "Contract Management System",
                "participant_email": "counsel@lawfirm.com",
                "participant_role": "Guest",
                "access_expires_at": "2025-12-12T10:30:00Z",
            }
        }


class InternalParticipantDetail(BaseModel):
    """Internal participant detail (registered user)"""

    user_id: str
    name: str
    email: str
    profile_picture_url: str | None = Field(
        None, description="User's profile picture URL from OAuth provider"
    )
    avatar_url: str | None = Field(None, description="User's avatar URL")
    status: str = Field(..., description="online or offline")
    invited_at: datetime

    class Config:
        from_attributes = True


class ExternalParticipantDetail(BaseModel):
    """External participant detail (guest access)"""

    participant_id: str
    name: str = Field(
        default="Guest", description="Display name (always 'Guest' for external participants)"
    )
    email: str
    role: str
    status: str = Field(
        default="offline", description="online if active in last 5 minutes, otherwise offline"
    )
    invited_at: datetime
    expires_at: datetime | None

    class Config:
        from_attributes = True


class TicketParticipantsResponse(BaseModel):
    """Response schema for listing all ticket participants"""

    internal_participants: List[InternalParticipantDetail] = Field(
        ..., description="Internal users (registered users in the system)"
    )
    external_participants: List[ExternalParticipantDetail] = Field(
        ..., description="External participants (guest access via magic link)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "internal_participants": [
                    {
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "John Doe",
                        "email": "john@company.com",
                        "profile_picture_url": "https://example.com/profile.jpg",
                        "avatar_url": "https://example.com/avatar.jpg",
                        "status": "online",
                        "invited_at": "2025-12-05T10:30:00Z",
                    }
                ],
                "external_participants": [
                    {
                        "participant_id": "223e4567-e89b-12d3-a456-426614174001",
                        "name": "Guest",
                        "email": "counsel@lawfirm.com",
                        "role": "Guest",
                        "status": "offline",
                        "invited_at": "2025-12-05T11:00:00Z",
                        "expires_at": "2025-12-12T11:00:00Z",
                    }
                ],
            }
        }
