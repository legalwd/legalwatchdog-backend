"""
Project Routes
API endpoints for project management operations.

This module provides RESTful endpoints for project CRUD operations,
including creation, retrieval, updates, archival, and deletion.
All endpoints require authentication and enforce organization-level
access control.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard, get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.core.dependencies.plan_limits import require_project_creation_allowed
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.schemas.blog_schema import (
    ProjectBulkBlogJobResponse,
)
from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
    BlogGenerationService,
)
from app.api.modules.v1.projects.schemas.project_schema import (
    BlogPublishProjectRequest,
    ProjectBase,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
    ProjectUsersResponse,
)
from app.api.modules.v1.projects.schemas.stats_response_schema import ProjectStatsResponse
from app.api.modules.v1.projects.services.project_service import ProjectService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import error_response, success_response

from .docs.project_routes_docs import (
    add_user_to_project_custom_errors,
    add_user_to_project_custom_success,
    add_user_to_project_responses,
    bulk_generate_project_blogs_responses,
    bulk_publish_project_blogs_responses,
    create_project_custom_errors,
    create_project_custom_success,
    create_project_responses,
    delete_project_custom_errors,
    delete_project_custom_success,
    delete_project_responses,
    get_bulk_generation_job_responses,
    get_project_custom_errors,
    get_project_custom_success,
    get_project_responses,
    get_project_users_custom_errors,
    get_project_users_custom_success,
    get_project_users_responses,
    list_bulk_generation_jobs_responses,
    list_projects_in_organization_custom_errors,
    list_projects_in_organization_custom_success,
    list_projects_in_organization_responses,
    remove_user_from_project_custom_errors,
    remove_user_from_project_custom_success,
    remove_user_from_project_responses,
    update_project_custom_errors,
    update_project_custom_success,
    update_project_responses,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/projects",
    tags=["Projects"],
    dependencies=[Depends(require_billing_access)],
)
logger = logging.getLogger("app")


@router.post(
    "",
    response_model=ProjectResponse,
    dependencies=[Depends(require_project_creation_allowed)],
    status_code=status.HTTP_201_CREATED,
    responses=create_project_responses,
)
async def create_project(
    payload: ProjectBase,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new project within the authenticated user's organization.

    This endpoint creates a project, associates it with the user's organization,
    and automatically adds the creating user as a member of the project. The project
    is initialized with the provided title, description, and optional master prompt.

    Args:
        payload (ProjectBase): Project data containing:
            - title (str): Project title (required, 1-255 characters)
            - description (Optional[str]): Project description
            - master_prompt (Optional[str]): High-level AI prompt
        organization_id (UUID): The organization under which the project is created.
        current_user (User): The authenticated user creating the project.
        db (AsyncSession): Database session for executing queries.

    Returns:
        JSONResponse: Standardized success response containing project details.

    Raises:
        HTTPException: If authentication fails (401) or database operation fails (500)
    """
    logger.info(f"Creating project for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.create_project(payload, organization_id, current_user.id)

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Project created successfully",
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except ValueError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )

    except Exception:
        logger.exception(f"Error creating project for user_id={current_user.id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create project. Please try again.",
        )


create_project._custom_errors = create_project_custom_errors
create_project._custom_success = create_project_custom_success


@router.get(
    "",
    response_model=ProjectListResponse,
    responses=list_projects_in_organization_responses,
)
async def list_projects_in_organization(
    organization_id: UUID,
    q: Optional[str] = Query(None, description="Search query for project title"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all projects belonging to the authenticated user's organization.

    Retrieves a paginated list of projects with optional search filtering. Only
    non-archived projects are returned, sorted by creation date descending.

    Args:
        organization_id (UUID): The organization to retrieve projects from.
        q (Optional[str]): Search query to filter projects by title.
        page (int): Page number for pagination (default: 1).
        limit (int): Number of items per page (default: 20, max: 100).
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Projects retrieved successfully"
            - data (ProjectListResponse): Projects list with pagination metadata.

    Raises:
        HTTPException: If authentication fails (401) or database retrieval fails (500)
    """
    logger.info(f"Listing projects for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        result = await project_service.list_projects(organization_id, q=q, page=page, limit=limit)

        projects_list = [ProjectResponse.model_validate(p).model_dump() for p in result["data"]]

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Projects retrieved successfully",
            data=ProjectListResponse(
                projects=projects_list,
                total=result["total"],
                page=result["page"],
                limit=result["limit"],
                total_pages=result["total_pages"],
            ).model_dump(),
        )

    except Exception:
        logger.exception(f"Error listing projects for user_id={current_user.id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve projects. Please try again.",
        )


list_projects_in_organization._custom_errors = list_projects_in_organization_custom_errors
list_projects_in_organization._custom_success = list_projects_in_organization_custom_success


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses=get_project_responses,
)
async def get_project(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve detailed information about a specific project.

    Args:
        project_id (UUID): The unique identifier of the project to retrieve.
        organization_id (UUID): The organization ID for access verification.
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Project retrieved successfully"
            - data (ProjectResponse): Complete project details.

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 404 Not Found if project doesn't exist or is inaccessible
            - 500 Internal Server Error if retrieval fails
    """
    logger.info(f"Getting project_id={project_id} for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.get_project_by_id(project_id, organization_id)

        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project retrieved successfully",
            data=ProjectResponse.model_validate(project),
        )

    except Exception:
        logger.exception(f"Error getting project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project.",
        )


get_project._custom_errors = get_project_custom_errors
get_project._custom_success = get_project_custom_success


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    responses=update_project_responses,
)
async def update_project(
    project_id: UUID,
    organization_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update project information with partial updates.

    Supports partial updates to project fields and archive/restore functionality.
    Only the fields provided in the request are modified.

    Args:
        project_id (UUID): Unique identifier of the project to update.
        organization_id (UUID): Organization ID for access verification.
        payload (ProjectUpdate): Fields to update:
            - title (Optional[str]): Project title
            - description (Optional[str]): Project description
            - master_prompt (Optional[str]): Master prompt
            - is_deleted (Optional[bool]): Archive (true) or restore (false)
        current_user (User): The authenticated user performing the update.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): Dynamic operation message
            - data (ProjectResponse): Updated project details.

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if update fails
    """
    logger.info(f"Updating project_id={project_id} for user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project, message = await project_service.update_project(
            project_id, organization_id, current_user.id, payload
        )

        if project is None:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message=message,
            data=ProjectResponse.model_validate(project).model_dump(),
        )

    except ValueError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )
    except Exception:
        logger.exception(f"Error updating project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to update project. Please try again.",
        )


update_project._custom_errors = update_project_custom_errors
update_project._custom_success = update_project_custom_success


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=delete_project_responses,
)
async def delete_project(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a project from the database.

    Args:
        project_id (UUID): Unique identifier of the project to delete.
        organization_id (UUID): Organization ID for access verification.
        current_user (User): The authenticated user performing the deletion.
        db (AsyncSession): Database session for query execution.

    Returns:
        Response: HTTP 204 No Content on successful deletion.

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user lacks permission
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if deletion fails
    """
    logger.info(f"Permanently deleting project_id={project_id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        deleted = await project_service.delete_project(project_id, current_user.id, organization_id)

        if not deleted:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except ValueError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )

    except Exception:
        logger.exception(f"Error during hard delete of project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to permanently delete project.",
        )


delete_project._custom_errors = delete_project_custom_errors
delete_project._custom_success = delete_project_custom_success


@router.get(
    "/{project_id}/users",
    response_model=ProjectUsersResponse,
    status_code=status.HTTP_200_OK,
    responses=get_project_users_responses,
)
async def get_project_users(
    project_id: UUID,
    organization_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of all users in a project.

    Retrieves the list of user IDs that are members of the specified project.
    Only users in the same organization can view project membership.

    Args:
        project_id (UUID): Unique identifier of the project.
        organization_id (UUID): Organization ID for access verification.
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Project users retrieved successfully"
            - data (dict): Dictionary with "user_ids" list

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user not in organization
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if retrieval fails
    """
    logger.info(f"Getting users for project_id={project_id}, user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        result = await project_service.get_project_users(
            project_id=project_id, organization_id=organization_id, page=page, limit=limit
        )

        if result is None:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project users retrieved successfully",
            data=result,
        )

    except Exception:
        logger.exception(f"Error getting users for project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project users.",
        )


get_project_users._custom_errors = get_project_users_custom_errors
get_project_users._custom_success = get_project_users_custom_success


@router.post(
    "/{project_id}/users/{user_id}",
    status_code=status.HTTP_201_CREATED,
    responses=add_user_to_project_responses,
)
async def add_user_to_project(
    project_id: UUID,
    user_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a user to a project.

    Adds an existing organization member to the specified project. The user
    to be added must already be a member of the organization. Only users
    with 'edit_projects' permission (Admin and Manager) can add users to projects.

    Args:
        project_id (UUID): Unique identifier of the project.
        user_id (UUID): UUID of the user to add to the project.
        organization_id (UUID): Organization ID for access verification.
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "User successfully added to project"
            - data (dict): Empty dict or relevant metadata

    Raises:
        HTTPException:
            - 400 Bad Request if user already in project or not in organization
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if current user lacks edit_projects permission
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if operation fails
    """
    logger.info(f"Adding user_id={user_id} to project_id={project_id} by user={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        success, message = await project_service.add_user(
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            current_user_id=current_user.id,
        )

        if not success:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=message,
            )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message=message,
            data={},
        )

    except ValueError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )

    except Exception:
        logger.exception(f"Error adding user_id={user_id} to project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to add user to project.",
        )


add_user_to_project._custom_errors = add_user_to_project_custom_errors
add_user_to_project._custom_success = add_user_to_project_custom_success


@router.delete(
    "/{project_id}/users/{user_id}",
    status_code=status.HTTP_200_OK,
    responses=remove_user_from_project_responses,
)
async def remove_user_from_project(
    project_id: UUID,
    user_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a user from a project.

    Removes a user's membership from the specified project. Only users with
    'edit_projects' permission (Admin and Manager) can remove users from projects.

    Args:
        project_id (UUID): Unique identifier of the project.
        user_id (UUID): UUID of the user to remove from the project.
        organization_id (UUID): Organization ID for access verification.
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "User successfully removed from project"
            - data (dict): Empty dict or relevant metadata

    Raises:
        HTTPException:
            - 400 Bad Request if user not in project
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if current user lacks edit_projects permission
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if operation fails
    """
    logger.info(
        f"Removing user_id={user_id} from project_id={project_id} by user={current_user.id}"
    )

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        success, message = await project_service.remove_user(
            project_id=project_id,
            user_id=user_id,
            organization_id=organization_id,
            current_user_id=current_user.id,
        )

        if not success:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=message,
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message=message,
            data={},
        )

    except ValueError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )

    except Exception:
        logger.exception(f"Error removing user_id={user_id} from project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to remove user from project.",
        )


remove_user_from_project._custom_errors = remove_user_from_project_custom_errors
remove_user_from_project._custom_success = remove_user_from_project_custom_success


@router.get(
    "/{project_id}/stats",
    response_model=ProjectStatsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_project_stats(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get change statistics for a project.

    Returns aggregated change metrics from all jurisdictions in the project,
    including unresolved change counts, severity levels, and recent change items.

    Args:
        project_id (UUID): Unique identifier of the project.
        organization_id (UUID): Organization ID for access verification.
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - change_count: Total number of unresolved changes
            - severity: Highest severity level (Major/Minor)
            - last_change_at: Timestamp of most recent change
            - change_summary: Summary of the latest change
            - jurisdictions: List of jurisdiction stats
            - change_items: Top 5 change items for preview

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user lacks access
            - 404 Not Found if project doesn't exist
            - 500 Internal Server Error if retrieval fails
    """
    logger.info(f"Getting stats for project_id={project_id}, user_id={current_user.id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        stats_service = ProjectService(db)
        stats = await stats_service.get_project_stats(project_id, organization_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Project statistics retrieved successfully",
            data=stats,
        )

    except Exception:
        logger.exception(f"Error getting stats for project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve project statistics.",
        )


@router.post(
    "/{project_id}/blog/bulk-generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProjectBulkBlogJobResponse,
    responses=bulk_generate_project_blogs_responses,
)
async def bulk_generate_project_blogs(
    project_id: UUID,
    organization_id: UUID,
    background_tasks: BackgroundTasks,
    publish_after_generate: bool = Query(
        False, description="Whether to also publish the generated blogs"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger bulk blog generation for all jurisdictions in a project.

    Creates a parent tracking job and enqueues background processing for
    each jurisdiction in the project.
    """
    logger.info(f"Triggering bulk blog generation for project_id={project_id}")

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        # Verify user has access to this project
        project_service = ProjectService(db)
        project = await project_service.get_project_by_id(project_id, organization_id)
        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        blog_service = BlogGenerationService(db)
        job = await blog_service.start_bulk_generation_async(
            project_id=project_id,
            user_id=current_user.id,
            publish_after_generate=publish_after_generate,
        )

        # Dispatch background execution
        background_tasks.add_task(blog_service._execute_bulk_generation_bg, job.id)

        return success_response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Bulk blog generation triggered. Check back in a few moments.",
            data=ProjectBulkBlogJobResponse.model_validate(job).model_dump(mode="json"),
        )

    except ValueError as e:
        return error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            message=str(e),
        )
    except Exception as e:
        from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP
        from app.api.core.custom_exceptions.exceptions import CustomDomainException

        if isinstance(e, CustomDomainException):
            return error_response(
                status_code=ERROR_STATUS_MAP.get(e.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
                message=e.message,
            )

        logger.exception(f"Error triggering bulk blog generation for project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred while triggering bulk generation.",
        )


@router.patch(
    "/{project_id}/blog/publish",
    status_code=status.HTTP_200_OK,
    responses=bulk_publish_project_blogs_responses,
)
async def bulk_publish_project_blogs(
    project_id: UUID,
    organization_id: UUID,
    payload: BlogPublishProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish or unpublish all jurisdiction blog posts under this project (Option A batch).

    Processes every non-deleted jurisdiction in the project, or only those listed in
    ``jurisdiction_ids`` when provided. Jurisdictions without a blog row are skipped.
    """
    logger.info(
        "Bulk blog publish for project_id=%s is_published=%s",
        project_id,
        payload.is_published,
    )

    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.get_project_by_id(project_id, organization_id)
        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        result = await ProjectService.publish_all_project_blogs(
            db,
            organization_id,
            project_id,
            payload.is_published,
            jurisdiction_ids=payload.jurisdiction_ids,
        )

        return success_response(
            status_code=result["status_code"],
            message=result["message"],
            data=result["data"],
        )

    except Exception as e:
        from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP
        from app.api.core.custom_exceptions.exceptions import CustomDomainException

        if isinstance(e, CustomDomainException):
            return error_response(
                status_code=ERROR_STATUS_MAP.get(e.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
                message=e.message,
            )

        logger.exception("Error in bulk_publish_project_blogs for project_id=%s", project_id)
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred while updating blog publish status.",
        )


@router.get(
    "/{project_id}/blog/bulk-jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=ProjectBulkBlogJobResponse,
    responses=get_bulk_generation_job_responses,
)
async def get_bulk_generation_job(
    project_id: UUID,
    job_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a specific bulk blog generation job."""
    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.get_project_by_id(project_id, organization_id)
        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        blog_service = BlogGenerationService(db)
        result = await blog_service.get_bulk_generation_status(db, project_id, job_id)

        return success_response(**result)

    except Exception as e:
        from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP
        from app.api.core.custom_exceptions.exceptions import CustomDomainException

        if isinstance(e, CustomDomainException):
            return error_response(
                status_code=ERROR_STATUS_MAP.get(e.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
                message=e.message,
            )

        logger.exception(f"Error retrieving bulk job {job_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve bulk job status.",
        )


@router.get(
    "/{project_id}/blog/bulk-jobs",
    status_code=status.HTTP_200_OK,
    responses=list_bulk_generation_jobs_responses,
)
async def list_bulk_generation_jobs(
    project_id: UUID,
    organization_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List bulk blog generation jobs for a project."""
    try:
        tenant = TenantGuard(db, current_user)
        await tenant.get_membership(organization_id)

        project_service = ProjectService(db)
        project = await project_service.get_project_by_id(project_id, organization_id)
        if not project:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Project not found",
            )

        blog_service = BlogGenerationService(db)
        result = await blog_service.list_bulk_generation_jobs(db, project_id, page, limit)

        return success_response(**result)

    except Exception as e:
        from app.api.core.custom_exceptions.error_status_code_mapper import ERROR_STATUS_MAP
        from app.api.core.custom_exceptions.exceptions import CustomDomainException

        if isinstance(e, CustomDomainException):
            return error_response(
                status_code=ERROR_STATUS_MAP.get(e.code, status.HTTP_500_INTERNAL_SERVER_ERROR),
                message=e.message,
            )

        logger.exception(f"Error listing bulk jobs for project_id={project_id}")
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to retrieve bulk jobs.",
        )
