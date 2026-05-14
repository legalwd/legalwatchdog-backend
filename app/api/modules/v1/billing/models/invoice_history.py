import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, func
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.api.modules.v1.billing.models.billing_account import BillingAccount


class InvoiceStatus(str, Enum):
    """Invoice statuses."""

    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    VOID = "VOID"
    PENDING = "PENDING"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class InvoiceHistory(SQLModel, table=True):
    """
    Persistent record of invoices and payments for a billing account.
    """

    __tablename__ = "billing_invoices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)

    billing_account_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("billing_accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    stripe_invoice_id: Optional[str] = Field(
        default=None,
        sa_column=Column(
            String(255),
            unique=True,
            index=True,
            nullable=True,
        ),
    )

    stripe_payment_intent_id: Optional[str] = Field(
        default=None, max_length=255, nullable=True, index=True
    )

    amount_due: int = Field(default=0, nullable=False)
    amount_paid: int = Field(default=0, nullable=False)
    currency: str = Field(default="USD", max_length=3, nullable=False)

    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT, nullable=False)

    hosted_invoice_url: Optional[str] = Field(default=None, nullable=True)
    invoice_pdf_url: Optional[str] = Field(default=None, nullable=True)

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

    billing_account: "BillingAccount" = Relationship(back_populates="invoices")
