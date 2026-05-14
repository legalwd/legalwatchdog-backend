"""Superadmin customer management routes for user analytics."""

import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.routes.docs.customers_docs import (
    activate_customer_custom_errors,
    activate_customer_custom_success,
    activate_customer_responses,
    deactivate_customer_custom_errors,
    deactivate_customer_custom_success,
    deactivate_customer_responses,
    get_customer_activity_responses,
    get_customer_detail_responses,
    get_customers_custom_errors,
    get_customers_custom_success,
    list_customers_responses,
)
from app.api.modules.v1.admin.services.customer_management_service import (
    CustomerManagementService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/superadmin/customers", tags=["Superadmin Customers"])


@router.get(
    "",
    responses=list_customers_responses,
)
async def list_customers(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    payment_status: Optional[str] = Query(
        None,
        description="Filter by payment status: trialing, paid, past_due",
    ),
    search: Optional[str] = Query(None, description="Search by name or email"),
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, last_active, credits_used",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    service = CustomerManagementService(db)
    result = await service.list_customers(
        page=page,
        limit=limit,
        payment_status=payment_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"Superadmin {current_user.email} listed customers "
        f"(page={page}, limit={limit}, total={result['total']})"
    )

    response_data = result["data"]
    response_data["meta"] = result["meta"]

    return success_response(
        status_code=HTTP_200_OK,
        message="Customers retrieved successfully",
        data=response_data,
    )


list_customers._custom_success = get_customers_custom_success
list_customers._custom_errors = get_customers_custom_errors


@router.get(
    "/{user_id}",
    responses=get_customer_detail_responses,
)
async def get_customer_detail(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = CustomerManagementService(db)
    customer_data = await service.get_customer_detail(user_id)

    logger.info(f"Superadmin {current_user.email} accessed customer detail for user {user_id}")

    return success_response(
        status_code=HTTP_200_OK,
        message="Customer details retrieved successfully",
        data=customer_data,
    )


get_customer_detail._custom_success = get_customers_custom_success
get_customer_detail._custom_errors = get_customers_custom_errors


@router.get(
    "/{user_id}/activity",
    responses=get_customer_activity_responses,
)
async def get_customer_activity(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90, description="Number of days"),
):
    service = CustomerManagementService(db)
    activity_data = await service.get_customer_activity(user_id, days)

    logger.info(f"Superadmin {current_user.email} accessed activity for user {user_id}")

    return success_response(
        status_code=HTTP_200_OK,
        message=f"Customer activity for the last {days} days retrieved successfully",
        data=activity_data,
    )


get_customer_activity._custom_success = get_customers_custom_success
get_customer_activity._custom_errors = get_customers_custom_errors


@router.patch(
    "/{user_id}/activate",
    responses=activate_customer_responses,
)
async def activate_customer(
    user_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Approve a customer account for feature access.

    Approves a lead after reviewing their demo request, granting them
    access to application features. The user can now create organizations,
    manage projects, and use all platform functionality.

    This sets is_approved=True and records the approval timestamp.
    The user can login and access features after approval.

    Args:
        user_id (UUID): Unique identifier of the customer to approve.
        current_user (User): The authenticated superadmin user.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Customer approved successfully"
            - data (dict): User details with is_approved and approved_at.

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user is not a superadmin
            - 404 Not Found if customer doesn't exist
            - 500 Internal Server Error if operation fails
    """
    service = CustomerManagementService(db)
    result = await service.activate_customer(user_id, background_tasks)

    logger.info(f"Superadmin {current_user.email} approved customer {user_id}")

    return success_response(
        status_code=HTTP_200_OK,
        message="Customer approved successfully",
        data=result,
    )


activate_customer._custom_success = activate_customer_custom_success
activate_customer._custom_errors = activate_customer_custom_errors


@router.patch(
    "/{user_id}/deactivate",
    responses=deactivate_customer_responses,
)
async def deactivate_customer(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Revoke customer approval and feature access.

    Revokes the user's approval status, blocking access to features
    while still allowing them to login and view their dashboard.
    Use this to restrict a previously approved customer's access.

    This sets is_approved=False. For account suspension, use
    is_active management separately.

    Args:
        user_id (UUID): Unique identifier of the customer to revoke.
        current_user (User): The authenticated superadmin user.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Customer approval revoked successfully"
            - data (dict): User details with updated is_approved status.

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user is not a superadmin
            - 404 Not Found if customer doesn't exist
            - 500 Internal Server Error if operation fails
    """
    service = CustomerManagementService(db)
    result = await service.deactivate_customer(user_id)

    logger.info(f"Superadmin {current_user.email} revoked approval for customer {user_id}")

    return success_response(
        status_code=HTTP_200_OK,
        message="Customer approval revoked successfully",
        data=result,
    )


deactivate_customer._custom_success = deactivate_customer_custom_success
deactivate_customer._custom_errors = deactivate_customer_custom_errors
