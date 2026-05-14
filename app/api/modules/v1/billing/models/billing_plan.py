import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, func
from sqlmodel import Field, SQLModel


class PlanInterval(str, Enum):
    """Billing interval for a plan/price."""

    MONTH = "month"
    YEAR = "year"


class PlanTier(str, Enum):
    """High-level plan tier"""

    ESSENTIAL = "ESSENTIAL"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


class BillingPlan(SQLModel, table=True):
    """
    Configurable subscription plan.
    """

    __tablename__ = "billing_plans"
    __table_args__ = (
        sa.UniqueConstraint(
            "code",
            "interval",
            "currency",
            name="uq_billing_plan_code_interval_currency",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    code: str = Field(max_length=50, nullable=False, index=True)

    tier: PlanTier = Field(
        sa_column=sa.Column(
            sa.Enum(PlanTier, name="billingplantier"),
            nullable=False,
        )
    )

    label: str = Field(max_length=100, nullable=False)

    description: Optional[str] = Field(default=None, max_length=255, nullable=True)

    interval: PlanInterval = Field(
        sa_column=sa.Column(
            sa.Enum(PlanInterval, name="billingplaninterval"),
            nullable=False,
        )
    )

    currency: str = Field(default="USD", max_length=3, nullable=False)
    amount: int = Field(nullable=False)

    # Stripe identifiers
    stripe_product_id: str = Field(max_length=255, nullable=False)
    stripe_price_id: str = Field(max_length=255, nullable=False)

    features_: List[str] = Field(
        default_factory=list,
        sa_column=Column(
            "features",
            JSON,
            nullable=False,
            server_default="[]",
        ),
    )

    is_most_popular: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="true"),
    )

    sort_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
