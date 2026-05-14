from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.core.logger import logger
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingStatus,
    Subscription,
    SubscriptionStatus,
)
from app.api.modules.v1.organization.models import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.roles_model import Role as RoleORM
from app.api.modules.v1.users.models.users_model import User as UserORM
from app.api.utils.celery_utils import syncify


@shared_task(bind=True, name="billing.tasks.expire_trials", max_retries=3, default_retry_delay=60)
def expire_trials(self):
    """
    Expire trials and block access for accounts with expired trials.
    Runs hourly.
    """
    try:
        syncify(_expire_trials_async)()
    except Exception as exc:
        logger.exception("expire_trials task failed")
        raise self.retry(exc=exc, countdown=60)


async def _expire_trials_async():
    logger.info("Running trial expiration task")

    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            statement = select(BillingAccount).where(
                BillingAccount.trial_ends_at <= now, BillingAccount.status == BillingStatus.TRIALING
            )

            result = await db.execute(statement)
            expired_accounts = result.scalars().all()

            logger.info(
                f"Found {len(expired_accounts)} expired trial accounts",
                extra={"count": len(expired_accounts)},
            )

            for billing_account in expired_accounts:
                try:
                    billing_account.status = BillingStatus.BLOCKED
                    db.add(billing_account)

                    await send_trial_expired_email_task(billing_account, db)

                    logger.info(
                        "Trial expired and account blocked",
                        extra={
                            "billing_account_id": str(billing_account.id),
                            "organization_id": str(billing_account.organization_id),
                        },
                    )

                except Exception as e:
                    logger.error(
                        "Failed to process expired trial",
                        exc_info=True,
                        extra={"billing_account_id": str(billing_account.id), "error": str(e)},
                    )
                    continue

            await db.commit()
            logger.info(
                "Trial expiration task completed", extra={"processed": len(expired_accounts)}
            )

        except Exception as e:
            logger.error("Trial expiration task failed", exc_info=True, extra={"error": str(e)})
            await db.rollback()
            raise


@shared_task(
    bind=True,
    name="billing.tasks.update_billing_status",
    max_retries=3,
    default_retry_delay=60,
)
def update_billing_status(self):
    """
    Update billing status based on subscription period.
    Fallback if webhook fails.
    Runs every 6 hours.
    """
    try:
        syncify(_update_billing_status_async)()
    except Exception as exc:
        logger.exception("update_billing_status task failed")
        raise self.retry(exc=exc, countdown=60)


async def _update_billing_status_async():
    """Async implementation of update_billing_status"""
    logger.info("Running billing status update task")

    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            # Get all billing accounts with subscriptions
            statement = select(BillingAccount).where(
                BillingAccount.stripe_subscription_id.isnot(None)
            )
            result = await db.execute(statement)
            billing_accounts = result.scalars().all()

            logger.info(
                f"Checking {len(billing_accounts)} billing accounts",
                extra={"count": len(billing_accounts)},
            )

            for billing_account in billing_accounts:
                try:
                    # Get active subscription
                    sub_statement = (
                        select(Subscription)
                        .where(
                            Subscription.billing_account_id == billing_account.id,
                            Subscription.is_active,
                        )
                        .order_by(Subscription.created_at.desc())
                    )

                    sub_result = await db.execute(sub_statement)
                    subscription = sub_result.scalars().first()

                    if not subscription:
                        continue

                    # Map Stripe subscription status to billing status
                    mapped_status = _map_subscription_status(subscription.status)

                    # Check if period has ended
                    if subscription.current_period_end < now:
                        if subscription.cancel_at_period_end:
                            mapped_status = BillingStatus.CANCELLED
                            subscription.is_active = False
                        elif subscription.status != SubscriptionStatus.ACTIVE:
                            mapped_status = BillingStatus.PAST_DUE

                    # Update billing account if status changed
                    if billing_account.status != mapped_status:
                        old_status = billing_account.status
                        billing_account.status = mapped_status

                        # Update period dates
                        billing_account.current_period_start = subscription.current_period_start
                        billing_account.current_period_end = subscription.current_period_end

                        db.add(billing_account)

                        logger.info(
                            "Billing status updated",
                            extra={
                                "billing_account_id": str(billing_account.id),
                                "old_status": old_status.value,
                                "new_status": mapped_status.value,
                            },
                        )

                        # Send notification if moved to past_due or blocked
                        if mapped_status in [BillingStatus.PAST_DUE, BillingStatus.BLOCKED]:
                            await send_payment_failed_email_task(billing_account, db)

                except Exception as e:
                    logger.error(
                        "Failed to update billing status",
                        exc_info=True,
                        extra={"billing_account_id": str(billing_account.id), "error": str(e)},
                    )
                    continue

            await db.commit()
            logger.info("Billing status update task completed")

        except Exception as e:
            logger.error(
                "Billing status update task failed", exc_info=True, extra={"error": str(e)}
            )
            await db.rollback()
            raise


@shared_task(
    bind=True,
    name="billing.tasks.send_trial_reminders",
    max_retries=3,
    default_retry_delay=60,
)
def send_trial_reminders(self):
    """
    Send trial reminder emails at 3 days and 1 day before expiry.
    Runs daily at 9 AM UTC.
    """
    try:
        syncify(_send_trial_reminders_async)()
    except Exception as exc:
        logger.exception("send_trial_reminders task failed")
        raise self.retry(exc=exc, countdown=60)


async def _send_trial_reminders_async():
    """Async implementation of send_trial_reminders"""
    logger.info("Running trial reminder task")

    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            # 3-day reminder: target accounts whose trial ends in roughly 3 days.
            # Use a 25-hour window centered on the 3-day mark so the daily Beat
            # job never misses an account or sends a duplicate.
            three_days_lower = now + timedelta(days=2, hours=23)
            three_days_upper = now + timedelta(days=3, hours=1)
            statement_3d = select(BillingAccount).where(
                BillingAccount.trial_ends_at >= three_days_lower,
                BillingAccount.trial_ends_at <= three_days_upper,
                BillingAccount.status == BillingStatus.TRIALING,
            )
            result_3d = await db.execute(statement_3d)
            accounts_3d = result_3d.scalars().all()

            for billing_account in accounts_3d:
                await send_trial_reminder_email_task(billing_account, days_remaining=3, db=db)
                logger.info(
                    "Sent 3-day trial reminder",
                    extra={"billing_account_id": str(billing_account.id)},
                )

            # 1-day reminder: same window approach.
            one_day_lower = now + timedelta(hours=23)
            one_day_upper = now + timedelta(days=1, hours=1)
            statement_1d = select(BillingAccount).where(
                BillingAccount.trial_ends_at >= one_day_lower,
                BillingAccount.trial_ends_at <= one_day_upper,
                BillingAccount.status == BillingStatus.TRIALING,
            )
            result_1d = await db.execute(statement_1d)
            accounts_1d = result_1d.scalars().all()

            for billing_account in accounts_1d:
                await send_trial_reminder_email_task(billing_account, days_remaining=1, db=db)
                logger.info(
                    "Sent 1-day trial reminder",
                    extra={"billing_account_id": str(billing_account.id)},
                )

            logger.info(
                "Trial reminder task completed",
                extra={"sent_3d": len(accounts_3d), "sent_1d": len(accounts_1d)},
            )

        except Exception as e:
            logger.error("Trial reminder task failed", exc_info=True, extra={"error": str(e)})
            raise


# ==================== HELPER FUNCTIONS ====================


def _map_subscription_status(stripe_status: SubscriptionStatus) -> BillingStatus:
    """Map Stripe subscription status to BillingStatus"""
    if stripe_status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
        return BillingStatus.ACTIVE
    elif stripe_status == SubscriptionStatus.PAST_DUE:
        return BillingStatus.PAST_DUE
    elif stripe_status in [
        SubscriptionStatus.INCOMPLETE,
        SubscriptionStatus.INCOMPLETE_EXPIRED,
        SubscriptionStatus.UNPAID,
    ]:
        return BillingStatus.UNPAID
    elif stripe_status in [SubscriptionStatus.CANCELED]:
        return BillingStatus.CANCELLED
    else:
        return BillingStatus.BLOCKED


async def _get_org_admins(
    billing_account: BillingAccount,
    db: AsyncSession,
) -> tuple[Organization | None, list[UserORM]]:
    """Fetch the organization and its admin/owner users for a billing account.

    Uses the provided session so that the caller's open transaction is reused,
    avoiding extra DB connections and ensuring consistency within a single task.

    Args:
        billing_account: The billing account whose organization to look up.
        db: The already-open async database session to reuse.

    Returns:
        Tuple of (Organization or None, list of admin/owner User objects).
    """
    org = await db.get(Organization, billing_account.organization_id)
    if not org:
        return None, []

    admin_statement = (
        select(UserORM)
        .join(UserOrganization, UserOrganization.user_id == UserORM.id)
        .join(RoleORM, RoleORM.id == UserOrganization.role_id)
        .where(
            UserOrganization.organization_id == org.id,
            RoleORM.name.in_(["admin", "owner"]),
        )
    )
    result = await db.execute(admin_statement)
    admins = result.scalars().all()
    return org, admins


# ==================== EMAIL TASK WRAPPERS ====================
# These are async because they are only ever called from within the async
# billing task implementations, which already have an event loop.  They
# accept the caller's open session to avoid redundant DB connections.


async def send_trial_expired_email_task(billing_account: BillingAccount, db: AsyncSession) -> None:
    """Send trial expired notification emails to org admins."""
    await _send_trial_expired_email_async(billing_account, db)


async def send_trial_reminder_email_task(
    billing_account: BillingAccount, days_remaining: int, db: AsyncSession
) -> None:
    """Send trial reminder notification emails to org admins."""
    await _send_trial_reminder_email_async(billing_account, days_remaining, db)


async def send_payment_failed_email_task(billing_account: BillingAccount, db: AsyncSession) -> None:
    """Send payment failed notification emails to org admins."""
    await _send_payment_failed_email_async(billing_account, db)


# ==================== ASYNC EMAIL IMPLEMENTATIONS ====================


async def _send_trial_expired_email_async(
    billing_account: BillingAccount, db: AsyncSession
) -> None:
    """Send trial expired notification to org admin/owner users."""
    try:
        org, admins = await _get_org_admins(billing_account, db)
        if not org:
            return

        for admin in admins:
            await send_email(
                template_name="trial_expired",
                subject="Your Legal Watchdog Trial Has Expired",
                recipient=admin.email,
                context={
                    "user_name": admin.name or admin.email,
                    "organization_name": org.name,
                    "billing_url": f"{settings.FRONTEND_URL}/billing",
                },
            )

    except Exception as e:
        logger.error(
            "Failed to send trial expired email",
            exc_info=True,
            extra={"billing_account_id": str(billing_account.id), "error": str(e)},
        )


async def _send_trial_reminder_email_async(
    billing_account: BillingAccount, days_remaining: int, db: AsyncSession
) -> None:
    """Send trial reminder notification to org admin/owner users."""
    try:
        org, admins = await _get_org_admins(billing_account, db)
        if not org:
            return

        for admin in admins:
            await send_email(
                template_name="trial_reminder",
                subject=(
                    f"Your Legal Watchdog Trial Ends in {days_remaining} "
                    f"Day{'s' if days_remaining > 1 else ''}"
                ),
                recipient=admin.email,
                context={
                    "user_name": admin.name or admin.email,
                    "organization_name": org.name,
                    "days_remaining": days_remaining,
                    "trial_ends_at": billing_account.trial_ends_at.strftime("%B %d, %Y"),
                    "billing_url": f"{settings.FRONTEND_URL}/billing",
                },
            )

    except Exception as e:
        logger.error(
            "Failed to send trial reminder email",
            exc_info=True,
            extra={"billing_account_id": str(billing_account.id), "error": str(e)},
        )


async def _send_payment_failed_email_async(
    billing_account: BillingAccount, db: AsyncSession
) -> None:
    """Send payment failed notification to org admin/owner users."""
    try:
        org, admins = await _get_org_admins(billing_account, db)
        if not org:
            return

        for admin in admins:
            await send_email(
                template_name="payment_failed",
                subject="Payment Failed - Action Required",
                recipient=admin.email,
                context={
                    "user_name": admin.name or admin.email,
                    "organization_name": org.name,
                    "billing_url": f"{settings.FRONTEND_URL}/billing",
                },
            )

    except Exception as e:
        logger.error(
            "Failed to send payment failed email",
            exc_info=True,
            extra={"billing_account_id": str(billing_account.id), "error": str(e)},
        )
