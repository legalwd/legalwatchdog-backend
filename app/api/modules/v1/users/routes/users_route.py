import logging
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.organization.routes.docs.organization_route_docs import (
    get_organization_custom_errors,
    get_organization_custom_success,
    get_organization_responses,
)
from app.api.modules.v1.organization.schemas.organization_schema import (
    OrganizationDetailResponse,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.routes.docs.user_routes_docs import (
    get_my_invitations_custom_errors,
    get_my_invitations_custom_success,
    get_my_invitations_responses,
    get_user_organization_details_custom_errors,
    get_user_organization_details_custom_success,
    get_user_organization_details_responses,
    get_user_organizations_custom_errors,
    get_user_organizations_custom_success,
    get_user_organizations_responses,
    get_user_profile_custom_errors,
    get_user_profile_custom_success,
    get_user_profile_responses,
    update_user_profile_custom_errors,
    update_user_profile_custom_success,
    update_user_profile_responses,
    upload_profile_picture_custom_errors,
    upload_profile_picture_custom_success,
    upload_profile_picture_responses,
)
from app.api.modules.v1.users.schemas.user_profile_schema import UpdateUserProfileRequest
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.response_payloads import success_response

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

logger = logging.getLogger("app")


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    responses=get_user_profile_responses,
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current authenticated user's complete profile.

    Returns comprehensive information about the authenticated user including:
    - Basic user information (id, email, name, etc.)
    - All organization memberships with roles
    - Account status and verification details
    - Timestamps

    Requirements:
    - User must be authenticated

    Args:
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with complete user profile

    Raises:
        NotFoundError: 404 if profile not found
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Retrieving profile for user_id={current_user.id}")

    service = UserCRUD(db)
    result = await service.get_user_profile(user_id=current_user.id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="User profile retrieved successfully",
        data=result,
    )


get_current_user_profile._custom_errors = get_user_profile_custom_errors
get_current_user_profile._custom_success = get_user_profile_custom_success


@router.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    responses=update_user_profile_responses,
    summary="Update current user's profile",
)
async def update_user_profile(
    payload: UpdateUserProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the authenticated user's profile information.

    Allows users to update their:
    - Name
    - Avatar URL

    Email cannot be changed via this endpoint for security reasons.

    Requirements:
    - User must be authenticated

    Args:
        payload: Profile update data
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with updated user profile

    Raises:
        NoFieldsToUpdateError: 400 if no fields provided
        NotFoundError: 404 if user not found
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Updating profile for user_id={current_user.id}")

    service = UserCRUD(db)
    result = await service.update_user_profile(user_id=current_user.id, payload=payload)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile updated successfully",
        data=result,
    )


update_user_profile._custom_errors = update_user_profile_custom_errors
update_user_profile._custom_success = update_user_profile_custom_success


@router.post(
    "/me/upload-profile-picture",
    status_code=status.HTTP_200_OK,
    responses=upload_profile_picture_responses,
    summary="Upload profile picture",
)
async def upload_user_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a profile picture for the authenticated user.

    Validates the file type, uploads to MinIO, and updates the user's profile_picture_url.

    Requirements:
    - User must be authenticated
    - File must be an image (jpeg, png, gif, webp)

    Args:
        file: Image file to upload
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with updated profile picture URL

    Raises:
        InvalidFileTypeError: 400 for invalid file type
        FileTooLargeError: 400 for files exceeding 5MB
        NotFoundError: 404 if user not found
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Uploading profile picture for user_id={current_user.id}")

    file_content = await file.read()

    service = UserCRUD(db)
    result = await service.upload_profile_picture(
        user_id=current_user.id,
        file_content=file_content,
        filename=file.filename,
        content_type=file.content_type,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile picture uploaded successfully",
        data=result,
    )


upload_user_profile_picture._custom_errors = upload_profile_picture_custom_errors
upload_user_profile_picture._custom_success = upload_profile_picture_custom_success


@router.get(
    "/me/invitations",
    status_code=status.HTTP_200_OK,
    responses=get_my_invitations_responses,
)
async def get_my_invitations(
    page: int = Query(default=1, ge=1, description="Page number (minimum: 1)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page (1-100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all pending invitations for the current authenticated user.

    Returns a list of all pending organization invitations that the current user has received.

    Requirements:
    - User must be authenticated

    Args:
        page: Page number
        limit: Items per page
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        dict: Success response with paginated list of pending invitations
            - items: List of InvitationResponse
            - pagination: Pagination metadata

    Raises:
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Retrieving pending invitations for user_id={current_user.id}")

    service = UserCRUD(db)
    result = await service.get_my_invitations(email=current_user.email, page=page, limit=limit)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Pending invitations retrieved successfully",
        data=result,
    )


get_my_invitations._custom_errors = get_my_invitations_custom_errors
get_my_invitations._custom_success = get_my_invitations_custom_success


@router.get(
    "/me/organizations",
    status_code=status.HTTP_200_OK,
    responses=get_user_organizations_responses,
)
async def get_all_user_organizations(
    page: int = Query(default=1, ge=1, description="Page number (minimum: 1)"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per page (1-100)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all organizations a user is a member of.

    Returns all organizations where the user has an active membership,
    along with their role in each organization.

    Requirements:
    - User must be authenticated
    - User can only view their own organizations (user_id must match current_user.id)

    Args:
        user_id: UUID of the user
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with list of organizations

    Raises:
        PermissionDeniedError: 403 if viewing another user's organizations
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Retrieving organizations for user_id={current_user.id}")

    service = UserCRUD(db)
    result = await service.get_all_user_organizations(
        user_id=current_user.id,
        page=page,
        limit=limit,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Organizations retrieved successfully",
        data=result,
    )


get_all_user_organizations._custom_errors = get_user_organizations_custom_errors
get_all_user_organizations._custom_success = get_user_organizations_custom_success


@router.get(
    "/{user_id}/organisations/{organization_id}",
    status_code=status.HTTP_200_OK,
    responses=get_user_organization_details_responses,
)
async def get_user_organization_details(
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of the organization for a specific user.

    Returns detailed information about an organization where the user
    is a member, including their role and the organization's details.

    Requirements:
    - User must be authenticated
    - User can only view their own organization details (user_id must match current_user.id)
    - User must be a member of the organization

    Args:
        user_id: UUID of the user
        organization_id: UUID of the organization
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        Success response with organization details

    Raises:
        PermissionDeniedError: 403 if viewing another user's details
        NotFoundError: 404 if organization or membership not found
        ProcessingError: 500 for database or server errors
    """
    logger.info(f"Retrieving details for org_id={organization_id} for user_id={user_id}")

    service = UserCRUD(db)
    result = await service.get_user_organization_details(
        user_id=user_id,
        organization_id=organization_id,
        current_user_id=current_user.id,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Organization details retrieved successfully",
        data=result,
    )


get_user_organization_details._custom_errors = get_user_organization_details_custom_errors
get_user_organization_details._custom_success = get_user_organization_details_custom_success


@router.get(
    "/me/organizations/{organization_id}",
    response_model=OrganizationDetailResponse,
    status_code=status.HTTP_200_OK,
    responses=get_organization_responses,
    dependencies=[Depends(require_billing_access)],
)
async def get_organization_details(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get organization details for the current user.

    This endpoint allows users to view details of their organization.
    Users can only view details of the organization they belong to.

    Requirements:
    - User must be authenticated
    - User must belong to the organization

    Args:
        organization_id: UUID of the organization to retrieve
        current_user: Authenticated user from JWT token
        db: Database session dependency

    Returns:
        OrganizationDetailResponse: Organization details

    Raises:
        NotFoundError: 404 if organization or membership not found
        ProcessingError: 500 for database or server errors
    """
    logger.info(
        f"Retrieving organization details for user_id={current_user.id}, org_id={organization_id}"
    )

    service = UserCRUD(db)
    result = await service.get_organization_details(
        organization_id=organization_id,
        requesting_user_id=current_user.id,
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Organization details retrieved successfully",
        data=result,
    )


get_organization_details._custom_errors = get_organization_custom_errors
get_organization_details._custom_success = get_organization_custom_success
