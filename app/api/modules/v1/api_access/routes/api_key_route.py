from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.api_access.enums.api_key_scope import Scopes
from app.api.modules.v1.api_access.schemas.api_access_schema import (
    APIKeyCreateSchema,
    APIKeyOutSchema,
    PaginatedAPIKeys,
    ScopeOut,
)
from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
from app.api.modules.v1.api_access.service.api_key_service import APIKeyService
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import error_response, success_response

from .docs.api_key_route_docs import (
    create_api_key_custom_errors,
    create_api_key_custom_success,
    create_api_key_responses,
    delete_api_key_custom_errors,
    delete_api_key_custom_success,
    delete_api_key_responses,
    get_api_key_custom_errors,
    get_api_key_custom_success,
    get_api_key_responses,
    get_scopes_custom_errors,
    get_scopes_custom_success,
    get_scopes_responses,
    list_api_keys_custom_errors,
    list_api_keys_custom_success,
    list_api_keys_responses,
    rotate_api_key_custom_errors,
    rotate_api_key_custom_success,
    rotate_api_key_responses,
    set_rotation_custom_errors,
    set_rotation_custom_success,
    set_rotation_responses,
)

router = APIRouter(prefix="/organization/{organization_id}/api-keys", tags=["API Keys"])

crud = APIKeyCRUD()
service = APIKeyService(crud)


@router.post(
    "/",
    response_model=APIKeyOutSchema,
    responses=create_api_key_responses,
)
async def create_api_key(
    organization_id: UUID,
    api_key_in: APIKeyCreateSchema,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Create a new API key for a given organization.

    Generates an API key with the specified details and stores it in the database.
    Additional background tasks (e.g., sending notifications) may be executed.

    **Path / Query Parameters**
    - organization_id: UUID of the organization for which the API key is created.

    **Request Body**
    - api_key_in: Schema containing API key details such as name, permissions, and expiration.

    **Dependencies**
    - background_tasks: Optional background tasks to run after creation.
    - db: Async database session.
    - current_user_permissions: Permissions of the requesting user, used for access control.

    **Returns**
    - APIKeyOutSchema: Information about the newly created API key
    (e.g., ID, name, key value, permissions, expiration).

    **Status Codes**
    - 200 OK: API key successfully created.
    - 403 Forbidden: User does not have permission to create API keys for this organization.
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    if api_key_in.organization_id != organization_id:
        return error_response(
            status_code=400,
            message="Organization mismatch",
            error_code="Organization mismatch",
        )

    requested_scopes = api_key_in.scope.split(",")
    service.validate_scope(requested_scopes)

    api_key_obj, raw_key = await service.generate_and_hash_api_key(
        db=db,
        key_name=api_key_in.key_name,
        organization_id=organization_id,
        user_id=api_key_in.user_id,
        receiver_email=api_key_in.receiver_email,
        generated_by=api_key_in.generated_by,
        scopes=requested_scopes,
        expires_at=api_key_in.expires_at,
    )

    if api_key_in.receiver_email:
        background_tasks.add_task(
            service.send_api_key_onboarding_email,
            db,
            api_key_obj,
            24,
        )

    api_key_response = APIKeyOutSchema(
        key_name=api_key_obj.key_name,
        organization_name=api_key_obj.organization.name,
        user_name=api_key_obj.owner_user.name if api_key_obj.owner_user else None,
        receiver_email=api_key_obj.receiver_email,
        api_key=raw_key,
        scope=api_key_obj.scope,
        generated_by=(api_key_obj.generated_by_user.name if api_key_obj.generated_by_user else ""),
        is_active=api_key_obj.is_active,
        created_at=api_key_obj.created_at,
        expires_at=api_key_obj.expires_at,
        last_used_at=api_key_obj.last_used_at,
        rotation_enabled=getattr(api_key_obj, "rotation_enabled", False),
        rotation_interval_days=getattr(api_key_obj, "rotation_interval_days", None),
        last_rotated_at=getattr(api_key_obj, "last_rotated_at", None),
    )

    return success_response(
        status_code=201,
        message="APIKey created Successfully",
        data=api_key_response.model_dump(),
    )


create_api_key._custom_errors = create_api_key_custom_errors
create_api_key._custom_success = create_api_key_custom_success


@router.get(
    "/",
    response_model=List[APIKeyOutSchema],
    responses=list_api_keys_responses,
)
async def list_api_keys(
    organization_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Retrieve a paginated list of API keys for a given organization.

    Returns API keys associated with `organization_id`, supporting pagination
    via `page` and `limit`.

    **Query Parameters**
    - page: Page number to retrieve (default: 1, ≥1)
    - limit: Number of items per page (default: 20, 1-100)

    **Path / Query Parameters**
    - organization_id: UUID of the organization

    **Dependencies**
    - db: Async database session
    - current_user_permissions: Permissions of the requesting user for access control

    **Returns**
    - List of APIKeyOutSchema objects representing the organization's API keys

    **Status Codes**
    - 200 OK: API keys retrieved successfully
    - 403 Forbidden: User does not have permission to view API keys for this organization
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    total_keys = await crud.count_keys_by_org(db, organization_id)
    pagination = calculate_pagination(total_keys, page, limit)

    api_keys = await crud.get_keys_by_org_paginated(
        db, organization_id, offset=(page - 1) * limit, limit=limit
    )

    results = [
        APIKeyOutSchema(
            key_name=k.key_name,
            organization_name=k.organization.name,
            user_name=k.owner_user.name if k.owner_user else None,
            receiver_email=k.receiver_email,
            api_key=k.hashed_key,
            scope=k.scope,
            generated_by=(k.generated_by_user.name if k.generated_by_user else ""),
            is_active=k.is_active,
            created_at=k.created_at,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            rotation_enabled=getattr(k, "rotation_enabled", False),
            rotation_interval_days=getattr(k, "rotation_interval_days", None),
            last_rotated_at=getattr(k, "last_rotated_at", None),
        )
        for k in api_keys
    ]

    paginated_results = PaginatedAPIKeys(items=results, pagination=pagination)

    return success_response(
        status_code=200,
        message="API Keys Retrieved successfully",
        data=paginated_results.model_dump(),
    )


list_api_keys._custom_errors = list_api_keys_custom_errors
list_api_keys._custom_success = list_api_keys_custom_success


@router.get(
    "/{api_key_id}",
    response_model=APIKeyOutSchema,
    responses=get_api_key_responses,
)
async def get_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Retrieve details of a specific API key for an organization.

    Fetches information about the API key identified by `api_key_id` within
    the given `organization_id`.

    **Path Parameters**
    - api_key_id: UUID of the API key to retrieve

    **Query / Path Parameters**
    - organization_id: UUID of the organization the API key belongs to

    **Dependencies**
    - db: Async database session
    - current_user_permissions: Permissions of the requesting user for access control

    **Returns**
    - APIKeyOutSchema: Details of the requested API key (e.g., name, value, permissions, expiration)

    **Status Codes**
    - 200 OK: API key retrieved successfully
    - 403 Forbidden: User does not have permission to access this API key
    - 404 Not Found: API key does not exist
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        return error_response(
            status_code=404,
            message="API key not found",
            error_code="API key not found",
        )

    api_key_response = APIKeyOutSchema(
        key_name=api_key.key_name,
        organization_name=api_key.organization.name,
        user_name=api_key.owner_user.name if api_key.owner_user else None,
        receiver_email=api_key.receiver_email,
        api_key=api_key.hashed_key,
        scope=api_key.scope,
        generated_by=(api_key.generated_by_user.name if api_key.generated_by_user else ""),
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        rotation_enabled=getattr(api_key, "rotation_enabled", False),
        rotation_interval_days=getattr(api_key, "rotation_interval_days", None),
        last_rotated_at=getattr(api_key, "last_rotated_at", None),
    )

    return success_response(
        status_code=200,
        message="APIKey retrieved successfully",
        data=api_key_response.model_dump(),
    )


get_api_key._custom_errors = get_api_key_custom_errors
get_api_key._custom_success = get_api_key_custom_success


@router.delete(
    "/{api_key_id}",
    status_code=204,
    responses=delete_api_key_responses,
)
async def delete_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Delete a specific API key for a given organization.

    Removes the API key identified by `api_key_id` from the specified
    `organization_id`. This action is irreversible.

    **Path Parameters**
    - api_key_id: UUID of the API key to delete

    **Query / Path Parameters**
    - organization_id: UUID of the organization the API key belongs to

    **Dependencies**
    - db: Async database session
    - current_user_permissions: Permissions of the requesting user for access control

    **Status Codes**
    - 204 No Content: API key deleted successfully
    - 403 Forbidden: User does not have permission to delete this API key
    - 404 Not Found: API key does not exist
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        return error_response(
            status_code=404,
            message="API Key not found",
            error_code="API Key not found",
        )

    await crud.delete_key(db, api_key_id)
    return success_response(status_code=204, message="API Key revoked")


delete_api_key._custom_errors = delete_api_key_custom_errors  # Add this
delete_api_key._custom_success = delete_api_key_custom_success


@router.post(
    "/{api_key_id}/rotate",
    response_model=dict,
    responses=rotate_api_key_responses,  # Add this
)
async def rotate_api_key(
    organization_id: UUID,
    api_key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Rotate (regenerate) the value of an existing API key.

    Generates a new API key value for the key identified by `api_key_id`
    within the specified `organization_id`. The previous key value is invalidated.

    **Path Parameters**
    - api_key_id: UUID of the API key to rotate

    **Query / Path Parameters**
    - organization_id: UUID of the organization the API key belongs to

    **Dependencies**
    - db: Async database session
    - current_user_permissions: Permissions of the requesting user for access control

    **Returns**
    - str: The new API key value

    **Status Codes**
    - 200 OK: API key rotated successfully
    - 403 Forbidden: User does not have permission to rotate this API key
    - 404 Not Found: API key does not exist
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        return error_response(
            status_code=404,
            message="API Key not found",
            error_code="API Key not found",
        )

    new_key = await service.api_key_rotation(db, api_key_id)
    return success_response(
        status_code=201,
        message="API key rotated",
        data={"api_key": new_key},
    )


class RotationToggleSchema(BaseModel):
    rotation_enabled: bool
    rotation_interval_days: int | None = None


rotate_api_key._custom_errors = rotate_api_key_custom_errors
rotate_api_key._custom_success = rotate_api_key_custom_success


@router.patch(
    "/{api_key_id}/rotation-settings",
    response_model=APIKeyOutSchema,
    responses=set_rotation_responses,
)
async def set_rotation(
    organization_id: UUID,
    api_key_id: UUID,
    payload: RotationToggleSchema,
    db: AsyncSession = Depends(get_db),
    current_user_permissions: dict = Depends(get_current_user),
):
    """
    Enable or disable automatic rotation for a specific API key.

    Updates the rotation setting of the API key identified by `api_key_id`
    within the specified `organization_id` according to the provided payload.

    **Path Parameters**
    - api_key_id: UUID of the API key to update rotation settings

    **Query / Path Parameters**
    - organization_id: UUID of the organization the API key belongs to

    **Request Body**
    - payload: RotationToggleSchema indicating whether rotation should be enabled or disabled

    **Dependencies**
    - db: Async database session
    - current_user_permissions: Permissions of the requesting user for access control

    **Returns**
    - APIKeyOutSchema: Updated API key information including rotation settings

    **Status Codes**
    - 200 OK: Rotation setting updated successfully
    - 403 Forbidden: User does not have permission to update this API key
    - 404 Not Found: API key does not exist
    """
    if not service.can_generate_key(current_user_permissions):
        return error_response(
            status_code=403,
            message="Insufficient permissions",
            error_code="Insufficient permissions",
        )

    api_key = await crud.get_key_by_id(db, api_key_id)
    if not api_key or api_key.organization_id != organization_id:
        return error_response(
            status_code=404,
            message="API Key not found",
            error_code="API Key not found",
        )

    updates = {
        "rotation_enabled": payload.rotation_enabled,
        "rotation_interval_days": payload.rotation_interval_days,
    }

    updated = await crud.update_key(db, api_key_id, **updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update API key rotation settings")

    api_key_response = APIKeyOutSchema(
        key_name=updated.key_name,
        organization_name=updated.organization.name,
        user_name=updated.owner_user.name if updated.owner_user else None,
        receiver_email=updated.receiver_email,
        api_key=updated.hashed_key,
        scope=updated.scope,
        generated_by=(updated.generated_by_user.name if updated.generated_by_user else ""),
        is_active=updated.is_active,
        created_at=updated.created_at,
        expires_at=updated.expires_at,
        last_used_at=updated.last_used_at,
        rotation_enabled=getattr(updated, "rotation_enabled", False),
        rotation_interval_days=getattr(updated, "rotation_interval_days", None),
        last_rotated_at=getattr(updated, "last_rotated_at", None),
    )

    return success_response(
        status_code=200,
        message="Rotation set successfully",
        data=api_key_response.model_dump(),
    )


set_rotation._custom_errors = set_rotation_custom_errors
set_rotation._custom_success = set_rotation_custom_success


@router.get(
    "/scopes",
    response_model=List[ScopeOut],
    responses=get_scopes_responses,
)
async def get_api_key_scopes(
    organization_id: UUID,
    current_user_permissions: dict = Depends(get_current_user),
):
    """Return available API key scopes for the UI dropdown."""
    if not service.can_generate_key(current_user_permissions):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    def friendly_label(value: str) -> str:
        if value == "*":
            return "All"
        parts = value.split(":")
        if len(parts) == 2:
            action, resource = parts
            return f"{action.replace('_', ' ').title()} {resource.replace('_', ' ').title()}"
        return value

    results = [ScopeOut(value=s.value, label=friendly_label(s.value)) for s in Scopes]

    return success_response(
        status_code=200, message="Scope retrieved successfully", data={"scopes": results}
    )


get_api_key_scopes._custom_errors = get_scopes_custom_errors
get_api_key_scopes._custom_success = get_scopes_custom_success
