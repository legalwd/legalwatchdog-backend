from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.api.utils.validators import is_company_email


class CompanySize(str, Enum):
    SMALL = "1-50"
    MEDIUM = "51-200"
    LARGE = "201-500"
    XLARGE = "501-1000"
    ENTERPRISE = "1000+"


class ContactUsRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    phone_number: str = Field(..., min_length=10, max_length=20)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=1000)

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            p = phonenumbers.parse(v, None)
            if not phonenumbers.is_valid_number(p):
                region = phonenumbers.region_code_for_number(p)
                if region:
                    raise ValueError(f"Invalid phone number (Country: {region})")
                else:
                    raise ValueError("Invalid phone number format")
            return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            raise ValueError("Invalid phone number format")

    @field_validator("email")
    @classmethod
    def email_must_be_company(cls, v: EmailStr) -> EmailStr:
        if not is_company_email(v):
            raise ValueError("Only company email addresses are allowed.")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class ContactUsDetail(BaseModel):
    """Schema for individual contact submission details"""

    id: UUID
    full_name: str
    email: str
    phone_number: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactUsResponse(BaseModel):
    message: str
    email: EmailStr


class ContactUsListResponse(BaseModel):
    """Response schema for GET all contacts"""

    contacts: List[ContactUsDetail]
    total: int
    page: int
    limit: int
    total_pages: int


class RequestDemoPayload(BaseModel):
    """Payload schema for demo request submissions."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    company_name: str = Field(..., min_length=1, max_length=255)
    company_size: CompanySize
    industry: str = Field(..., min_length=1, max_length=100)
    company_website_url: HttpUrl
    country: str = Field(..., min_length=1, max_length=100)
    work_email: EmailStr
    job_title: Optional[str] = Field(default=None, max_length=255)
    additional_context: Optional[str] = Field(default=None, max_length=4000)

    @field_validator("first_name", "last_name", "company_name", "industry", "country")
    @classmethod
    def strip_text(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value


class RequestDemoResponse(BaseModel):
    """Response data schema for a persisted demo request."""

    id: UUID
    first_name: str
    last_name: str
    company_name: str
    company_size: CompanySize
    industry: str
    company_website_url: str
    country: str
    work_email: EmailStr
    job_title: Optional[str] = None
    additional_context: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
