from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.routes.docs.source_discovery_docs import (
    accept_sources_custom_errors,
    accept_sources_custom_success,
    accept_sources_responses,
    suggest_sources_custom_errors,
    suggest_sources_custom_success,
    suggest_sources_responses,
)
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestionRequest
from app.api.modules.v1.scraping.schemas.source_service import SourceAccept
from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(
    tags=["AI Source Discovery (Powered by Parallel.ai)"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)


@router.post(
    "/sources/suggest",
    summary="Discover sources using Parallel.ai Search API",
    responses=suggest_sources_responses,
)
async def suggest_sources(
    payload: SuggestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Discover high-quality web sources using Parallel.ai's AI-native search.

    Args:
        payload: Search request with query, optional jurisdiction, and parameters
        db: Database session for usage logging
        current_user: Authenticated user

    Returns:
        dict: Success response with discovered sources and metadata

    Raises:
        500: Configuration error (missing API key) or search API failure
    """

    service = SourceDiscoveryService(db_session=db)
    result = await service.suggest_and_cache(db, payload, current_user)

    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Found {result.get('count', 0)} high-quality sources",
        data=result,
    )


suggest_sources._custom_errors = suggest_sources_custom_errors
suggest_sources._custom_success = suggest_sources_custom_success


@router.post(
    "/sources/accept-suggestions",
    summary="Accept Parallel.ai-suggested sources",
    responses=accept_sources_responses,
)
async def accept_suggested_sources(
    payload: SourceAccept,
    session_id: Optional[str] = Query(
        None,
        description=(
            "Session ID from the suggest-sources response. "
            "If provided, sources will be retrieved from cache."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept Parallel.ai-discovered sources and create monitoring records.

    Takes sources discovered by Parallel.ai's AI-native search and converts them
    into active monitoring sources in your database. The sources are ready for
    scraping with your configured scraping rules.


    Args:
        payload: Acceptance request with sources and monitoring configuration
        db: Database session
        current_user: Authenticated user

    Returns:
        dict: Success response with created source records

    Raises:
        400: Duplicate URLs or invalid suggestion data
        422: Request validation failed
        500: Database error or internal server error
    """

    service = SourceDiscoveryService(db_session=db)
    result = await service.accept_suggested_sources(db, payload, session_id, current_user)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Sources activated for monitoring",
        data=result,
    )


accept_suggested_sources._custom_errors = accept_sources_custom_errors
accept_suggested_sources._custom_success = accept_sources_custom_success


@router.get(
    "/sources/suggested-sources/{session_id}",
    summary="Retrieve cached suggested sources",
)
async def retrieve_cached_sources(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve previously cached search results.

    Args:
        session_id: Session ID from a previous suggest_sources response
        current_user: Authenticated user

    Returns:
        dict: Cached sources if session is still valid

    Raises:
        404: Session expired or not found
    """
    service = SourceDiscoveryService()
    result = await service.get_cached_session_with_expiry(current_user.id, session_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Previously generated sources retrieved",
        data=result,
    )
