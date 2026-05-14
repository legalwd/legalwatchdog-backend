"""Service for customer management operations."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    CustomerActivityError,
    CustomerDataRetrievalError,
    CustomerNotFoundError,
    CustomerUsageError,
    InvalidCustomerFilterError,
    PaymentStatusError,
)
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.models.billing_plan import BillingPlan
from app.api.modules.v1.organization.models.user_organization_model import (
    UserOrganization,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger(__name__)


class CustomerManagementService:
    """Service handling customer management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_customers(
        self,
        page: int = 1,
        limit: int = 20,
        payment_status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> dict:
        """
        List customers with pagination and filtering.
        Returns the exact same structure as the original route.
        """
        try:
            if payment_status:
                valid_statuses = ["trialing", "paid", "past_due"]
                if payment_status.lower() not in valid_statuses:
                    raise PaymentStatusError(
                        f"Invalid payment status: {payment_status}. "
                        f"Must be one of: {', '.join(valid_statuses)}"
                    )

            valid_sort_fields = ["created_at", "last_active", "credits_used"]
            if sort_by not in valid_sort_fields:
                raise InvalidCustomerFilterError(
                    f"Invalid sort field: {sort_by}. Must be one of: {', '.join(valid_sort_fields)}"
                )

            if sort_order.lower() not in ["asc", "desc"]:
                raise InvalidCustomerFilterError(
                    f"Invalid sort order: {sort_order}. Must be 'asc' or 'desc'"
                )

            query = (
                select(User)
                .outerjoin(UserOrganization, User.id == UserOrganization.user_id)
                .outerjoin(
                    BillingAccount,
                    UserOrganization.organization_id == BillingAccount.organization_id,
                )
                .distinct(User.id)
            )

            if payment_status:
                payment_status_upper = payment_status.upper()
                if payment_status_upper == "TRIALING":
                    query = query.where(
                        (BillingAccount.status == "TRIALING") | BillingAccount.status.is_(None)
                    )
                elif payment_status_upper == "PAID":
                    query = query.where(BillingAccount.status == "ACTIVE")
                elif payment_status_upper == "PAST_DUE":
                    query = query.where(BillingAccount.status == "PAST_DUE")

            if search:
                search_pattern = f"%{search}%"
                query = query.where(
                    or_(
                        User.name.ilike(search_pattern),
                        User.email.ilike(search_pattern),
                    )
                )

            count_query = (
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .outerjoin(UserOrganization, User.id == UserOrganization.user_id)
                .outerjoin(
                    BillingAccount,
                    UserOrganization.organization_id == BillingAccount.organization_id,
                )
            )

            if payment_status:
                payment_status_upper = payment_status.upper()
                if payment_status_upper == "TRIALING":
                    count_query = count_query.where(
                        (BillingAccount.status == "TRIALING") | BillingAccount.status.is_(None)
                    )
                elif payment_status_upper == "PAID":
                    count_query = count_query.where(BillingAccount.status == "ACTIVE")
                elif payment_status_upper == "PAST_DUE":
                    count_query = count_query.where(BillingAccount.status == "PAST_DUE")

            if search:
                search_pattern = f"%{search}%"
                count_query = count_query.where(
                    or_(
                        User.name.ilike(search_pattern),
                        User.email.ilike(search_pattern),
                    )
                )

            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0

            if sort_by == "created_at":
                sort_column = User.created_at
            elif sort_by == "last_active":
                sort_column = User.last_active
            else:
                sort_column = User.created_at

            if sort_order.lower() == "asc":
                query = query.order_by(User.id, sort_column.asc())
            else:
                query = query.order_by(User.id, sort_column.desc())

            offset = (page - 1) * limit
            query = query.offset(offset).limit(limit)

            result = await self.db.execute(query)
            users = result.scalars().all()

            customers_data = []
            failed_users = []

            for user in users:
                try:
                    async with self.db.begin_nested():
                        user_data = await self._get_user_with_payment_status(user.id)
                        customers_data.append(user_data)
                except Exception as e:
                    failed_users.append({"id": str(user.id), "email": user.email})
                    logger.error(
                        f"Failed to retrieve customer data for user {user.id} ({user.email}): {e}",
                        exc_info=True,
                    )
                    continue

            if failed_users:
                logger.error(
                    f"Failed to retrieve data for {len(failed_users)} user(s): {failed_users}"
                )

            pagination = calculate_pagination(total, page, limit)

            return {
                "data": {"customers": customers_data},
                "meta": pagination,
                "total": total,
            }

        except (InvalidCustomerFilterError, PaymentStatusError, CustomerNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Error listing customers: {e}", exc_info=True)
            raise CustomerDataRetrievalError("Failed to retrieve customers list")

    async def get_customer_detail(self, user_id: UUID) -> dict:
        """
        Get detailed customer analytics.
        Returns the EXACT same structure as the original route.
        """
        try:
            try:
                profile = await self._get_user_with_payment_status(user_id)
            except CustomerNotFoundError as e:
                logger.warning(f"Customer {user_id} not found: {e}")
                raise

            feature_usage = await self.get_feature_usage_breakdown(user_id=user_id)

            llm_usage = {}
            try:
                from app.api.core.llm.usage_tracker import LLMUsageTracker

                org_ids = await self._get_user_organization_ids(user_id)
                tracker = LLMUsageTracker()
                llm_usage = await tracker.get_usage_stats(
                    db=self.db,
                    user_id=user_id,
                    organization_ids=org_ids if org_ids else None,
                    start_date=datetime.now(timezone.utc) - timedelta(days=30),
                )
            except Exception as llm_error:
                logger.warning(f"Failed to get LLM usage for user {user_id}: {llm_error}")
                llm_usage = {
                    "total_requests": 0,
                    "total_cost_usd": 0.0,
                    "total_tokens": 0,
                }

            parallel_usage = {}
            try:
                from app.api.core.parallel.usage_tracker import ParallelUsageTracker

                org_ids = await self._get_user_organization_ids(user_id)
                parallel_tracker = ParallelUsageTracker()
                parallel_usage = await parallel_tracker.get_usage_stats(
                    db=self.db,
                    user_id=user_id,
                    organization_ids=org_ids if org_ids else None,
                    start_date=datetime.now(timezone.utc) - timedelta(days=30),
                )
            except Exception as parallel_error:
                logger.warning(
                    f"Failed to get Parallel AI usage for user {user_id}: {parallel_error}"
                )
                parallel_usage = {
                    "total_requests": 0,
                    "total_cost_usd": 0.0,
                    "total_content_mb": 0.0,
                }

            return {
                "profile": profile,
                "feature_usage": feature_usage,
                "llm_usage": llm_usage,
                "parallel_usage": parallel_usage,
            }

        except CustomerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error retrieving customer detail: {e}", exc_info=True)
            raise CustomerUsageError("Failed to retrieve customer details")

    async def get_customer_activity(self, user_id: UUID, days: int = 7) -> dict:
        """
        Get customer activity timeline.
        Returns the EXACT same structure as the original route.
        """
        try:
            if not 1 <= days <= 90:
                raise InvalidCustomerFilterError("Days must be between 1 and 90")

            try:
                await self._get_user_with_payment_status(user_id)
            except CustomerNotFoundError as e:
                logger.warning(f"Customer {user_id} not found: {e}")
                raise

            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            feature_usage = await self.get_feature_usage_breakdown(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            return {
                "user_id": str(user_id),
                "date_range": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days,
                },
                "feature_usage": feature_usage,
            }

        except (CustomerNotFoundError, InvalidCustomerFilterError):
            raise
        except Exception as e:
            logger.error(f"Error retrieving customer activity: {e}", exc_info=True)
            raise CustomerActivityError("Failed to retrieve customer activity")

    async def get_feature_usage_breakdown(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Get feature usage breakdown for a customer.
        Delegates to SuperadminMetricsService for actual implementation.
        """
        try:
            from app.api.modules.v1.admin.services.superadmin_metrics_service import (
                SuperadminMetricsService,
            )

            metrics_service = SuperadminMetricsService(self.db)
            org_ids = await self._get_user_organization_ids(user_id)

            return await metrics_service.get_feature_usage_breakdown(
                user_id=None,
                organization_id=org_ids[0] if org_ids else None,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.warning(f"Failed to get feature usage for user {user_id}: {e}")
            return []

    async def _get_user_organization_ids(self, user_id: UUID) -> List[UUID]:
        """Get all organization IDs for a user."""
        query = select(UserOrganization.organization_id).where(UserOrganization.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def _get_user_with_payment_status(self, user_id: UUID) -> dict:
        """
        Get user data with payment status.
        Returns the EXACT same structure as in the original route.
        """
        query = (
            select(
                User.id,
                User.name,
                User.email,
                User.created_at,
                User.last_active,
                User.is_approved,
                BillingAccount.status.label("payment_status"),
                BillingPlan.tier.label("plan_tier"),
                BillingPlan.label.label("plan_label"),
                BillingPlan.interval.label("plan_interval"),
                BillingPlan.amount.label("plan_amount"),
            )
            .outerjoin(UserOrganization, User.id == UserOrganization.user_id)
            .outerjoin(
                BillingAccount,
                UserOrganization.organization_id == BillingAccount.organization_id,
            )
            .outerjoin(
                BillingPlan,
                BillingAccount.current_price_id == BillingPlan.stripe_price_id,
            )
            .where(User.id == user_id)
        )

        result = await self.db.execute(query)
        user_data = result.fetchone()

        if not user_data:
            raise CustomerNotFoundError(f"Customer with ID {user_id} not found")

        from app.api.db.models.llm_usage import LLMUsageLog

        org_ids = await self._get_user_organization_ids(user_id)

        conditions = [LLMUsageLog.user_id == user_id]
        if org_ids:
            conditions.append(LLMUsageLog.organization_id.in_(org_ids))

        credits_query = select(func.sum(LLMUsageLog.total_tokens)).where(or_(*conditions))
        credits_result = await self.db.execute(credits_query)
        credits_used = credits_result.scalar() or 0

        amount_spent = 0.0
        llm_cost_query = select(func.sum(LLMUsageLog.cost_usd)).where(
            and_(
                or_(
                    LLMUsageLog.user_id == user_id,
                    LLMUsageLog.organization_id.in_(org_ids) if org_ids else False,
                ),
                LLMUsageLog.success == True,  # noqa: E712
            )
        )
        llm_cost_result = await self.db.execute(llm_cost_query)
        amount_spent = float(llm_cost_result.scalar() or 0.0)

        payment_status = user_data.payment_status or "trialing"
        payment_status_map = {
            None: "trialing",
            "TRIALING": "trialing",
            "ACTIVE": "paid",
            "PAST_DUE": "past_due",
        }

        plan_info = None
        if hasattr(user_data, "plan_tier") and user_data.plan_tier:
            plan_info = {
                "tier": user_data.plan_tier,
                "label": user_data.plan_label,
                "interval": user_data.plan_interval,
                "amount": user_data.plan_amount,
            }

        return {
            "id": str(user_data.id),
            "name": user_data.name,
            "email": user_data.email,
            "is_approved": user_data.is_approved,
            "payment_status": payment_status_map.get(payment_status, payment_status),
            "plan": plan_info,
            "registration_date": (
                user_data.created_at.isoformat() if user_data.created_at else None
            ),
            "last_active": (user_data.last_active.isoformat() if user_data.last_active else None),
            "credits_used": credits_used,
            "amount_spent": amount_spent,
        }

    async def _get_llm_usage(self, user_id: UUID) -> dict:
        """Get LLM usage statistics for a user."""
        try:
            from datetime import timedelta

            from app.api.core.llm.usage_tracker import LLMUsageTracker

            org_ids = await self._get_user_organization_ids(user_id)
            tracker = LLMUsageTracker()

            return await tracker.get_usage_stats(
                db=self.db,
                user_id=user_id,
                organization_ids=org_ids if org_ids else None,
                start_date=datetime.now(timezone.utc) - timedelta(days=30),
            )
        except Exception as e:
            logger.warning(f"Failed to get LLM usage for user {user_id}: {e}")
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
            }

    async def _get_parallel_usage(self, user_id: UUID) -> dict:
        """Get Parallel usage statistics for a user."""
        try:
            from datetime import timedelta

            from app.api.core.parallel.usage_tracker import ParallelUsageTracker

            org_ids = await self._get_user_organization_ids(user_id)
            tracker = ParallelUsageTracker()

            return await tracker.get_usage_stats(
                db=self.db,
                user_id=user_id,
                organization_ids=org_ids if org_ids else None,
                start_date=datetime.now(timezone.utc) - timedelta(days=30),
            )
        except Exception as e:
            logger.warning(f"Failed to get Parallel usage for user {user_id}: {e}")
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "total_content_mb": 0.0,
            }

    async def activate_customer(
        self, user_id: UUID, background_tasks: BackgroundTasks = None
    ) -> dict:
        """
        Approve a customer account (set is_approved=True).
        Grants the user access to application features after approval.

        This is used for lead management - new signups are unapproved by
        default and must be approved by a superadmin to access features.

        Args:
            user_id: UUID of the user to approve

        Returns:
            dict with user profile data including updated is_approved status

        Raises:
            CustomerNotFoundError: If the user doesn't exist
        """
        try:
            user = await self.db.get(User, user_id)
            if not user:
                raise CustomerNotFoundError(f"Customer with ID {user_id} not found")

            user.is_approved = True
            user.approved_at = datetime.now(timezone.utc)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            # Send approval confirmation email
            if background_tasks:
                background_tasks.add_task(
                    send_email,
                    "account_approved.html",
                    "Your Account Has Been Approved",
                    user.email,
                    {
                        "full_name": user.name,
                        "approved_at": user.approved_at.strftime("%B %d, %Y"),
                    },
                )
                logger.info(f"Queued approval confirmation email for user_id={user_id}")

            logger.info(f"Customer {user_id} approved successfully")

            return {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "is_approved": user.is_approved,
                "approved_at": (user.approved_at.isoformat() if user.approved_at else None),
            }

        except CustomerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error approving customer {user_id}: {e}", exc_info=True)
            raise CustomerDataRetrievalError(f"Failed to approve customer: {str(e)}")

    async def deactivate_customer(self, user_id: UUID) -> dict:
        """
        Revoke customer approval (set is_approved=False).
        Removes the user's access to application features.

        This revokes the approval status, blocking access to features
        while still allowing login. For account suspension, use is_active.

        Args:
            user_id: UUID of the user to revoke approval from

        Returns:
            dict with user profile data including updated is_approved status

        Raises:
            CustomerNotFoundError: If the user doesn't exist
        """
        try:
            user = await self.db.get(User, user_id)
            if not user:
                raise CustomerNotFoundError(f"Customer with ID {user_id} not found")

            user.is_approved = False
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(f"Customer {user_id} approval revoked successfully")

            return {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
                "is_approved": user.is_approved,
                "approved_at": (user.approved_at.isoformat() if user.approved_at else None),
            }

        except CustomerNotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Error revoking customer approval {user_id}: {e}",
                exc_info=True,
            )
            raise CustomerDataRetrievalError(f"Failed to revoke customer approval: {str(e)}")
