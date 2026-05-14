"""
Pydantic schemas for ScrapeJob API responses.

Defines request/response models for scrape job status tracking endpoints.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.scraping.models.scrape_job import ScrapeJobStatus


class ScrapeJobResponse(BaseModel):
    """
    Response schema for a scrape job.

    Provides status information for frontend polling.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique job identifier")
    source_id: uuid.UUID = Field(description="Source being scraped")
    status: ScrapeJobStatus = Field(description="Current job status")
    result: Optional[Dict[str, Any]] = Field(
        default=None, description="Scrape result on completion"
    )
    error_message: Optional[str] = Field(
        default=None, description="User-friendly error message on failure"
    )
    data_revision_id: Optional[uuid.UUID] = Field(
        default=None, description="Created data revision ID if successful"
    )
    is_baseline: bool = Field(
        default=False,
        description="Indicates if this is the first/baseline revision for the source "
        "(serves as comparison baseline for future changes)",
    )
    created_at: datetime = Field(description="Job creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")


class ScrapeJobCreateResponse(BaseModel):
    """
    Response schema for triggering a new scrape job.

    Returns the job ID for status polling.
    """

    job_id: uuid.UUID = Field(description="Job ID for polling status")
    source_id: uuid.UUID = Field(description="Source being scraped")
    status: ScrapeJobStatus = Field(description="Initial job status (PENDING)")
    message: str = Field(
        default="Scrape job queued successfully",
        description="User-friendly status message",
    )
