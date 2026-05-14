import logging
from datetime import datetime, timezone
from typing import List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import TenantGuard
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.core.dependencies.plan_limits import require_jurisdiction_creation_allowed
from app.api.db.database import SyncSessionLocal, get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
    JurisdictionResponseSchema,
    JurisdictionScrapeHistoryResponse,
    JurisdictionUpdateSchema,
)
from app.api.modules.v1.jurisdictions.service.async_jurisdiction_state_service import (
    AsyncJurisdictionStateService,
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    JurisdictionService,
    OrgResourceGuard,
    get_descendant_ids,
)
from app.api.modules.v1.projects.schemas.stats_response_schema import JurisdictionStatsResponse
from app.api.modules.v1.scraping.schemas.source_service import SourceRead
from app.api.modules.v1.scraping.service.data_page_service import DataPageService
from app.api.modules.v1.scraping.service.jurisdiction_scraping_service import (
    JurisdictionScrapingService,
)
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import error_response, success_response

from .docs.jurisdiction_route_docs import (
    create_jurisdiction_custom_errors,
    create_jurisdiction_custom_success,
    create_jurisdiction_responses,
    get_all_jurisdictions_custom_errors,
    get_all_jurisdictions_custom_success,
    get_all_jurisdictions_responses,
    get_jurisdiction_custom_errors,
    get_jurisdiction_custom_success,
    get_jurisdiction_data_page_responses,
    get_jurisdiction_responses,
    get_jurisdiction_scrape_history_custom_errors,
    get_jurisdiction_scrape_history_custom_success,
    get_jurisdiction_scrape_history_responses,
    get_jurisdiction_scrape_job_summary_responses,
    get_jurisdiction_scrape_status_responses,
    get_jurisdiction_state_custom_errors,
    get_jurisdiction_state_custom_success,
    get_jurisdiction_state_history_custom_errors,
    get_jurisdiction_state_history_custom_success,
    get_jurisdiction_state_history_responses,
    get_jurisdiction_state_responses,
    get_jurisdictions_by_project_custom_errors,
    get_jurisdictions_by_project_custom_success,
    get_jurisdictions_by_project_responses,
    get_sources_for_jurisdiction_custom_errors,
    get_sources_for_jurisdiction_custom_success,
    get_sources_for_jurisdiction_responses,
    restore_jurisdiction_custom_errors,
    restore_jurisdiction_custom_success,
    restore_jurisdiction_responses,
    restore_jurisdictions_by_project_id_custom_errors,
    restore_jurisdictions_by_project_id_custom_success,
    restore_jurisdictions_by_project_id_responses,
    soft_delete_jurisdiction_custom_errors,
    soft_delete_jurisdiction_custom_success,
    soft_delete_jurisdiction_responses,
    soft_delete_jurisdictions_by_project_custom_errors,
    soft_delete_jurisdictions_by_project_custom_success,
    soft_delete_jurisdictions_by_project_responses,
    trigger_jurisdiction_scrape_responses,
    update_jurisdiction_custom_errors,
    update_jurisdiction_custom_success,
    update_jurisdiction_responses,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/organizations/{organization_id}/jurisdictions",
    tags=["Jurisdictions"],
    dependencies=[Depends(TenantGuard), Depends(OrgResourceGuard), Depends(require_billing_access)],
)

service = JurisdictionService()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=JurisdictionResponseSchema,
    dependencies=[Depends(require_jurisdiction_creation_allowed)],
    responses=create_jurisdiction_responses,
)
async def create_jurisdiction(
    organization_id: UUID, payload: JurisdictionCreateSchema, db: AsyncSession = Depends(get_db)
):
    """
    Create a new Jurisdiction within a project.

    This endpoint registers a new jurisdiction entity associated with a specific
    project. It supports hierarchical structures through an optional `parent_id`
    and allows additional metadata such as descriptions, prompts, and scraped data
    to be stored. Timestamps may be provided, but are typically managed by the system.

    Args:
        payload (JurisdictionCreateSchema): The data required to create a new
            jurisdiction. Includes:
                - project_id (UUID): The ID of the project this jurisdiction belongs to.
                - parent_id (Optional[UUID]): Optional reference to a parent jurisdiction,
                allowing nested or hierarchical structures.
                - name (str): The name of the jurisdiction.
                - description (Optional[str]): A detailed description of the jurisdiction.
                - prompt (Optional[str]): Optional text prompt or instruction content
                associated with the jurisdiction.
                - scrape_output (Optional[Dict[str, Any]]): Optional structured data
                generated from scraping or automated processes.
                - created_at (Optional[datetime]): Optional creation timestamp.
                - updated_at (Optional[datetime]): Optional update timestamp.
                - deleted_at (Optional[datetime]): Optional deletion timestamp.
                - is_deleted (bool): Soft-delete flag (defaults to False).

        db (AsyncSession): Database session dependency for performing persistence operations.

    Returns:
        JurisdictionResponseSchema: The newly created jurisdiction, including its
        generated ID and all persisted fields.

    Raises:
        HTTPException: If the jurisdiction cannot be created due to validation issues,
        a missing parent or project reference, or underlying database errors.
    """

    jurisdiction = Jurisdiction(**payload.model_dump())
    logger.debug("Creating jurisdiction with payload: %s", payload.model_dump())

    try:
        created = await service.create(db, jurisdiction, organization_id)

        logger.info("Jurisdiction created successfully %s", created)
        return success_response(
            status_code=201,
            message="Jurisdiction created successfully",
            data={"jurisdiction": created},
        )

    except Exception as e:
        logger.exception("Failed to create jurisdiction")
        return error_response(status_code=400, message=f"Failed to create jurisdiction {str(e)}")


create_jurisdiction._custom_errors = create_jurisdiction_custom_errors
create_jurisdiction._custom_success = create_jurisdiction_custom_success


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
    responses=get_all_jurisdictions_responses,
)
async def get_all_jurisdictions(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve jurisdictions from the system with pagination.

    Args:
        db (AsyncSession): Database session used to retrieve jurisdiction records.
        page (int): Page number (1-based).
        page_size (int): Number of items per page.

    Returns:
        List[JurisdictionResponseSchema]: A paginated list of jurisdiction records.
    """

    logger.debug("Fetching jurisdictions from DB (page=%s, page_size=%s)", page, page_size)

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    jurisdictions = await service.get_all_jurisdictions(db, organization_id=organization_id)

    total = len(jurisdictions)
    if total == 0:
        logger.info("No jurisdictions found for organization_id=%s", organization_id)
        return error_response(status_code=404, message="No jurisdictions found")

    start = (page - 1) * page_size
    end = start + page_size
    page_items = jurisdictions[start:end]

    pagination = calculate_pagination(total=total, page=page, limit=page_size)

    logger.info(
        "Retrieved %d jurisdictions for organization_id=%s, page %d",
        len(page_items),
        organization_id,
        page,
    )

    def _jid(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Jurisdiction IDs on page %d: %s", page, [_jid(j) for j in page_items])

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": page_items, "pagination": pagination},
    )


get_all_jurisdictions._custom_errors = get_all_jurisdictions_custom_errors
get_all_jurisdictions._custom_success = get_all_jurisdictions_custom_success


@router.get(
    "/project/{project_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
    responses=get_jurisdictions_by_project_responses,
)
async def get_jurisdictions_by_project(
    organization_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve jurisdictions from the system by project id including pagination.

    Args:
        project_id (UUID): ID of a project to filter jurisdictions by.
        db (AsyncSession): Database session used to retrieve jurisdiction records.
        page (int): Page number (1-based).
        page_size (int): Number of items per page.

    Returns:
        List[JurisdictionResponseSchema]: A paginated list of jurisdiction records.
    """

    jurisdictions = await service.get_jurisdictions_by_project(db, project_id, organization_id)
    logger.debug("Retrieved %d jurisdictions", len(jurisdictions) if jurisdictions else 0)

    if not jurisdictions:
        logger.info("No jurisdictions found")
        return error_response(status_code=404, message="No jurisdictions found")

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    total = len(jurisdictions)
    pagination = calculate_pagination(total=total, page=page, limit=page_size)

    start = (page - 1) * page_size
    end = start + page_size
    page_items = jurisdictions[start:end]

    logger.info("Retrieved %d jurisdictions for page %d", len(page_items), page)

    def _jid(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Jurisdiction IDs on page %d: %s", page, [_jid(j) for j in page_items])

    return success_response(
        status_code=200,
        message="Jurisdictions retrieved successfully",
        data={"jurisdictions": page_items, "pagination": pagination},
    )


get_jurisdictions_by_project._custom_errors = get_jurisdictions_by_project_custom_errors
get_jurisdictions_by_project._custom_success = get_jurisdictions_by_project_custom_success


@router.delete(
    "/project/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=soft_delete_jurisdictions_by_project_responses,
)
async def soft_delete_jurisdictions_by_project(
    organization_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete all jurisdictions in a project including
    nested jurisdictions.
    Args:
        project_id
         db (AsyncSession): Database session.
    Return:
           Archived ids
    """
    logger.debug(
        "Soft deleting jurisdictions for project_id=%s. "
        "This will also archive all nested child jurisdictions.",
        project_id,
    )
    deleted = await service.soft_delete(organization_id, db, project_id=project_id)
    logger.debug("Deleted result: %s", deleted)

    if not deleted:
        logger.info("No jurisdictions found to delete")
        return error_response(status_code=404, message="No jurisdictions found to delete")

    deleted_list = cast(List[Jurisdiction], deleted)
    deleted_ids = [str(j.id) for j in deleted_list]

    logger.info(
        "Archived %d jurisdiction(s) including nested jurisdictions for project_id=%s",
        len(deleted_ids),
        project_id,
    )
    logger.debug(
        "Archived jurisdiction IDs (nested jurisdictions were also archived): %s", deleted_ids
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


soft_delete_jurisdictions_by_project._custom_errors = (
    soft_delete_jurisdictions_by_project_custom_errors
)
soft_delete_jurisdictions_by_project._custom_success = (
    soft_delete_jurisdictions_by_project_custom_success
)


@router.get(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
    responses=get_jurisdiction_responses,
)
async def get_jurisdiction(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """
    Retrieve a single jurisdiction by its unique identifier.
    Supports pagination for the jurisdiction's children via `page` and `page_size`.
    """

    logger.debug(
        "Fetching jurisdiction with id=%s (page=%s, page_size=%s)", jurisdiction_id, page, page_size
    )
    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    if not jurisdiction:
        logger.info("jurisdiction not found: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found")

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    try:
        if isinstance(jurisdiction, dict):
            children = jurisdiction.get("children") or []
        else:
            children = getattr(jurisdiction, "children", []) or []
    except Exception:
        children = []

    if children is None or not isinstance(children, (list, tuple)):
        children = []

    total_children = len(children)
    pagination = calculate_pagination(total=total_children, page=page, limit=page_size)

    start = (page - 1) * page_size
    end = start + page_size
    page_children = children[start:end]

    try:
        if isinstance(jurisdiction, dict):
            jurisdiction_payload = dict(jurisdiction)
        else:
            jurisdiction_payload = service._serialize_jurisdiction(jurisdiction)
    except Exception:
        jurisdiction_payload = {
            "id": getattr(jurisdiction, "id", None),
            "project_id": getattr(jurisdiction, "project_id", None),
            "parent_id": getattr(jurisdiction, "parent_id", None),
            "name": getattr(jurisdiction, "name", None),
            "description": getattr(jurisdiction, "description", None),
            "prompt": getattr(jurisdiction, "prompt", None),
            "scrape_output": getattr(jurisdiction, "scrape_output", None),
            "created_at": getattr(jurisdiction, "created_at", None),
            "updated_at": getattr(jurisdiction, "updated_at", None),
            "deleted_at": getattr(jurisdiction, "deleted_at", None),
            "is_deleted": getattr(jurisdiction, "is_deleted", None),
            "children": getattr(jurisdiction, "children", []) or [],
        }

    jurisdiction_payload["children"] = page_children

    logger.info(
        "Jurisdiction retrieved successfully: id=%s, project_id=%s, returned_children=%d/%d",
        jurisdiction_payload.get("id"),
        jurisdiction_payload.get("project_id"),
        len(page_children),
        total_children,
    )
    logger.debug("Jurisdiction details: %s", jurisdiction_payload)

    return success_response(
        status_code=200,
        message="Jurisdiction retrieved successfully",
        data={"jurisdiction": jurisdiction_payload, "pagination": pagination},
    )


get_jurisdiction._custom_errors = get_jurisdiction_custom_errors
get_jurisdiction._custom_success = get_jurisdiction_custom_success


@router.patch(
    "/{jurisdiction_id}",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
    responses=update_jurisdiction_responses,
)
async def update_jurisdiction(
    organization_id: UUID,
    jurisdiction_id: UUID,
    payload: JurisdictionUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an existing jurisdiction.

    This endpoint applies partial updates to a jurisdiction identified by its
    `jurisdiction_id`. Only the fields provided in the request payload will be
    updated; all other fields remain unchanged. The update may modify structural
    relationships (such as assigning a new `parent_id`), metadata, descriptive
    content, or soft-deletion status. The `updated_at` timestamp may be supplied
    manually, though many implementations will override it automatically.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to update.
        payload (JurisdictionUpdateSchema): A schema containing the fields to update.
            All fields are optional, enabling partial updates. Fields include:
                - parent_id (Optional[UUID]): Updated parent jurisdiction reference.
                - name (Optional[str]): New name for the jurisdiction.
                - description (Optional[str]): Updated descriptive text.
                - prompt (Optional[str]): Modified prompt or instruction text.
                - scrape_output (Optional[Dict[str, Any]]): Updated structured or scraped data.
                - updated_at (Optional[datetime]): Optional manual update timestamp.
                - is_deleted (Optional[bool]): Allows soft-deleting or restoring the jurisdiction.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        JurisdictionResponseSchema: The updated jurisdiction record with all fields
        persisted and returned in their latest state.

    Raises:
        HTTPException: If the jurisdiction does not exist, if validation fails,
        or if a database error occurs during the update process.
    """

    try:
        logger.debug(
            "Updating jurisdiction id=%s with payload: %s",
            jurisdiction_id,
            payload.model_dump(exclude_unset=True),
        )
        incoming = payload.model_dump(exclude_unset=True)

        if "is_deleted" in incoming and incoming.get("is_deleted") is True:
            logger.debug("Archiving jurisdiction via PATCH: id=%s", jurisdiction_id)
            deleted = await service.soft_delete(
                organization_id, db, jurisdiction_id=jurisdiction_id
            )
            if not deleted:
                logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
                return error_response(status_code=404, message="Jurisdiction not found")

            logger.info(
                "Jurisdiction archived successfully via PATCH: id=%s",
                jurisdiction_id,
            )
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        if "is_deleted" in incoming and incoming.get("is_deleted") is False:
            logger.debug("Restoring jurisdiction via PATCH: id=%s", jurisdiction_id)
            restored = await service.restore_jurisdiction_and_children(
                db, jurisdiction_id, organization_id
            )
            if not restored:
                return error_response(
                    status_code=404, message="Jurisdiction not found or not deleted"
                )

            return success_response(
                status_code=200,
                message="Jurisdiction restored successfully",
                data={"jurisdiction": restored},
            )

        jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction:
            logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
            return error_response(status_code=404, message="Jurisdiction not found")

        new_parent_id = incoming.get("parent_id")
        if new_parent_id:
            if new_parent_id == jurisdiction.id:
                error_response(status_code=400, message="Cannot set parent_id to self")

            descendant_ids = await get_descendant_ids(jurisdiction.id, db)
            if new_parent_id in descendant_ids:
                return error_response(
                    status_code=400,
                    message="Cannot set parent_id to a descendant jurisdiction (cycle detected)",
                )

        for key, value in incoming.items():
            setattr(jurisdiction, key, value)

        if "is_deleted" in incoming:
            jurisdiction.deleted_at = (
                datetime.now(timezone.utc) if incoming.get("is_deleted") else None
            )

        updated = await service.update(db, jurisdiction, organization_id)

        logger.info(
            "Jurisdiction updated successfully: id=%s, project_id=%s",
            updated.id,
            updated.project_id,
        )
        logger.debug("Updated jurisdiction details: %s", updated)
        return success_response(
            status_code=200,
            message="Jurisdiction updated successfully",
            data={"jurisdiction": updated},
        )

    except Exception:
        return error_response(status_code=400, message="Failed to update jurisdiction")


update_jurisdiction._custom_errors = update_jurisdiction_custom_errors
update_jurisdiction._custom_success = update_jurisdiction_custom_success


@router.delete(
    "/{jurisdiction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=soft_delete_jurisdiction_responses,
)
async def soft_delete_jurisdiction(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Soft delete a single jurisdiction by ID
    whether flat or nested jurisdictions.
    Args:
        jurisdiction_id
        db (AsyncSession): Database session.
    Return:
           Archived ids
    """
    logger.debug("Soft deleting jurisdiction with id=%s", jurisdiction_id)
    deleted = await service.soft_delete(organization_id, db, jurisdiction_id=jurisdiction_id)
    logger.debug("Deleted result: %s", deleted)

    if not deleted:
        logger.info("Jurisdiction not found with id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found")

    logger.info(
        "Jurisdiction (including nested jurisdiction if any) archived successfully: id=%s",
        jurisdiction_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


soft_delete_jurisdiction._custom_errors = soft_delete_jurisdiction_custom_errors
soft_delete_jurisdiction._custom_success = soft_delete_jurisdiction_custom_success


@router.post(
    "/{jurisdiction_id}/restoration",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionResponseSchema,
    responses=restore_jurisdiction_responses,
)
async def restore_jurisdiction(
    organization_id: UUID, jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)
):
    """
    Restore a previously archived (soft-deleted) jurisdiction
    whether flat or nested.

    This endpoint reverses a soft deletion by setting the jurisdiction’s `is_deleted`
    flag back to `False` and clearing its `deleted_at` timestamp if applicable. It
    returns the fully restored jurisdiction record. If the jurisdiction is not
    currently archived—or does not exist—an appropriate error response is returned.

    Args:
        jurisdiction_id (UUID): The unique identifier of the jurisdiction to restore.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        JurisdictionResponseSchema: The restored jurisdiction with its updated
        deletion status and associated metadata.

    Raises:
        HTTPException: If the jurisdiction does not exist, is not archived,
        or if a database error occurs during the restoration process.
    """
    logger.debug("Attempting to restore jurisdiction with id=%s", jurisdiction_id)

    try:
        restored = await service.restore_jurisdiction_and_children(
            db, jurisdiction_id, organization_id
        )
    except Exception as exc:
        logger.debug(
            "restore_jurisdiction_and_children failed, falling back to legacy restore flow: %s", exc
        )
        try:
            jurisdiction = await service.get_jurisdiction_for_restoration(
                db, organization_id, jurisdiction_id, restore_nested=True
            )
            if not jurisdiction:
                restored = None
            else:
                try:
                    jurisdiction.is_deleted = False
                    jurisdiction.deleted_at = None
                except Exception:
                    pass
                updated = await service.update(db, jurisdiction, organization_id)
                if isinstance(updated, dict):
                    restored = updated
                else:
                    try:
                        restored = service._serialize_jurisdiction(updated)
                    except Exception:
                        restored = {
                            "id": getattr(updated, "id", None),
                            "project_id": getattr(updated, "project_id", None),
                            "parent_id": getattr(updated, "parent_id", None),
                            "name": getattr(updated, "name", None),
                            "description": getattr(updated, "description", None),
                            "is_deleted": getattr(updated, "is_deleted", None),
                            "deleted_at": getattr(updated, "deleted_at", None),
                            "children": getattr(updated, "children", [])
                            or updated.__dict__.get("children", []),
                        }
        except Exception as exc2:
            logger.debug("Legacy restore flow failed: %s", exc2)
            restored = None

    if not restored:
        logger.info("Jurisdiction not found or nothing to restore: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found or not deleted")

    logger.info(
        "Jurisdiction restored successfully: id=%s, project_id=%s",
        restored.get("id"),
        restored.get("project_id"),
    )
    logger.debug("Restored jurisdiction details: %s", restored)
    return success_response(
        status_code=200,
        message="Jurisdiction restored successfully",
        data={"jurisdiction": restored},
    )


restore_jurisdiction._custom_errors = restore_jurisdiction_custom_errors
restore_jurisdiction._custom_success = restore_jurisdiction_custom_success


@router.post(
    "/project/{project_id}/restoration",
    status_code=status.HTTP_200_OK,
    response_model=List[JurisdictionResponseSchema],
    responses=restore_jurisdictions_by_project_id_responses,
)
async def restore_jurisdictions_by_project_id(
    project_id: UUID, organization_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Restore all archived jurisdictions (whether flat or nested)
    for a project and return them.
       Args:
        project_id (UUID): The unique identifier of the project to restore
        all its jurisdiction.
        db (AsyncSession): Database session used to retrieve and update the jurisdiction.

    Returns:
        List[JurisdictionResponseSchema]: List of restored jurisdictions with its updated
        deletion status and associated metadata.

    Raises:
        HTTPException: If the jurisdictions does not exist, are not archived,
        or if a database error occurs during the restoration process.
    """
    logger.debug("Restoring all archived jurisdictions for project_id=%s", project_id)
    restored_jurisdictions = await service.restore_all_archived_jurisdictions(
        db, organization_id, project_id
    )
    logger.debug("Restored result: %s", restored_jurisdictions)

    if not restored_jurisdictions:
        logger.info("No archived jurisdictions found for this project")
        return error_response(
            status_code=404, message="No archived jurisdictions found for this project"
        )

    logger.info(
        "Restored %d jurisdiction(s) successfully for project_id=%s",
        len(restored_jurisdictions),
        project_id,
    )

    def _jid_or_dict(j):
        try:
            return str(j["id"]) if isinstance(j, dict) else str(getattr(j, "id", ""))
        except Exception:
            return ""

    logger.debug("Restored jurisdiction IDs: %s", [_jid_or_dict(j) for j in restored_jurisdictions])
    return success_response(
        status_code=200,
        message=f"Restored {len(restored_jurisdictions)} jurisdiction(s)",
        data={"jurisdictions": restored_jurisdictions},
    )


restore_jurisdictions_by_project_id._custom_errors = (
    restore_jurisdictions_by_project_id_custom_errors
)
restore_jurisdictions_by_project_id._custom_success = (
    restore_jurisdictions_by_project_id_custom_success
)


@router.get(
    "/{jurisdiction_id}/sources",
    status_code=status.HTTP_200_OK,
    response_model=List[SourceRead],
    responses=get_sources_for_jurisdiction_responses,
)
async def get_sources_for_jurisdiction(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """
    Retrieve sources for a specific jurisdiction with optional filtering and pagination.

    Args:
        organization_id (UUID): Organization identifier.
        jurisdiction_id (UUID): Jurisdiction identifier.
        db (AsyncSession): Database session.
        skip (int): Pagination offset (default 0).
        limit (int): Maximum records to return (default 100, max 500).
        is_active (Optional[bool]): Filter by active status.

    Returns:
        JSONResponse: Standard success response with list of sources.

    Raises:
        HTTPException: 404 if jurisdiction not found.
    """
    logger.info(
        f"User retrieving sources for jurisdiction: {jurisdiction_id} "
        f"(skip={skip}, limit={limit}, is_active={is_active})"
    )

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    if not jurisdiction:
        logger.info("Jurisdiction not found: id=%s", jurisdiction_id)
        return error_response(status_code=404, message="Jurisdiction not found")

    source_service = SourceService()
    sources = await source_service.get_sources(
        db=db,
        skip=skip,
        limit=limit,
        jurisdiction_id=jurisdiction_id,
        is_active=is_active,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Sources retrieved successfully",
        data={"sources": [source.model_dump() for source in sources]},
    )


get_sources_for_jurisdiction._custom_errors = get_sources_for_jurisdiction_custom_errors
get_sources_for_jurisdiction._custom_success = get_sources_for_jurisdiction_custom_success


_JURISDICTION_STATE_DUMP_EXCLUDE = {
    "jurisdiction",
    "confirmed_by_user",
    "originating_job",
    "history",
}
_HISTORY_DUMP_EXCLUDE = {"state", "changed_by_user"}


@router.get(
    "/{jurisdiction_id}/state",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_state_responses,
)
async def get_jurisdiction_state(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get current jurisdiction state (Compliance Ledger).

    Returns all state rows for the jurisdiction. For audit history, use GET .../state/history.
    """
    logger.info(f"Getting jurisdiction state for id={jurisdiction_id}")

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    if not jurisdiction:
        return error_response(status_code=404, message="Jurisdiction not found")

    async_jurisdiction_state_service = AsyncJurisdictionStateService(db)
    jurisdiction_state = await async_jurisdiction_state_service.get_jurisdiction_state(
        jurisdiction_id
    )
    items = [
        item.model_dump(mode="json", exclude=_JURISDICTION_STATE_DUMP_EXCLUDE)
        for item in jurisdiction_state.values()
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Jurisdiction state retrieved successfully",
        data={
            "jurisdiction_id": str(jurisdiction_id),
            "items": items,
        },
    )


get_jurisdiction_state._custom_errors = get_jurisdiction_state_custom_errors
get_jurisdiction_state._custom_success = get_jurisdiction_state_custom_success


@router.get(
    "/{jurisdiction_id}/state/history",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_state_history_responses,
)
async def get_jurisdiction_state_history(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    page_size: int = 10,
):
    """Get paginated audit log of all jurisdiction state history for a jurisdiction.

    Returns rows from the jurisdiction_state_history table (audit log for what
    happens in scrape/acceptance history), with proper pagination.
    """
    logger.info(f"Getting jurisdiction state history for id={jurisdiction_id}")

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    if not jurisdiction:
        return error_response(status_code=404, message="Jurisdiction not found")

    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return error_response(status_code=400, message="Invalid pagination parameters")
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    offset = (page - 1) * page_size
    async_jurisdiction_state_service = AsyncJurisdictionStateService(db)
    (
        history_rows,
        total,
    ) = await async_jurisdiction_state_service.get_jurisdiction_state_history_paginated(
        jurisdiction_id, limit=page_size, offset=offset
    )

    items = []
    for h in history_rows:
        item = h.model_dump(mode="json", exclude=_HISTORY_DUMP_EXCLUDE)
        state = getattr(h, "state", None)
        item["field_key"] = state.field_key if state else None
        items.append(item)

    pagination = calculate_pagination(total=total, page=page, limit=page_size)
    pagination["has_next"] = page < pagination["total_pages"]
    pagination["has_prev"] = page > 1

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Jurisdiction state history retrieved successfully",
        data={
            "jurisdiction_id": str(jurisdiction_id),
            "items": items,
            "pagination": pagination,
        },
    )


get_jurisdiction_state_history._custom_errors = get_jurisdiction_state_history_custom_errors
get_jurisdiction_state_history._custom_success = get_jurisdiction_state_history_custom_success


@router.post(
    "/{jurisdiction_id}/scrape",
    status_code=status.HTTP_202_ACCEPTED,
    responses=trigger_jurisdiction_scrape_responses,
)
async def trigger_jurisdiction_scrape(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger a scrape for all sources in a jurisdiction.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID to scrape.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Job ID and status.
    """
    logger.info(f"Manual scrape triggered for jurisdiction {jurisdiction_id}")

    jurisdiction = await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    if not jurisdiction:
        return error_response(status_code=404, message="Jurisdiction not found")

    with SyncSessionLocal() as sync_db:
        scraping_service = JurisdictionScrapingService(sync_db)
        job = scraping_service.trigger_jurisdiction_scrape(jurisdiction_id)

        return success_response(
            status_code=status.HTTP_202_ACCEPTED,
            message="Jurisdiction scrape initiated",
            data={
                "job_id": str(job.id),
                "status": job.status,
                "total_sources": job.total_sources,
                "started_at": job.started_at,
            },
        )


@router.get(
    "/{jurisdiction_id}/scrape-status",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_scrape_status_responses,
)
async def get_jurisdiction_scrape_status(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get lightweight status of most recent jurisdiction scrape job.

    Lightweight endpoint for polling scrape progress.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Job status with progress percentage.
    """
    await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)

    with SyncSessionLocal() as sync_db:
        data_page_service = DataPageService(sync_db)
        status_data = data_page_service.get_scrape_status(jurisdiction_id)

        return success_response(
            status_code=status.HTTP_200_OK, message="Scrape status retrieved", data=status_data
        )


@router.get(
    "/{jurisdiction_id}/scrape-history",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_scrape_history_responses,
)
async def get_jurisdiction_scrape_history(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    job_status: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by job status \
        (PENDING, SCRAPING, CONSOLIDATING, FILTERING, ANALYZING, COMPLETED, FAILED)",
    ),
):
    """Get paginated scrape history for a jurisdiction.

    Retrieve a paginated list of past scrape jobs for a jurisdiction,
    including their statuses, timestamps, and results.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID.
        db (AsyncSession): Database session.
        page (int): Page number (1-based, default 1).
        page_size (int): Items per page (default 10, max 100).
        status (Optional[str]): Filter by job status.

    Returns:
        JSONResponse: Paginated list of scrape jobs with metadata.
    """
    logger.info(
        f"Getting scrape history for jurisdiction={jurisdiction_id}, page={page},\
             status={job_status}"
    )

    jobs, total = await service.get_scrape_history(
        db=db,
        jurisdiction_id=jurisdiction_id,
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        status_filter=job_status,
    )

    pagination = calculate_pagination(total=total, page=page, limit=page_size)
    history_response = JurisdictionScrapeHistoryResponse(jobs=jobs, pagination=pagination)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Scrape history retrieved successfully",
        data=history_response,
    )


get_jurisdiction_scrape_history._custom_errors = get_jurisdiction_scrape_history_custom_errors
get_jurisdiction_scrape_history._custom_success = get_jurisdiction_scrape_history_custom_success


@router.get(
    "/{jurisdiction_id}/data-page",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_data_page_responses,
)
async def get_jurisdiction_data_page(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full consolidated data page content with change tracking.

    Heavy endpoint with full extracted content and field-level changes.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Full data page with extracted content and changes.
    """
    await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)

    with SyncSessionLocal() as sync_db:
        data_page_service = DataPageService(sync_db)
        page_data = data_page_service.get_data_page(jurisdiction_id)

        return success_response(
            status_code=status.HTTP_200_OK, message="Data page retrieved", data=page_data
        )


@router.get(
    "/{jurisdiction_id}/scrape-jobs/{job_id}/summary",
    status_code=status.HTTP_200_OK,
    responses=get_jurisdiction_scrape_job_summary_responses,
)
async def get_jurisdiction_scrape_job_summary(
    organization_id: UUID,
    jurisdiction_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get markdown summary and changes for a specific jurisdiction scrape job.

    Returns the markdown summary, change summary, and individual changes
    for a specific JurisdictionScrapeJob. Handles FAILED jobs by returning
    error_message with null summary data.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID.
        job_id (UUID): JurisdictionScrapeJob ID.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Scrape job summary with markdown content and changes.

    Raises:
        JurisdictionScrapeJobNotFoundError: If job doesn't exist.
        BadRequestError: If job doesn't belong to this jurisdiction.
    """
    await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)

    with SyncSessionLocal() as sync_db:
        data_page_service = DataPageService(sync_db)
        summary_data = data_page_service.get_scrape_job_summary(job_id, jurisdiction_id)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Scrape job summary retrieved",
            data=summary_data,
        )


@router.get(
    "/{jurisdiction_id}/stats",
    status_code=status.HTTP_200_OK,
    response_model=JurisdictionStatsResponse,
)
async def get_jurisdiction_stats(
    organization_id: UUID,
    jurisdiction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get change statistics for a jurisdiction.

    Returns change metrics including unresolved change counts, severity levels,
    and revision details with field changes.

    Args:
        organization_id (UUID): Organization ID.
        jurisdiction_id (UUID): Jurisdiction ID.
        db (AsyncSession): Database session.

    Returns:
        JSONResponse: Success response containing:
            - change_count: Number of unresolved changes
            - severity: Highest severity level (Major/Minor)
            - last_change_at: Timestamp of most recent change
            - change_summary: Summary of the latest change
            - revisions: List of revision details (max 5)

    Raises:
        HTTPException: 404 if jurisdiction not found.
    """
    logger.info(f"Getting stats for jurisdiction_id={jurisdiction_id}")

    await service.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)
    stats = await service.get_jurisdiction_stats(db, jurisdiction_id, organization_id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Jurisdiction statistics retrieved successfully",
        data=stats,
    )
