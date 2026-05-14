"""Taxonomy route handlers."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.schemas.campaign_schema import (
    CampaignStatusResponse,
    GeoWarning,
    TaxonomyApprovalResponse,
    TaxonomyDetailResponse,
    TaxonomyEditRequest,
    TaxonomyNodeSchema,
    TaxonomyPreviewStats,
)
from app.api.modules.v1.campaigns.service.campaign_service import CampaignService
from app.api.modules.v1.campaigns.service.taxonomy_generation_service import (
    TaxonomyGenerationService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.campaign_routes_docs import (
    approve_taxonomy_custom_errors,
    approve_taxonomy_custom_success,
    approve_taxonomy_responses,
    edit_taxonomy_custom_errors,
    edit_taxonomy_custom_success,
    edit_taxonomy_responses,
    generate_taxonomy_custom_errors,
    generate_taxonomy_custom_success,
    generate_taxonomy_responses,
    get_taxonomy_custom_errors,
    get_taxonomy_custom_success,
    get_taxonomy_responses,
)

router = APIRouter(prefix="/campaigns", tags=["Taxonomy"])
logger = logging.getLogger("app")


@router.post(
    "/{campaign_id}/generate-taxonomy",
    status_code=status.HTTP_202_ACCEPTED,
    responses=generate_taxonomy_responses,
)
async def generate_taxonomy(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue LLM taxonomy generation for a campaign (superadmin only).

    Returns immediately with 202 Accepted. The actual LLM work runs in the
    background via Celery. Poll GET /campaigns/{campaign_id} to track progress.

    Status transitions:
    DRAFT → GENERATING_TAXONOMY (synchronous, before response)
    GENERATING_TAXONOMY → TAXONOMY_READY (async, via Celery worker)

    Args:
        campaign_id (UUID): Target campaign UUID.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: 202 with campaign status (GENERATING_TAXONOMY).

    Raises:
        NotFoundError: 404 if campaign does not exist.
        ResourceLockedError: 423 if campaign is not in DRAFT or FAILED status.
    """
    service = TaxonomyGenerationService(db)
    campaign = await service.enqueue_taxonomy_generation(campaign_id)
    snapshot = campaign.generation_config_snapshot or {}
    task_id = snapshot.get("taxonomy_task_id")

    payload = CampaignStatusResponse(
        id=campaign.id,
        status=campaign.status,
        taxonomy_task_id=str(task_id) if task_id else None,
    )

    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Taxonomy generation started. Poll campaign status for progress.",
        data=payload.model_dump(),
    )


generate_taxonomy._custom_errors = generate_taxonomy_custom_errors
generate_taxonomy._custom_success = generate_taxonomy_custom_success


@router.get(
    "/{campaign_id}/taxonomy",
    status_code=status.HTTP_200_OK,
    responses=get_taxonomy_responses,
)
async def get_taxonomy(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve taxonomy tree with geo warnings and preview stats (superadmin only).

    Args:
        campaign_id (UUID): Target campaign UUID.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Taxonomy detail with tree, warnings, and preview stats.

    Raises:
        NotFoundError: 404 if campaign does not exist.
    """
    campaign_service = CampaignService(db)
    campaign = await campaign_service.get_campaign(campaign_id)

    taxonomy_json = campaign.taxonomy_json or {"nodes": []}
    nodes = taxonomy_json.get("nodes", [])

    # Use stored geo warnings instead of re-running validation
    snapshot = campaign.generation_config_snapshot or {}
    geo_stats = snapshot.get("geo_stats", {})
    stored_warnings = snapshot.get("geo_warnings", [])

    # Compute preview stats
    stats = _compute_preview_stats(nodes, geo_stats)
    warnings = [
        GeoWarning(
            node_name=w.get("node_name", ""),
            depth=w.get("depth", 0),
            issue=w.get("issue", ""),
            original_name=w.get("original_name"),
            resolved_name=w.get("resolved_name"),
            iso_code=w.get("iso_code"),
        )
        for w in stored_warnings
    ]

    response = TaxonomyDetailResponse(
        campaign_id=campaign.id,
        status=campaign.status,
        taxonomy=[TaxonomyNodeSchema.model_validate(n) for n in nodes],
        warnings=warnings,
        preview_stats=stats,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Taxonomy retrieved successfully.",
        data=response.model_dump(),
    )


get_taxonomy._custom_errors = get_taxonomy_custom_errors
get_taxonomy._custom_success = get_taxonomy_custom_success


@router.patch(
    "/{campaign_id}/taxonomy",
    status_code=status.HTTP_200_OK,
    responses=edit_taxonomy_responses,
)
async def edit_taxonomy(
    campaign_id: UUID,
    payload: TaxonomyEditRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Replace taxonomy nodes and re-run geo validation (superadmin only).

    Only allowed when campaign status is TAXONOMY_READY.

    Args:
        campaign_id (UUID): Target campaign UUID.
        payload (TaxonomyEditRequest): New taxonomy nodes.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Updated taxonomy detail.

    Raises:
        NotFoundError: 404 if campaign does not exist.
        ResourceLockedError: 423 if campaign is not in TAXONOMY_READY status.
    """
    new_taxonomy = {"nodes": [n.model_dump(mode="json") for n in payload.taxonomy]}

    service = TaxonomyGenerationService(db)
    campaign, geo_result = await service.edit_taxonomy(campaign_id, new_taxonomy)

    nodes = geo_result.normalized_taxonomy.get("nodes", [])
    stats = _compute_preview_stats(nodes, geo_result.stats)
    warnings = [
        GeoWarning(
            node_name=w.node_name,
            depth=w.depth,
            issue=w.issue,
            original_name=w.original_name,
            resolved_name=w.resolved_name,
            iso_code=w.iso_code,
        )
        for w in geo_result.warnings
    ]

    response = TaxonomyDetailResponse(
        campaign_id=campaign.id,
        status=campaign.status,
        taxonomy=[TaxonomyNodeSchema.model_validate(n) for n in nodes],
        warnings=warnings,
        preview_stats=stats,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Taxonomy updated and re-validated.",
        data=response.model_dump(),
    )


edit_taxonomy._custom_errors = edit_taxonomy_custom_errors
edit_taxonomy._custom_success = edit_taxonomy_custom_success


@router.post(
    "/{campaign_id}/approve-taxonomy",
    status_code=status.HTTP_200_OK,
    responses=approve_taxonomy_responses,
)
async def approve_taxonomy(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve the taxonomy, recording approver and timestamp (superadmin only).

    Only allowed when campaign status is TAXONOMY_READY.

    Args:
        campaign_id (UUID): Target campaign UUID.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Approval confirmation with audit fields.

    Raises:
        NotFoundError: 404 if campaign does not exist.
        ResourceLockedError: 423 if campaign is not in TAXONOMY_READY status.
    """
    service = TaxonomyGenerationService(db)
    campaign = await service.approve_taxonomy(campaign_id, current_user.id)

    response = TaxonomyApprovalResponse(
        campaign_id=campaign.id,
        taxonomy_approved_by=campaign.taxonomy_approved_by,
        taxonomy_approved_at=campaign.taxonomy_approved_at,
        status=campaign.status,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Taxonomy approved successfully.",
        data=response.model_dump(),
    )


approve_taxonomy._custom_errors = approve_taxonomy_custom_errors
approve_taxonomy._custom_success = approve_taxonomy_custom_success


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_preview_stats(nodes: list, geo_stats: dict = None) -> TaxonomyPreviewStats:
    """Walk the taxonomy nodes and compute preview counts."""
    stats = TaxonomyPreviewStats()
    _count_recursive(nodes, depth=1, stats=stats)
    stats.distinct_countries = stats.countries
    if geo_stats:
        stats.countries_matched = geo_stats.get("countries_matched", 0)
        stats.subdivisions_matched = geo_stats.get("subdivisions_matched", 0)
        stats.cities_matched = geo_stats.get("cities_matched", 0)
        stats.unrecognized_count = geo_stats.get("unrecognized_count", 0)
        stats.unrecognized_top_level = geo_stats.get("unrecognized_top_level", 0)
        stats.regional_entities_expanded = geo_stats.get("regional_entities_expanded", 0)
        stats.distinct_countries = geo_stats.get("distinct_countries", stats.distinct_countries)
    return stats


def _count_recursive(nodes: list, depth: int, stats: TaxonomyPreviewStats) -> None:
    for node in nodes:
        stats.total_nodes += 1
        if depth == 1:
            stats.countries += 1
        elif depth == 2:
            stats.states += 1
        elif depth == 3:
            stats.cities += 1
        children = node.get("children", []) if isinstance(node, dict) else (node.children or [])
        if children:
            _count_recursive(children, depth + 1, stats)
