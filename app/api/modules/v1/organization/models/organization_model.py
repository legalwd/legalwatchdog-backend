import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column, DateTime, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.api_access.models.api_key_model import APIKey
    from app.api.modules.v1.organization.models.invitation_model import Invitation
    from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.tickets.models.ticket_model import Ticket
    from app.api.modules.v1.users.models.roles_model import Role


class CompanySize(str, Enum):
    """Enum for organization company size."""

    SMALL = "1-50"
    MEDIUM = "51-200"
    LARGE = "201-500"
    XLARGE = "501-1000"
    ENTERPRISE = "1000+"


# Default organization settings
DEFAULT_ORG_SETTINGS = {
    "visibility": "private",
    "require_strong_passwords": True,
    "require_2fa": True,
    "allow_external_sharing": False,
    "audit_logging_enabled": True,
    "project_default_privacy": "private",
}


class Organization(SQLModel, table=True):
    """Organization model.

    Attributes:
        id: UUID of the organization
        name: Name of the organization
        industry: Industry type of the organization
        location: Location of the organization
        plan: Subscription plan of the organization
        logo_url: URL of the organization logo
        settings: Settings of the organization
        billing_info: Billing information of the organization
        is_active: Whether the organization is active
        created_at: Timestamp of when the organization was created
        updated_at: Timestamp of when the organization was updated
        deleted_at: Timestamp of when the organization was deleted
        user_memberships: List of user memberships in the organization
        roles: List of roles in the organization
        projects: List of projects in the organization
        invitations: List of invitations to the organization
    """

    __tablename__ = "organizations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    name: str = Field(max_length=255, nullable=False, index=True)

    industry: str = Field(max_length=100, nullable=True)

    location: Optional[str] = Field(
        None, max_length=255, description="Organization location (e.g., 'United Kingdom', 'Global')"
    )

    country: Optional[str] = Field(None, max_length=100, description="Organization country")

    email: Optional[str] = Field(None, max_length=255, description="Organization contact email")

    company_size: Optional[CompanySize] = Field(None, description="Organization company size")

    org_type: Optional[str] = Field(None, max_length=100, description="Organization type")

    plan: Optional[str] = Field(
        None, max_length=50, description="Subscription plan (e.g., 'Professional', 'Enterprise')"
    )

    logo_url: Optional[str] = Field(None, max_length=500, description="Organization logo URL")

    settings: dict = Field(
        default_factory=lambda: DEFAULT_ORG_SETTINGS.copy(),
        sa_column=Column(JSON, nullable=False, server_default=json.dumps(DEFAULT_ORG_SETTINGS)),
    )

    billing_info: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )

    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True),
        default=None,
    )
    user_memberships: list["UserOrganization"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    roles: list["Role"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    projects: list["Project"] = Relationship(
        back_populates="organization",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    invitations: list["Invitation"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    tickets: list["Ticket"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    api_keys: list["APIKey"] = Relationship(
        back_populates="organization", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


Index(
    "ix_org_active_not_deleted",
    Organization.is_active,
    postgresql_where=Organization.deleted_at.is_(None),
)
