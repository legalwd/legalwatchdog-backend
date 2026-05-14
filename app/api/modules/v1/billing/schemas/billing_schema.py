from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.modules.v1.billing.models import PlanTier


class BillingAccountResponse(BaseModel):
    id: UUID
    organization_id: UUID
    status: str
    currency: str
    default_payment_method_id: Optional[UUID] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BillingPlanInfo(BaseModel):
    id: Optional[UUID] = None
    code: str

    tier: PlanTier
    label: str
    interval: Literal["month", "year"]
    currency: str
    amount: int

    description: Optional[str] = None
    features: list[str] = Field(
        default_factory=list,
        description="List of feature bullet points for this plan/price.",
    )
    is_most_popular: bool = False
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
