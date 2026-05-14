"""Pydantic schemas for the Guides listing API.

Provides request/response models for industry and region listing pages
used by the public-facing blog guide site.

The API follows a two-tier pagination strategy:
1. Industry listing returns regions with jurisdiction counts (no full lists)
2. Region listing returns jurisdictions with rich SEO data (paginated)
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SortOrder(str, Enum):
    """Supported sort options for listing endpoints."""

    NAME_ASC = "name"
    NAME_DESC = "name_desc"
    UPDATED_DESC = "updated"
    UPDATED_ASC = "updated_asc"


class JurisdictionSummary(BaseModel):
    """Minimal jurisdiction data for region listing pages.

    Provides enough data for SEO indexing and user preview
    without loading full content.

    Attributes:
        id: Jurisdiction UUID.
        name: Display name of the jurisdiction.
        slug: URL-safe slug segment.
        post_url: Full URL to the blog post.
        summary: Short description from meta_description.
        updated_at: Last update timestamp.
        key_topics: Top regulatory topics for this jurisdiction.
    """

    id: UUID
    name: str
    slug: str
    post_url: str
    summary: str = Field(description="Short preview from meta_description")
    updated_at: datetime
    key_topics: List[str] = Field(
        default_factory=list,
        description="Top regulatory topics/fields for this jurisdiction",
    )

    model_config = ConfigDict(from_attributes=True)


class RegionSummary(BaseModel):
    """Region data for industry listing pages.

    Includes aggregate counts for SEO and UI but no jurisdiction list
    (deferred to the region detail page).

    Attributes:
        id: Parent jurisdiction UUID (acts as region root).
        name: Display name of the region.
        slug: URL-safe slug segment.
        jurisdiction_count: Number of child jurisdictions.
        latest_update: Most recent update across all child jurisdictions.
        url: URL to the region listing page.
    """

    id: UUID
    name: str
    slug: str
    jurisdiction_count: int = Field(description="Number of jurisdictions under this region")
    latest_update: Optional[datetime] = Field(
        default=None,
        description="Most recent update across all jurisdictions",
    )
    url: str = Field(description="URL to region listing page")

    model_config = ConfigDict(from_attributes=True)


class PaginationInfo(BaseModel):
    """Pagination metadata for listing responses."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    total_items: int = Field(ge=0, description="Total number of items")


class IndustryListingResponse(BaseModel):
    """Response schema for industry-level guide listing.

    Returns a paginated list of regions with aggregate data.
    Does not include individual jurisdictions for performance.

    Attributes:
        industry: Industry identifier (e.g., "eor", "fintech").
        industry_display_name: Human-readable industry name.
        total_jurisdictions: Total count across all regions.
        last_updated: Latest update timestamp across all posts.
        regions: Paginated list of regions with counts.
        pagination: Pagination metadata.
    """

    industry: str = Field(description="Industry identifier")
    industry_display_name: str = Field(description="Human-readable industry name")
    total_jurisdictions: int = Field(description="Total jurisdictions across all regions")
    last_updated: Optional[datetime] = Field(
        default=None,
        description="Most recent update across all regions",
    )
    regions: List[RegionSummary]
    pagination: PaginationInfo


class RegionListingResponse(BaseModel):
    """Response schema for region-level guide listing.

    Returns a paginated list of jurisdictions within a region.

    Attributes:
        industry: Industry identifier.
        region_id: Parent jurisdiction UUID.
        region_name: Display name of the region.
        region_slug: URL-safe slug for the region.
        jurisdictions: Paginated list of jurisdiction summaries.
        pagination: Pagination metadata.
    """

    industry: str
    region_id: UUID
    region_name: str
    region_slug: str
    jurisdictions: List[JurisdictionSummary]
    pagination: PaginationInfo


class JurisdictionDetailResponse(BaseModel):
    """Response schema for individual jurisdiction blog metadata.

    Used for SEO pre-rendering and schema.org markup.

    Attributes:
        id: Jurisdiction UUID.
        name: Display name.
        slug: URL-safe slug.
        industry: Industry identifier.
        post_url: Full URL to the blog post.
        breadcrumbs: Precomputed breadcrumb trail from jurisdiction hierarchy.
        title: Blog post title.
        meta_description: SEO meta description.
        keywords: SEO keywords.
        published_at: Publication timestamp.
        updated_at: Last update timestamp.
    """

    id: UUID
    name: str
    slug: str
    industry: str
    post_url: str
    breadcrumbs: List[Dict[str, str]] = Field(
        description="Precomputed breadcrumb trail: [{'name': str, 'url': str}, ...]",
    )
    title: str
    meta_description: str
    keywords: List[str]
    published_at: Optional[datetime]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
