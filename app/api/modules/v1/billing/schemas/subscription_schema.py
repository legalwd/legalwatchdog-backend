from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.api.modules.v1.billing.models.billing_account import BillingStatus

from .billing_schema import BillingPlanInfo


class SubscriptionStatusResponse(BaseModel):
    billing_account_id: UUID
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

    status: BillingStatus
    cancel_at_period_end: bool = False

    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None

    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    next_billing_at: Optional[datetime] = None

    current_plan: Optional[BillingPlanInfo] = None


class SubscriptionChangePlanRequest(BaseModel):
    plan_id: UUID
