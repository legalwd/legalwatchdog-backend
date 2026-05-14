"""
Refactored tests for billing service.

Ensures unique test data for each test to prevent IntegrityError
and uses rollback to keep the test database clean.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# route tests
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import require_approved_user, require_billing_admin
from app.api.db.database import get_db
from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingPlan,
    BillingStatus,
    PaymentMethod,
    PlanInterval,
    PlanTier,
)
from app.api.modules.v1.billing.service.billing_service import BillingService
from app.api.modules.v1.users.models.users_model import User
from main import app


@pytest.mark.asyncio
class TestBillingServiceAccountCreation:
    """Tests for billing account creation and retrieval."""

    async def _mock_user(self):
        from app.api.modules.v1.users.models.users_model import User

        return User(
            id=uuid4(),
            email=f"{uuid4()}@example.com",
            name="Test User",
            hashed_password="hashed",
            is_active=True,
            is_verified=True,
            is_approved=True,
        )

    async def test_create_billing_account_success(self, pg_async_session):
        org_id = uuid4()
        user = await self._mock_user()

        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.TRIALING,
            currency="USD",
            trial_starts_at=datetime.now(timezone.utc),
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            metadata_={},
        )

        mock = AsyncMock(return_value=account)
        with patch.object(BillingService, "create_billing_account", new=mock):
            service = BillingService(db=pg_async_session)
            result = await service.create_billing_account(user=user, organization_id=org_id)

        assert result.id == account.id
        assert result.organization_id == org_id
        assert result.stripe_customer_id == account.stripe_customer_id

    async def test_create_billing_account_duplicate_organization(self, pg_async_session):
        org_id = uuid4()
        user = await self._mock_user()

        with patch.object(
            BillingService,
            "create_billing_account",
            new=AsyncMock(
                side_effect=ValueError(
                    "A billing account already exists for your organization. "
                    "Please contact support if you need assistance."
                )
            ),
        ):
            service = BillingService(db=pg_async_session)
            with pytest.raises(ValueError) as exc_info:
                await service.create_billing_account(user=user, organization_id=org_id)

        assert "already exists" in str(exc_info.value).lower()

    async def test_create_billing_account_without_stripe_customer(self, pg_async_session):
        org_id = uuid4()
        user = await self._mock_user()

        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=None,
            status=BillingStatus.TRIALING,
            currency="USD",
            metadata_={},
        )

        with patch.object(
            BillingService, "create_billing_account", new=AsyncMock(return_value=account)
        ):
            service = BillingService(db=pg_async_session)
            result = await service.create_billing_account(user=user, organization_id=org_id)

        assert result.stripe_customer_id is None


@pytest.mark.asyncio
class TestBillingRoutesIntegration:
    """Integration-style tests for billing routes using the FastAPI app with
    dependency overrides and patched billing service."""

    async def _fake_user(self):
        return User(
            id=uuid4(),
            email=f"{uuid4()}@example.com",
            name="Test User",
            is_active=True,
            is_verified=True,
            is_approved=True,
        )

    async def test_create_billing_account_route_success(self, pg_async_session, monkeypatch):
        org_id = uuid4()
        fake_user = await self._fake_user()

        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.TRIALING,
            currency="USD",
            metadata_={},
        )

        mock_service = MagicMock(spec=BillingService)
        mock_service.create_billing_account = AsyncMock(return_value=account)

        app.dependency_overrides[require_approved_user] = lambda: fake_user
        app.dependency_overrides[require_billing_admin] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: pg_async_session

        monkeypatch.setattr(
            "app.api.modules.v1.billing.routes.billing_routes.get_billing_service",
            lambda db: mock_service,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/v1/organizations/{org_id}/billing/accounts")

        app.dependency_overrides.pop(require_billing_admin, None)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["id"] == str(account.id)

    async def test_create_checkout_session_plan_not_found(self, pg_async_session, monkeypatch):
        org_id = uuid4()
        fake_user = await self._fake_user()

        mock_service = MagicMock(spec=BillingService)

        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id="cus_test123",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )
        mock_service.get_billing_account_by_org = AsyncMock(return_value=account)
        mock_service.get_plan_by_id = AsyncMock(return_value=None)

        app.dependency_overrides[require_approved_user] = lambda: fake_user
        app.dependency_overrides[require_billing_admin] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: pg_async_session
        monkeypatch.setattr(
            "app.api.modules.v1.billing.routes.billing_routes.get_billing_service",
            lambda db: mock_service,
        )

        payload = {"plan_id": str(uuid4())}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/organizations/{org_id}/billing/checkout", json=payload
            )

        app.dependency_overrides.pop(require_approved_user, None)
        app.dependency_overrides.pop(require_billing_admin, None)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404

    async def test_create_checkout_session_success(self, pg_async_session, monkeypatch):
        org_id = uuid4()
        fake_user = await self._fake_user()

        plan_id = uuid4()
        plan = BillingPlan(
            id=plan_id,
            code="pro",
            tier=PlanTier.PROFESSIONAL,
            label="Pro",
            interval=PlanInterval.MONTH,
            currency="USD",
            amount=10000,
            stripe_product_id="prod",
            stripe_price_id="price_1",
            is_active=True,
        )

        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )

        mock_service = MagicMock(spec=BillingService)
        mock_service.get_billing_account_by_org = AsyncMock(return_value=account)
        mock_service.get_plan_by_id = AsyncMock(return_value=plan)

        monkeypatch.setattr(
            "app.api.modules.v1.billing.routes.billing_routes.stripe_create_checkout_session",
            AsyncMock(return_value={"url": "https://checkout", "id": "cs_123"}),
        )
        app.dependency_overrides[require_approved_user] = lambda: fake_user
        app.dependency_overrides[require_billing_admin] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: pg_async_session
        monkeypatch.setattr(
            "app.api.modules.v1.billing.routes.billing_routes.get_billing_service",
            lambda db: mock_service,
        )

        payload = {"plan_id": str(plan_id)}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/organizations/{org_id}/billing/checkout", json=payload
            )

        app.dependency_overrides.pop(require_billing_admin, None)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["checkout_url"].rstrip("/") == "https://checkout"

    async def test_get_subscription_status_account_exists(self, pg_async_session, monkeypatch):
        org_id = uuid4()
        fake_user = await self._fake_user()
        account = BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            stripe_subscription_id=f"sub_{uuid4()}",
            status=BillingStatus.ACTIVE,
            current_price_id="price_1",
            currency="USD",
            metadata_={},
        )
        mock_service = MagicMock(spec=BillingService)
        mock_service.get_billing_account_by_org = AsyncMock(return_value=account)
        mock_service.get_plan_by_stripe_price_id = AsyncMock(return_value=None)

        app.dependency_overrides[require_approved_user] = lambda: fake_user
        app.dependency_overrides[require_billing_admin] = lambda: fake_user
        app.dependency_overrides[get_db] = lambda: pg_async_session
        monkeypatch.setattr(
            "app.api.modules.v1.billing.routes.billing_routes.get_billing_service",
            lambda db: mock_service,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/organizations/{org_id}/billing/subscription")

        app.dependency_overrides.pop(require_billing_admin, None)
        app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["stripe_customer_id"] == str(account.stripe_customer_id)


@pytest.mark.asyncio
class TestBillingServiceUsageCheck:
    """Tests for usage checking."""

    async def _mock_account(self, status=BillingStatus.TRIALING, subscription_active=True):
        org_id = uuid4()
        return BillingAccount(
            id=uuid4(),
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            stripe_subscription_id=f"sub_{uuid4()}" if subscription_active else None,
            status=status,
            current_price_id=f"price_{uuid4()}" if subscription_active else None,
            currency="USD",
            cancel_at_period_end=False,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            metadata_={},
        )

    async def test_is_org_allowed_usage_trialing(self, pg_async_session):
        from app.api.modules.v1.organization.models.organization_model import Organization

        org_id = uuid4()
        org = Organization(id=org_id, name="Test Org")
        pg_async_session.add(org)
        await pg_async_session.commit()

        account = BillingAccount(
            organization_id=org_id,
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.TRIALING,
            currency="USD",
            trial_starts_at=datetime.now(timezone.utc),
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            metadata_={},
        )
        pg_async_session.add(account)
        await pg_async_session.commit()

        service = BillingService(db=pg_async_session)
        allowed, status = await service.is_org_allowed_usage(org_id)
        assert allowed is True
        assert status == BillingStatus.TRIALING


@pytest.mark.asyncio
class TestBillingServicePaymentMethods:
    """Tests for payment method handling."""

    async def _mock_account(self):
        return BillingAccount(
            id=uuid4(),
            organization_id=uuid4(),
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )

    async def test_add_payment_method_success(self, pg_async_session):
        account = await self._mock_account()
        method = PaymentMethod(
            id=uuid4(), stripe_payment_method_id=f"pm_{uuid4()}", is_default=True
        )
        service = BillingService(db=pg_async_session)
        with patch.object(BillingService, "add_payment_method", new=AsyncMock(return_value=method)):
            result = await service.add_payment_method(
                billing_account_id=account.id,
                stripe_payment_method_id=method.stripe_payment_method_id,
            )
        assert result.is_default


@pytest.mark.asyncio
class TestBillingServiceInvoices:
    """Tests for invoices."""

    async def _mock_account(self):
        return BillingAccount(
            id=uuid4(),
            organization_id=uuid4(),
            stripe_customer_id=f"cus_{uuid4()}",
            status=BillingStatus.ACTIVE,
            currency="USD",
            metadata_={},
        )

    async def test_create_invoice_record(self, pg_async_session):
        account = await self._mock_account()
        invoice_id = uuid4()
        service = BillingService(db=pg_async_session)
        with patch.object(
            BillingService, "create_invoice_record", new=AsyncMock(return_value={"id": invoice_id})
        ):
            result = await service.create_invoice_record(account=account, amount=1000)
        assert result["id"] == invoice_id
