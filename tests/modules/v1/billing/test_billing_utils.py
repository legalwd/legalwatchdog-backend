"""
Tests for billing utility functions.

This module tests helper functions used across the billing system including
status mapping, timestamp parsing, and data transformations.
"""

from datetime import datetime, timezone

from app.api.modules.v1.billing.models import (
    BillingPlan,
    BillingStatus,
    InvoiceStatus,
    PlanInterval,
    PlanTier,
)
from app.api.modules.v1.billing.utils.billings_utils import (
    map_plan_to_plan_info,
    map_stripe_invoice_status,
    map_stripe_status_to_billing_status,
    parse_ts,
)


class TestParseTimestamp:
    """Tests for parse_ts utility function."""

    def test_parse_valid_timestamp(self):
        """Test parsing a valid Unix timestamp."""
        timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        result = parse_ts(timestamp, "test_field")

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.year == 2022
        assert result.month == 1
        assert result.day == 1

    def test_parse_none_timestamp(self):
        """Test parsing None returns None."""
        result = parse_ts(None, "test_field")
        assert result is None

    def test_parse_empty_string_timestamp(self):
        """Test parsing empty string returns None."""
        result = parse_ts("", "test_field")
        assert result is None

    def test_parse_zero_timestamp(self):
        """Test parsing zero timestamp returns None."""
        result = parse_ts(0, "test_field")
        assert result is None

    def test_parse_invalid_timestamp(self):
        """Test parsing invalid timestamp returns None and logs warning."""
        result = parse_ts("invalid", "test_field")
        assert result is None

    def test_parse_timestamp_as_string(self):
        """Test parsing timestamp provided as string."""
        timestamp_str = "1640995200"
        result = parse_ts(timestamp_str, "test_field")

        assert result is not None
        assert result.year == 2022


class TestMapStripeStatusToBillingStatus:
    """Tests for Stripe status to BillingStatus mapping."""

    def test_map_trialing_status(self):
        """Test mapping 'trialing' Stripe status."""
        result = map_stripe_status_to_billing_status("trialing")
        assert result == BillingStatus.TRIALING

    def test_map_active_status(self):
        """Test mapping 'active' Stripe status."""
        result = map_stripe_status_to_billing_status("active")
        assert result == BillingStatus.ACTIVE

    def test_map_past_due_status(self):
        """Test mapping 'past_due' Stripe status."""
        result = map_stripe_status_to_billing_status("past_due")
        assert result == BillingStatus.PAST_DUE

    def test_map_incomplete_status(self):
        """Test mapping 'incomplete' Stripe status."""
        result = map_stripe_status_to_billing_status("incomplete")
        assert result == BillingStatus.UNPAID

    def test_map_incomplete_expired_status(self):
        """Test mapping 'incomplete_expired' Stripe status."""
        result = map_stripe_status_to_billing_status("incomplete_expired")
        assert result == BillingStatus.UNPAID

    def test_map_unpaid_status(self):
        """Test mapping 'unpaid' Stripe status."""
        result = map_stripe_status_to_billing_status("unpaid")
        assert result == BillingStatus.UNPAID

    def test_map_canceled_status(self):
        """Test mapping 'canceled' Stripe status."""
        result = map_stripe_status_to_billing_status("canceled")
        assert result == BillingStatus.CANCELLED

    def test_map_cancelled_status_uk_spelling(self):
        """Test mapping 'cancelled' (UK spelling) Stripe status."""
        result = map_stripe_status_to_billing_status("cancelled")
        assert result == BillingStatus.CANCELLED

    def test_map_unknown_status_defaults_to_unpaid(self):
        """Test mapping unknown Stripe status defaults to UNPAID."""
        result = map_stripe_status_to_billing_status("unknown_status")
        assert result == BillingStatus.UNPAID


class TestMapStripeInvoiceStatus:
    """Tests for Stripe invoice status mapping."""

    def test_map_draft_invoice_status(self):
        """Test mapping 'draft' invoice status."""
        result = map_stripe_invoice_status("draft")
        assert result == InvoiceStatus.DRAFT

    def test_map_open_invoice_status(self):
        """Test mapping 'open' invoice status."""
        result = map_stripe_invoice_status("open")
        assert result == InvoiceStatus.OPEN

    def test_map_paid_invoice_status(self):
        """Test mapping 'paid' invoice status."""
        result = map_stripe_invoice_status("paid")
        assert result == InvoiceStatus.PAID

    def test_map_void_invoice_status(self):
        """Test mapping 'void' invoice status."""
        result = map_stripe_invoice_status("void")
        assert result == InvoiceStatus.VOID

    def test_map_uncollectible_invoice_status(self):
        """Test mapping 'uncollectible' to FAILED."""
        result = map_stripe_invoice_status("uncollectible")
        assert result == InvoiceStatus.FAILED

    def test_map_none_invoice_status_defaults_to_pending(self):
        """Test mapping None defaults to PENDING."""
        result = map_stripe_invoice_status(None)
        assert result == InvoiceStatus.PENDING

    def test_map_unknown_invoice_status_defaults_to_pending(self):
        """Test mapping unknown status defaults to PENDING."""
        result = map_stripe_invoice_status("unknown")
        assert result == InvoiceStatus.PENDING


class TestMapPlanToPlanInfo:
    """Tests for BillingPlan to BillingPlanInfo mapping."""

    def test_map_complete_plan(self):
        """Test mapping a complete BillingPlan to BillingPlanInfo."""
        from uuid import uuid4

        plan = BillingPlan(
            id=uuid4(),
            code="professional_monthly",
            tier=PlanTier.PROFESSIONAL,
            label="Professional Plan",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=10000,
            description="Full-featured plan",
            features_=["Feature 1", "Feature 2", "Feature 3"],
            is_most_popular=True,
            is_active=True,
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
        )

        result = map_plan_to_plan_info(plan)

        assert result.id == plan.id
        assert result.code == "professional_monthly"
        assert result.tier == PlanTier.PROFESSIONAL
        assert result.label == "Professional Plan"
        assert result.interval == "month"
        assert result.currency == "USD"
        assert result.amount == 10000
        assert result.description == "Full-featured plan"
        assert result.features == ["Feature 1", "Feature 2", "Feature 3"]
        assert result.is_most_popular is True
        assert result.is_active is True

    def test_map_plan_with_empty_features(self):
        """Test mapping plan with no features."""
        from uuid import uuid4

        plan = BillingPlan(
            id=uuid4(),
            code="basic",
            tier=PlanTier.ESSENTIAL,
            label="Basic",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=5000,
            features_=[],
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
        )

        result = map_plan_to_plan_info(plan)
        assert result.features == []

    def test_map_plan_with_none_features(self):
        """Test mapping plan where features_ is None."""
        from uuid import uuid4

        plan = BillingPlan(
            id=uuid4(),
            code="basic",
            tier=PlanTier.ESSENTIAL,
            label="Basic",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=5000,
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
        )
        # Simulate None features
        plan.features_ = None

        result = map_plan_to_plan_info(plan)
        assert result.features == []

    def test_map_yearly_plan(self):
        """Test mapping yearly interval plan."""
        from uuid import uuid4

        plan = BillingPlan(
            id=uuid4(),
            code="enterprise_yearly",
            tier=PlanTier.ENTERPRISE,
            label="Enterprise Annual",
            interval=PlanInterval.YEAR,
            currency="USD",
            amount=100000,
            stripe_product_id="prod_test",
            stripe_price_id="price_test",
        )

        result = map_plan_to_plan_info(plan)
        assert result.interval == "year"
