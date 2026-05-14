from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel


class CheckoutSessionCreateRequest(BaseModel):
    """
    Request body for starting a Stripe Checkout session.
    """

    plan_id: UUID
    metadata: Optional[Dict[str, Any]] = None


class CheckoutSessionResponse(BaseModel):
    """
    Response containing the Stripe Checkout session details.
    """

    checkout_url: AnyHttpUrl
    session_id: str
