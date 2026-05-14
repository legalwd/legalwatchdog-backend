import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.routes.docs.scraping_admin_docs import (
    clear_stuck_jobs_custom_errors,
    clear_stuck_jobs_custom_success,
    clear_stuck_jobs_responses,
    manual_scrape_source_custom_errors,
    manual_scrape_source_custom_success,
    manual_scrape_source_responses,
    retry_stuck_jobs_custom_errors,
    retry_stuck_jobs_custom_success,
    retry_stuck_jobs_responses,
)
from app.api.modules.v1.admin.services.scraping_admin_service import ScrapingAdminService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraping", tags=["Scraping Admin"])


@router.post(
    "/sources/{source_id}/scrape",
    status_code=status.HTTP_202_ACCEPTED,
    responses=manual_scrape_source_responses,
)
async def manual_scrape_source_endpoint(
    source_id: str,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ScrapingAdminService(db)
    result = await service.manual_scrape_source(source_id, current_user.id)

    logger.info(f"Superadmin {current_user.id} manually triggered scrape for source {source_id}")

    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Manual scrape task initiated",
        data=result,
    )


manual_scrape_source_endpoint._custom_errors = manual_scrape_source_custom_errors
manual_scrape_source_endpoint._custom_success = manual_scrape_source_custom_success


@router.post(
    "/retry-stuck-jobs",
    status_code=status.HTTP_202_ACCEPTED,
    responses=retry_stuck_jobs_responses,
)
async def retry_stuck_jobs_endpoint(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = ScrapingAdminService(db)
    result = await service.retry_stuck_jobs(current_user.id)

    logger.info(f"Superadmin {current_user.id} initiated retry of stuck jobs")

    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Retry stuck jobs task initiated",
        data=result,
    )


retry_stuck_jobs_endpoint._custom_errors = retry_stuck_jobs_custom_errors
retry_stuck_jobs_endpoint._custom_success = retry_stuck_jobs_custom_success


@router.post(
    "/jobs/clear-stuck",
    status_code=status.HTTP_200_OK,
    responses=clear_stuck_jobs_responses,
)
async def clear_stuck_jobs_endpoint(
    source_id: Optional[str] = None,
    current_user: Annotated[User, Depends(require_superadmin)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    service = ScrapingAdminService(db)
    result = await service.clear_stuck_jobs(source_id, current_user.id)

    message = (
        "No stuck jobs found"
        if result["cleared_count"] == 0
        else f"Successfully cleared {result['cleared_count']} stuck jobs"
    )

    logger.info(
        f"Superadmin {current_user.id} manually cleared {result['cleared_count']} stuck jobs "
        f"(source_filter={source_id})"
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message=message,
        data=result,
    )


clear_stuck_jobs_endpoint._custom_errors = clear_stuck_jobs_custom_errors
clear_stuck_jobs_endpoint._custom_success = clear_stuck_jobs_custom_success
