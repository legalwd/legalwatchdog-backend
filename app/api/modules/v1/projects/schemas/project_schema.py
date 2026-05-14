from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Project title")
    description: Optional[str] = Field(None, description="Project description")


class ProjectUpdateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Project title")
    description: Optional[str] = Field(None, description="Project description")
    master_prompt: Optional[str] = Field(None, description="High-level AI prompt for the project")


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    master_prompt: Optional[str] = None
    is_deleted: Optional[bool] = None

    @field_validator("master_prompt", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v


class ProjectUserAssignment(BaseModel):
    user_ids: List[UUID] = Field(..., description="List of user IDs to assign to project")


class ProjectResponse(ProjectUpdateBase):
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    page: int
    limit: int
    total_pages: Optional[int] = None


class ProjectUserDetail(BaseModel):
    """Schema for detailed user information in projects."""

    user_id: UUID
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    added_at: str

    model_config = ConfigDict(from_attributes=True)


class ProjectUsersResponse(BaseModel):
    users: List[ProjectUserDetail]
    total: int
    page: int
    limit: int
    total_pages: int


class BlogPublishProjectRequest(BaseModel):
    """Request schema for batch publish/unpublish of all jurisdiction blogs in a project.

    Attributes:
        is_published: True to publish, False to unpublish.
        jurisdiction_ids: If set, only these jurisdictions (must belong to the project).
            If omitted, all non-deleted jurisdictions in the project are processed.
    """

    is_published: bool
    jurisdiction_ids: Optional[List[UUID]] = None
