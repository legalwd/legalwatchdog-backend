"""API routes for jurisdiction blog post operations.

Provides endpoints for retrieving, generating, and publishing blog posts
auto-generated from jurisdiction state (Compliance Ledger) data.

Routes:
    GET /{jurisdiction_id}/blog - Retrieve blog post
    POST /{jurisdiction_id}/blog/generate - Trigger blog regeneration (returns job_id)
    PATCH /{jurisdiction_id}/blog/publish - Publish/unpublish blog post
    GET /{jurisdiction_id}/blog/generations/{job_id} - Get generation job status
    GET /{jurisdiction_id}/blog/generations - List generation jobs
"""

import logging
from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.core.dependencies.auth import TenantGuard
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import SyncSessionLocal, get_db
from app.api.modules.v1.jurisdictions.schemas.blog_schema import (
    BlogPostResponse,
    BlogPublishRequest,
)
from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
    BlogGenerationService,
)
from app.api.modules.v1.jurisdictions.service.blog_search_service import BlogSearchService
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import OrgResourceGuard
from app.api.utils.response_payloads import success_response

from .docs.blog_route_docs import (
    generate_blog_custom_errors,
    generate_blog_custom_success,
    generate_blog_responses,
    get_all_blog_posts_custom_errors,
    get_all_blog_posts_custom_success,
    get_all_blog_posts_responses,
    get_blog_custom_errors,
    get_blog_custom_success,
    get_blog_responses,
    get_generation_status_custom_errors,
    get_generation_status_custom_success,
    get_generation_status_responses,
    list_generations_custom_errors,
    list_generations_custom_success,
    list_generations_responses,
    publish_blog_custom_errors,
    publish_blog_custom_success,
    publish_blog_responses,
)

blog_search_service = BlogSearchService()


router = APIRouter(
    prefix="/organizations/{organization_id}/jurisdictions",
    tags=["Jurisdiction Blog Posts"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard), Depends(require_billing_access)],
)

logger = logging.getLogger(__name__)


@router.get(
    "/blog/posts",
    response_model=List[BlogPostResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all published blog posts",
    description="Fetches blog posts, ranks them based on relevance to \
        query terms, and returns a paginated list.",
    responses=get_all_blog_posts_responses,
)
async def get_all_blog_posts(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    query_terms: Optional[Union[List[str], str]] = Query(
        None, description="Search terms as string or list of strings"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Number of posts per page"),
):
    """
    Retrieve, rank, and paginate blog posts for a given organization.

    Args:
        organization_id (UUID): Filter posts by organization.
        db (AsyncSession): Database session (injected).
        query_terms (Union[List[str], str]): Terms to search in blog content,\
            title, keywords, meta description.
        page (int): Page number for pagination (default=1).
        limit (int): Number of posts per page (default=20, max=100).

    Returns:
        List[BlogPostResponse]: List of ranked and paginated blog posts.

    Raises:
        ProcessingError: If fetching or ranking posts fails internally \
            (logged but not exposed as DB errors).
    """
    result = await blog_search_service.get_all_blog_posts_service(
        db=db, query_terms=query_terms, page=page, limit=limit, organization_id=organization_id
    )

    return success_response(
        status_code=result["status_code"], message=result["message"], data=result["data"]
    )


@router.get(
    "/{jurisdiction_id}/blog",
    response_model=BlogPostResponse,
    status_code=status.HTTP_200_OK,
    responses=get_blog_responses,
)
async def get_blog_post(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the blog post for a jurisdiction.

    Returns the published blog post if it exists and is published.
    Draft posts (is_published=False) are only visible to organization members.

    Args:
        organization_id: Organization UUID (from path).
        jurisdiction_id: Jurisdiction UUID.
        db: Database session.

    Returns:
        JSONResponse: Blog post data with content and metadata.

    Raises:
        ResourceNotFoundError: If jurisdiction or blog post doesn't exist.
    """
    result = await BlogGenerationService.get_blog_post(db, organization_id, jurisdiction_id)

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


@router.post(
    "/{jurisdiction_id}/blog/generate",
    status_code=status.HTTP_202_ACCEPTED,
    responses=generate_blog_responses,
)
async def generate_blog_post(
    organization_id: UUID,
    jurisdiction_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger manual blog post generation.

    Creates a BlogGenerationJob to track the generation lifecycle,
    then runs generation in the background. Returns 202 with job_id
    for status polling.

    Args:
        organization_id: Organization UUID (from path).
        jurisdiction_id: Jurisdiction UUID.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        JSONResponse: 202 response with job_id for polling.

    Raises:
        ResourceNotFoundError: If jurisdiction doesn't exist.
        BlogGenerationInProgressError: If a generation is already in progress.
    """
    result = await BlogGenerationService.trigger_generation(db, organization_id, jurisdiction_id)

    job = result.pop("_job")
    background_tasks.add_task(_generate_blog_in_background, jurisdiction_id, job.id)

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


@router.get(
    "/{jurisdiction_id}/blog/generations/{job_id}",
    status_code=status.HTTP_200_OK,
    responses=get_generation_status_responses,
)
async def get_generation_status(
    organization_id: UUID,
    jurisdiction_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of a specific blog generation job.

    Returns the full job details including status, timestamps, and
    error information if applicable.

    Args:
        organization_id: Organization UUID (from path).
        jurisdiction_id: Jurisdiction UUID.
        job_id: BlogGenerationJob UUID.
        db: Database session.

    Returns:
        JSONResponse: Job status details.

    Raises:
        ResourceNotFoundError: If jurisdiction or job not found.
    """
    result = await BlogGenerationService.get_generation_status(
        db, organization_id, jurisdiction_id, job_id
    )

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


@router.get(
    "/{jurisdiction_id}/blog/generations",
    status_code=status.HTTP_200_OK,
    responses=list_generations_responses,
)
async def list_generation_jobs(
    organization_id: UUID,
    jurisdiction_id: UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """
    List blog generation jobs for a jurisdiction.

    Returns a paginated list of generation jobs sorted by creation date
    (most recent first). Useful for viewing generation history.

    Args:
        organization_id: Organization UUID (from path).
        jurisdiction_id: Jurisdiction UUID.
        page: Page number (1-indexed).
        limit: Items per page (1-100).
        db: Database session.

    Returns:
        JSONResponse: Paginated list of generation jobs.

    Raises:
        ResourceNotFoundError: If jurisdiction not found.
    """
    result = await BlogGenerationService.list_generation_jobs(
        db, organization_id, jurisdiction_id, page, limit
    )

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


@router.patch(
    "/{jurisdiction_id}/blog/publish",
    status_code=status.HTTP_200_OK,
    responses=publish_blog_responses,
)
async def publish_blog_post(
    organization_id: UUID,
    jurisdiction_id: UUID,
    payload: BlogPublishRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Publish or unpublish a blog post.

    Sets the is_published flag and published_at timestamp.
    Only organization members with access can publish posts.

    Args:
        organization_id: Organization UUID (from path).
        jurisdiction_id: Jurisdiction UUID.
        payload: Publish request with is_published boolean.
        db: Database session.

    Returns:
        JSONResponse: Updated blog post with new publish status.

    Raises:
        ResourceNotFoundError: If jurisdiction or blog post not found.
    """
    result = await BlogGenerationService.publish_blog_post(
        db, organization_id, jurisdiction_id, payload.is_published
    )

    return success_response(
        status_code=result["status_code"],
        message=result["message"],
        data=result["data"],
    )


async def _generate_blog_in_background(jurisdiction_id: UUID, job_id: UUID):
    """Background task to generate blog post with job tracking.

    Opens a new sync database session for the background task.
    Follows the pattern used in waitlist, organization, specialist routes.

    Args:
        jurisdiction_id: Jurisdiction to generate blog for.
        job_id: BlogGenerationJob ID for status tracking.
    """
    db: Session = SyncSessionLocal()
    try:
        service = BlogGenerationService(db)
        result = service.generate_blog_post_sync(jurisdiction_id, job_id=job_id)
        logger.info(
            f"Background blog generation completed: {result['status']} for {jurisdiction_id}"
        )
    except Exception as e:
        logger.error(f"Background blog generation failed for {jurisdiction_id}: {e}", exc_info=True)
    finally:
        db.close()


# Attach custom markers for OpenAPI generator
get_blog_post._custom_errors = get_blog_custom_errors
get_blog_post._custom_success = get_blog_custom_success

generate_blog_post._custom_errors = generate_blog_custom_errors
generate_blog_post._custom_success = generate_blog_custom_success

publish_blog_post._custom_errors = publish_blog_custom_errors
publish_blog_post._custom_success = publish_blog_custom_success

get_generation_status._custom_errors = get_generation_status_custom_errors
get_generation_status._custom_success = get_generation_status_custom_success

list_generation_jobs._custom_errors = list_generations_custom_errors
list_generation_jobs._custom_success = list_generations_custom_success

get_all_blog_posts._custom_errors = get_all_blog_posts_custom_errors
get_all_blog_posts._custom_success = get_all_blog_posts_custom_success
