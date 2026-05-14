from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DataRevisionResponse(BaseModel):
    """
    Schema for a single data revision.
    """

    id: UUID
    source_id: UUID
    minio_object_key: str
    content_hash: Optional[str] = None
    extracted_data: Optional[Dict] = None
    ai_summary: Optional[str] = None
    ai_markdown_summary: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    scraped_at: datetime
    was_change_detected: bool
    is_baseline: bool
    ticket_created: bool

    model_config = ConfigDict(from_attributes=True)


class PaginationMetadata(BaseModel):
    """
    Schema for pagination metadata.
    """

    total: int
    page: int
    limit: int
    total_pages: int


class PaginatedRevisions(BaseModel):
    """
    Schema for paginated revision history response.
    """

    revisions: List[DataRevisionResponse]
    pagination: PaginationMetadata
