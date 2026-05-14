"""Superadmin metrics service for dashboard analytics."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import Integer, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    AICreditsMetricsError,
    CustomerNotFoundError,
    InvalidDateRangeError,
    ParallelMetricsError,
    PaymentBreakdownError,
    RevenueMetricsError,
    UserMetricsError,
    UserPaymentStatusError,
)
from app.api.db.models.llm_usage import LLMUsageLog
from app.api.db.models.parallel_usage import ParallelUsageLog
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.models.invoice_history import InvoiceHistory, InvoiceStatus
from app.api.modules.v1.organization.models.user_organization_model import (
    UserOrganization,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.feature_mapping import (
    get_feature_from_endpoint,
)

logger = logging.getLogger(__name__)


class SuperadminMetricsService:
    """Service for calculating superadmin dashboard metrics and analytics.

    Aggregates data from billing, user, and LLM usage tables to provide
    comprehensive metrics for product owner dashboard monitoring.

    Attributes:
        db (AsyncSession): Database session for queries.

    Examples:
        >>> service = SuperadminMetricsService(db)
        >>> revenue_metrics = await service.get_revenue_metrics()
        >>> print(revenue_metrics["total"])
        150000.00
    """

    def __init__(self, db: AsyncSession):
        """Initialize metrics service.

        Args:
            db (AsyncSession): Database session.
        """
        self.db = db

    async def get_revenue_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Calculate revenue metrics with trends and detailed comparisons.

        Aggregates total revenue from invoice history, converts to dollars,
        and provides daily trends with percentage change vs previous period.

        Args:
            start_date (Optional[datetime]): Start date for filtering.
            end_date (Optional[datetime]): End date for filtering.

        Returns:
            dict: Revenue metrics with:
                - total_revenue: Revenue in dollars (converted from cents)
                - previous_period_revenue: Previous period revenue in dollars
                - percent_change: Percentage change from previous period
                - trend: Human-readable trend ("up", "down", or "stable")
                - daily_trends: Daily revenue breakdown
                - period_start/end: ISO formatted date range

        Raises:
            InvalidDateRangeError: If start_date is after end_date
            RevenueMetricsError: If revenue metrics calculation fails

        Examples:
            >>> metrics = await service.get_revenue_metrics()
            >>> print(f"${metrics['total_revenue']:.2f}")
            $1500.00
            >>> print(metrics['trend'])
            'up'
        """
        try:
            now = datetime.now(timezone.utc)
            end_date = end_date or now
            start_date = start_date or (now - timedelta(days=30))

            if start_date >= end_date:
                raise InvalidDateRangeError("Start date must be before end date")

            period_length = (end_date - start_date).days
            prev_start = start_date - timedelta(days=period_length)
            prev_end = start_date

            current_revenue_query = select(func.sum(InvoiceHistory.amount_paid)).where(
                and_(
                    InvoiceHistory.status == InvoiceStatus.PAID,
                    InvoiceHistory.created_at >= start_date,
                    InvoiceHistory.created_at <= end_date,
                )
            )
            current_revenue = await self.db.scalar(current_revenue_query) or 0

            prev_revenue_query = select(func.sum(InvoiceHistory.amount_paid)).where(
                and_(
                    InvoiceHistory.status == InvoiceStatus.PAID,
                    InvoiceHistory.created_at >= prev_start,
                    InvoiceHistory.created_at < prev_end,
                )
            )
            prev_revenue = await self.db.scalar(prev_revenue_query) or 0

            if prev_revenue > 0:
                percent_change = ((current_revenue - prev_revenue) / prev_revenue) * 100
            else:
                percent_change = 100.0 if current_revenue > 0 else 0.0
            daily_query = (
                select(
                    func.date_trunc("day", InvoiceHistory.created_at).label("date"),
                    func.sum(InvoiceHistory.amount_paid).label("revenue"),
                )
                .where(
                    and_(
                        InvoiceHistory.status == InvoiceStatus.PAID,
                        InvoiceHistory.created_at >= start_date,
                    )
                )
                .group_by("date")
                .order_by("date")
            )

            daily_result = await self.db.execute(daily_query)
            daily_trends = [
                {"date": row.date.isoformat(), "revenue": float(row.revenue) / 100}
                for row in daily_result.all()
            ]

            return {
                "total_revenue": float(current_revenue) / 100,
                "previous_period_revenue": float(prev_revenue) / 100,
                "percent_change": round(percent_change, 2),
                "trend": "up" if percent_change > 0 else "down" if percent_change < 0 else "stable",
                "daily_trends": daily_trends,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
            }

        except InvalidDateRangeError:
            logger.error(f"Invalid date range: start={start_date}, end={end_date}")
            raise
        except Exception as e:
            logger.exception(f"Failed to calculate revenue metrics: {str(e)}")
            raise RevenueMetricsError(
                "Unable to calculate revenue metrics. Please try again later."
            )

    async def _get_monthly_revenue_trend(self, months: int = 12) -> list[dict]:
        """Get monthly revenue trend for chart display.

        Args:
            months (int): Number of months to retrieve.

        Returns:
            list[dict]: Monthly revenue data with month and amount.

        Examples:
            >>> trend = await service._get_monthly_revenue_trend(6)
            >>> print(trend[0])
            {'month': '2024-07', 'revenue': 12000.00}
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=months * 30)

        stmt = (
            select(
                func.date_trunc("month", InvoiceHistory.created_at).label("month"),
                func.sum(InvoiceHistory.amount_paid).label("revenue"),
            )
            .where(
                and_(
                    InvoiceHistory.created_at >= start_date,
                    InvoiceHistory.status == InvoiceStatus.PAID,
                )
            )
            .group_by("month")
            .order_by("month")
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {"month": row.month.strftime("%Y-%m"), "revenue": float(row.revenue or 0.0) / 100}
            for row in rows
        ]

    async def get_user_metrics(
        self,
        start_date: Optional[datetime] = None,
    ) -> dict:
        """Calculate user growth and distribution metrics with business KPIs.

        Aggregates user counts, segments by payment status, and calculates
        key business metrics like conversion and activity rates.

        Args:
            start_date (Optional[datetime]): Start date for filtering new users.

        Returns:
            dict: User metrics with:
                - total_users: Total active users count
                - new_users: New users in period
                - active_users: Users who logged in last 30 days
                - paid_users: Organizations with ACTIVE billing status
                - trial_users: Organizations on TRIALING billing status (or without billing status)
                - activity_rate: % of users active (business KPI)
                - conversion_rate: % of users on paid plans (business KPI)
                - daily_growth: Daily new user chart data
                - period_start: ISO formatted start date

        Raises:
            UserMetricsError: If user metrics calculation fails

        Examples:
            >>> metrics = await service.get_user_metrics()
            >>> print(f"{metrics['conversion_rate']}% conversion")
            12.5% conversion
        """
        try:
            now = datetime.now(timezone.utc)
            start_date = start_date or (now - timedelta(days=30))

            total_users_query = select(func.count(User.id)).where(User.is_active)
            total_users = await self.db.scalar(total_users_query) or 0

            new_users_query = select(func.count(User.id)).where(
                and_(User.is_active, User.created_at >= start_date)
            )
            new_users = await self.db.scalar(new_users_query) or 0

            active_cutoff = now - timedelta(days=30)
            active_users_query = select(func.count(User.id)).where(
                and_(User.is_active, User.last_login >= active_cutoff)
            )
            active_users = await self.db.scalar(active_users_query) or 0

            from app.api.modules.v1.billing.models.billing_account import BillingStatus

            paid_users_query = select(
                func.count(func.distinct(BillingAccount.organization_id))
            ).where(BillingAccount.status == BillingStatus.ACTIVE)
            paid_users = await self.db.scalar(paid_users_query) or 0

            trial_users_query = select(
                func.count(func.distinct(BillingAccount.organization_id))
            ).where(
                (BillingAccount.status == BillingStatus.TRIALING) | BillingAccount.status.is_(None)
            )
            trial_users = await self.db.scalar(trial_users_query) or 0

            daily_growth_query = (
                select(
                    func.date_trunc("day", User.created_at).label("date"),
                    func.count(User.id).label("new_users"),
                )
                .where(and_(User.is_active, User.created_at >= start_date))
                .group_by("date")
                .order_by("date")
            )

            growth_result = await self.db.execute(daily_growth_query)
            daily_growth = [
                {"date": row.date.isoformat(), "new_users": row.new_users}
                for row in growth_result.all()
            ]

            return {
                "total_users": total_users,
                "new_users": new_users,
                "active_users": active_users,
                "paid_users": paid_users,
                "trial_users": trial_users,
                "activity_rate": round(
                    (active_users / total_users * 100) if total_users > 0 else 0, 2
                ),
                "conversion_rate": round(
                    (paid_users / total_users * 100) if total_users > 0 else 0, 2
                ),
                "daily_growth": daily_growth,
                "period_start": start_date.isoformat(),
            }

        except Exception as e:
            logger.exception(f"Failed to calculate user metrics: {str(e)}")
            raise UserMetricsError("Unable to calculate user metrics. Please try again later.")

    async def get_ai_credit_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Calculate AI credit consumption and cost metrics with detailed breakdowns.

        Aggregates token usage, costs, success rates, and provides breakdown by
        provider and feature to enable cost optimization and reliability monitoring.

        Args:
            start_date (Optional[datetime]): Start date for filtering.
            end_date (Optional[datetime]): End date for filtering.

        Returns:
            dict: AI credit metrics with:
                - total_tokens: Total tokens consumed (successful requests only)
                - total_cost: Total cost in USD
                - total_requests: Total LLM requests count
                - success_rate: Percentage of successful requests
                - average_cost_per_request: Average USD cost per request
                - provider_breakdown: Usage by provider (OpenRouter, Gemini)
                - feature_breakdown: Top 10 endpoints by cost
                - hourly_trends: Last 24 hours hourly data
                - period_start/end: ISO formatted date range

        Raises:
            InvalidDateRangeError: If start_date is after end_date
            AICreditsMetricsError: If AI credits metrics calculation fails

        Examples:
            >>> metrics = await service.get_ai_credit_metrics()
            >>> print(f"${metrics['total_cost']:.2f}")
            $123.45
            >>> print(f"{metrics['success_rate']}% success")
            98.5% success
        """
        try:
            now = datetime.now(timezone.utc)
            end_date = end_date or now
            start_date = start_date or (now - timedelta(days=30))

            if start_date >= end_date:
                raise InvalidDateRangeError("Start date must be before end date")

            total_tokens_query = select(func.sum(LLMUsageLog.total_tokens)).where(
                and_(
                    LLMUsageLog.created_at >= start_date,
                    LLMUsageLog.created_at <= end_date,
                    LLMUsageLog.success,
                )
            )
            total_tokens = await self.db.scalar(total_tokens_query) or 0

            total_cost_query = select(func.sum(LLMUsageLog.cost_usd)).where(
                and_(
                    LLMUsageLog.created_at >= start_date,
                    LLMUsageLog.created_at <= end_date,
                    LLMUsageLog.success,
                )
            )
            total_cost = await self.db.scalar(total_cost_query) or Decimal("0")

            total_requests_query = select(func.count(LLMUsageLog.id)).where(
                and_(
                    LLMUsageLog.created_at >= start_date,
                    LLMUsageLog.created_at <= end_date,
                )
            )
            total_requests = await self.db.scalar(total_requests_query) or 0

            success_requests_query = select(func.count(LLMUsageLog.id)).where(
                and_(
                    LLMUsageLog.created_at >= start_date,
                    LLMUsageLog.created_at <= end_date,
                    LLMUsageLog.success,
                )
            )
            success_requests = await self.db.scalar(success_requests_query) or 0
            success_rate = (
                round((success_requests / total_requests * 100), 2) if total_requests > 0 else 0
            )

            provider_breakdown_query = (
                select(
                    LLMUsageLog.provider,
                    func.count(LLMUsageLog.id).label("requests"),
                    func.sum(LLMUsageLog.total_tokens).label("tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("cost"),
                )
                .where(
                    and_(
                        LLMUsageLog.created_at >= start_date,
                        LLMUsageLog.created_at <= end_date,
                        LLMUsageLog.success,
                    )
                )
                .group_by(LLMUsageLog.provider)
            )

            provider_result = await self.db.execute(provider_breakdown_query)
            provider_breakdown = [
                {
                    "provider": row.provider,
                    "requests": row.requests,
                    "tokens": row.tokens or 0,
                    "cost": float(row.cost or 0),
                }
                for row in provider_result.all()
            ]

            endpoint_breakdown_query = (
                select(
                    LLMUsageLog.endpoint,
                    func.count(LLMUsageLog.id).label("requests"),
                    func.sum(LLMUsageLog.total_tokens).label("tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("cost"),
                )
                .where(
                    and_(
                        LLMUsageLog.created_at >= start_date,
                        LLMUsageLog.created_at <= end_date,
                        LLMUsageLog.success,
                    )
                )
                .group_by(LLMUsageLog.endpoint)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
                .limit(10)
            )

            endpoint_result = await self.db.execute(endpoint_breakdown_query)
            feature_breakdown = [
                {
                    "endpoint": row.endpoint,
                    "requests": row.requests,
                    "tokens": row.tokens or 0,
                    "cost": float(row.cost or 0),
                }
                for row in endpoint_result.all()
            ]

            hourly_start = now - timedelta(hours=24)
            hourly_query = (
                select(
                    func.date_trunc("hour", LLMUsageLog.created_at).label("hour"),
                    func.count(LLMUsageLog.id).label("requests"),
                    func.sum(LLMUsageLog.total_tokens).label("tokens"),
                    func.sum(LLMUsageLog.cost_usd).label("cost"),
                )
                .where(
                    and_(
                        LLMUsageLog.created_at >= hourly_start,
                        LLMUsageLog.success,
                    )
                )
                .group_by("hour")
                .order_by("hour")
            )

            hourly_result = await self.db.execute(hourly_query)
            hourly_trends = [
                {
                    "hour": row.hour.isoformat(),
                    "requests": row.requests,
                    "tokens": row.tokens or 0,
                    "cost": float(row.cost or 0),
                }
                for row in hourly_result.all()
            ]

            return {
                "total_tokens": total_tokens,
                "total_cost": float(total_cost),
                "total_requests": total_requests,
                "success_rate": success_rate,
                "average_cost_per_request": (
                    round(float(total_cost) / total_requests, 4) if total_requests > 0 else 0
                ),
                "provider_breakdown": provider_breakdown,
                "feature_breakdown": feature_breakdown,
                "hourly_trends": hourly_trends,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
            }

        except InvalidDateRangeError:
            logger.error(f"Invalid date range: start={start_date}, end={end_date}")
            raise
        except Exception as e:
            logger.exception(f"Failed to calculate AI credits metrics: {str(e)}")
            raise AICreditsMetricsError(
                "Unable to calculate AI credits metrics. Please try again later."
            )

    async def _get_monthly_token_trend(self, months: int = 12) -> list[dict]:
        """Get monthly token usage trend for chart display.

        Args:
            months (int): Number of months to retrieve.

        Returns:
            list[dict]: Monthly token data with month and token count.

        Examples:
            >>> trend = await service._get_monthly_token_trend(6)
            >>> print(trend[0])
            {'month': '2024-07', 'tokens': 1500000}
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=months * 30)

        stmt = (
            select(
                func.date_trunc("month", LLMUsageLog.created_at).label("month"),
                func.sum(LLMUsageLog.total_tokens).label("tokens"),
            )
            .where(LLMUsageLog.created_at >= start_date)
            .group_by("month")
            .order_by("month")
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {"month": row.month.strftime("%Y-%m"), "tokens": int(row.tokens or 0)} for row in rows
        ]

    async def get_trialing_vs_paid_breakdown(
        self,
        months: int = 12,
    ) -> list[dict]:
        """Get trialing vs paid users breakdown by month.

        Args:
            months (int): Number of months to retrieve (1-24).

        Returns:
            list[dict]: Monthly breakdown with trialing and paid counts.

        Raises:
            InvalidDateRangeError: If months is not between 1 and 24
            PaymentBreakdownError: If payment breakdown calculation fails

        Examples:
            >>> breakdown = await service.get_trialing_vs_paid_breakdown(6)
            >>> print(breakdown[0])
            {'month': '2024-07', 'trialing': 100, 'paid': 50}
        """
        try:
            if months < 1 or months > 24:
                raise InvalidDateRangeError("Months must be between 1 and 24")

            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=months * 30)

            # Query users with their billing status per month
            stmt = (
                select(
                    func.date_trunc("month", User.created_at).label("month"),
                    func.count(User.id).label("total"),
                    func.sum(case((BillingAccount.status == "ACTIVE", 1), else_=0)).label("paid"),
                    func.sum(
                        case(
                            (
                                BillingAccount.status.is_(None)
                                | (BillingAccount.status == "TRIALING"),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("trialing"),
                )
                .select_from(User)
                .outerjoin(UserOrganization, User.id == UserOrganization.user_id)
                .outerjoin(
                    BillingAccount,
                    UserOrganization.organization_id == BillingAccount.organization_id,
                )
                .where(User.created_at >= start_date)
                .group_by("month")
                .order_by("month")
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            return [
                {
                    "month": row.month.strftime("%Y-%m"),
                    "trialing": int(row.trialing or 0),
                    "paid": int(row.paid or 0),
                }
                for row in rows
            ]

        except InvalidDateRangeError:
            logger.error(f"Invalid months parameter: months={months}")
            raise
        except Exception as e:
            logger.exception(f"Failed to calculate payment breakdown: {str(e)}")
            raise PaymentBreakdownError(
                "Unable to calculate payment breakdown. Please try again later."
            )

    async def get_user_with_payment_status(
        self,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get comprehensive user details with payment status and billing info.

        Retrieves detailed user profile including billing account information,
        recent invoices, AI usage statistics, and verification status.

        Args:
            user_id (UUID): User identifier.

        Returns:
            Optional[dict]: User profile with comprehensive details, or None if not found.
                Contains:
                - id, name, email: Basic user info
                - payment_status: Human-readable status (Free/Trial/Paid/etc.)
                - is_active, is_verified: Account status flags
                - joined_date, last_login, last_active: Activity timestamps
                - activity_duration_days: Days since registration
                - ai_usage: Nested structure with requests/tokens/cost
                - recent_invoices: Last 5 invoices with details
                - billing_account: Trial and billing date information

        Raises:
            CustomerNotFoundError: If user with given ID is not found
            UserPaymentStatusError: If unable to retrieve user payment status

        Examples:
            >>> user_data = await service.get_user_with_payment_status(user_id)
            >>> if user_data:
            ...     print(f"{user_data['name']} - {user_data['payment_status']}")
            ...     print(f"Invoices: {len(user_data['recent_invoices'])}")
        """
        try:
            user = await self.db.get(User, user_id)

            if not user:
                raise CustomerNotFoundError(f"Customer with ID {user_id} not found")

            billing_account = None
            payment_status = "Free"

            user_org_query = select(UserOrganization).where(
                and_(UserOrganization.user_id == user_id, UserOrganization.is_active)
            )
            user_org_result = await self.db.execute(user_org_query)
            user_org = user_org_result.scalars().first()

            if user_org:
                billing_query = select(BillingAccount).where(
                    BillingAccount.organization_id == user_org.organization_id
                )
                billing_account = await self.db.scalar(billing_query)

                if billing_account:
                    from app.api.modules.v1.billing.models.billing_account import BillingStatus

                    if billing_account.status == BillingStatus.TRIALING:
                        payment_status = "Trial"
                    elif billing_account.status == BillingStatus.ACTIVE:
                        payment_status = "Paid"
                    elif billing_account.status == BillingStatus.PAST_DUE:
                        payment_status = "Past Due"
                    elif billing_account.status == BillingStatus.CANCELLED:
                        payment_status = "Cancelled"

            invoices = []
            if billing_account:
                invoices_query = (
                    select(InvoiceHistory)
                    .where(InvoiceHistory.billing_account_id == billing_account.id)
                    .order_by(InvoiceHistory.created_at.desc())
                    .limit(5)
                )
                invoices_result = await self.db.execute(invoices_query)
                invoices = [
                    {
                        "id": str(inv.id),
                        "amount": float(inv.amount_paid) / 100,
                        "status": inv.status.value,
                        "created_at": inv.created_at.isoformat(),
                    }
                    for inv in invoices_result.scalars().all()
                ]

            ai_usage_query = select(
                func.count(LLMUsageLog.id).label("requests"),
                func.sum(LLMUsageLog.total_tokens).label("tokens"),
                func.sum(LLMUsageLog.cost_usd).label("cost"),
            ).where(LLMUsageLog.user_id == user_id)
            ai_usage_result = await self.db.execute(ai_usage_query)
            ai_usage = ai_usage_result.first()

            activity_duration_days = (datetime.now(timezone.utc) - user.created_at).days

            return {
                "id": str(user.id),
                "name": user.full_name or "N/A",
                "email": user.email,
                "payment_status": payment_status,
                "joined_date": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "activity_duration_days": activity_duration_days,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "ai_usage": {
                    "total_requests": ai_usage.requests or 0,
                    "total_tokens": ai_usage.tokens or 0,
                    "total_cost": float(ai_usage.cost or 0),
                },
                "recent_invoices": invoices,
                "billing_account": (
                    {
                        "status": billing_account.status.value,
                        "trial_ends_at": (
                            billing_account.trial_ends_at.isoformat()
                            if billing_account.trial_ends_at
                            else None
                        ),
                        "next_billing_at": (
                            billing_account.next_billing_at.isoformat()
                            if billing_account.next_billing_at
                            else None
                        ),
                    }
                    if billing_account
                    else None
                ),
            }

        except CustomerNotFoundError:
            logger.error(f"Customer not found: user_id={user_id}")
            raise
        except Exception as e:
            logger.exception(f"Failed to retrieve user payment status: {str(e)}")
            raise UserPaymentStatusError(
                "Unable to retrieve user payment status. Please try again later."
            )

    async def get_feature_usage_breakdown(
        self,
        user_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get feature-level usage breakdown from endpoint mapping.

        Args:
            user_id (Optional[UUID]): Filter by user.
            organization_id (Optional[UUID]): Filter by organization.
            start_date (Optional[datetime]): Start date for filtering.
            end_date (Optional[datetime]): End date for filtering.

        Returns:
            list[dict]: Feature usage with credits and count per feature.

        Examples:
            >>> usage = await service.get_feature_usage_breakdown(user_id=user_id)
            >>> print(usage[0])
            {'feature': 'AI Source Extraction', 'credits_used': 50000, 'usage_count': 120}
        """
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        try:
            if start_date > end_date:
                raise InvalidDateRangeError(
                    f"Start date {start_date} cannot be after end date {end_date}"
                )

            conditions = [
                LLMUsageLog.created_at >= start_date,
                LLMUsageLog.created_at <= end_date,
            ]

            if user_id:
                conditions.append(LLMUsageLog.user_id == user_id)
            if organization_id:
                conditions.append(LLMUsageLog.organization_id == organization_id)

            stmt = (
                select(
                    LLMUsageLog.endpoint,
                    func.sum(LLMUsageLog.total_tokens).label("credits_used"),
                    func.count(LLMUsageLog.id).label("usage_count"),
                )
                .where(and_(*conditions))
                .group_by(LLMUsageLog.endpoint)
                .order_by(func.sum(LLMUsageLog.total_tokens).desc())
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            feature_usage = {}
            for row in rows:
                feature = get_feature_from_endpoint(row.endpoint)
                feature_name = feature.value

                if feature_name not in feature_usage:
                    feature_usage[feature_name] = {
                        "feature": feature_name,
                        "credits_used": 0,
                        "usage_count": 0,
                    }

                feature_usage[feature_name]["credits_used"] += int(row.credits_used or 0)
                feature_usage[feature_name]["usage_count"] += int(row.usage_count or 0)

            return list(feature_usage.values())

        except InvalidDateRangeError:
            logger.error(f"Invalid date range: start={start_date}, end={end_date}")
            raise
        except Exception as e:
            logger.exception(f"Failed to calculate feature usage breakdown: {str(e)}")
            raise AICreditsMetricsError(
                "Unable to calculate feature usage breakdown. Please try again later."
            )

    async def get_parallel_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculate Parallel.ai usage metrics for superadmin dashboard.

        Aggregates Parallel.ai extraction requests, costs, success rates,
        and performance metrics over the specified time period.

        Args:
            start_date: Optional start date for filtering.
            end_date: Optional end date for filtering.

        Returns:
            Dict containing:
                - total_requests: Total extraction requests
                - successful_requests: Successful extractions
                - failed_requests: Failed extractions
                - success_rate: Percentage of successful extractions
                - total_cost: Total API costs in USD
                - avg_latency_ms: Average request latency
                - total_content_mb: Total extracted content size in MB
                - endpoint_breakdown: Usage by API endpoint
                - daily_trends: Daily request counts and costs

        Raises:
            InvalidDateRangeError: If start_date is after end_date
            ParallelMetricsError: If calculation fails

        Examples:
            >>> service = SuperadminMetricsService(db)
            >>> metrics = await service.get_parallel_metrics()
            >>> print(metrics['total_requests'])
            1250
        """
        now = datetime.now(timezone.utc)
        end_date = end_date or now
        start_date = start_date or (now - timedelta(days=30))

        try:
            if start_date > end_date:
                raise InvalidDateRangeError(
                    f"Start date {start_date} cannot be after end date {end_date}"
                )

            # Aggregate statistics
            stats_query = select(
                func.count(ParallelUsageLog.id).label("total_requests"),
                func.sum(func.cast(ParallelUsageLog.success, Integer)).label("successful_requests"),
                func.sum(ParallelUsageLog.cost).label("total_cost"),
                func.avg(ParallelUsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(ParallelUsageLog.content_size_bytes).label("total_content_bytes"),
            ).where(
                and_(
                    ParallelUsageLog.created_at >= start_date,
                    ParallelUsageLog.created_at <= end_date,
                )
            )

            result = await self.db.execute(stats_query)
            row = result.one()

            total_requests = row.total_requests or 0
            successful_requests = row.successful_requests or 0
            failed_requests = total_requests - successful_requests
            success_rate = (
                round((successful_requests / total_requests) * 100, 2)
                if total_requests > 0
                else 0.0
            )
            total_cost = float(row.total_cost or Decimal("0"))
            avg_latency_ms = int(row.avg_latency_ms) if row.avg_latency_ms else 0
            total_content_bytes = row.total_content_bytes or 0
            total_content_mb = round(total_content_bytes / (1024 * 1024), 2)

            endpoint_query = (
                select(
                    ParallelUsageLog.endpoint_name,
                    func.count(ParallelUsageLog.id).label("requests"),
                    func.sum(ParallelUsageLog.cost).label("cost"),
                )
                .where(
                    and_(
                        ParallelUsageLog.created_at >= start_date,
                        ParallelUsageLog.created_at <= end_date,
                        ParallelUsageLog.success,
                    )
                )
                .group_by(ParallelUsageLog.endpoint_name)
                .order_by(func.count(ParallelUsageLog.id).desc())
            )

            endpoint_result = await self.db.execute(endpoint_query)
            endpoint_breakdown = [
                {
                    "endpoint": row.endpoint_name,
                    "requests": row.requests,
                    "cost": float(row.cost or Decimal("0")),
                }
                for row in endpoint_result.all()
            ]

            date_trunc_expr = func.date_trunc("day", ParallelUsageLog.created_at)
            daily_query = (
                select(
                    date_trunc_expr.label("date"),
                    func.count(ParallelUsageLog.id).label("requests"),
                    func.sum(ParallelUsageLog.cost).label("cost"),
                )
                .where(
                    and_(
                        ParallelUsageLog.created_at >= start_date,
                        ParallelUsageLog.created_at <= end_date,
                    )
                )
                .group_by(date_trunc_expr)
                .order_by(date_trunc_expr)
            )

            daily_result = await self.db.execute(daily_query)
            daily_trends = [
                {
                    "date": row.date.isoformat(),
                    "requests": row.requests,
                    "cost": float(row.cost or Decimal("0")),
                }
                for row in daily_result.all()
            ]

            return {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": success_rate,
                "total_cost": total_cost,
                "avg_latency_ms": avg_latency_ms,
                "total_content_mb": total_content_mb,
                "endpoint_breakdown": endpoint_breakdown,
                "daily_trends": daily_trends,
            }

        except InvalidDateRangeError:
            logger.error(f"Invalid date range: start={start_date}, end={end_date}")
            raise
        except Exception as e:
            logger.exception(f"Failed to calculate parallel metrics: {str(e)}")
            raise ParallelMetricsError(
                "Unable to calculate parallel metrics. Please try again later."
            )
