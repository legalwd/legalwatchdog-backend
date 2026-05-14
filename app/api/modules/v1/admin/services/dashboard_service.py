"""
Service layer for superadmin dashboard operations.
Handles all business logic and database interactions for dashboard metrics.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    AICreditsMetricsError,
    AICreditsTrendError,
    DashboardOverviewError,
    InvalidDateRangeError,
    ParallelMetricsError,
    PaymentBreakdownError,
    RevenueMetricsError,
    RevenueTrendError,
    UserMetricsError,
)
from app.api.modules.v1.admin.services.superadmin_metrics_service import (
    SuperadminMetricsService,
)

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Service class for dashboard business logic.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the dashboard service.

        Args:
            db (AsyncSession): Database session for querying metrics data
        """
        self.db = db
        self.metrics_service = SuperadminMetricsService(db)

    async def get_dashboard_overview(self, days: int = 30, user_email: str = None) -> Dict:
        """
        Get comprehensive dashboard overview metrics.

        Args:
            days: Number of days to analyze (1-365).
            user_email: Email of the superadmin accessing the dashboard (for logging).

        Returns:
            dict: Dashboard metrics with revenue, users, AI credits, and breakdowns

        Raises:
            InvalidDateRangeError: If date range exceeds limits
            DashboardOverviewError: If unable to retrieve dashboard overview
        """
        try:
            self._validate_days(days)

            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            revenue_metrics = await self.metrics_service.get_revenue_metrics(start_date, end_date)
            user_metrics = await self.metrics_service.get_user_metrics(start_date)
            ai_credit_metrics = await self.metrics_service.get_ai_credit_metrics(
                start_date, end_date
            )
            parallel_metrics = await self.metrics_service.get_parallel_metrics(start_date, end_date)
            payment_breakdown = await self.metrics_service.get_trialing_vs_paid_breakdown(months=12)

            dashboard_data = {
                "revenue": revenue_metrics,
                "users": user_metrics,
                "ai_credits": ai_credit_metrics,
                "parallel_ai": parallel_metrics,
                "payment_breakdown": payment_breakdown,
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days,
                },
            }

            if user_email:
                logger.info(f"Superadmin {user_email} accessed dashboard overview (days={days})")

            return dashboard_data

        except InvalidDateRangeError:
            logger.error(f"Invalid days parameter: days={days}")
            raise
        except (
            RevenueMetricsError,
            UserMetricsError,
            AICreditsMetricsError,
            ParallelMetricsError,
            PaymentBreakdownError,
        ):
            raise
        except Exception as e:
            logger.exception(f"Failed to get dashboard overview: {str(e)}")
            raise DashboardOverviewError(
                "Unable to load dashboard overview. Please try again later."
            )

    async def get_revenue_trend(self, months: int = 12, user_email: str = None) -> Dict:
        """
        Get detailed revenue trend for time-series chart.

        Args:
            months: Number of months to retrieve (1-24).
            user_email: Email of the superadmin (for logging).

        Returns:
            dict: Revenue trend data with monthly breakdown

        Raises:
            InvalidDateRangeError: If months parameter exceeds limits
            RevenueTrendError: If unable to retrieve revenue trend
        """
        try:
            self._validate_months(months)

            trend = await self.metrics_service._get_monthly_revenue_trend(months)

            if user_email:
                logger.info(f"Superadmin {user_email} accessed revenue trend (months={months})")

            return {"trend": trend, "months": months}

        except InvalidDateRangeError:
            logger.error(f"Invalid months parameter: months={months}")
            raise
        except RevenueMetricsError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get revenue trend: {str(e)}")
            raise RevenueTrendError("Unable to load revenue trends. Please try again later.")

    async def get_ai_credits_trend(self, months: int = 12, user_email: str = None) -> Dict:
        """
        Get AI credit consumption trend for monitoring usage patterns.

        Args:
            months: Number of months to retrieve (1-24).
            user_email: Email of the superadmin (for logging).

        Returns:
            dict: AI credits trend data with monthly token counts

        Raises:
            InvalidDateRangeError: If months parameter exceeds limits
            AICreditsTrendError: If unable to retrieve AI credits trend
        """
        try:
            self._validate_months(months)

            trend = await self.metrics_service._get_monthly_token_trend(months)

            if user_email:
                logger.info(f"Superadmin {user_email} accessed AI credits trend (months={months})")

            return {"trend": trend, "months": months}

        except InvalidDateRangeError:
            logger.error(f"Invalid months parameter: months={months}")
            raise
        except AICreditsMetricsError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get AI credits trend: {str(e)}")
            raise AICreditsTrendError("Unable to load AI credit trends. Please try again later.")

    async def get_payment_breakdown(self, months: int = 12, user_email: str = None) -> Dict:
        """
        Get trialing vs paid users breakdown by month.

        Args:
            months: Number of months to retrieve (1-24).
            user_email: Email of the superadmin (for logging).

        Returns:
            dict: Payment breakdown with trialing and paid user counts per month

        Raises:
            InvalidDateRangeError: If months parameter exceeds limits
            PaymentBreakdownError: If unable to retrieve payment breakdown
        """
        try:
            self._validate_months(months)

            breakdown = await self.metrics_service.get_trialing_vs_paid_breakdown(months)

            if user_email:
                logger.info(f"Superadmin {user_email} accessed payment breakdown (months={months})")

            return {"breakdown": breakdown, "months": months}

        except InvalidDateRangeError:
            logger.error(f"Invalid months parameter: months={months}")
            raise
        except PaymentBreakdownError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get payment breakdown: {str(e)}")
            raise PaymentBreakdownError("Unable to load payment breakdown. Please try again later.")

    def _validate_days(self, days: int) -> None:
        """
        Validate that days parameter is within allowed range.

        Args:
            days: Number of days to validate

        Raises:
            InvalidDateRangeError: If days is outside allowed range
        """
        if days < 1 or days > 365:
            raise InvalidDateRangeError("Days must be between 1 and 365")

    def _validate_months(self, months: int) -> None:
        """
        Validate that months parameter is within allowed range.

        Args:
            months: Number of months to validate

        Raises:
            InvalidDateRangeError: If months is outside allowed range
        """
        if months < 1 or months > 24:
            raise InvalidDateRangeError("Months must be between 1 and 24")
