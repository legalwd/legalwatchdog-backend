import asyncio
import logging
import time
from typing import Any, Callable, Dict, Optional

import stripe

from app.api.core.config import settings
from app.api.modules.v1.billing.stripe.errors import SubscriptionAlreadyCanceledError

_DEFAULT_TIMEOUT = settings.STRIPE_API_TIMEOUT
_DEFAULT_RETRIES = settings.STRIPE_RETRY_COUNT
_DEFAULT_BACKOFF = settings.STRIPE_RETRY_BACKOFF

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _run_blocking_with_retries(
    fn: Callable[..., Any],
    *args,
    timeout: Optional[float] = None,
    retries: int = _DEFAULT_RETRIES,
    backoff: float = _DEFAULT_BACKOFF,
    **kwargs,
) -> Any:
    """
    Blocking helper executed inside a threadpool. Performs retries with exponential
    backoff for transient stripe/network errors.

    Args:
        fn: callable to execute (blocking).
        *args, **kwargs: passed to fn.
        timeout: per-attempt timeout in seconds (for internal use only; caller-side
                 will typically use asyncio.wait_for).
        retries: number of attempts (>=1).
        backoff: initial backoff in seconds (exponential).
    Returns:
        Result of fn(*args, **kwargs).
    Raises:
        stripe.error.StripeError (or subclass) on non-retriable errors or if retries exhausted.
        Any exception raised by fn if not a Stripe/network error.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn(*args, **kwargs)
        except stripe.error.RateLimitError as e:
            logger.warning("Stripe rate limit on attempt %d/%d: %s", attempt, retries, str(e))
            if attempt >= retries:
                raise
        except stripe.error.APIConnectionError as e:
            logger.warning(
                "Stripe API connection error attempt %d/%d: %s", attempt, retries, str(e)
            )
            if attempt >= retries:
                raise
        except stripe.error.StripeError:
            raise
        except Exception:
            raise

        sleep_for = backoff * (2 ** (attempt - 1))
        time.sleep(sleep_for)


async def _run_blocking(
    fn: Callable[..., Any], *args, timeout: Optional[float] = None, **kwargs
) -> Any:
    """
    Execute blocking function in threadpool and optionally apply asyncio timeout.

    Args:
        fn: blocking callable
        *args, **kwargs: passed through
        timeout: overall await timeout in seconds for the single attempt

    Returns:
        Result of fn

    Raises:
        asyncio.TimeoutError if operation did not complete in time.
        Any exception raised by fn.
    """
    loop = asyncio.get_running_loop()

    def blocking():
        return fn(*args, **kwargs)

    future = loop.run_in_executor(None, blocking)
    wait_timeout = timeout or _DEFAULT_TIMEOUT
    return await asyncio.wait_for(future, timeout=wait_timeout)


async def create_customer(
    email: str,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Stripe Customer. Runs in executor and retries transient errors.

    Args:
        email: customer email
        name: optional customer name
        metadata: optional metadata dictionary

    Returns:
        stripe.Customer (as dict-like)
    Raises:
        stripe.error.StripeError on failure.
    """
    metadata = metadata or {}

    def _create():
        return _run_blocking_with_retries(
            stripe.Customer.create, email=email, name=name, metadata=metadata
        )

    logger.debug("Creating Stripe customer for email=%s", email)
    return await _run_blocking(_create, timeout=_DEFAULT_TIMEOUT)


async def retrieve_customer(customer_id: str) -> Dict[str, Any]:
    """
    Retrieve a Stripe Customer by ID.

    Args:
        customer_id: stripe customer id (cus_...)

    Returns:
        stripe.Customer dict
    """

    def _get():
        return _run_blocking_with_retries(stripe.Customer.retrieve, customer_id)

    logger.debug("Retrieving Stripe customer %s", customer_id)
    return await _run_blocking(_get, timeout=_DEFAULT_TIMEOUT)


async def attach_payment_method(
    customer_id: str, payment_method_id: str, set_as_default: bool = False
) -> Dict[str, Any]:
    """
    Attach a Stripe payment method to a customer and optionally set it as the default.

    Args:
        customer_id (str): Stripe customer ID to attach the payment method to.
        payment_method_id (str): Stripe payment method ID to be attached.
        set_as_default (bool): Whether to set this method as the default for invoices.

    Returns:
        Dict[str, Any]: The attached Stripe PaymentMethod object as a dictionary.

    Raises:
        ValueError: If Stripe rejects the payment method as invalid.
        Exception: If the Stripe API call or executor execution fails.
    """

    def _attach():
        try:
            pm = _run_blocking_with_retries(
                stripe.PaymentMethod.attach, payment_method_id, customer=customer_id
            )
            if set_as_default:
                _run_blocking_with_retries(
                    stripe.Customer.modify,
                    customer_id,
                    invoice_settings={"default_payment_method": payment_method_id},
                )
            return pm
        except stripe.error.InvalidRequestError as e:
            logger.warning(
                "Stripe rejected payment method: payment_method_id=%s, error=%s",
                payment_method_id,
                str(e),
            )
            raise ValueError(
                "The payment method you're trying to use is invalid or has expired. "
                "Please add a new payment method."
            ) from e

    logger.info(
        "Attaching payment method %s to customer %s (set_default=%s)",
        payment_method_id,
        customer_id,
        set_as_default,
    )
    return await _run_blocking(_attach, timeout=_DEFAULT_TIMEOUT)


async def detach_payment_method(payment_method_id: str) -> Dict[str, Any]:
    """
    Detach a PaymentMethod from its customer in Stripe.

    Args:
        payment_method_id: stripe PaymentMethod id

    Returns:
        The detached PaymentMethod object (as dict).
    """

    def _detach():
        return _run_blocking_with_retries(stripe.PaymentMethod.detach, payment_method_id)

    logger.info("Detaching payment method %s", payment_method_id)
    return await _run_blocking(_detach, timeout=_DEFAULT_TIMEOUT)


async def retrieve_payment_method(payment_method_id: str) -> Dict[str, Any]:
    """
    Retrieve a Stripe payment method by its identifier.

    Args:
        payment_method_id (str): The Stripe payment method ID to fetch.

    Returns:
        Dict[str, Any]: The retrieved Stripe PaymentMethod data.

    Raises:
        Exception: If the Stripe retrieval request fails.
    """

    def _get():
        return _run_blocking_with_retries(stripe.PaymentMethod.retrieve, payment_method_id)

    logger.debug("Retrieving stripe payment method %s", payment_method_id)
    return await _run_blocking(_get, timeout=_DEFAULT_TIMEOUT)


async def create_checkout_session(
    success_url: str,
    cancel_url: str,
    customer_id: Optional[str] = None,
    mode: str = "subscription",
    price_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session for subscriptions or one-off payments.

    Args:
        success_url: Redirect URL on success
        cancel_url: Redirect URL on cancel
        customer_id: Optional existing Stripe customer id
        mode: "subscription" or "payment"
        price_id: Price ID for the checkout (required for subscription mode)
        metadata: Optional metadata

    Returns:
        stripe.checkout.Session
    """
    metadata = metadata or {}

    def _create():
        if mode not in ("subscription", "payment"):
            raise ValueError("mode must be 'subscription' or 'payment'")

        session_payload = {
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
        }

        if customer_id:
            session_payload["customer"] = customer_id

        if not price_id:
            raise ValueError("price_id is required for checkout session")

        session_payload["line_items"] = [{"price": price_id, "quantity": 1}]

        if mode == "subscription":
            session_payload["subscription_data"] = {"metadata": metadata}

        return _run_blocking_with_retries(stripe.checkout.Session.create, **session_payload)

    logger.info(
        "Creating Stripe checkout session mode=%s price=%s customer=%s", mode, price_id, customer_id
    )
    return await _run_blocking(_create, timeout=_DEFAULT_TIMEOUT)


async def create_subscription(
    customer_id: str,
    price_id: str,
    default_payment_method: Optional[str] = None,
    trial_period_days: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Stripe subscription for a customer.

    Args:
        customer_id: stripe customer id
        price_id: stripe price id (price_...)
        default_payment_method: optional payment method to attach and set as default
        trial_period_days: optional trial override
        metadata: optional metadata

    Returns:
        stripe.Subscription dict
    """
    metadata = metadata or {}

    def _create():
        sub_kwargs = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "expand": ["latest_invoice.payment_intent"],
            "metadata": metadata,
        }

        if default_payment_method:
            _run_blocking_with_retries(
                stripe.PaymentMethod.attach, default_payment_method, customer=customer_id
            )
            _run_blocking_with_retries(
                stripe.Customer.modify,
                customer_id,
                invoice_settings={"default_payment_method": default_payment_method},
            )

        if trial_period_days is not None:
            sub_kwargs["trial_period_days"] = trial_period_days

        return _run_blocking_with_retries(stripe.Subscription.create, **sub_kwargs)

    logger.info("Creating subscription for customer=%s price=%s", customer_id, price_id)
    return await _run_blocking(_create, timeout=_DEFAULT_TIMEOUT)


async def retrieve_subscription(subscription_id: str) -> dict:
    """
    Retrieve a Stripe subscription by its identifier.

    Args:
        subscription_id (str): The Stripe subscription ID to fetch.

    Returns:
        dict: The retrieved Stripe Subscription object.

    Raises:
        Exception: If the Stripe retrieval request fails.
    """

    def _get():
        return _run_blocking_with_retries(
            stripe.Subscription.retrieve,
            subscription_id,
        )

    logger.debug("Retrieving Stripe subscription %s", subscription_id)
    return await _run_blocking(_get, timeout=_DEFAULT_TIMEOUT)


async def update_subscription_price(
    subscription_id: str,
    new_price_id: str,
) -> dict:
    """
    Update a Stripe subscription to use a new price for its existing item.

    Args:
        subscription_id (str): The Stripe subscription ID to update.
        new_price_id (str): The new Stripe price ID to apply to the subscription.

    Returns:
        dict: The updated Stripe Subscription object.

    Raises:
        SubscriptionAlreadyCanceledError: If the subscription is already canceled.
        Exception: If the Stripe update request fails.
    """

    def _update():
        sub = _run_blocking_with_retries(
            stripe.Subscription.retrieve,
            subscription_id,
        )

        if sub.get("status") == "canceled":
            raise SubscriptionAlreadyCanceledError(
                "Subscription is canceled and cannot be changed."
            )

        item_id = sub["items"]["data"][0]["id"]

        updated = _run_blocking_with_retries(
            stripe.Subscription.modify,
            subscription_id,
            items=[
                {
                    "id": item_id,
                    "price": new_price_id,
                }
            ],
            proration_behavior="create_prorations",
        )
        return updated

    logger.info(
        "Updating subscription %s to price=%s",
        subscription_id,
        new_price_id,
    )
    return await _run_blocking(_update, timeout=_DEFAULT_TIMEOUT)


async def cancel_subscription(
    subscription_id: str,
    cancel_at_period_end: bool = True,
) -> dict:
    """
    Cancel a Stripe subscription either immediately or at the end of the current period.

    Args:
        subscription_id (str): The Stripe subscription ID to cancel.
        cancel_at_period_end (bool): If True, cancel at period end; otherwise cancel now.

    Returns:
        dict: The updated or deleted Stripe Subscription object, depending on mode.

    Raises:
        Exception: If the Stripe cancellation request fails.
    """

    def _cancel():
        if cancel_at_period_end:
            return _run_blocking_with_retries(
                stripe.Subscription.modify,
                subscription_id,
                cancel_at_period_end=True,
            )
        else:
            return _run_blocking_with_retries(
                stripe.Subscription.delete,
                subscription_id,
            )

    logger.info(
        "Cancelling subscription %s (cancel_at_period_end=%s)",
        subscription_id,
        cancel_at_period_end,
    )
    return await _run_blocking(_cancel, timeout=_DEFAULT_TIMEOUT)


async def create_invoice_for_customer_with_price_id(
    customer_id: str,
    price_id: str,
    quantity: int = 1,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create and finalize a one-off Stripe invoice for a customer using a price and quantity.

    Args:
        customer_id (str): Stripe customer ID to invoice.
        price_id (str): Stripe price ID used to generate the invoice item.
        quantity (int): Quantity applied to the price. Defaults to 1.
        description (Optional[str]): Optional description for the invoice item.
        metadata (Optional[Dict[str, Any]]): Extra metadata for both invoice and item.

    Returns:
        Dict[str, Any]: The finalized Stripe Invoice object.

    Raises:
        Exception: If Stripe invoice creation, item creation, or finalization fails.
    """
    metadata = metadata or {}

    def _create():
        # this logic sends the invoice to the customer email
        # we can charge it automatically by setting collection_method="charge_automatically"
        invoice = stripe.Invoice.create(
            customer=customer_id,
            auto_advance=False,
            collection_method="send_invoice",
            days_until_due=settings.STRIPE_INVOICE_DURATION_DAYS,
            metadata=metadata,
        )

        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice.id,
            pricing={"price": price_id},
            quantity=quantity,
            description=description,
            metadata=metadata,
        )

        finalized = stripe.Invoice.finalize_invoice(invoice.id)
        return finalized

    logger.info(
        "Creating invoice for customer %s price=%s quantity=%s",
        customer_id,
        price_id,
        quantity,
    )
    return await _run_blocking(
        lambda: _run_blocking_with_retries(_create),
        timeout=_DEFAULT_TIMEOUT * 2,
    )


async def create_invoice_for_customer_with_amount(
    customer_id: str,
    amount: int,
    currency: str = "USD",
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a one-off invoice for a customer and attempt to finalize (optionally pay).

    Note: For many flows you create an invoice via subscriptions or invoice items + finalize.
    This helper demonstrates a simple invoice creation flow.

    Args:
        customer_id: stripe customer id
        amount: integer amount in smallest currency unit (e.g. cents)
        currency: currency code
        description: optional description
        metadata: optional metadata

    Returns:
        stripe.Invoice dict
    """
    metadata = metadata or {}

    def _create():
        invoice = stripe.Invoice.create(
            customer=customer_id,
            auto_advance=False,
            collection_method="send_invoice",
            days_until_due=settings.STRIPE_INVOICE_DURATION_DAYS,
            metadata=metadata,
        )

        stripe.InvoiceItem.create(
            customer=customer_id,
            invoice=invoice.id,
            amount=amount,
            currency=currency,
            description=description,
            metadata=metadata,
        )

        finalized = stripe.Invoice.finalize_invoice(invoice.id)

        return finalized

    logger.info("Creating invoice for customer %s amount=%s %s", customer_id, amount, currency)
    return await _run_blocking(
        lambda: _run_blocking_with_retries(_create), timeout=_DEFAULT_TIMEOUT * 2
    )


async def verify_webhook_signature(payload: bytes, header: str) -> Dict[str, Any]:
    """
    Verify a Stripe webhook payload and return the parsed event.

    Args:
        payload: raw request.body() bytes
        header: the 'Stripe-Signature' header value

    Returns:
        The stripe.Event object (dict)

    Raises:
        stripe.error.SignatureVerificationError if verification fails
    """
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not configured - cannot verify webhooks")
        raise RuntimeError("Webhook secret not configured")

    def _construct():
        return _run_blocking_with_retries(
            stripe.Webhook.construct_event, payload, header, webhook_secret
        )

    logger.debug("Verifying stripe webhook signature (len=%d)", len(payload))
    return await _run_blocking(_construct, timeout=_DEFAULT_TIMEOUT)
