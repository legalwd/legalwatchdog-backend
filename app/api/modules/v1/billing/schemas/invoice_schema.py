from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvoiceResponse(BaseModel):
    id: UUID
    billing_account_id: UUID
    amount_due: int
    amount_paid: int
    currency: str
    status: str
    stripe_invoice_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    invoice_pdf_url: Optional[str] = None

    plan_code: Optional[str] = None
    plan_label: Optional[str] = None
    plan_interval: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
