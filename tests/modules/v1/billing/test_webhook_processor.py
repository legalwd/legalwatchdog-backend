"""
Refactored tests for Stripe webhook event processing.

All original test coverage retained with reduced repetition.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingPlan,
    BillingStatus,
    InvoiceStatus,
    PlanInterval,
    PlanTier,
)
from app.api.modules.v1.billing.service.billing_service import BillingService
from app.api.modules.v1.billing.stripe.webhook_processor import (
    _handle_checkout_session_completed,
    _handle_invoice_event,
    _handle_payment_intent_event,
    _handle_payment_method_attached,
    _handle_subscription_event,
    _is_event_processed,
    _mark_event_processed,
    process_stripe_event,
)
from app.api.modules.v1.organization.models.organization_model import Organization


@pytest.mark.asyncio
class TestWebhookIdempotency:
    """Tests for webhook event idempotency checks."""

    async def test_mark_event_processed(self, mock_redis):
        await _mark_event_processed("evt_test")
        mock_redis.set.assert_called_once()

    @pytest.mark.parametrize("exists,expected", [(1, True), (0, False)])
    async def test_is_event_processed(self, mock_redis, exists, expected):
        # Mock exists should return the expected boolean directly
        async def mock_exists(key):
            return exists

        mock_redis.exists.side_effect = mock_exists
        result = await _is_event_processed("evt_test")
        assert result is expected

    async def test_is_event_processed_handles_redis_error(self, mock_redis):
        mock_redis.exists.side_effect = Exception("Redis connection failed")
        result = await _is_event_processed("evt_test")
        assert result is False


@pytest.mark.asyncio
class TestInvoiceEventHandling:
    """Tests for invoice event processing."""

    async def test_handle_invoice_event_create_update(self, pg_async_session):
        """Test invoice create/update flows."""
        service = BillingService(pg_async_session)
        org_id = uuid4()

        # Ensure organization exists to satisfy FK constraints
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        # Create billing account
        account = BillingAccount(
            organization_id=org_id,
            stripe_customer_id="cus_test123",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        # Create new invoice event with unique ID to avoid data collision
        invoice_data = {
            "id": "in_test123_create_update",
            "customer": "cus_test123",
            "total": 10000,
            "amount_due": 10000,
            "amount_paid": 10000,
            "currency": "usd",
            "status": "paid",
            "payment_intent": "pi_test123",
            "hosted_invoice_url": "https://invoice.stripe.com/test",
            "invoice_pdf": "https://invoice.stripe.com/test.pdf",
            "lines": {
                "data": [
                    {
                        "metadata": {
                            "plan_code": "professional",
                            "plan_interval": "month",
                            "plan_tier": "professional",
                        },
                        "price": {"id": "price_test123"},
                    }
                ]
            },
        }

        # Test creating invoice
        result = await _handle_invoice_event(pg_async_session, invoice_data)
        assert result["action"] == "invoice_upserted"
        created_invoice = await service.find_invoice_by_stripe_invoice_id(
            "in_test123_create_update"
        )
        assert created_invoice.amount_due == 10000
        assert created_invoice.status == InvoiceStatus.PAID

        # Test updating invoice - modify and re-handle the same invoice data
        invoice_data_update = invoice_data.copy()
        invoice_data_update["total"] = 20000
        invoice_data_update["amount_due"] = 20000
        result = await _handle_invoice_event(pg_async_session, invoice_data_update)
        assert result["action"] == "invoice_upserted"
        # Refetch from DB to see updated values
        updated_invoice = await service.find_invoice_by_stripe_invoice_id(
            "in_test123_create_update"
        )
        assert updated_invoice.amount_due == 20000

    async def test_handle_invoice_event_invalid_cases(self, pg_async_session):
        # No customer
        invoice_data = {"id": "in_test123", "total": 10000, "status": "paid"}
        result = await _handle_invoice_event(pg_async_session, invoice_data)
        assert result["action"] == "invoice_no_customer"

        # Account not found
        invoice_data = {
            "id": "in_test123",
            "customer": "cus_nonexistent",
            "status": "paid",
            "lines": {"data": []},
        }
        result = await _handle_invoice_event(pg_async_session, invoice_data)
        assert result["action"] == "invoice_account_not_found"


@pytest.mark.asyncio
class TestPaymentIntentEventHandling:
    """Tests for payment intent event processing."""

    @pytest.mark.parametrize(
        "status,expected_action", [("succeeded", "payment_succeeded"), ("failed", "payment_failed")]
    )
    async def test_handle_payment_intent_succeeded_failed(
        self, pg_async_session, status, expected_action
    ):
        service = BillingService(pg_async_session)
        org_id = uuid4()

        # create organization for the billing account
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        account = await service.create_billing_account(organization_id=org_id)
        invoice = await service.create_invoice_record(
            billing_account_id=account.id,
            amount_due=10000,
            stripe_payment_intent_id="pi_test123",
            status=InvoiceStatus.OPEN,
        )

        pi_data = {"id": "pi_test123", "amount": 10000, "status": status}
        result = await _handle_payment_intent_event(pg_async_session, pi_data)
        assert result["action"] == expected_action

        await pg_async_session.refresh(invoice)
        if status == "succeeded":
            assert invoice.status == InvoiceStatus.PAID
            assert invoice.amount_paid == 10000
        else:
            assert invoice.status == InvoiceStatus.FAILED

    async def test_handle_payment_intent_edge_cases(self, pg_async_session):
        # Invoice not found
        pi_data = {"id": "pi_nonexistent", "amount": 10000, "status": "succeeded"}
        result = await _handle_payment_intent_event(pg_async_session, pi_data)
        assert result["action"] == "payment_intent_invoice_not_found"

        # Missing ID
        pi_data = {"amount": 10000, "status": "succeeded"}
        result = await _handle_payment_intent_event(pg_async_session, pi_data)
        assert result["action"] == "payment_intent_invalid_payload"


@pytest.mark.asyncio
class TestSubscriptionEventHandling:
    """Tests for subscription event processing."""

    async def test_handle_subscription_event(self, pg_async_session):
        BillingService(pg_async_session)
        org_id = uuid4()

        # Ensure organization exists
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        account = BillingAccount(
            organization_id=org_id,
            stripe_customer_id="cus_test123",
            status=BillingStatus.TRIALING,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        plan = BillingPlan(
            code="professional_monthly",
            tier=PlanTier.PROFESSIONAL,
            label="Professional",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=10000,
            stripe_product_id="prod_test",
            stripe_price_id="price_test123",
            is_active=True,
        )
        pg_async_session.add(plan)
        await pg_async_session.commit()

        # Normal subscription event
        sub_data = {
            "id": "sub_test123",
            "customer": "cus_test123",
            "status": "active",
            "items": {"data": [{"price": {"id": "price_test123"}, "quantity": 1}]},
        }
        result = await _handle_subscription_event(pg_async_session, sub_data)
        assert result["action"] == "subscription_processed"
        await pg_async_session.refresh(account)
        assert account.stripe_subscription_id == "sub_test123"
        assert account.status == BillingStatus.ACTIVE
        assert account.current_price_id == "price_test123"

        # Missing customer
        sub_data = {"id": "sub_test123", "status": "active"}
        result = await _handle_subscription_event(pg_async_session, sub_data)
        assert result["action"] == "subscription_invalid_payload"

        # Account not found
        sub_data = {
            "id": "sub_test123",
            "customer": "cus_nonexistent",
            "status": "active",
            "items": {"data": []},
        }
        result = await _handle_subscription_event(pg_async_session, sub_data)
        assert result["action"] == "billing_account_not_found"

        # Trial update
        sub_data = {
            "id": "sub_test123",
            "customer": "cus_test123",
            "status": "trialing",
            "trial_start": 1640995200,
            "trial_end": 1642204800,
            "items": {"data": []},
        }
        result = await _handle_subscription_event(pg_async_session, sub_data)
        assert result["action"] == "subscription_processed"
        await pg_async_session.refresh(account)
        assert account.trial_starts_at is not None
        assert account.trial_ends_at is not None

        org_from_db = await pg_async_session.get(Organization, org_id)
        assert org_from_db is not None
        assert org_from_db.billing_info is not None
        assert org_from_db.billing_info["stripe_subscription_id"] == "sub_test123"
        assert org_from_db.billing_info["current_price_id"] == "price_test123"
        assert org_from_db.plan is not None


@pytest.mark.asyncio
class TestCheckoutSessionEventHandling:
    """Tests for checkout.session.completed event processing."""

    async def test_checkout_session(self, pg_async_session):
        service = BillingService(pg_async_session)
        org_id = uuid4()

        # create organization before creating billing account
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        account = await service.create_billing_account(organization_id=org_id)

        # Normal linking
        session_data = {
            "id": "cs_test123",
            "customer": account.stripe_customer_id,
            "subscription": "sub_test123",
            "metadata": {
                "organization_id": str(org_id),
                "billing_account_id": str(account.id),
                "plan": "professional",
            },
        }
        result = await _handle_checkout_session_completed(pg_async_session, session_data)
        assert result["action"] == "checkout_session_completed"

        # Account not found
        session_data = {
            "id": "cs_test123",
            "customer": "cus_nonexistent",
            "subscription": "sub_test123",
            "metadata": {},
        }
        result = await _handle_checkout_session_completed(pg_async_session, session_data)
        assert result["action"] == "checkout_completed_account_not_found"

        # Find by metadata
        session_data = {
            "id": "cs_test123",
            "customer": "cus_different",
            "subscription": "sub_test123",
            "metadata": {"billing_account_id": str(account.id)},
        }
        result = await _handle_checkout_session_completed(pg_async_session, session_data)
        assert result["action"] == "checkout_session_completed"


@pytest.mark.asyncio
class TestPaymentMethodEventHandling:
    """Tests for payment_method.attached event processing."""

    async def test_payment_method_attached(self, pg_async_session):
        service = BillingService(pg_async_session)
        org_id = uuid4()
        mock_stripe_customer = {"id": "cus_test123"}

        # ensure org exists
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_create_customer",
            new=AsyncMock(return_value=mock_stripe_customer),
        ):
            account = await service.create_billing_account(
                organization_id=org_id, customer_email="test@example.com"
            )

        # Create - use unique PM IDs to avoid collision
        pm_data = {
            "id": "pm_test123_new",
            "customer": "cus_test123",
            "type": "card",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2025},
        }
        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test123_new"}),
        ):
            result = await _handle_payment_method_attached(pg_async_session, pm_data)
        assert result["action"] == "payment_method_attached_recorded"

        # - use different PM ID
        pm_data_existing = {
            "id": "pm_test123_existing",
            "customer": "cus_test123",
            "type": "card",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2025},
        }
        with patch(
            "app.api.modules.v1.billing.service.billing_service.stripe_attach_payment_method",
            new=AsyncMock(return_value={"id": "pm_test123_existing"}),
        ):
            await service.add_payment_method(
                billing_account_id=account.id, stripe_payment_method_id="pm_test123_existing"
            )
        result = await _handle_payment_method_attached(pg_async_session, pm_data_existing)
        assert result["action"] == "payment_method_already_recorded"

        # Account not found - use unique PM ID
        pm_data_notfound = {"id": "pm_test123_notfound", "customer": "cus_nonexistent", "card": {}}
        result = await _handle_payment_method_attached(pg_async_session, pm_data_notfound)
        assert result["action"] == "payment_method_account_not_found"


@pytest.mark.asyncio
class TestProcessStripeEvent:
    """Tests for main event processing dispatcher."""

    async def test_process_stripe_event_dispatcher(self, pg_async_session, mock_redis):
        BillingService(pg_async_session)
        org_id = uuid4()

        # ensure org exists for direct BillingAccount insert
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        account = BillingAccount(
            organization_id=org_id,
            stripe_customer_id="cus_test123",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        # Normal invoice event
        mock_redis.exists.return_value = 0
        event = {
            "id": "evt_test123",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test123",
                    "customer": "cus_test123",
                    "total": 10000,
                    "amount_due": 10000,
                    "amount_paid": 10000,
                    "currency": "usd",
                    "status": "paid",
                    "lines": {"data": []},
                }
            },
        }
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is True and result["action"] == "invoice_upserted"

        # Subscription
        event = {
            "id": "evt_test456",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "items": {"data": []},
                }
            },
        }
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is True and result["action"] == "subscription_processed"

        # Already processed - set up mock to return 1 (true) for exists
        async def mock_exists_true(key):
            return 1

        mock_redis.exists.side_effect = mock_exists_true
        event = {"id": "evt_duplicate", "type": "invoice.paid", "data": {"object": {}}}
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is False and result["action"] == "already_processed"

        # Invalid payload - reset mock to return 0 (not processed)
        mock_redis.exists.side_effect = None
        mock_redis.exists.return_value = 0
        event = {"data": {"object": {}}}
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is False and result["action"] == "invalid_event"

        # Unhandled event
        event = {"id": "evt_test789", "type": "unknown.event.type", "data": {"object": {}}}
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is True and result["action"] == "unhandled_event_type"

        # Charge succeeded no-op
        event = {
            "id": "evt_charge",
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_test123", "payment_intent": "pi_test123"}},
        }
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is True and result["action"] == "charge_succeeded_noop"

        # Marks as processed
        mock_redis.exists.return_value = 0
        event = {
            "id": "evt_mark_test",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test123",
                    "customer": "cus_test123",
                    "total": 10000,
                    "status": "paid",
                    "lines": {"data": []},
                }
            },
        }
        await process_stripe_event(pg_async_session, event)
        assert mock_redis.set.call_count > 0

        # Processing error
        event = {
            "id": "evt_error",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_test123",
                    "customer": "cus_nonexistent",
                    "total": 10000,
                    "status": "paid",
                    "lines": {"data": []},
                }
            },
        }
        result = await process_stripe_event(pg_async_session, event)
        assert result["processed"] is True and result["action"] == "invoice_account_not_found"
