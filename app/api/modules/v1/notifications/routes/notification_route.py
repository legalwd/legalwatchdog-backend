import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.notifications.routes.docs.notification_route_docs import (
    get_notification_context_custom_errors,
    get_notification_context_custom_success,
    get_notification_context_responses,
    get_notification_custom_errors,
    get_notification_custom_success,
    get_notification_responses,
    get_notification_stats_custom_errors,
    get_notification_stats_custom_success,
    get_notification_stats_responses,
    get_notifications_custom_errors,
    get_notifications_custom_success,
    get_notifications_responses,
    mark_all_read_custom_errors,
    mark_all_read_custom_success,
    mark_all_read_responses,
    mark_notifications_read_custom_errors,
    mark_notifications_read_custom_success,
    mark_notifications_read_responses,
    update_notification_custom_errors,
    update_notification_custom_success,
    update_notification_responses,
)
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationContextResponse,
    NotificationFilter,
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
    NotificationStats,
    NotificationUpdate,
)
from app.api.modules.v1.notifications.service.notification_service import (
    NotificationService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user notifications",
    responses=get_notifications_responses,
)
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    notification_type: Optional[str] = Query(None, description="Filter by type"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    organization_id: Optional[uuid.UUID] = Query(None, description="Filter by organization"),
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by source"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve notifications for the authenticated user with support for pagination and filtering.

    This endpoint allows clients to fetch a paginated list of notifications belonging
    to the current user. Filters can be applied based on notification status, type,
    read state, organization, or source. The response also includes the total count
    of notifications matching the filters and the user's unread notification count.

    Requirements:
    - User must be authenticated (verified via JWT)

    Args:
        page (int): The page number to retrieve. Must be 1 or greater.
        limit (int): Number of items to return per page. Must be between 1 and 100.
        status_filter (Optional[str]): Filter notifications by status.
        notification_type (Optional[str]): Filter by notification type category.
        is_read (Optional[bool]): Filter by read state.
        organization_id (Optional[uuid.UUID]): Filter notifications linked to an organization.
        source_id (Optional[uuid.UUID]): Filter notifications linked to a specific source.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        NotificationListResponse: Paginated list of notifications with metadata.
    """
    filters = NotificationFilter(
        status=status_filter,
        notification_type=notification_type,
        is_read=is_read,
        organization_id=organization_id,
        source_id=source_id,
    )

    skip = (page - 1) * limit
    result = await NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.id,
        filters=filters,
        skip=skip,
        limit=limit,
    )

    logger.info(
        f"Retrieved {len(result['notifications'])} notifications for user {current_user.id}"
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Notifications retrieved successfully",
        data=result,
    )


get_notifications._custom_errors = get_notifications_custom_errors
get_notifications._custom_success = get_notifications_custom_success


@router.get(
    "/stats",
    response_model=NotificationStats,
    status_code=status.HTTP_200_OK,
    summary="Get notification statistics",
    responses=get_notification_stats_responses,
)
async def get_notification_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get statistics about the current user's notifications.

    This endpoint provides aggregated statistics about the user's notifications,
    such as total count, unread count, counts by type, counts by status, etc.
    Useful for dashboard displays and notification badges.

    Requirements:
    - User must be authenticated

    Args:
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        NotificationStats: Statistical information about notifications.
    """
    stats = await NotificationService.get_notification_stats(db=db, user_id=current_user.id)

    logger.info(f"Retrieved notification stats for user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Notification statistics retrieved successfully",
        data=stats,
    )


get_notification_stats._custom_errors = get_notification_stats_custom_errors
get_notification_stats._custom_success = get_notification_stats_custom_success


@router.post(
    "/mark-read",
    status_code=status.HTTP_200_OK,
    summary="Mark notifications as read",
    responses=mark_notifications_read_responses,
)
async def mark_notifications_read(
    mark_data: NotificationMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark one or more notifications as read.

    This endpoint allows users to mark multiple notifications as read in a single request.
    Only notifications belonging to the current user will be affected.

    Requirements:
    - User must be authenticated
    - User must own the notifications

    Args:
        mark_data (NotificationMarkRead): Request body with notification IDs.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        dict: Success message with count of notifications marked as read.
    """
    count = await NotificationService.mark_as_read(
        db=db,
        notification_ids=mark_data.notification_ids,
        user_id=current_user.id,
    )

    logger.info(f"Marked {count} notifications as read for user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Marked {count} notification(s) as read",
        data={"count": count},
    )


mark_notifications_read._custom_errors = mark_notifications_read_custom_errors
mark_notifications_read._custom_success = mark_notifications_read_custom_success


@router.post(
    "/mark-all-read",
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    responses=mark_all_read_responses,
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all unread notifications as read for the current user.

    This endpoint marks all notifications belonging to the authenticated user
    that are currently unread as read. Useful for "clear all" functionality.

    Requirements:
    - User must be authenticated

    Args:
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        dict: Success message with count of notifications marked as read.
    """
    count = await NotificationService.mark_all_as_read(db=db, user_id=current_user.id)

    logger.info(f"Marked all {count} notifications as read for user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Marked {count} notification(s) as read",
        data={"count": count},
    )


mark_all_read._custom_errors = mark_all_read_custom_errors
mark_all_read._custom_success = mark_all_read_custom_success


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification by ID",
    responses=get_notification_responses,
)
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific notification by ID.

    This endpoint retrieves detailed information about a single notification.
    Users can only access their own notifications.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID): The unique identifier of the notification.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        NotificationResponse: The notification details.
    """
    notification = await NotificationService.get_notification_by_id(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )

    logger.info(f"Retrieved notification {notification_id} for user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Notification retrieved successfully",
        data=notification,
    )


get_notification._custom_errors = get_notification_custom_errors
get_notification._custom_success = get_notification_custom_success


@router.get(
    "/{notification_id}/context",
    response_model=NotificationContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get notification with full context",
    responses=get_notification_context_responses,
)
async def get_notification_with_context(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get notification with full context including related entities.

    This endpoint provides comprehensive information about a notification,
    including all related entities such as projects, sources, revisions, etc.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID): The unique identifier of the notification.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        NotificationContextResponse: Notification with full contextual information.
    """
    context = await NotificationService.get_notification_with_context(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )

    logger.info(f"Retrieved notification context for {notification_id}, user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Notification context retrieved successfully",
        data=context,
    )


get_notification_with_context._custom_errors = get_notification_context_custom_errors
get_notification_with_context._custom_success = get_notification_context_custom_success


@router.patch(
    "/{notification_id}",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update notification",
    responses=update_notification_responses,
)
async def update_notification(
    notification_id: uuid.UUID,
    update_data: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a notification.

    This endpoint allows users to update notification properties such as
    marking it as read/unread or changing its status.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID): The unique identifier of the notification.
        update_data (NotificationUpdate): The fields to update.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        NotificationResponse: The updated notification details.
    """
    notification = await NotificationService.update_notification(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
        update_data=update_data,
    )

    logger.info(f"Updated notification {notification_id} for user {current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Notification updated successfully",
        data=notification,
    )


update_notification._custom_errors = update_notification_custom_errors
update_notification._custom_success = update_notification_custom_success


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification",
)
async def delete_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a notification.

    This endpoint allows users to delete a specific notification.
    The notification is permanently removed from the database.

    Requirements:
    - User must be authenticated
    - User must own the notification

    Args:
        notification_id (uuid.UUID): The unique identifier of the notification.
        db (AsyncSession): Database session dependency.
        current_user (User): The authenticated user from the request context.

    Returns:
        204 No Content on success
    """
    await NotificationService.delete_notification(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )

    logger.info(f"Deleted notification {notification_id} for user {current_user.id}")

    return None
