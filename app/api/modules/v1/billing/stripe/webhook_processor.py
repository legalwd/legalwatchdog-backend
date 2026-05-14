import logging
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.redis_service import get_redis_client
from app.api.modules.v1.billing.models import InvoiceHistory
from app.api.modules.v1.billing.models.billing_account import BillingAccount as BA
from app.api.modules.v1.billing.service.billing_service import get_billing_service
from app.api.modules.v1.billing.utils.billings_utils import map_plan_to_plan_info

logger = logging.getLogger(__name__)


ENVIRONMENT = settings.ENVIRONMENT.lower()
_EVENT_KEY_PREFIX = f"stripe_event_processed:{ENVIRONMENT}:"
_EVENT_TTL_SECONDS = 30 * 24 * 3600


async def _mark_event_processed(event_id: str) -> None:
    """
    Mark a Stripe event as processed by recording an idempotency key in Redis.

    Args:
        event_id (str): Unique Stripe event identifier to mark as processed.

    Raises:
        Exception: If the Redis operation fails (error is logged and suppressed).
    """
    client = await get_redis_client()
    key = _EVENT_KEY_PREFIX + event_id
    try:
        try:
            await client.set(key, "1", ex=_EVENT_TTL_SECONDS, nx=True)
        except TypeError:
            was_set = await client.setnx(key, "1")
            if was_set:
                await client.expire(key, _EVENT_TTL_SECONDS)
        logger.debug("Marked stripe event processed: %s", event_id)
    except Exception:
        logger.exception("Failed to mark stripe event processed: %s", event_id)


async def _is_event_processed(event_id: str) -> bool:
    """
    Check whether a Stripe event has already been processed using a Redis key.

    Args:
        event_id (str): Unique Stripe event identifier to check.

    Returns:
        bool: True if the event is already marked as processed, otherwise False.

    Raises:
        Exception: If the Redis lookup fails (error is logged and False is returned).
    """
    client = await get_redis_client()
    key = _EVENT_KEY_PREFIX + event_id
    try:
        exists = await client.exists(key)
        return bool(exists)
    except Exception:
        logger.exception("Failed to check processed state for stripe event: %s", event_id)
        return False


async def _handle_invoice_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle invoice-related Stripe events and update local invoice records.

    Args:
        db (AsyncSession): Database session used for invoice lookups and updates.
        data (Dict[str, Any]): Stripe invoice payload (event.data.object).

    Returns:
        Dict[str, Any]: A structured action result describing what was performed.

    Raises:
        Exception: If invoice lookup or update fails after logging the error.
    """
    billing_service = get_billing_service(db)

    stripe_invoice_id = data.get("id")
    if not stripe_invoice_id:
        logger.warning("Invoice event with no id: %s", data)
        return {"action": "invoice_invalid_payload", "details": {}}

    customer_id = data.get("customer")
    if not customer_id:
        logger.warning(
            "Invoice %s has no customer id, cannot link to billing account", stripe_invoice_id
        )
        return {
            "action": "invoice_no_customer",
            "stripe_invoice_id": stripe_invoice_id,
        }

    account = await billing_service.find_billing_account_by_customer_id(customer_id)
    if not account:
        logger.warning(
            "No billing account found for stripe_customer_id=%s (invoice=%s)",
            customer_id,
            stripe_invoice_id,
        )
        return {
            "action": "invoice_account_not_found",
            "stripe_invoice_id": stripe_invoice_id,
            "customer_id": customer_id,
        }

    try:
        invoice = await billing_service.upsert_invoice_from_stripe(
            account=account,
            stripe_invoice=data,
        )
        return {
            "action": "invoice_upserted",
            "invoice_id": str(invoice.id),
            "stripe_invoice_id": stripe_invoice_id,
            "status": invoice.status.value,
        }
    except Exception:
        logger.exception(
            "Error syncing invoice for stripe_invoice_id=%s customer=%s",
            stripe_invoice_id,
            customer_id,
        )
        raise


async def _handle_payment_intent_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle payment_intent events to update local invoices as paid or failed.

    Args:
        db (AsyncSession): Database session used for invoice lookups and updates.
        data (Dict[str, Any]): Stripe payment_intent payload (event.data.object).

    Returns:
        Dict[str, Any]: A structured action result describing what was performed.

    Raises:
        Exception: If invoice lookup or update fails after logging the error.
    """
    billing_service = get_billing_service(db)
    pi_id = data.get("id")
    amount = data.get("amount_received") or data.get("amount") or 0
    status = data.get("status")

    if not pi_id:
        logger.warning("PaymentIntent event with no id: %s", data)
        return {"action": "payment_intent_invalid_payload", "details": {}}

    try:
        invoice: InvoiceHistory | None = await billing_service.find_invoice_by_payment_intent_id(
            stripe_payment_intent_id=pi_id
        )

        if not invoice:
            logger.info("No local invoice found for payment_intent=%s", pi_id)
            return {"action": "payment_intent_invoice_not_found", "payment_intent": pi_id}

        if status == "succeeded":
            updated = await billing_service.mark_invoice_paid(
                invoice_id=invoice.id,
                amount_paid=amount,
            )
            return {"action": "payment_succeeded", "invoice_id": str(updated.id)}
        else:
            updated = await billing_service.mark_invoice_failed(invoice_id=invoice.id)
            return {"action": "payment_failed", "invoice_id": str(updated.id)}

    except Exception:
        logger.exception("Error handling payment_intent event for pi=%s", pi_id)
        raise


async def _handle_subscription_event(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle subscription events and sync billing account periods, price, and status.

    Args:
        db (AsyncSession): Database session used for billing account updates.
        data (Dict[str, Any]): Stripe subscription payload (event.data.object).

    Returns:
        Dict[str, Any]: A structured action result describing what was performed.

    Raises:
        Exception: If billing account lookup or update fails after logging the error.
    """
    billing_service = get_billing_service(db)
    customer_id = data.get("customer")
    sub_id = data.get("id")

    if not customer_id:
        logger.warning("Subscription event missing customer: %s", data)
        return {"action": "subscription_invalid_payload", "details": {}}

    try:
        account = await billing_service.find_billing_account_by_customer_id(customer_id)
        if not account:
            logger.info("No billing account matched stripe customer %s", customer_id)
            return {"action": "billing_account_not_found", "stripe_customer_id": customer_id}

        await billing_service.attach_stripe_customer(
            billing_account_id=account.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=sub_id,
        )

        update_values = (
            await billing_service._build_billing_account_updates_from_stripe_subscription(data)
        )

        update_values["stripe_subscription_id"] = sub_id

        if update_values:
            stmt = (
                update(BA)
                .where(BA.id == account.id)
                .values(**update_values)
                .execution_options(synchronize_session="fetch")
            )
            await db.execute(stmt)
            await db.commit()
            await db.refresh(account)

        current_plan_info = None
        if account.current_price_id:
            plan = await billing_service.get_plan_by_stripe_price_id(account.current_price_id)
            if plan:
                current_plan_info = map_plan_to_plan_info(plan)

        org_id = getattr(account, "organization_id", None)

        if not org_id:
            metadata = data.get("metadata") or {}
            org_id_str = metadata.get("organization_id")
            if org_id_str:
                org_id = UUID(org_id_str)

        if org_id:
            await billing_service._sync_org_billing_from_account(
                db=db,
                organization_id=org_id,
                account=account,
                plan_info=current_plan_info,
            )
        else:
            logger.warning(
                "No organization_id found while syncing subscription event for account %s",
                account.id,
            )

        logger.info(
            "Processed subscription event for subscription=%s customer=%s (org=%s)",
            sub_id,
            customer_id,
            org_id,
        )
        return {
            "action": "subscription_processed",
            "billing_account_id": str(account.id),
            "organization_id": str(org_id) if org_id else None,
        }

    except Exception:
        await db.rollback()
        logger.exception("Error handling subscription event for subscription=%s", sub_id)
        raise


async def _handle_checkout_session_completed(
    db: AsyncSession, data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle checkout.session.completed events and link them to billing accounts.

    Args:
        db (AsyncSession): Database session used for billing account resolution.
        data (Dict[str, Any]): Stripe checkout session payload (event.data.object).

    Returns:
        Dict[str, Any]: A structured action result describing the checkout outcome.

    Raises:
        Exception: If billing account updates fail after logging the error.
    """
    billing_service = get_billing_service(db)

    session_id = data.get("id")
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    metadata = data.get("metadata") or {}

    org_id = metadata.get("organization_id")
    billing_account_id = metadata.get("billing_account_id")
    plan = metadata.get("plan")

    account = None
    if billing_account_id:
        account = await billing_service.get_billing_account_by_id(billing_account_id)

    if not account and customer_id:
        account = await billing_service.find_billing_account_by_customer_id(customer_id)

    if not account:
        logger.info(
            "Checkout session completed but no billing account found "
            "session=%s customer=%s metadata=%s",
            session_id,
            customer_id,
            metadata,
        )
        return {
            "action": "checkout_completed_account_not_found",
            "session_id": session_id,
            "customer_id": customer_id,
            "organization_id": org_id,
        }

    if subscription_id and not account.stripe_subscription_id:
        await billing_service.attach_stripe_customer(
            billing_account_id=account.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
        )

    logger.info(
        "Checkout session completed for billing_account=%s plan=%s session=%s subscription=%s",
        account.id,
        plan,
        session_id,
        subscription_id,
    )

    return {
        "action": "checkout_session_completed",
        "billing_account_id": str(account.id),
        "organization_id": org_id,
        "plan": plan,
        "session_id": session_id,
        "subscription_id": subscription_id,
    }


async def _handle_payment_method_attached(db: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle payment_method.attached events and create local payment method records.

    Args:
        db (AsyncSession): Database session used for billing account and payment method changes.
        data (Dict[str, Any]): Stripe payment_method payload (event.data.object).

    Returns:
        Dict[str, Any]: A structured action result describing what was performed.

    Raises:
        Exception: If payment method creation or related lookups fail after logging the error.
    """
    billing_service = get_billing_service(db)

    pm_id = data.get("id")
    customer_id = data.get("customer")
    if not pm_id or not customer_id:
        logger.warning("payment_method.attached missing id/customer: %s", data)
        return {"action": "payment_method_invalid_payload", "details": {}}

    existing = await billing_service.find_payment_method_by_stripe_id(pm_id)
    if existing:
        logger.info(
            "payment_method.attached for already-recorded pm=%s (id=%s)",
            pm_id,
            existing.id,
        )
        return {
            "action": "payment_method_already_recorded",
            "payment_method_id": str(existing.id),
            "stripe_payment_method_id": pm_id,
        }

    account = await billing_service.find_billing_account_by_customer_id(customer_id)
    if not account:
        logger.info(
            "payment_method.attached but no billing account found for customer=%s",
            customer_id,
        )
        return {
            "action": "payment_method_account_not_found",
            "customer_id": customer_id,
        }

    card = data.get("card") or {}
    brand = card.get("brand")
    last4 = card.get("last4")
    exp_month = card.get("exp_month")
    exp_year = card.get("exp_year")

    pm = await billing_service.add_payment_method(
        billing_account_id=account.id,
        stripe_payment_method_id=pm_id,
        card_brand=brand,
        last4=last4,
        exp_month=exp_month,
        exp_year=exp_year,
        is_default=True,
        metadata={"source": "webhook_payment_method.attached"},
    )

    logger.info(
        "Created local payment method %s from webhook for billing_account=%s",
        pm.id,
        account.id,
    )

    return {
        "action": "payment_method_attached_recorded",
        "payment_method_id": str(pm.id),
        "billing_account_id": str(account.id),
        "stripe_payment_method_id": pm_id,
        "customer_id": customer_id,
    }


async def process_stripe_event(db: AsyncSession, event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatch a Stripe event to the appropriate handler with idempotency protection.

    Args:
        db (AsyncSession): Database session used across handler calls.
        event (Dict[str, Any]): Full Stripe event payload to be processed.

    Returns:
        Dict[str, Any]: A structured result containing processed status and action details.

    Raises:
        Exception: Not propagated; any handler error is logged and folded into the result.
    """
    event_id: str = event.get("id")
    event_type: str = event.get("type")
    if not event_id or not event_type:
        logger.warning("Invalid stripe event payload (missing id/type)")
        return {"processed": False, "action": "invalid_event", "details": {}}

    try:
        if await _is_event_processed(event_id):
            logger.info("Stripe event already processed: %s", event_id)
            return {"processed": False, "action": "already_processed", "event_id": event_id}
    except Exception:
        logger.warning("Idempotency check failed for event %s; proceeding", event_id)

    data_obj = event.get("data", {}).get("object", {}) or {}
    result = {"processed": True, "action": "unhandled_event", "event_type": event_type}

    logger.info("Processing stripe event: id=%s type=%s", event_id, event_type)
    try:
        if event_type.startswith("invoice."):
            result = await _handle_invoice_event(db, data_obj)

        elif event_type.startswith("payment_intent."):
            result = await _handle_payment_intent_event(db, data_obj)

        elif event_type.startswith("customer.subscription.") or event_type.startswith(
            "subscription."
        ):
            result = await _handle_subscription_event(db, data_obj)

        elif event_type == "checkout.session.completed":
            result = await _handle_checkout_session_completed(db, data_obj)

        elif event_type == "payment_method.attached":
            result = await _handle_payment_method_attached(db, data_obj)

        # common event are no-opped but I logged here
        elif event_type == "charge.succeeded":
            charge_id = data_obj.get("id")
            pi_id = data_obj.get("payment_intent")
            logger.info(
                "Charge succeeded (no-op, handled via payment_intent): charge=%s payment_intent=%s",
                charge_id,
                pi_id,
            )
            result = {
                "action": "charge_succeeded_noop",
                "charge_id": charge_id,
                "payment_intent_id": pi_id,
            }

        elif event_type == "invoiceitem.created":
            logger.info("invoiceitem.created no-op: invoice_item=%s", data_obj)
            return {
                "action": "invoiceitem_created_noop",
                "invoice_item_id": data_obj.get("id"),
            }

        elif event_type.startswith("customer."):
            logger.info("Customer event no-op: type=%s id=%s", event_type, data_obj.get("id"))
            result = {"action": "customer_noop", "event_type": event_type}

        else:
            logger.info("Unhandled stripe event type: %s, data=%s", event_type, data_obj)
            result = {"action": "unhandled_event_type", "event_type": event_type}

        try:
            await _mark_event_processed(event_id)
        except Exception:
            pass

        return {"processed": True, "action": result.get("action"), "details": result}
    except Exception as exc:
        logger.exception("Failed to process stripe event %s: %s", event_id, str(exc))
        return {"processed": False, "action": "processing_failed", "error": str(exc)}
