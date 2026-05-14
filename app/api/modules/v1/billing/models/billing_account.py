import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, ForeignKey, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.billing.models.invoice_history import InvoiceHistory
    from app.api.modules.v1.billing.models.payment_method import PaymentMethod


class BillingStatus(str, Enum):
    """Billing account statuses."""

    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    UNPAID = "UNPAID"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class BillingAccount(SQLModel, table=True):
    """
    Billing account record for an organisation.
    """

    __tablename__ = "billing_accounts"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_billing_org"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    organization_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    stripe_customer_id: Optional[str] = Field(
        default=None, max_length=255, nullable=True, index=True
    )

    stripe_subscription_id: Optional[str] = Field(
        default=None, max_length=255, nullable=True, index=True
    )

    status: BillingStatus = Field(
        sa_column=sa.Column(sa.Enum(BillingStatus, name="billingstatus"), nullable=False),
        default=BillingStatus.TRIALING,
    )

    trial_starts_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    trial_ends_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    current_period_start: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    current_period_end: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    next_billing_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    currency: str = Field(default="USD", max_length=3, nullable=False)

    current_price_id: Optional[str] = Field(default=None, max_length=255, nullable=True)

    default_payment_method_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey(
                "billing_payment_methods.id",
                ondelete="SET NULL",
                name="fk_ba_default_payment_method_id",
                use_alter=True,
            ),
            nullable=True,
            index=True,
        ),
    )
    cancel_at_period_end: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
    )

    metadata_: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON, nullable=False, server_default="{}"),
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

    payment_methods: List["PaymentMethod"] = Relationship(
        back_populates="billing_account",
        sa_relationship_kwargs={
            "foreign_keys": "[PaymentMethod.billing_account_id]",
            "cascade": "all, delete-orphan",
        },
    )

    invoices: List["InvoiceHistory"] = Relationship(
        back_populates="billing_account",
    )

    default_payment_method: Optional["PaymentMethod"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "BillingAccount.default_payment_method_id == PaymentMethod.id",
            "foreign_keys": "[BillingAccount.default_payment_method_id]",
            "uselist": False,
        }
    )
