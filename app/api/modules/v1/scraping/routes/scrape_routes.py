"""
API routes for Scrape Job operations.

Provides endpoints for:
- POST /sources/{source_id}/scrapes - Trigger manual scrape for a source
- GET /sources/{source_id}/scrapes/{job_id} - Get scrape job status
- GET /sources/{source_id}/scrapes/active - Get active scrape job for a source
- GET /sources/{source_id}/scrapes - List all scrape jobs for a source
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.core.dependencies.plan_limits import (
    require_scan_allowed_for_source,
)
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.modules.v1.scraping.routes.docs.scrape_routes_docs import (
    get_active_scrape_job_custom_errors,
    get_active_scrape_job_custom_success,
    get_active_scrape_job_responses,
    get_scrape_job_status_custom_errors,
    get_scrape_job_status_custom_success,
    get_scrape_job_status_responses,
    list_scrape_jobs_custom_errors,
    list_scrape_jobs_custom_success,
    list_scrape_jobs_responses,
    manual_scrape_trigger_custom_errors,
    manual_scrape_trigger_custom_success,
    manual_scrape_trigger_responses,
)
from app.api.modules.v1.scraping.service.scrape_job_service import ScrapeJobService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(
    prefix="/sources",
    tags=["Scrapes"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard)],
)
logger = logging.getLogger("app")


@router.post(
    "/{source_id}/scrapes",
    status_code=status.HTTP_202_ACCEPTED,
    responses=manual_scrape_trigger_responses,
    dependencies=[Depends(require_scan_allowed_for_source)],
)
async def manual_scrape_trigger(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger an asynchronous scrape job for a specific source.

    This endpoint queues a scrape job and returns immediately with a job ID.
    Use the job status endpoint to poll for completion.

    Concurrency is controlled per source - only one active job (PENDING or IN_PROGRESS)
    is allowed per source at a time. If a job is already running, a 409 Conflict
    response is returned.

    Args:
        source_id (uuid.UUID): The UUID of the source to scrape.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: 202 Accepted with job_id for polling, or error response.

    Raises:
        HTTPException: 404 if source not found, 400 if source inactive,
                      409 if scrape already in progress.
    """
    result = await ScrapeJobService.manual_scrape_trigger(db, source_id, current_user)

    logger.info(
        f"User {current_user.id} triggered scrape job {result['data']['job_id']} "
        f"for source {source_id}"
    )

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


manual_scrape_trigger._custom_errors = manual_scrape_trigger_custom_errors
manual_scrape_trigger._custom_success = manual_scrape_trigger_custom_success


@router.get(
    "/{source_id}/scrapes/active",
    status_code=status.HTTP_200_OK,
    responses=get_active_scrape_job_responses,
)
async def get_active_scrape_job(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the currently active scrape job for a source.

    Returns the active scrape job (PENDING or IN_PROGRESS) if one exists.
    This endpoint allows the frontend to recover job IDs after page refreshes
    or connection issues, without needing to store job IDs locally.

    Args:
        source_id (uuid.UUID): The UUID of the source to check for active jobs.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: 200 with active job details, or 204 if no active job.

    Raises:
        HTTPException: 404 if source not found.
    """
    result = await ScrapeJobService.get_active_scrape_job(db, source_id, current_user)

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


get_active_scrape_job._custom_errors = get_active_scrape_job_custom_errors
get_active_scrape_job._custom_success = get_active_scrape_job_custom_success


@router.get(
    "/{source_id}/scrapes",
    status_code=status.HTTP_200_OK,
    responses=list_scrape_jobs_responses,
)
async def list_scrape_jobs(
    source_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all scrape jobs for a source.

    Returns a paginated list of all scrape jobs for the specified source,
    ordered by creation date (newest first). Useful for viewing job history
    and retrying failed scrapes.

    Args:
        source_id (uuid.UUID): The UUID of the source to list jobs for.
        page (int): Page number (default 1)
        limit (int): Items per page (default 20)
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: 200 with paginated list of scrape jobs.

    Raises:
        HTTPException: 404 if source not found.
    """
    result = await ScrapeJobService.list_scrape_jobs(db, source_id, page, limit, current_user)

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


list_scrape_jobs._custom_errors = list_scrape_jobs_custom_errors
list_scrape_jobs._custom_success = list_scrape_jobs_custom_success


@router.get(
    "/{source_id}/scrapes/{job_id}",
    status_code=status.HTTP_200_OK,
    responses=get_scrape_job_status_responses,
)
async def get_scrape_job_status(
    source_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of a scrape job.

    Use this endpoint to poll for job completion after triggering a manual scrape.
    Returns the current status and, if completed, the scrape results or error message.

    Args:
        source_id (uuid.UUID): The UUID of the source.
        job_id (uuid.UUID): The UUID of the scrape job.
        db (AsyncSession): Database session.
        current_user (User): Authenticated user.

    Returns:
        JSONResponse: Success response with job status and results.

    Raises:
        HTTPException: 404 if job not found or doesn't belong to the source.
    """
    result = await ScrapeJobService.get_scrape_job_status(db, source_id, job_id, current_user)

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


get_scrape_job_status._custom_errors = get_scrape_job_status_custom_errors
get_scrape_job_status._custom_success = get_scrape_job_status_custom_success
