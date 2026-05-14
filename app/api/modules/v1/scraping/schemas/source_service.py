"""
Pydantic schemas for Source entity.

Defines request and response models for source CRUD operations.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.api.modules.v1.scraping.models.source_model import SourceType
from app.api.modules.v1.scraping.validators import URLValidator


class SourceCreate(BaseModel):
    """
    Schema for creating a new source.

    Attributes:
        jurisdiction_id (uuid.UUID): Parent jurisdiction UUID.
        name (str): Human-readable source name.
        url (HttpUrl): Target URL to scrape.
        source_type (SourceType): Type of source (web, pdf, api).
        scrape_frequency (str): Cron-like frequency string (e.g., "DAILY", "HOURLY").
        auto_create_tickets (bool): Whether to auto-create tickets from this source.
        auth_details (Optional[Dict]): Authentication credentials (will be encrypted).
        scraping_rules (Optional[Dict]): Custom extraction rules.
    """

    jurisdiction_id: uuid.UUID
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: HttpUrl
    source_type: SourceType = SourceType.WEB
    scrape_frequency: str = Field(default="DAILY", min_length=1)
    auto_create_tickets: bool = False
    auth_details: Optional[Dict] = None
    scraping_rules: Optional[Dict] = {}

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: HttpUrl) -> HttpUrl:
        """Validate URL format and domain restrictions.

        Args:
            v (HttpUrl): The URL to validate.

        Returns:
            HttpUrl: The validated URL.

        Raises:
            ValueError: If URL validation fails.


        """

        is_valid, error_msg, error_code = URLValidator.validate_url_format(str(v))
        if not is_valid:
            raise ValueError(error_msg)

        is_valid, error_msg, error_code = URLValidator.validate_domain(str(v))
        if not is_valid:
            raise ValueError(error_msg)

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Supreme Court Opinions",
                "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                "source_type": "web",
                "scrape_frequency": "DAILY",
                "auth_details": None,
                "scraping_rules": {
                    "title_selector": ".opinion-title",
                    "content_selector": ".opinion-content",
                    "date_selector": ".opinion-date",
                },
            }
        }
    )


class SourceUpdate(BaseModel):
    """
    Schema for updating an existing source.

    All fields are optional to support partial updates.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[HttpUrl] = None
    source_type: Optional[SourceType] = None
    scrape_frequency: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    is_deleted: Optional[bool] = None
    auto_create_tickets: Optional[bool] = None
    auth_details: Optional[Dict] = None
    scraping_rules: Optional[Dict] = None


class SourceRead(BaseModel):
    """
    Schema for source responses.

    Ensures auth_details are never exposed (only has_auth flag).

    Attributes:
        id (uuid.UUID): Source unique identifier.
        jurisdiction_id (uuid.UUID): Parent jurisdiction UUID.
        name (str): Source name.
        url (str): Source URL.
        source_type (SourceType): Type of source.
        scrape_frequency (str): Scraping schedule.
        is_active (bool): Whether source is enabled.
        is_deleted (bool): Whether source is soft-deleted.
        auto_create_tickets (bool): Whether tickets are auto-created from this source.
        has_auth (bool): Whether source has authentication configured.
        created_at (datetime): Timestamp of creation.
    """

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    name: Optional[str]
    url: str
    source_type: SourceType
    scrape_frequency: str
    is_active: bool
    is_deleted: bool
    auto_create_tickets: bool
    has_auth: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceBulkCreate(BaseModel):
    """
    Schema for bulk creating multiple sources.

    Attributes:
        sources (List[SourceCreate]): List of source creation payloads.
    """

    sources: List[SourceCreate] = Field(..., min_items=1, max_items=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sources": [
                    {
                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Supreme Court Opinions",
                        "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                        "source_type": "web",
                        "scrape_frequency": "DAILY",
                    },
                    {
                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Federal Register",
                        "url": "https://www.federalregister.gov/",
                        "source_type": "web",
                        "scrape_frequency": "HOURLY",
                    },
                ]
            }
        }
    )


class SourceAccept(BaseModel):
    """
    Schema for accepting AI-suggested sources and converting them to sources.

    Combines suggested source data with required creation fields.
    """

    suggested_sources: List[dict] = Field(
        ...,
        description="List of suggested sources from AI, "
        "each containing title, url, snippet, confidence_reason, is_official",
    )
    jurisdiction_id: uuid.UUID = Field(..., description="Parent jurisdiction UUID for all sources")
    source_type: SourceType = Field(default=SourceType.WEB, description="Type of source")
    scrape_frequency: str = Field(default="DAILY", description="Scraping frequency")
    scraping_rules: Optional[Dict] = Field(default={}, description="Custom extraction rules")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "suggested_sources": [
                    {
                        "title": "Supreme Court Opinions",
                        "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                        "snippet": "Official opinions from the Supreme Court",
                        "confidence_reason": "Official government domain",
                        "is_official": True,
                    }
                ],
                "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_type": "web",
                "scrape_frequency": "DAILY",
            }
        }
    )
