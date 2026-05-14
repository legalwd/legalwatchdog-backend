"""Tests for superadmin metrics service."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import (
    AICreditsMetricsError,
    CustomerNotFoundError,
    InvalidDateRangeError,
    ParallelMetricsError,
    PaymentBreakdownError,
    RevenueMetricsError,
    UserMetricsError,
    UserPaymentStatusError,
)
from app.api.modules.v1.admin.services.superadmin_metrics_service import SuperadminMetricsService


@pytest.mark.asyncio
async def test_superadmin_metrics_service_init():
    """Test service initialization."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)
    assert service.db == mock_db


@pytest.mark.asyncio
async def test_get_revenue_metrics_success():
    """Test successful revenue metrics calculation."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_current_result = MagicMock()
    mock_current_result.scalar.return_value = 150000  # cents
    mock_prev_result = MagicMock()
    mock_prev_result.scalar.return_value = 138000  # cents

    mock_daily_result = MagicMock()
    mock_daily_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[mock_current_result, mock_prev_result, mock_daily_result]
    )
    mock_db.scalar = AsyncMock(side_effect=[150000, 138000])

    result = await service.get_revenue_metrics()

    assert "total_revenue" in result
    assert "trend" in result
    assert "percent_change" in result
    assert "daily_trends" in result


@pytest.mark.asyncio
async def test_get_user_metrics_success():
    """Test successful user metrics calculation."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.scalar = AsyncMock(
        side_effect=[
            45,
            500,
            300,
            10,
            5,
        ]
    )

    mock_growth_result = MagicMock()
    mock_growth_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_growth_result)

    result = await service.get_user_metrics()

    assert "new_users" in result
    assert "total_users" in result
    assert "paid_users" in result
    assert "trial_users" in result
    assert "conversion_rate" in result


@pytest.mark.asyncio
async def test_get_ai_credit_metrics_success():
    """Test successful AI credit metrics calculation."""
    from decimal import Decimal
    from types import SimpleNamespace

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.scalar = AsyncMock(
        side_effect=[
            1500000,
            Decimal("15.50"),
            150,
            150,
        ]
    )

    mock_provider_row = SimpleNamespace(
        provider="openrouter", requests=150, tokens=1500000, cost=Decimal("15.50")
    )
    mock_provider_result = MagicMock()
    mock_provider_result.all.return_value = [mock_provider_row]

    mock_feature_result = MagicMock()
    mock_feature_result.all.return_value = []

    mock_hourly_result = MagicMock()
    mock_hourly_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[mock_provider_result, mock_feature_result, mock_hourly_result]
    )

    result = await service.get_ai_credit_metrics()

    assert "total_tokens" in result
    assert "total_cost" in result
    assert "success_rate" in result
    assert "provider_breakdown" in result


@pytest.mark.asyncio
async def test_get_trialing_vs_paid_breakdown_success():
    """Test successful trialing vs paid breakdown."""
    from types import SimpleNamespace

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_row = SimpleNamespace(month=MagicMock(), total=100, paid=50, trialing=50)
    mock_row.month.strftime.return_value = "2024-01"
    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await service.get_trialing_vs_paid_breakdown(months=12)

    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_user_with_payment_status_success():
    """Test successful user with payment status retrieval."""
    from decimal import Decimal
    from types import SimpleNamespace

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)
    user_id = uuid4()

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.full_name = "John Doe"
    mock_user.email = "john@example.com"
    mock_user.is_active = True
    mock_user.is_verified = True
    mock_user.created_at = MagicMock()
    mock_user.last_active = MagicMock()

    mock_join_result = MagicMock()
    mock_join_result.first.return_value = (mock_user, None, None)  # user, billing, user_org

    mock_ai_row = SimpleNamespace(
        total_requests=100, total_tokens=50000, total_cost=Decimal("5.00")
    )
    mock_ai_result = MagicMock()
    mock_ai_result.first.return_value = mock_ai_row

    mock_invoices_result = MagicMock()
    mock_invoices_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[mock_join_result, mock_ai_result, mock_invoices_result]
    )

    result = await service.get_user_with_payment_status(user_id=user_id)

    assert "id" in result
    assert "name" in result
    assert "payment_status" in result
    assert "ai_usage" in result


@pytest.mark.asyncio
async def test_get_feature_usage_breakdown_success():
    """Test successful feature usage breakdown."""
    from types import SimpleNamespace

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    # Mock execute to return rows with endpoint, credits_used, usage_count
    mock_row = SimpleNamespace(endpoint="/api/scrape", credits_used=10000, usage_count=100)
    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]

    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await service.get_feature_usage_breakdown()

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_parallel_metrics_success():
    """Test successful parallel metrics calculation."""
    from decimal import Decimal
    from types import SimpleNamespace

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_stats_row = SimpleNamespace(
        total_requests=1250,
        successful_requests=1200,
        total_cost=Decimal("125.50"),
        avg_latency_ms=250.5,
        total_content_bytes=5242880,
    )
    mock_stats_result = MagicMock()
    mock_stats_result.one.return_value = mock_stats_row

    mock_endpoint_result = MagicMock()
    mock_endpoint_result.all.return_value = []

    mock_daily_result = MagicMock()
    mock_daily_result.all.return_value = []

    mock_db.execute = AsyncMock(
        side_effect=[mock_stats_result, mock_endpoint_result, mock_daily_result]
    )

    result = await service.get_parallel_metrics()

    assert "total_requests" in result
    assert "successful_requests" in result


@pytest.mark.asyncio
async def test_get_revenue_metrics_invalid_date_range():
    """Test InvalidDateRangeError in revenue metrics."""
    from datetime import datetime

    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    start_date = datetime(2025, 1, 10)
    end_date = datetime(2025, 1, 1)

    with pytest.raises(InvalidDateRangeError):
        await service.get_revenue_metrics(start_date=start_date, end_date=end_date)


@pytest.mark.asyncio
async def test_get_revenue_metrics_generic_error():
    """Test RevenueMetricsError on database failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.execute.side_effect = Exception("DB Connection Failed")

    with pytest.raises(RevenueMetricsError):
        await service.get_revenue_metrics()


@pytest.mark.asyncio
async def test_get_user_metrics_error():
    """Test UserMetricsError on failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.scalar.side_effect = Exception("DB Error")

    with pytest.raises(UserMetricsError):
        await service.get_user_metrics()


@pytest.mark.asyncio
async def test_get_ai_credit_metrics_error():
    """Test AICreditsMetricsError on failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.scalar.side_effect = Exception("DB Error")

    with pytest.raises(AICreditsMetricsError):
        await service.get_ai_credit_metrics()


@pytest.mark.asyncio
async def test_get_parallel_metrics_error():
    """Test ParallelMetricsError on failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.execute.side_effect = Exception("DB Error")

    with pytest.raises(ParallelMetricsError):
        await service.get_parallel_metrics()


@pytest.mark.asyncio
async def test_get_user_with_payment_status_not_found():
    """Test CustomerNotFoundError when user does not exist."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)
    user_id = uuid4()

    mock_db.get.return_value = None

    with pytest.raises(CustomerNotFoundError):
        await service.get_user_with_payment_status(user_id=user_id)


@pytest.mark.asyncio
async def test_get_user_with_payment_status_error():
    """Test UserPaymentStatusError on failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)
    user_id = uuid4()

    mock_db.get.return_value = MagicMock(id=user_id)
    mock_db.execute.side_effect = Exception("DB Error")

    with pytest.raises(UserPaymentStatusError):
        await service.get_user_with_payment_status(user_id=user_id)


@pytest.mark.asyncio
async def test_get_trialing_vs_paid_breakdown_invalid_months():
    """Test InvalidDateRangeError for invalid months."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    with pytest.raises(InvalidDateRangeError):
        await service.get_trialing_vs_paid_breakdown(months=25)


@pytest.mark.asyncio
async def test_get_trialing_vs_paid_breakdown_error():
    """Test PaymentBreakdownError on failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.execute.side_effect = Exception("DB Error")

    with pytest.raises(PaymentBreakdownError):
        await service.get_trialing_vs_paid_breakdown(months=12)


@pytest.mark.asyncio
async def test_get_feature_usage_breakdown_error():
    """Test AICreditsMetricsError for feature usage failure."""
    mock_db = AsyncMock()
    service = SuperadminMetricsService(db=mock_db)

    mock_db.execute.side_effect = Exception("DB Error")

    with pytest.raises(AICreditsMetricsError):
        await service.get_feature_usage_breakdown()
