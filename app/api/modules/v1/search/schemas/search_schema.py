from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Enum for different types of entities that can be searched; will be updated when needed
class SearchableEntity(str, Enum):
    DATA_REVISION = "data_revision"


class SearchOperator(str, Enum):
    """Enum for search operators used in full-text search queries."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class SearchRequest(BaseModel):
    """Request schema for full-text search on data revisions."""

    query: str = Field(..., description="Search query string", examples=["tax regulations"])
    operator: SearchOperator = Field(
        SearchOperator.AND, description="Boolean operator for multiple terms"
    )
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(10, ge=1, le=100, description="Number of results per page")
    min_rank: float = Field(0.0, ge=0.0, le=1.0, description="Minimum relevance score")
    extracted_data_filters: Optional[dict] = Field(
        default_factory=dict,
        description=(
            "Optional filters for extracted_data JSONB field. "
            "Example: {'category': 'legal', 'year': '2025'}"
        ),
        examples=[{}],
    )

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "query": "environmental protection",
                "operator": "AND",
                "page": 1,
                "limit": 10,
                "min_rank": 0.0,
                "extracted_data_filters": {},
            }
        },
    )


class DataRevisionSearchResult(BaseModel):
    """Search result for a single data revision."""

    id: UUID
    title: Optional[str]
    summary: Optional[str]
    content: Optional[str]
    key_fields: Optional[dict]
    revision_date: Optional[datetime]
    relevance_score: float = Field(..., ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """Response schema for search results with pagination metadata."""

    results: List[DataRevisionSearchResult]
    total: int = Field(..., description="Total number of matching results")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of results per page")
    total_pages: int = Field(..., description="Total number of pages")
    query: str = Field(..., description="Search query used")
    operator: str = Field(..., description="Search operator used")
