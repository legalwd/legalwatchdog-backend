import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, func
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.billing.models.billing_account import BillingAccount


class PaymentMethod(SQLModel, table=True):
    """
    Non-sensitive payment method metadata for a billing account
    """

    __tablename__ = "billing_payment_methods"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    billing_account_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("billing_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    stripe_payment_method_id: str = Field(max_length=255, nullable=False, index=True)

    card_brand: Optional[str] = Field(default=None, max_length=50, nullable=True)

    last4: Optional[str] = Field(default=None, max_length=4, nullable=True)

    exp_month: Optional[int] = Field(default=None, nullable=True)
    exp_year: Optional[int] = Field(default=None, nullable=True)

    is_default: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))

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

    billing_account: "BillingAccount" = Relationship(
        back_populates="payment_methods",
        sa_relationship_kwargs={"foreign_keys": "[PaymentMethod.billing_account_id]"},
    )
