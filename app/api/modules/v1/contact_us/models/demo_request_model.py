import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.api.modules.v1.contact_us.schemas.contact_us import CompanySize


class DemoRequest(SQLModel, table=True):
    """Model representing a request-a-demo submission from a prospect."""

    __tablename__ = "demo_requests"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    first_name: str = Field(max_length=255, nullable=False)
    last_name: str = Field(max_length=255, nullable=False)
    company_name: str = Field(max_length=255, nullable=False)
    company_size: CompanySize = Field(nullable=False)
    industry: str = Field(max_length=100, nullable=False)
    company_website_url: str = Field(max_length=500, nullable=False)
    country: str = Field(max_length=100, nullable=False)
    work_email: str = Field(max_length=255, nullable=False, index=True)
    job_title: Optional[str] = Field(default=None, max_length=255, nullable=True)
    additional_context: Optional[str] = Field(default=None, max_length=4000, nullable=True)

    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
