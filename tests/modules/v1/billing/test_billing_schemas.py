"""
Tests for billing Pydantic schemas.

This module tests request and response schema validation for the billing system.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.modules.v1.billing.models import PlanTier
from app.api.modules.v1.billing.schemas.billing_schema import (
    BillingAccountResponse,
    BillingPlanInfo,
)


class TestBillingAccountResponse:
    """Tests for BillingAccountResponse schema."""

    def test_valid_billing_account_response(self):
        """Test creating valid BillingAccountResponse."""
        org_id = uuid4()
        account_id = uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "id": account_id,
            "organization_id": org_id,
            "status": "TRIALING",
            "currency": "USD",
            "stripe_customer_id": "cus_test123",
            "stripe_subscription_id": "sub_test123",
            "trial_starts_at": now,
            "trial_ends_at": now,
            "created_at": now,
            "updated_at": now,
        }

        response = BillingAccountResponse(**data)

        assert response.id == account_id
        assert response.organization_id == org_id
        assert response.status == "TRIALING"
        assert response.currency == "USD"
        assert response.stripe_customer_id == "cus_test123"

    def test_billing_account_response_with_optional_fields_none(self):
        """Test BillingAccountResponse with optional fields as None."""
        data = {
            "id": uuid4(),
            "organization_id": uuid4(),
            "status": "TRIALING",
            "currency": "USD",
            "default_payment_method_id": None,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "trial_starts_at": None,
            "trial_ends_at": None,
            "created_at": None,
            "updated_at": None,
        }

        response = BillingAccountResponse(**data)

        assert response.default_payment_method_id is None
        assert response.stripe_customer_id is None
        assert response.trial_starts_at is None

    def test_billing_account_response_missing_required_field(self):
        """Test BillingAccountResponse fails without required fields."""
        data = {
            "id": uuid4(),
            # Missing organization_id
            "status": "TRIALING",
            "currency": "USD",
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingAccountResponse(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("organization_id",) for error in errors)

    def test_billing_account_response_invalid_uuid(self):
        """Test BillingAccountResponse fails with invalid UUID."""
        data = {
            "id": "not-a-uuid",
            "organization_id": uuid4(),
            "status": "TRIALING",
            "currency": "USD",
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingAccountResponse(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)


class TestBillingPlanInfo:
    """Tests for BillingPlanInfo schema."""

    def test_valid_billing_plan_info(self):
        """Test creating valid BillingPlanInfo."""
        plan_id = uuid4()

        data = {
            "id": plan_id,
            "code": "professional_monthly",
            "tier": PlanTier.PROFESSIONAL,
            "label": "Professional Plan",
            "interval": "month",
            "currency": "USD",
            "amount": 10000,
            "description": "Full-featured plan",
            "features": ["Feature 1", "Feature 2"],
            "is_most_popular": True,
            "is_active": True,
        }

        plan_info = BillingPlanInfo(**data)

        assert plan_info.id == plan_id
        assert plan_info.code == "professional_monthly"
        assert plan_info.tier == PlanTier.PROFESSIONAL
        assert plan_info.label == "Professional Plan"
        assert plan_info.interval == "month"
        assert plan_info.amount == 10000
        assert len(plan_info.features) == 2

    def test_billing_plan_info_defaults(self):
        """Test BillingPlanInfo default values."""
        data = {
            "code": "basic",
            "tier": PlanTier.ESSENTIAL,
            "label": "Basic Plan",
            "interval": "month",
            "currency": "USD",
            "amount": 5000,
        }

        plan_info = BillingPlanInfo(**data)

        assert plan_info.id is None
        assert plan_info.description is None
        assert plan_info.features == []
        assert plan_info.is_most_popular is False
        assert plan_info.is_active is True

    def test_billing_plan_info_invalid_interval(self):
        """Test BillingPlanInfo fails with invalid interval."""
        data = {
            "code": "test",
            "tier": PlanTier.ESSENTIAL,
            "label": "Test",
            "interval": "daily",  # Invalid - only month/year allowed
            "currency": "USD",
            "amount": 1000,
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingPlanInfo(**data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("interval",) for error in errors)

    def test_billing_plan_info_missing_required_fields(self):
        """Test BillingPlanInfo fails without required fields."""
        data = {
            "code": "test",
            # Missing tier, label, interval, currency, amount
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingPlanInfo(**data)

        errors = exc_info.value.errors()
        required_fields = {"tier", "label", "interval", "currency", "amount"}
        error_fields = {error["loc"][0] for error in errors}

        assert required_fields.issubset(error_fields)

    def test_billing_plan_info_negative_amount(self):
        """Test BillingPlanInfo with negative amount (should pass validation)."""
        data = {
            "code": "test",
            "tier": PlanTier.ESSENTIAL,
            "label": "Test",
            "interval": "month",
            "currency": "USD",
            "amount": -100,
        }

        # Schema doesn't enforce positive amounts, so this should succeed
        plan_info = BillingPlanInfo(**data)
        assert plan_info.amount == -100

    def test_billing_plan_info_empty_features_list(self):
        """Test BillingPlanInfo with empty features list."""
        data = {
            "code": "test",
            "tier": PlanTier.ESSENTIAL,
            "label": "Test",
            "interval": "month",
            "currency": "USD",
            "amount": 1000,
            "features": [],
        }

        plan_info = BillingPlanInfo(**data)
        assert plan_info.features == []

    def test_billing_plan_info_yearly_interval(self):
        """Test BillingPlanInfo with yearly interval."""
        data = {
            "code": "enterprise_yearly",
            "tier": PlanTier.ENTERPRISE,
            "label": "Enterprise Annual",
            "interval": "year",
            "currency": "USD",
            "amount": 100000,
        }

        plan_info = BillingPlanInfo(**data)
        assert plan_info.interval == "year"
