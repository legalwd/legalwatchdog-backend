import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db
from app.api.modules.v1.billing.routes.docs.webhook_route_docs import (
    stripe_webhook_custom_errors,
    stripe_webhook_custom_success,
    stripe_webhook_responses,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    verify_webhook_signature,
)
from app.api.modules.v1.billing.stripe.webhook_processor import process_stripe_event
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
    responses=stripe_webhook_responses,
)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Stripe webhook receiver.

    Args:
        request (Request): The incoming HTTP request containing the webhook payload.

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`.

    Raises:
        Exception: For unexpected errors encountered while processing the webhook.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get("Stripe-Signature") or request.headers.get(
            "stripe-signature"
        )
        if not sig_header:
            logger.warning("Missing Stripe-Signature header")
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST, message="Missing signature header"
            )

        try:
            event = await verify_webhook_signature(payload=payload, header=sig_header)
        except Exception as exc:
            logger.warning("Stripe webhook signature verification failed: %s", str(exc))
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST, message="Invalid webhook signature"
            )

        try:
            result: Dict[str, Any] = await process_stripe_event(db=db, event=event)
        except Exception as exc:
            logger.exception("Error processing stripe event: %s", str(exc))
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Failed to process webhook event",
            )

        processed = result.get("processed", False)
        action = result.get("action", "unknown")
        details = result.get("details", {})

        # If processing failed, let Stripe retry by returning 400.
        if not processed and action == "processing_failed":
            logger.warning(
                "Stripe event processing failed (will request retry) - details=%s", details
            )
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Processing failed, will retry",
            )

        # For already-processed or successfully-processed events, return 200.
        logger.info(
            "Stripe webhook processed: action=%s processed=%s details=%s",
            action,
            processed,
            details,
        )
        return success_response(
            status_code=status.HTTP_200_OK, message="Webhook processed", data=result
        )

    except Exception as exc:
        logger.exception("Unexpected error in stripe_webhook handler: %s", str(exc))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, message="Internal server error"
        )


stripe_webhook._custom_errors = stripe_webhook_custom_errors
stripe_webhook._custom_success = stripe_webhook_custom_success
