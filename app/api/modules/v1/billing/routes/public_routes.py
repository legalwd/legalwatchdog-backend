import logging
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.billing.routes.docs.billing_routes_docs import (
    list_plans_custom_errors,
    list_plans_custom_success,
    list_plans_responses,
)
from app.api.modules.v1.billing.schemas.billing_schema import (
    BillingPlanInfo,
)
from app.api.modules.v1.billing.service.billing_service import BillingService, get_billing_service
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    response_model=List[BillingPlanInfo],
    summary="List available subscription plans",
    responses=list_plans_responses,
)
async def list_plans(
    db: AsyncSession = Depends(get_db),
):
    """
    Return the available subscription plans with pricing and Stripe metadata.

    Args:
        db (AsyncSession): Database session injected by Depends(get_db).

    Returns:
        dict: On success, returns a dict with keys:
            - status_code (int): HTTP status code (200)
            - message (str): Human-readable message
            - data (List[BillingPlanInfo]): List of billing plans
        On error, returns a dict with keys:
            - status_code (int): HTTP status code (500)
            - message (str): Error message
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        plans = await billing_service.list_active_plans()

        response_items: List[BillingPlanInfo] = []
        for plan in plans:
            response_items.append(
                BillingPlanInfo(
                    id=plan.id,
                    code=plan.code,
                    tier=plan.tier,
                    label=plan.label,
                    interval=plan.interval.value,
                    currency=plan.currency,
                    amount=plan.amount,
                    description=plan.description,
                    features=getattr(plan, "features_", []) or [],
                    is_most_popular=plan.is_most_popular,
                    is_active=plan.is_active,
                )
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Plans retrieved",
            data=response_items,
        )
    except Exception as e:
        logger.exception("Failed to list billing plans: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list billing plans",
        )


list_plans._custom_errors = list_plans_custom_errors
list_plans._custom_success = list_plans_custom_success
