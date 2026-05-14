import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.db.database import get_db
from app.api.modules.v1.billing.models.billing_account import BillingAccount, BillingStatus
from app.api.modules.v1.billing.service.billing_service import get_billing_service

logger = logging.getLogger(__name__)


async def require_billing_access(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> BillingAccount:
    """
    Validate an organization’s billing state before allowing access to protected routes.
    EDIT: In `dev` ENVIRONMENT, the guard is effectively disabled and simply returns
        the billing account (or None) without blocking access.

    Args:
        organization_id (UUID): ID of the organization whose billing access is being checked.
        db (AsyncSession): Database session used to fetch billing data and evaluate eligibility.

    Returns:
        BillingAccount: The organization’s billing account when access is permitted.

    Raises:
        HTTPException: If the billing account is missing or the billing state blocks access.
    """
    service = get_billing_service(db)
    account: BillingAccount | None = await service.get_billing_account_by_org(organization_id)

    return  # disabling billing
    env = settings.ENVIRONMENT.lower()
    if env in ("dev", "development"):
        return account

    if not account:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Billing account not found for this organisation.",
        )

    allowed, effective_status = await service.is_org_allowed_usage(organization_id)

    effective_status = effective_status or account.status

    if allowed:
        return account

    if effective_status == BillingStatus.BLOCKED:
        detail = "This organisation’s billing account is blocked. Please contact support."
        http_status = status.HTTP_403_FORBIDDEN
    elif effective_status == BillingStatus.CANCELLED:
        detail = "Subscription is cancelled. Please renew your subscription to continue."
        http_status = status.HTTP_402_PAYMENT_REQUIRED
    elif effective_status == BillingStatus.UNPAID:
        detail = "Billing is unpaid or inactive. Please subscribe to continue."
        http_status = status.HTTP_402_PAYMENT_REQUIRED
    elif effective_status == BillingStatus.PAST_DUE:
        detail = "Billing is past due. Please subscribe to continue."
        http_status = status.HTTP_402_PAYMENT_REQUIRED
    elif effective_status == BillingStatus.TRIALING:
        detail = "Trial has expired or is not valid. Please subscribe to continue."
        http_status = status.HTTP_402_PAYMENT_REQUIRED
    else:
        detail = "Billing account is not in a valid state. Please contact support."
        http_status = status.HTTP_402_PAYMENT_REQUIRED

    logger.info(
        "Billing access denied for org=%s (status=%s)",
        organization_id,
        effective_status.name if isinstance(effective_status, BillingStatus) else effective_status,
    )

    raise HTTPException(status_code=http_status, detail=detail)
