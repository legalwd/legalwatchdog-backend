import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlmodel import Field, SQLModel

from app.api.utils.validators import is_company_email


class InvitationCreate(BaseModel):
    invited_email: EmailStr = Field(description="Email of the user to invite")
    role_name: str = Field(
        default="Member", description="Role name (e.g., 'Admin', 'Member', 'Manager')"
    )

    @field_validator("invited_email")
    @classmethod
    def email_must_be_company(cls, v):
        if not is_company_email(v):
            raise ValueError("Only company email addresses are allowed.")
        return v


class InvitationResponse(SQLModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    invited_email: EmailStr
    inviter_id: uuid.UUID
    token: str
    role_id: Optional[uuid.UUID]
    status: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # type: ignore


class InvitationListItem(SQLModel):
    """Response model for a single invitation in a list"""

    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    invited_email: EmailStr
    inviter_id: uuid.UUID
    inviter_name: str
    inviter_email: Optional[EmailStr]
    role_id: Optional[uuid.UUID]
    role_name: Optional[str]
    status: str
    is_expired: bool = Field(description="Whether the invitation has expired")
    expires_at: datetime
    accepted_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # type: ignore


class InvitationListResponse(SQLModel):
    """Paginated response for organization invitations"""

    invitations: list[InvitationListItem]
    total: int
    page: int
    limit: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)  # type: ignore
