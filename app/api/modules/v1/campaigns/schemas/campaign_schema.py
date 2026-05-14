"""Campaign Pydantic request and response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.api.modules.v1.campaigns.models.campaign_model import (
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus


class CampaignCreateRequest(BaseModel):
    """Request schema for creating a Campaign.

    Args:
        organization_id (UUID): Owning organization UUID.
        name (str): Campaign display name.
        industry (str): Industry vertical to monitor.
        domain_description (Optional[str]): Freeform domain description.
        project_id (Optional[UUID]): Optional linked project UUID.
        target_depth (CampaignTargetDepth): Geographic depth (COUNTRY/STATE/CITY).
        monitor_backend (CampaignMonitorBackend): Scheduling backend.
        monitor_cadence (Optional[str]): Cron or named cadence string.
        sources_per_jurisdiction (int): Sources to discover per jurisdiction (1–20).
        max_jurisdictions (int): Upper bound on jurisdictions (min 1).

    Examples:
        >>> req = CampaignCreateRequest(
        ...     organization_id=UUID("..."),
        ...     name="GDPR Monitor",
        ...     industry="Technology",
        ...     target_depth=CampaignTargetDepth.COUNTRY,
        ...     monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        ... )
    """

    organization_id: UUID = Field(..., description="Owning organization UUID")
    name: str = Field(..., max_length=255, description="Campaign display name")
    industry: str = Field(..., max_length=255, description="Industry vertical to monitor")
    domain_description: Optional[str] = Field(
        default=None,
        description="Freeform description of the monitoring domain",
    )
    project_id: Optional[UUID] = Field(
        default=None,
        description="Optional linked project UUID",
    )
    target_depth: CampaignTargetDepth = Field(
        default=CampaignTargetDepth.COUNTRY,
        description="Deepest geographic unit to include",
    )
    monitor_backend: CampaignMonitorBackend = Field(
        default=CampaignMonitorBackend.CELERY_BEAT,
        description="Execution backend for monitoring",
    )
    monitor_cadence: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Cron-style or named cadence string",
    )
    sources_per_jurisdiction: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Sources to discover per jurisdiction",
    )
    max_jurisdictions: int = Field(
        default=15000,
        ge=1,
        description="Upper bound on jurisdiction count",
    )


class CampaignUpdateRequest(BaseModel):
    """Request schema for patching a Campaign (DRAFT status only).

    All fields are optional; only provided fields are updated.

    Examples:
        >>> patch = CampaignUpdateRequest(name="Renamed Campaign")
    """

    name: Optional[str] = Field(default=None, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=255)
    domain_description: Optional[str] = Field(default=None)
    project_id: Optional[UUID] = Field(default=None)
    target_depth: Optional[CampaignTargetDepth] = Field(default=None)
    monitor_backend: Optional[CampaignMonitorBackend] = Field(default=None)
    monitor_cadence: Optional[str] = Field(default=None, max_length=100)
    sources_per_jurisdiction: Optional[int] = Field(default=None, ge=1, le=20)
    max_jurisdictions: Optional[int] = Field(default=None, ge=1)


class ExecutionLogResponse(BaseModel):
    """Response schema for a CampaignExecutionLog entry.

    Examples:
        >>> log = ExecutionLogResponse(
        ...     id=UUID("..."),
        ...     campaign_id=UUID("..."),
        ...     phase="TAXONOMY",
        ... )
    """

    id: UUID
    campaign_id: UUID
    phase: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    error_log: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class CampaignResponse(BaseModel):
    """Response schema for a single Campaign resource.

    Examples:
        >>> resp = CampaignResponse(
        ...     id=UUID("..."),
        ...     organization_id=UUID("..."),
        ...     name="GDPR Monitor",
        ...     industry="Technology",
        ...     status=CampaignStatus.DRAFT,
        ...     target_depth=CampaignTargetDepth.COUNTRY,
        ...     monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        ...     sources_per_jurisdiction=5,
        ...     max_jurisdictions=15000,
        ...     created_at=datetime.utcnow(),
        ...     updated_at=datetime.utcnow(),
        ... )
    """

    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    name: str
    industry: str
    domain_description: Optional[str] = None
    target_depth: CampaignTargetDepth
    monitor_backend: CampaignMonitorBackend
    monitor_cadence: Optional[str] = None
    sources_per_jurisdiction: int
    max_jurisdictions: int
    status: CampaignStatus
    taxonomy_json: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    created_by: Optional[UUID] = None
    taxonomy_approved_by: Optional[UUID] = None
    taxonomy_approved_at: Optional[datetime] = None
    launched_by: Optional[UUID] = None
    generation_model: Optional[str] = None
    taxonomy_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    execution_logs: List[ExecutionLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    """Paginated list response for Campaigns.

    Examples:
        >>> resp = CampaignListResponse(
        ...     campaigns=[],
        ...     total=0,
        ...     page=1,
        ...     limit=20,
        ...     total_pages=0,
        ... )
    """

    campaigns: List[CampaignResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class CampaignStatusResponse(BaseModel):
    """Lightweight status-only response for a Campaign.

    Examples:
        >>> resp = CampaignStatusResponse(
        ...     id=UUID("..."),
        ...     status=CampaignStatus.DRAFT,
        ...     taxonomy_task_id=None,
        ... )
    """

    id: UUID
    status: CampaignStatus
    taxonomy_task_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaxonomyNodeSchema(BaseModel):
    """A single node in the campaign taxonomy tree.

    Examples:
        >>> node = TaxonomyNodeSchema(
        ...     name="California",
        ...     description="California state employment overlays",
        ...     suggested_prompt="Extract California-specific EOR fields...",
        ...     suggested_search_queries=["California labor code 2026"],
        ...     children=[],
        ... )
    """

    name: str
    description: Optional[str] = None
    suggested_prompt: Optional[str] = None
    suggested_search_queries: Optional[List[str]] = None
    iso_code: Optional[str] = None
    children: Optional[List["TaxonomyNodeSchema"]] = None

    model_config = ConfigDict(from_attributes=True)


TaxonomyNodeSchema.model_rebuild()


class GeoWarning(BaseModel):
    """A single geo-validation warning entry."""

    node_name: str
    depth: int
    issue: str
    original_name: Optional[str] = None
    resolved_name: Optional[str] = None
    iso_code: Optional[str] = None


class TaxonomyPreviewStats(BaseModel):
    """Preview statistics for the taxonomy tree."""

    total_nodes: int = 0
    countries: int = 0
    distinct_countries: int = 0
    states: int = 0
    cities: int = 0
    countries_matched: int = 0
    subdivisions_matched: int = 0
    cities_matched: int = 0
    unrecognized_count: int = 0
    unrecognized_top_level: int = 0
    regional_entities_expanded: int = 0


class TaxonomyDetailResponse(BaseModel):
    """Full taxonomy response with tree, warnings, and preview stats."""

    campaign_id: UUID
    status: CampaignStatus
    taxonomy: List[TaxonomyNodeSchema]
    warnings: List[GeoWarning] = []
    preview_stats: TaxonomyPreviewStats = TaxonomyPreviewStats()


class TaxonomyResponse(BaseModel):
    """Response wrapper for a Campaign's taxonomy tree.

    Examples:
        >>> resp = TaxonomyResponse(
        ...     campaign_id=UUID("..."),
        ...     taxonomy=[],
        ... )
    """

    campaign_id: UUID
    taxonomy: List[TaxonomyNodeSchema]


class TaxonomyEditRequest(BaseModel):
    """Request schema for replacing a Campaign's taxonomy.

    Examples:
        >>> req = TaxonomyEditRequest(taxonomy=[])
    """

    taxonomy: List[TaxonomyNodeSchema]


class TaxonomyApprovalResponse(BaseModel):
    """Response confirming taxonomy approval with audit fields."""

    campaign_id: UUID
    taxonomy_approved_by: UUID
    taxonomy_approved_at: datetime
    status: CampaignStatus


class FailedDiscoveryJurisdictionResponse(BaseModel):
    """Response schema for a jurisdiction blocked on manual source remediation."""

    id: UUID
    campaign_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    discovery_status: DiscoveryStatus

    model_config = ConfigDict(from_attributes=True)


class FailedDiscoveryJurisdictionListResponse(BaseModel):
    """Response schema for campaign failed-discovery jurisdiction listing."""

    jurisdictions: List[FailedDiscoveryJurisdictionResponse]
    total: int


class CampaignBlogBatchPublishRequest(BaseModel):
    """Request schema for campaign-level blog batch publish operations.

    Attributes:
        is_published: True to publish selected blogs, False to unpublish them.
        blog_ids: Optional specific campaign blog post IDs to update.
        publish_all: When True, apply the operation to all generated campaign blogs.

    Examples:
        Publish all campaign blogs:
            {"is_published": true, "publish_all": true}

        Unpublish all campaign blogs:
            {"is_published": false, "publish_all": true}

        Publish specific blogs:
            {"is_published": true, "blog_ids": ["uuid1", "uuid2"]}

        Unpublish specific blogs:
            {"is_published": false, "blog_ids": ["uuid1"]}
    """

    is_published: bool = Field(
        default=True,
        description="True to publish blogs, False to unpublish them.",
    )
    blog_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Optional list of specific blog post IDs within the campaign.",
    )
    publish_all: bool = Field(
        default=False,
        description="Apply the operation to all generated campaign blogs.",
    )

    @model_validator(mode="after")
    def validate_selection(self) -> "CampaignBlogBatchPublishRequest":
        """Require either publish_all=True or at least one blog ID."""
        if not self.publish_all and not self.blog_ids:
            raise ValueError("Provide blog_ids or set publish_all=true.")
        return self


class JurisdictionManualSourcesRequest(BaseModel):
    """Manual source payload used to remediate failed source discovery."""

    urls: List[HttpUrl] = Field(..., min_length=1, max_length=50)


class JurisdictionRemediationResponse(BaseModel):
    """Response schema for single-jurisdiction remediation actions."""

    jurisdiction_id: UUID
    discovery_status: DiscoveryStatus
    sources_created: int
    scrape_dispatch_task_id: Optional[str] = None


class CampaignResetRequest(BaseModel):
    """Request schema for resetting a Campaign to a specific phase."""

    target_status: CampaignStatus = Field(
        ...,
        description="The pipeline phase to reset the campaign to.",
    )
