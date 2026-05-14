"""
Tests for Stripe API adapter functions.

This module tests the Stripe API wrapper functions with mocked Stripe SDK calls.
"""

from unittest.mock import patch

import pytest
import stripe

from app.api.modules.v1.billing.stripe.errors import SubscriptionAlreadyCanceledError
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    attach_payment_method,
    cancel_subscription,
    create_checkout_session,
    create_customer,
    create_subscription,
    detach_payment_method,
    retrieve_customer,
    retrieve_payment_method,
    retrieve_subscription,
    update_subscription_price,
    verify_webhook_signature,
)


@pytest.mark.asyncio
class TestStripeCustomerOperations:
    """Tests for Stripe customer creation and retrieval."""

    async def test_create_customer_success(self):
        """Test successful Stripe customer creation."""
        mock_customer = {
            "id": "cus_test123",
            "email": "test@example.com",
            "name": "Test User",
            "object": "customer",
        }

        with patch("stripe.Customer.create", return_value=mock_customer):
            result = await create_customer(
                email="test@example.com",
                name="Test User",
                metadata={"org_id": "123"},
            )

        assert result["id"] == "cus_test123"
        assert result["email"] == "test@example.com"
        assert result["name"] == "Test User"

    async def test_create_customer_with_metadata(self):
        """Test customer creation includes metadata."""
        mock_customer = {"id": "cus_test123", "metadata": {"org_id": "456"}}

        with patch("stripe.Customer.create", return_value=mock_customer) as mock_create:
            await create_customer(
                email="test@example.com",
                metadata={"org_id": "456", "plan": "professional"},
            )

            # Verify metadata was passed
            call_args = mock_create.call_args
            assert call_args[1]["metadata"]["org_id"] == "456"
            assert call_args[1]["metadata"]["plan"] == "professional"

    async def test_create_customer_stripe_error(self):
        """Test customer creation handles Stripe errors."""
        with patch("stripe.Customer.create", side_effect=stripe.error.APIError("API Error")):
            with pytest.raises(stripe.error.APIError):
                await create_customer(email="test@example.com")

    async def test_retrieve_customer_success(self):
        """Test successful customer retrieval."""
        mock_customer = {"id": "cus_test123", "email": "test@example.com"}

        with patch("stripe.Customer.retrieve", return_value=mock_customer):
            result = await retrieve_customer("cus_test123")

        assert result["id"] == "cus_test123"
        assert result["email"] == "test@example.com"

    async def test_retrieve_customer_not_found(self):
        """Test retrieving non-existent customer raises error."""
        with patch(
            "stripe.Customer.retrieve",
            side_effect=stripe.error.InvalidRequestError("No such customer", "customer"),
        ):
            with pytest.raises(stripe.error.InvalidRequestError):
                await retrieve_customer("cus_nonexistent")


@pytest.mark.asyncio
class TestStripePaymentMethodOperations:
    """Tests for payment method operations."""

    async def test_attach_payment_method_success(self):
        """Test successful payment method attachment."""
        mock_pm = {
            "id": "pm_test123",
            "customer": "cus_test123",
            "card": {"brand": "visa", "last4": "4242"},
        }

        with patch("stripe.PaymentMethod.attach", return_value=mock_pm):
            result = await attach_payment_method(
                customer_id="cus_test123",
                payment_method_id="pm_test123",
                set_as_default=False,
            )

        assert result["id"] == "pm_test123"
        assert result["customer"] == "cus_test123"

    async def test_attach_payment_method_as_default(self):
        """Test attaching payment method and setting as default."""
        mock_pm = {"id": "pm_test123", "customer": "cus_test123"}
        mock_customer = {"id": "cus_test123"}

        with patch("stripe.PaymentMethod.attach", return_value=mock_pm):
            with patch("stripe.Customer.modify", return_value=mock_customer) as mock_modify:
                await attach_payment_method(
                    customer_id="cus_test123",
                    payment_method_id="pm_test123",
                    set_as_default=True,
                )

                # Verify Customer.modify was called to set default
                mock_modify.assert_called_once()
                call_args = mock_modify.call_args
                assert call_args[0][0] == "cus_test123"
                assert call_args[1]["invoice_settings"]["default_payment_method"] == "pm_test123"

    async def test_attach_payment_method_invalid_raises_value_error(self):
        """Test attaching invalid payment method raises ValueError."""
        with patch(
            "stripe.PaymentMethod.attach",
            side_effect=stripe.error.InvalidRequestError("Invalid payment method", "pm"),
        ):
            with pytest.raises(ValueError, match="payment method.*invalid"):
                await attach_payment_method(
                    customer_id="cus_test123",
                    payment_method_id="pm_invalid",
                )

    async def test_detach_payment_method_success(self):
        """Test successful payment method detachment."""
        mock_pm = {"id": "pm_test123", "customer": None}

        with patch("stripe.PaymentMethod.detach", return_value=mock_pm):
            result = await detach_payment_method("pm_test123")

        assert result["id"] == "pm_test123"
        assert result["customer"] is None

    async def test_retrieve_payment_method_success(self):
        """Test successful payment method retrieval."""
        mock_pm = {
            "id": "pm_test123",
            "type": "card",
            "card": {"brand": "visa", "last4": "4242"},
        }

        with patch("stripe.PaymentMethod.retrieve", return_value=mock_pm):
            result = await retrieve_payment_method("pm_test123")

        assert result["id"] == "pm_test123"
        assert result["type"] == "card"


@pytest.mark.asyncio
class TestStripeCheckoutOperations:
    """Tests for Stripe Checkout session creation."""

    async def test_create_checkout_session_subscription_mode(self):
        """Test creating checkout session in subscription mode."""
        mock_session = {
            "id": "cs_test123",
            "url": "https://checkout.stripe.com/test",
            "mode": "subscription",
        }

        with patch("stripe.checkout.Session.create", return_value=mock_session):
            result = await create_checkout_session(
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                customer_id="cus_test123",
                mode="subscription",
                price_id="price_test123",
            )

        assert result["id"] == "cs_test123"
        assert result["url"] == "https://checkout.stripe.com/test"
        assert result["mode"] == "subscription"

    async def test_create_checkout_session_requires_price_id(self):
        """Test checkout session creation fails without price_id."""
        with pytest.raises(ValueError, match="price_id is required"):
            await create_checkout_session(
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                mode="subscription",
                price_id=None,
            )

    async def test_create_checkout_session_invalid_mode(self):
        """Test checkout session creation fails with invalid mode."""
        with pytest.raises(ValueError, match="mode must be"):
            await create_checkout_session(
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                mode="invalid_mode",
                price_id="price_test123",
            )

    async def test_create_checkout_session_with_metadata(self):
        """Test checkout session includes metadata."""
        mock_session = {"id": "cs_test123", "metadata": {"org_id": "456"}}

        with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
            await create_checkout_session(
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                mode="subscription",
                price_id="price_test123",
                metadata={"org_id": "456", "plan": "pro"},
            )

            # Verify metadata was passed
            call_args = mock_create.call_args[1]
            assert call_args["metadata"]["org_id"] == "456"
            assert call_args["metadata"]["plan"] == "pro"


@pytest.mark.asyncio
class TestStripeSubscriptionOperations:
    """Tests for subscription creation and management."""

    async def test_create_subscription_success(self):
        """Test successful subscription creation."""
        mock_subscription = {
            "id": "sub_test123",
            "customer": "cus_test123",
            "status": "active",
            "items": {"data": [{"price": {"id": "price_test123"}}]},
        }

        with patch("stripe.Subscription.create", return_value=mock_subscription):
            result = await create_subscription(
                customer_id="cus_test123",
                price_id="price_test123",
            )

        assert result["id"] == "sub_test123"
        assert result["status"] == "active"

    async def test_create_subscription_with_trial(self):
        """Test subscription creation with trial period."""
        mock_subscription = {"id": "sub_test123", "trial_end": 1234567890}

        with patch("stripe.Subscription.create", return_value=mock_subscription) as mock_create:
            await create_subscription(
                customer_id="cus_test123",
                price_id="price_test123",
                trial_period_days=14,
            )

            # Verify trial_period_days was passed
            call_args = mock_create.call_args[1]
            assert call_args["trial_period_days"] == 14

    async def test_create_subscription_with_payment_method(self):
        """Test subscription creation with payment method."""
        mock_pm = {"id": "pm_test123"}
        mock_customer = {"id": "cus_test123"}
        mock_subscription = {"id": "sub_test123"}

        with patch("stripe.PaymentMethod.attach", return_value=mock_pm):
            with patch("stripe.Customer.modify", return_value=mock_customer):
                with patch("stripe.Subscription.create", return_value=mock_subscription):
                    result = await create_subscription(
                        customer_id="cus_test123",
                        price_id="price_test123",
                        default_payment_method="pm_test123",
                    )

        assert result["id"] == "sub_test123"

    async def test_retrieve_subscription_success(self):
        """Test successful subscription retrieval."""
        mock_subscription = {"id": "sub_test123", "status": "active"}

        with patch("stripe.Subscription.retrieve", return_value=mock_subscription):
            result = await retrieve_subscription("sub_test123")

        assert result["id"] == "sub_test123"
        assert result["status"] == "active"

    async def test_update_subscription_price_success(self):
        """Test successful subscription price update."""
        mock_existing_sub = {
            "id": "sub_test123",
            "status": "active",
            "items": {"data": [{"id": "si_test123", "price": {"id": "price_old"}}]},
        }
        mock_updated_sub = {
            "id": "sub_test123",
            "items": {"data": [{"price": {"id": "price_new123"}}]},
        }

        with patch("stripe.Subscription.retrieve", return_value=mock_existing_sub):
            with patch("stripe.Subscription.modify", return_value=mock_updated_sub):
                result = await update_subscription_price(
                    subscription_id="sub_test123",
                    new_price_id="price_new123",
                )

        assert result["id"] == "sub_test123"

    async def test_update_subscription_price_already_canceled_raises_error(self):
        """Test updating canceled subscription raises SubscriptionAlreadyCanceledError."""
        mock_canceled_sub = {
            "id": "sub_test123",
            "status": "canceled",
        }

        with patch("stripe.Subscription.retrieve", return_value=mock_canceled_sub):
            with pytest.raises(SubscriptionAlreadyCanceledError):
                await update_subscription_price(
                    subscription_id="sub_test123",
                    new_price_id="price_new123",
                )

    async def test_cancel_subscription_at_period_end(self):
        """Test canceling subscription at period end."""
        mock_subscription = {
            "id": "sub_test123",
            "cancel_at_period_end": True,
        }

        with patch("stripe.Subscription.modify", return_value=mock_subscription):
            result = await cancel_subscription(
                subscription_id="sub_test123",
                cancel_at_period_end=True,
            )

        assert result["cancel_at_period_end"] is True

    async def test_cancel_subscription_immediately(self):
        """Test canceling subscription immediately."""
        mock_subscription = {
            "id": "sub_test123",
            "status": "canceled",
        }

        with patch("stripe.Subscription.delete", return_value=mock_subscription):
            result = await cancel_subscription(
                subscription_id="sub_test123",
                cancel_at_period_end=False,
            )

        assert result["status"] == "canceled"


@pytest.mark.asyncio
class TestStripeWebhookVerification:
    """Tests for Stripe webhook signature verification."""

    async def test_verify_webhook_signature_success(self):
        """Test successful webhook signature verification."""
        mock_event = {
            "id": "evt_test123",
            "type": "invoice.payment_succeeded",
            "data": {"object": {}},
        }

        payload = b'{"type": "invoice.payment_succeeded"}'
        signature = "test_signature"

        with patch("stripe.Webhook.construct_event", return_value=mock_event):
            result = await verify_webhook_signature(payload, signature)

        assert result["id"] == "evt_test123"
        assert result["type"] == "invoice.payment_succeeded"

    async def test_verify_webhook_signature_invalid_raises_error(self):
        """Test invalid webhook signature raises error."""
        payload = b'{"type": "test"}'
        signature = "invalid_signature"

        with patch(
            "stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("Invalid signature", "sig"),
        ):
            with pytest.raises(stripe.error.SignatureVerificationError):
                await verify_webhook_signature(payload, signature)

    async def test_verify_webhook_signature_missing_secret_raises_error(self):
        """Test webhook verification without secret raises RuntimeError."""
        payload = b'{"type": "test"}'
        signature = "test_signature"

        with patch("app.api.core.config.settings.STRIPE_WEBHOOK_SECRET", None):
            with pytest.raises(RuntimeError, match="Webhook secret not configured"):
                await verify_webhook_signature(payload, signature)


@pytest.mark.asyncio
class TestStripeRetryMechanism:
    """Tests for retry mechanism with transient errors."""

    async def test_rate_limit_error_retries(self):
        """Test that rate limit errors trigger retries."""
        mock_customer = {"id": "cus_test123"}

        # Simulate rate limit on first call, success on second
        side_effects = [
            stripe.error.RateLimitError("Rate limited"),
            mock_customer,
        ]

        with patch("stripe.Customer.create", side_effect=side_effects):
            result = await create_customer(email="test@example.com")

        assert result["id"] == "cus_test123"

    async def test_api_connection_error_retries(self):
        """Test that API connection errors trigger retries."""
        mock_customer = {"id": "cus_test123"}

        # Simulate connection error on first call, success on second
        side_effects = [
            stripe.error.APIConnectionError("Connection failed"),
            mock_customer,
        ]

        with patch("stripe.Customer.create", side_effect=side_effects):
            result = await create_customer(email="test@example.com")

        assert result["id"] == "cus_test123"

    async def test_non_retriable_error_raises_immediately(self):
        """Test that non-retriable errors are raised immediately."""
        with patch(
            "stripe.Customer.create",
            side_effect=stripe.error.InvalidRequestError("Invalid request", "email"),
        ):
            with pytest.raises(stripe.error.InvalidRequestError):
                await create_customer(email="invalid")
