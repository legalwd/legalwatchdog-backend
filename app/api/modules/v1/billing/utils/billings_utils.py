import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.api.core.config import settings
from app.api.modules.v1.billing.models import BillingPlan, BillingStatus, InvoiceStatus
from app.api.modules.v1.billing.schemas import BillingPlanInfo

logger = logging.getLogger(__name__)

TRIAL_DURATION_DAYS = settings.TRIAL_DURATION_DAYS
DEFAULT_CURRENCY = "USD"


def parse_ts(value: Any, field_name: str) -> Optional[datetime]:
    """
    Parse a UNIX timestamp-like value into a timezone-aware UTC datetime.

    Args:
        value: The timestamp to parse.
        field_name: The name of the field (used for logging on parse failure).

    Returns:
        Optional[datetime]: A timezone-aware datetime in UTC if parsing succeeds, otherwise None.
    """
    if value in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except Exception:
        logger.warning("Failed to parse %s=%s", field_name, value)
        return None


def map_stripe_status_to_billing_status(stripe_status: str) -> BillingStatus:
    """
    Map a Stripe subscription status string to our BillingStatus enum.

    Args:
        stripe_status: The status string returned by Stripe for a subscription

    Returns:
        BillingStatus: Corresponding internal BillingStatus value.
    """
    if stripe_status == "trialing":
        return BillingStatus.TRIALING
    if stripe_status == "active":
        return BillingStatus.ACTIVE
    if stripe_status == "past_due":
        return BillingStatus.PAST_DUE
    if stripe_status in ("incomplete", "incomplete_expired", "unpaid"):
        return BillingStatus.UNPAID
    if stripe_status in ("canceled", "cancelled"):
        return BillingStatus.CANCELLED
    return BillingStatus.UNPAID


def map_stripe_invoice_status(stripe_status: Optional[str]) -> InvoiceStatus:
    """
    Map Stripe's invoice.status -> our InvoiceStatus enum.
    Args:
        stripe_status (Optional[str]): The raw status value returned by Stripe.

    Returns:
        InvoiceStatus: The mapped internal invoice status, defaulting to PENDING.
    """
    if not stripe_status:
        return InvoiceStatus.PENDING

    mapping = {
        "draft": InvoiceStatus.DRAFT,
        "open": InvoiceStatus.OPEN,
        "paid": InvoiceStatus.PAID,
        "void": InvoiceStatus.VOID,
        "uncollectible": InvoiceStatus.FAILED,
    }
    return mapping.get(stripe_status, InvoiceStatus.PENDING)


def map_plan_to_plan_info(plan: BillingPlan) -> BillingPlanInfo:
    return BillingPlanInfo(
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
