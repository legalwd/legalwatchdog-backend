"""Superadmin dashboard routes for product owner monitoring."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.routes.docs.dashboard_docs import (
    get_ai_credits_trend_custom_errors,
    get_ai_credits_trend_custom_success,
    get_ai_credits_trend_responses,
    get_dashboard_overview_custom_errors,
    get_dashboard_overview_custom_success,
    get_dashboard_overview_responses,
    get_payment_breakdown_custom_errors,
    get_payment_breakdown_custom_success,
    get_payment_breakdown_responses,
    get_revenue_trend_custom_errors,
    get_revenue_trend_custom_success,
    get_revenue_trend_responses,
)
from app.api.modules.v1.admin.services.dashboard_service import DashboardService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/superadmin/dashboard", tags=["Superadmin Dashboard"])


@router.get("/overview", responses=get_dashboard_overview_responses)
async def get_dashboard_overview(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(30, ge=1, le=365, description="Number of days for metrics"),
):
    """Get comprehensive dashboard overview metrics.

    Aggregates revenue, user counts, AI credit consumption, and payment
    status breakdowns for product owner monitoring dashboard.
    """
    service = DashboardService(db)
    dashboard_data = await service.get_dashboard_overview(days=days, user_email=current_user.email)

    return success_response(
        status_code=HTTP_200_OK,
        message="Dashboard overview loaded successfully.",
        data=dashboard_data,
    )


get_dashboard_overview._custom_success = get_dashboard_overview_custom_success
get_dashboard_overview._custom_errors = get_dashboard_overview_custom_errors


@router.get("/revenue-trend", responses=get_revenue_trend_responses)
async def get_revenue_trend(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(12, ge=1, le=24, description="Number of months"),
):
    """Get detailed revenue trend for time-series chart.

    Provides monthly revenue breakdown for visualizing revenue patterns
    and identifying growth trends.
    """
    service = DashboardService(db)
    trend_data = await service.get_revenue_trend(months=months, user_email=current_user.email)

    return success_response(
        status_code=HTTP_200_OK,
        message=f"Revenue trends for the last {months} months loaded successfully.",
        data=trend_data,
    )


get_revenue_trend._custom_success = get_revenue_trend_custom_success
get_revenue_trend._custom_errors = get_revenue_trend_custom_errors


@router.get(
    "/ai-credits-trend",
    responses=get_ai_credits_trend_responses,
)
async def get_ai_credits_trend(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(12, ge=1, le=24, description="Number of months"),
):
    """Get AI credit consumption trend for monitoring usage patterns.

    Provides monthly token usage breakdown to track AI feature adoption
    and identify high-usage periods.
    """
    service = DashboardService(db)
    trend_data = await service.get_ai_credits_trend(months=months, user_email=current_user.email)

    return success_response(
        status_code=HTTP_200_OK,
        message=f"AI credit usage trends for the last {months} months loaded successfully.",
        data=trend_data,
    )


get_ai_credits_trend._custom_success = get_ai_credits_trend_custom_success
get_ai_credits_trend._custom_errors = get_ai_credits_trend_custom_errors


@router.get(
    "/payment-breakdown",
    responses=get_payment_breakdown_responses,
)
async def get_payment_breakdown(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(12, ge=1, le=24, description="Number of months"),
):
    """Get trialing vs paid users breakdown by month.

    Shows distribution of trialing and paying users over time to monitor
    conversion rates and subscription growth.
    """
    service = DashboardService(db)
    breakdown_data = await service.get_payment_breakdown(
        months=months, user_email=current_user.email
    )

    return success_response(
        status_code=HTTP_200_OK,
        message=f"Payment breakdown for the last {months} months loaded successfully.",
        data=breakdown_data,
    )


get_payment_breakdown._custom_success = get_payment_breakdown_custom_success
get_payment_breakdown._custom_errors = get_payment_breakdown_custom_errors
