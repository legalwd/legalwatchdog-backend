"""
Schemas for project and jurisdiction statistics.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class ChangeItem(BaseModel):
    """Individual change item from field changes."""

    field: str
    old_value: str
    new_value: str
    change_type: str
    jurisdiction_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RevisionDetail(BaseModel):
    """Details about a specific revision with changes."""

    id: str
    title: str
    summary: str
    severity: Literal["Major", "Minor"]
    created_at: Optional[str] = None
    field_changes: List[dict] = []

    model_config = ConfigDict(from_attributes=True)


class JurisdictionStatSummary(BaseModel):
    """Summary stats for a jurisdiction within a project."""

    id: str
    name: str
    change_count: int = 0
    severity: Optional[Literal["Major", "Minor"]] = None
    last_change_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JurisdictionStatsResponse(BaseModel):
    """Response schema for jurisdiction stats endpoint."""

    change_count: int = 0
    severity: Optional[Literal["Major", "Minor"]] = None
    last_change_at: Optional[str] = None
    change_summary: Optional[str] = None
    revisions: List[RevisionDetail] = []

    model_config = ConfigDict(from_attributes=True)


class ProjectStatsResponse(BaseModel):
    """Response schema for project stats endpoint."""

    change_count: int = 0
    severity: Optional[Literal["Major", "Minor"]] = None
    last_change_at: Optional[str] = None
    change_summary: Optional[str] = None
    jurisdictions: List[JurisdictionStatSummary] = []
    change_items: List[ChangeItem] = []

    model_config = ConfigDict(from_attributes=True)
