"""Campaign CRUD and Taxonomy route handlers."""

import asyncio
import logging
from typing import AsyncIterable, Optional
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.api.core.config import settings
from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.models.campaign_model import CampaignStatus
from app.api.modules.v1.campaigns.pipelines.base import CampaignPipelineRunner
from app.api.modules.v1.campaigns.pipelines.factory import get_pipeline_runner
from app.api.modules.v1.campaigns.schemas.campaign_schema import (
    CampaignBlogBatchPublishRequest,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignResponse,
    CampaignUpdateRequest,
)
from app.api.modules.v1.campaigns.service.campaign_content_service import (
    CampaignContentService,
)
from app.api.modules.v1.campaigns.service.campaign_remediation_service import (
    CampaignRemediationService,
)
from app.api.modules.v1.campaigns.service.campaign_service import CampaignService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.campaign_routes_docs import (
    backfill_campaign_content_custom_errors,
    backfill_campaign_content_custom_success,
    backfill_campaign_content_responses,
    campaign_status_custom_errors,
    campaign_status_custom_success,
    campaign_status_responses,
    cancel_campaign_custom_errors,
    cancel_campaign_custom_success,
    cancel_campaign_responses,
    create_campaign_custom_errors,
    create_campaign_custom_success,
    create_campaign_responses,
    delete_campaign_custom_errors,
    delete_campaign_custom_success,
    delete_campaign_responses,
    get_campaign_custom_errors,
    get_campaign_custom_success,
    get_campaign_responses,
    launch_campaign_custom_errors,
    launch_campaign_custom_success,
    launch_campaign_responses,
    list_campaign_blogs_custom_errors,
    list_campaign_blogs_custom_success,
    list_campaign_blogs_responses,
    list_campaigns_custom_errors,
    list_campaigns_custom_success,
    list_campaigns_responses,
    pause_campaign_custom_errors,
    pause_campaign_custom_success,
    pause_campaign_responses,
    preview_campaign_blog_custom_errors,
    preview_campaign_blog_custom_success,
    preview_campaign_blog_responses,
    progress_stream_custom_errors,
    progress_stream_custom_success,
    progress_stream_responses,
    publish_campaign_blogs_custom_errors,
    publish_campaign_blogs_custom_success,
    publish_campaign_blogs_responses,
    resume_campaign_custom_errors,
    resume_campaign_custom_success,
    resume_campaign_responses,
    retry_failed_campaign_content_custom_errors,
    retry_failed_campaign_content_custom_success,
    retry_failed_campaign_content_responses,
    run_campaign_content_custom_errors,
    run_campaign_content_custom_success,
    run_campaign_content_responses,
    update_campaign_custom_errors,
    update_campaign_custom_success,
    update_campaign_responses,
)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
logger = logging.getLogger("app")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses=create_campaign_responses,
)
async def create_campaign(
    payload: CampaignCreateRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new Campaign in DRAFT status (superadmin only).

    Args:
        payload (CampaignCreateRequest): Campaign fields.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Standardized success response with the new campaign.

    Raises:
        HTTPException: 403 if caller is not a superadmin.
    """
    service = CampaignService(db)
    campaign = await service.create_campaign(
        payload=payload,
        organization_id=payload.organization_id,
        created_by=current_user.id,
    )
    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Campaign created successfully.",
        data=CampaignResponse.model_validate(campaign).model_dump(),
    )


create_campaign._custom_errors = create_campaign_custom_errors
create_campaign._custom_success = create_campaign_custom_success


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    responses=list_campaigns_responses,
)
async def list_campaigns(
    organization_id: Optional[UUID] = Query(
        default=None,
        description="Filter by organization UUID",
    ),
    campaign_status: Optional[CampaignStatus] = Query(
        default=None,
        alias="status",
        description="Filter by campaign status",
    ),
    industry: Optional[str] = Query(
        default=None,
        description="Case-insensitive partial industry filter",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    List campaigns with optional filters and pagination (superadmin only).

    Args:
        organization_id (Optional[UUID]): Filter by owning organization.
        campaign_status (Optional[CampaignStatus]): Filter by lifecycle status.
        industry (Optional[str]): Partial case-insensitive industry match.
        page (int): 1-based page index.
        limit (int): Number of results per page (max 100).
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Paginated campaign list.
    """
    service = CampaignService(db)
    result = await service.list_campaigns(
        organization_id=organization_id,
        status_filter=campaign_status,
        industry_filter=industry,
        page=page,
        limit=limit,
    )
    list_response = CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in result["items"]],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        total_pages=result["total_pages"],
    )
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaigns retrieved successfully.",
        data=list_response.model_dump(),
    )


list_campaigns._custom_errors = list_campaigns_custom_errors
list_campaigns._custom_success = list_campaigns_custom_success


@router.get(
    "/{campaign_id}",
    status_code=status.HTTP_200_OK,
    responses=get_campaign_responses,
)
async def get_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a single Campaign by ID (superadmin only).

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Campaign detail with execution logs.

    Raises:
        NotFoundError: If no campaign with the given ID exists (404).
    """
    service = CampaignService(db)
    campaign = await service.get_campaign(campaign_id)
    snapshot = campaign.generation_config_snapshot or {}
    task_id = snapshot.get("taxonomy_task_id")

    payload = CampaignResponse.model_validate(campaign).model_dump()
    payload["taxonomy_task_id"] = str(task_id) if task_id else None

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign retrieved successfully.",
        data=payload,
    )


get_campaign._custom_errors = get_campaign_custom_errors
get_campaign._custom_success = get_campaign_custom_success


@router.patch(
    "/{campaign_id}",
    status_code=status.HTTP_200_OK,
    responses=update_campaign_responses,
)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdateRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Partially update a Campaign (DRAFT status only, superadmin only).

    Args:
        campaign_id (UUID): Primary key of the campaign to update.
        payload (CampaignUpdateRequest): Fields to update.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Updated campaign.

    Raises:
        NotFoundError: 404 if campaign does not exist.
        ResourceLockedError: 423 if campaign is not in DRAFT status.
    """
    service = CampaignService(db)
    campaign = await service.update_campaign(campaign_id, payload)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign updated successfully.",
        data=CampaignResponse.model_validate(campaign).model_dump(),
    )


update_campaign._custom_errors = update_campaign_custom_errors
update_campaign._custom_success = update_campaign_custom_success


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_200_OK,
    responses=delete_campaign_responses,
)
async def delete_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a Campaign (DRAFT status only, superadmin only).

    Args:
        campaign_id (UUID): Primary key of the campaign to delete.
        current_user (User): Authenticated superadmin user.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Confirmation of deletion.

    Raises:
        NotFoundError: 404 if campaign does not exist.
        ResourceLockedError: 423 if campaign is not in DRAFT status.
    """
    service = CampaignService(db)
    await service.delete_campaign(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign deleted successfully.",
        data={},
    )


delete_campaign._custom_errors = delete_campaign_custom_errors
delete_campaign._custom_success = delete_campaign_custom_success


@router.post(
    "/{campaign_id}/launch",
    status_code=status.HTTP_202_ACCEPTED,
    responses=launch_campaign_responses,
)
async def launch_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    runner: CampaignPipelineRunner = Depends(get_pipeline_runner),
):
    """
    Launch the campaign pipeline for a valid campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        runner (CampaignPipelineRunner): Initialized runner backend.

    Returns:
        JSONResponse: Standardized response with task details.

    Raises:
        HTTPException: 404 if campaign is not found.
        HTTPException: 500 if pipeline is already running or cannot be started.
    """
    result = await runner.run(campaign_id, launched_by=current_user.id)
    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Campaign pipeline launched.",
        data=result,
    )


launch_campaign._custom_errors = launch_campaign_custom_errors
launch_campaign._custom_success = launch_campaign_custom_success


@router.get(
    "/{campaign_id}/status",
    status_code=status.HTTP_200_OK,
    responses=campaign_status_responses,
)
async def get_campaign_status(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    runner: CampaignPipelineRunner = Depends(get_pipeline_runner),
):
    """
    Get the pipeline status of a specific campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        runner (CampaignPipelineRunner): Initialized runner backend.

    Returns:
        JSONResponse: Standardized response with campaign status.
    """
    result = await runner.get_status(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign status retrieved.",
        data=result,
    )


get_campaign_status._custom_errors = campaign_status_custom_errors
get_campaign_status._custom_success = campaign_status_custom_success


@router.post(
    "/{campaign_id}/content/run",
    status_code=status.HTTP_202_ACCEPTED,
    responses=run_campaign_content_responses,
)
async def run_campaign_content(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Queue a campaign-level content generation run."""
    service = CampaignContentService(db)
    result = await service.trigger_content_pipeline(campaign_id, mode="run")
    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Campaign content pipeline queued.",
        data=result,
    )


run_campaign_content._custom_errors = run_campaign_content_custom_errors
run_campaign_content._custom_success = run_campaign_content_custom_success


@router.post(
    "/{campaign_id}/content/retry-failed",
    status_code=status.HTTP_202_ACCEPTED,
    responses=retry_failed_campaign_content_responses,
)
async def retry_failed_campaign_content(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Retry only the jurisdictions that failed in the latest content run."""
    service = CampaignContentService(db)
    result = await service.trigger_content_pipeline(campaign_id, mode="retry_failed")
    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Failed campaign content jobs queued for retry.",
        data=result,
    )


retry_failed_campaign_content._custom_errors = retry_failed_campaign_content_custom_errors
retry_failed_campaign_content._custom_success = retry_failed_campaign_content_custom_success


@router.post(
    "/{campaign_id}/content/backfill-missing",
    status_code=status.HTTP_202_ACCEPTED,
    responses=backfill_campaign_content_responses,
)
async def backfill_campaign_content(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Generate missing campaign blogs from existing jurisdiction state."""
    service = CampaignContentService(db)
    result = await service.trigger_content_pipeline(campaign_id, mode="backfill_missing")
    return success_response(
        status_code=status.HTTP_202_ACCEPTED,
        message="Missing campaign blog generation queued.",
        data=result,
    )


backfill_campaign_content._custom_errors = backfill_campaign_content_custom_errors
backfill_campaign_content._custom_success = backfill_campaign_content_custom_success


@router.post(
    "/{campaign_id}/pause",
    status_code=status.HTTP_200_OK,
    responses=pause_campaign_responses,
)
async def pause_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    runner: CampaignPipelineRunner = Depends(get_pipeline_runner),
):
    """
    Pause a running campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        runner (CampaignPipelineRunner): Initialized runner backend.

    Returns:
        JSONResponse: Empty response marking pause status.
    """
    await runner.pause(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign paused.",
        data={},
    )


pause_campaign._custom_errors = pause_campaign_custom_errors
pause_campaign._custom_success = pause_campaign_custom_success


@router.post(
    "/{campaign_id}/resume",
    status_code=status.HTTP_200_OK,
    responses=resume_campaign_responses,
)
async def resume_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    runner: CampaignPipelineRunner = Depends(get_pipeline_runner),
):
    """
    Resume a paused campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        runner (CampaignPipelineRunner): Initialized runner backend.

    Returns:
        JSONResponse: Empty response marking resume status.
    """
    await runner.resume(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign resumed.",
        data={},
    )


resume_campaign._custom_errors = resume_campaign_custom_errors
resume_campaign._custom_success = resume_campaign_custom_success


@router.post(
    "/{campaign_id}/cancel",
    status_code=status.HTTP_200_OK,
    responses=cancel_campaign_responses,
)
async def cancel_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    runner: CampaignPipelineRunner = Depends(get_pipeline_runner),
):
    """
    Cancel an active or paused campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        runner (CampaignPipelineRunner): Initialized runner backend.

    Returns:
        JSONResponse: Empty response marking cancellation.
    """
    await runner.cancel(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign cancelled.",
        data={},
    )


cancel_campaign._custom_errors = cancel_campaign_custom_errors
cancel_campaign._custom_success = cancel_campaign_custom_success


async def _progress_event_generator(campaign_id: UUID) -> AsyncIterable[ServerSentEvent]:
    """Generator for SSE stream from Redis Pub/Sub."""
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    channel = f"campaign_progress:{campaign_id}"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield ServerSentEvent(data=message["data"], event="progress")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.aclose()


@router.get(
    "/{campaign_id}/progress-stream",
    response_class=EventSourceResponse,
    status_code=status.HTTP_200_OK,
    responses=progress_stream_responses,
)
async def stream_campaign_progress(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
):
    """
    Stream campaign real-time progress using Server-Sent Events (SSE).

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.

    Returns:
        EventSourceResponse: Text/event-stream response.
    """
    return EventSourceResponse(_progress_event_generator(campaign_id))


stream_campaign_progress._custom_errors = progress_stream_custom_errors
stream_campaign_progress._custom_success = progress_stream_custom_success


@router.post(
    "/{campaign_id}/retry-failed-jobs",
    status_code=status.HTTP_200_OK,
)
async def retry_failed_campaign_jobs(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retry all failed jurisdiction scrape jobs for a campaign.

    Args:
        campaign_id (UUID): Primary key of the campaign.
        current_user (User): Authenticated superadmin.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Standardized success response with retry details.
    """
    remediation_service = CampaignRemediationService(db)
    result = await remediation_service.retry_failed_jurisdiction_scrapes(campaign_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Retry failed jobs initiated.",
        data=result,
    )


@router.get(
    "/{campaign_id}/blogs",
    status_code=status.HTTP_200_OK,
    responses=list_campaign_blogs_responses,
)
async def list_campaign_blogs(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    List all generated blog posts for a campaign.

    Args:
        campaign_id (UUID): The campaign identifier.

    Returns:
        JSONResponse: Standardized success response with list of blogs.
    """
    service = CampaignService(db)
    blogs = await service.list_campaign_blogs(campaign_id=campaign_id)

    # Use standard response schema model mapping pattern
    from app.api.modules.v1.jurisdictions.schemas.blog_schema import BlogPostResponse

    data = [BlogPostResponse.model_validate(b).model_dump(mode="json") for b in blogs]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Campaign blog posts retrieved successfully.",
        data=data,
    )


list_campaign_blogs._custom_errors = list_campaign_blogs_custom_errors
list_campaign_blogs._custom_success = list_campaign_blogs_custom_success


@router.post(
    "/{campaign_id}/blogs/publish",
    status_code=status.HTTP_200_OK,
    responses=publish_campaign_blogs_responses,
)
async def publish_campaign_blogs(
    campaign_id: UUID,
    payload: CampaignBlogBatchPublishRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Publish or unpublish campaign blogs in batch.

    Request body options:

    **Publish all blogs:**
    ```json
    {"is_published": true, "publish_all": true}
    ```

    **Unpublish all blogs:**
    ```json
    {"is_published": false, "publish_all": true}
    ```

    **Publish specific blogs:**
    ```json
    {"is_published": true, "blog_ids": ["uuid1", "uuid2"]}
    ```

    **Unpublish specific blogs:**
    ```json
    {"is_published": false, "blog_ids": ["uuid1"]}
    ```
    """
    service = CampaignService(db)
    result = await service.batch_publish_campaign_blogs(campaign_id, payload)

    action_label = "publish" if payload.is_published else "unpublish"
    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Campaign blog batch {action_label} completed.",
        data=result,
    )


publish_campaign_blogs._custom_errors = publish_campaign_blogs_custom_errors
publish_campaign_blogs._custom_success = publish_campaign_blogs_custom_success


@router.get(
    "/{campaign_id}/blogs/{blog_id}/preview",
    status_code=status.HTTP_200_OK,
    responses=preview_campaign_blog_responses,
    response_class=HTMLResponse,
)
async def preview_campaign_blog(
    campaign_id: UUID,
    blog_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Render an internal HTML preview for a campaign blog without publishing it."""
    service = CampaignService(db)
    html = await service.render_campaign_blog_preview(campaign_id, blog_id)
    return HTMLResponse(
        content=html,
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


preview_campaign_blog._custom_errors = preview_campaign_blog_custom_errors
preview_campaign_blog._custom_success = preview_campaign_blog_custom_success
