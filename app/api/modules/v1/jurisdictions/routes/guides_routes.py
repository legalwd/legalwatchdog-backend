"""Public Guides listing routes.

Exposes industry and region listing endpoints for the SEO-optimised
public guide pages. All routes are unauthenticated (public).

URL hierarchy:
    GET /guides/{industry}/                    → industry listing (regions + counts)
    GET /guides/{industry}/{region}/           → region listing (paginated jurisdictions)
    GET /guides/{industry}/{region}/{jur}/     → jurisdiction detail (metadata + breadcrumbs)
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.schemas.guides_schema import SortOrder
from app.api.modules.v1.jurisdictions.service.guides_service import GuidesService
from app.api.utils.response_payloads import success_response

from .docs.guides_route_docs import (
    get_jurisdiction_detail_custom_errors,
    get_jurisdiction_detail_custom_success,
    get_jurisdiction_detail_responses,
    list_industry_custom_errors,
    list_industry_custom_success,
    list_industry_responses,
    list_region_custom_errors,
    list_region_custom_success,
    list_region_responses,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/guides",
    tags=["Public Guides"],
)


@router.get(
    "/{industry_slug}",
    status_code=status.HTTP_200_OK,
    responses=list_industry_responses,
)
async def list_industry_guides(
    industry_slug: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort: SortOrder = Query(default=SortOrder.NAME_ASC, description="Sort order"),
    db: AsyncSession = Depends(get_db),
):
    """List all regions for an industry with jurisdiction counts.

    Returns a paginated list of top-level regions (e.g., countries) that have
    published compliance guides under the given industry. Intended for the
    industry-level landing page (e.g., /guides/eor/).

    Args:
        industry_slug: URL slug of the industry (e.g., "eor", "fintech").
        page: Page number (1-indexed).
        per_page: Number of regions per page (max 100).
        sort: Sort order for regions.
        db: Database session.

    Returns:
        dict: Standardized success response containing IndustryListingResponse.
    """
    service = GuidesService(db)
    data = await service.list_industry(
        industry_slug=industry_slug,
        page=page,
        per_page=per_page,
        sort=sort,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Industry listing retrieved successfully",
        data=data.model_dump(),
    )


list_industry_guides._custom_errors = list_industry_custom_errors
list_industry_guides._custom_success = list_industry_custom_success


@router.get(
    "/{industry_slug}/{region_slug}",
    status_code=status.HTTP_200_OK,
    responses=list_region_responses,
)
async def list_region_guides(
    industry_slug: str,
    region_slug: str,
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort: SortOrder = Query(default=SortOrder.NAME_ASC, description="Sort order"),
    db: AsyncSession = Depends(get_db),
):
    """List all jurisdictions within a region for an industry.

    Returns a paginated list of jurisdictions (e.g., US states) with rich SEO
    data including summary, last update, and key topics. Intended for the
    region-level page (e.g., /guides/eor/united-states/).

    Args:
        industry_slug: URL slug of the industry (e.g., "eor").
        region_slug: URL slug of the region (e.g., "united-states").
        page: Page number (1-indexed).
        per_page: Number of jurisdictions per page (max 100).
        sort: Sort order for jurisdictions.
        db: Database session.

    Returns:
        dict: Standardized success response containing RegionListingResponse.
    """
    service = GuidesService(db)
    data = await service.list_region(
        industry_slug=industry_slug,
        region_slug=region_slug,
        page=page,
        per_page=per_page,
        sort=sort,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Region listing retrieved successfully",
        data=data.model_dump(),
    )


list_region_guides._custom_errors = list_region_custom_errors
list_region_guides._custom_success = list_region_custom_success


@router.get(
    "/{industry_slug}/{region_slug}/{jurisdiction_slug}",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_detail_responses,
)
async def get_jurisdiction_guide_detail(
    industry_slug: str,
    region_slug: str,
    jurisdiction_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get jurisdiction detail metadata for schema.org markup and SEO.

    Returns structured metadata for an individual jurisdiction's published
    blog post, including precomputed breadcrumbs for schema.org BreadcrumbList.
    Intended to support SSR/SSG pre-rendering and search engine markup.

    Args:
        industry_slug: URL slug of the industry (e.g., "eor").
        region_slug: URL slug of the region (e.g., "united-states").
        jurisdiction_slug: URL slug of the jurisdiction (e.g., "california").
        db: Database session.

    Returns:
        dict: Standardized success response containing JurisdictionDetailResponse.
    """
    service = GuidesService(db)
    data = await service.get_jurisdiction_detail(
        industry_slug=industry_slug,
        region_slug=region_slug,
        jurisdiction_slug=jurisdiction_slug,
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Jurisdiction detail retrieved successfully",
        data=data.model_dump(),
    )


get_jurisdiction_guide_detail._custom_errors = get_jurisdiction_detail_custom_errors
get_jurisdiction_guide_detail._custom_success = get_jurisdiction_detail_custom_success
