from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.api.modules.v1.organization.models.organization_model import CompanySize


class CreateOrganizationRequest(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=2, max_length=255, description="Organization name")
    industry: str | None = Field(None, max_length=100, description="Industry type")
    country: Optional[str] = Field(None, max_length=100, description="Organization country")
    email: Optional[EmailStr] = Field(None, description="Organization contact email")
    company_size: Optional[CompanySize] = Field(None, description="Organization company size")
    org_type: Optional[str] = Field(None, max_length=100, description="Organization type")
    job_title: Optional[str] = Field(None, max_length=255, description="Creator's job title")

    @field_validator("name")
    def name_validator(cls, v: str) -> str:
        """
        Validate and normalize an organization name.

        Args:
            v (str): The organization name to validate.
        Returns:
            str: The stripped organization name if it passes validation.
        Raises:
            ValueError: If the name is shorter than 2 characters
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Organization name must be at least 2 characters long")

        if not any(c.isalpha() for c in v):
            raise ValueError("Organization name must contain at least one letter")

        return v

    @field_validator("industry")
    def industry_must_be_letters_only(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate the 'industry' field for the organization schema.

        Args:
            cls
                The validator class (unused).
            v : Optional[str]
                The industry value to validate.
        Returns
            Optional[str]
                The stripped industry string, or None if the input is None.
        Raises
            ValueError
                If the value is shorter than 2 characters,
                if it contains any digits,
                or if it contains no alphabetic characters.
        """
        if v is None:
            return v

        v = v.strip()
        if len(v) < 2:
            raise ValueError("Industry must be at least 2 characters long")

        if any(c.isdigit() for c in v):
            raise ValueError("Industry must not contain numbers")

        if not any(c.isalpha() for c in v):
            raise ValueError("Industry must contain at least one letter")

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation",
                "industry": "Technology",
                "country": "United States",
                "email": "contact@acme.com",
                "company_size": "51-200",
                "org_type": "Private",
                "job_title": "CEO",
            }
        }
    )


class CreateOrganizationResponse(BaseModel):
    """Schema for organization response data."""

    organization_id: str
    organization_name: str
    user_id: str
    role: str
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                "organization_name": "Acme Corporation",
                "country": "United States",
                "email": "contact@acme.com",
                "company_size": "51-200",
                "org_type": "Private",
                "user_id": "123e4567-e89b-12d3-a456-426614174001",
                "role": "admin",
                "message": "Organization created successfully",
            }
        }
    )


class UpdateOrganizationRequest(BaseModel):
    """Schema for updating an organization."""

    name: Optional[str] = Field(None, min_length=2, max_length=255, description="Organization name")
    industry: Optional[str] = Field(None, min_length=2, max_length=100, description="Industry type")
    location: Optional[str] = Field(
        None, min_length=2, max_length=255, description="Organization location"
    )
    country: Optional[str] = Field(None, max_length=100, description="Organization country")
    email: Optional[EmailStr] = Field(None, description="Organization contact email")
    company_size: Optional[CompanySize] = Field(None, description="Organization company size")
    org_type: Optional[str] = Field(None, max_length=100, description="Organization type")
    logo_url: Optional[HttpUrl] = Field(None, max_length=500, description="Organization logo URL")
    is_active: Optional[bool] = Field(None, description="Organization active status")

    @field_validator("name")
    def update_name_validator(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate the `name` field ensuring it meets organization naming rules.

        Args:
            cls: The model class (automatically provided by Pydantic).
            v (Optional[str]): The input value for the `name` field.

        Returns:
            Optional[str]: The cleaned and validated name value.

        Raises:
            ValueError: If the name is too short, contains digits, or has no letters.
        """
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Organization name must be at least 2 characters long")

        if not any(c.isalpha() for c in v):
            raise ValueError("Organization name must contain at least one letter")

        return v

    @field_validator("industry")
    def update_industry_must_be_letters_only(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate the `industry` field ensuring it meets organization industry naming rules.

        Args:
            cls: The model class (automatically provided by Pydantic).
            v (Optional[str]): The input value for the `industry` field.

        Returns:
            Optional[str]: The cleaned and validated industry value.

        Raises:
            ValueError: If the industry name is too short, contains digits, or has no letters.
        """

        if v is None:
            return v

        v = v.strip()
        if len(v) < 2:
            raise ValueError("Industry must be at least 2 characters long")

        if any(c.isdigit() for c in v):
            raise ValueError("Industry must not contain numbers")

        if not any(c.isalpha() for c in v):
            raise ValueError("Industry must contain at least one letter")

        return v

    @field_validator("location")
    def update_location_basic_validation(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate and normalize a location string.
        Args:
            v (Optional[str]): The location to validate.

        Returns:
            Optional[str]: The stripped location string when valid
        Raises:
            ValueError:
                If the stripped location is shorter than 2 characters or
                contains no alphabetic characters.
        """

        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Location must be at least 2 characters long")
        if not any(c.isalpha() for c in v):
            raise ValueError("Location must contain at least one letter")
        return v

    @field_validator("logo_url", mode="before")
    def update_logo_url_and_validate(cls, v: Optional[str]) -> Optional[str]:
        """
        Pre-validation for the `logo_url` field.

        Parameters:
                cls: The model/class that the validator is bound to.
                v: The incoming raw value for `logo_url`.

        Returns:
                Optional[str]: The normalized logo URL string or None.

        Raises:
                ValueError: If the stripped string exceeds 500 characters.
        """
        if v is None:
            return v
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                return None
            if len(v) > 500:
                raise ValueError("Logo URL must be at most 500 characters long")
            return v
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Acme Corporation Updated",
                "industry": "Software Development",
                "is_active": True,
            }
        }
    )


class OrganizationDetailResponse(BaseModel):
    """Schema for organization detail response."""

    id: str
    name: str
    industry: Optional[str]
    location: Optional[str]
    country: Optional[str]
    email: Optional[str]
    company_size: Optional[CompanySize]
    org_type: Optional[str]
    plan: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    projects_count: int
    created_at: datetime
    updated_at: datetime
    settings: dict
    billing_info: dict

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Acme Corporation",
                "industry": "Technology",
                "location": "United Kingdom",
                "plan": "Enterprise",
                "logo_url": "https://example.com/logo.png",
                "is_active": True,
                "projects_count": 5,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "settings": {},
                "billing_info": {},
            }
        }
    )


class UpdateMemberStatusRequest(BaseModel):
    """Schema for updating a member's active status within an organization."""

    is_active: bool = Field(..., description="New active status for the member")

    model_config = ConfigDict(json_schema_extra={"example": {"is_active": True}})


class UpdateMemberRoleRequest(BaseModel):
    """Schema for updating a member's role within an organization."""

    role_name: str = Field(..., description="New role name to assign to the member")

    model_config = ConfigDict(json_schema_extra={"example": {"role_name": "Manager"}})


class OrganizationUserItem(BaseModel):
    """Schema for a single user in an organization"""

    user_id: str
    email: str
    name: str
    avatar_url: Optional[str]
    is_active: bool
    is_verified: bool
    role: str | None
    role_id: str | None
    title: Optional[str]
    department: Optional[str]
    membership_active: bool
    joined_at: str
    created_at: str


class OrganizationUsersResponse(BaseModel):
    """Schema for organization users response"""

    users: List[OrganizationUserItem]
    total: int
    page: int
    limit: int
    total_pages: int
