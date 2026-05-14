"""Tests for dashboard service."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    AICreditsTrendError,
    DashboardOverviewError,
    InvalidDateRangeError,
    PaymentBreakdownError,
    RevenueTrendError,
)
from app.api.modules.v1.admin.services.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_get_dashboard_overview_success():
    """Test successful dashboard overview retrieval."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    mock_revenue = {"total": 150000.00}
    mock_users = {"new_users": 45}
    mock_ai_credits = {"total_tokens": 1500000}
    mock_parallel = {"total_requests": 1250}
    mock_payment = {"paid": 200, "trialing": 120}

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service.get_revenue_metrics = AsyncMock(return_value=mock_revenue)
        mock_metrics_service.get_user_metrics = AsyncMock(return_value=mock_users)
        mock_metrics_service.get_ai_credit_metrics = AsyncMock(return_value=mock_ai_credits)
        mock_metrics_service.get_parallel_metrics = AsyncMock(return_value=mock_parallel)
        mock_metrics_service.get_trialing_vs_paid_breakdown = AsyncMock(return_value=mock_payment)

        result = await service.get_dashboard_overview(days=30, user_email="admin@example.com")

        assert "revenue" in result
        assert "users" in result
        assert "ai_credits" in result
        assert "parallel_ai" in result
        assert "payment_breakdown" in result
        assert "date_range" in result


@pytest.mark.asyncio
async def test_get_dashboard_overview_invalid_days():
    """Test dashboard overview with invalid days parameter."""
    mock_db = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = AsyncMock()

        with pytest.raises(InvalidDateRangeError):
            await service.get_dashboard_overview(days=400)


@pytest.mark.asyncio
async def test_get_dashboard_overview_service_error():
    """Test dashboard overview when metrics service fails."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service.get_revenue_metrics = AsyncMock(
            side_effect=Exception("Database error")
        )

        with pytest.raises(DashboardOverviewError):
            await service.get_dashboard_overview(days=30)


@pytest.mark.asyncio
async def test_get_revenue_trend_success():
    """Test successful revenue trend retrieval."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    mock_trend = [
        {"month": "2024-01", "revenue": 10000.00},
        {"month": "2024-02", "revenue": 12000.00},
    ]

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service._get_monthly_revenue_trend = AsyncMock(return_value=mock_trend)

        result = await service.get_revenue_trend(months=12, user_email="admin@example.com")

        assert "trend" in result
        assert "months" in result
        assert result["months"] == 12
        assert len(result["trend"]) == 2


@pytest.mark.asyncio
async def test_get_revenue_trend_invalid_months():
    """Test revenue trend with invalid months parameter."""
    mock_db = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = AsyncMock()

        with pytest.raises(InvalidDateRangeError):
            await service.get_revenue_trend(months=30)


@pytest.mark.asyncio
async def test_get_revenue_trend_service_error():
    """Test revenue trend when metrics service fails."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service._get_monthly_revenue_trend = AsyncMock(
            side_effect=Exception("Service error")
        )

        with pytest.raises(RevenueTrendError):
            await service.get_revenue_trend(months=12)


@pytest.mark.asyncio
async def test_get_ai_credits_trend_success():
    """Test successful AI credits trend retrieval."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    mock_trend = [
        {"month": "2024-01", "tokens": 150000},
        {"month": "2024-02", "tokens": 180000},
    ]

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service._get_monthly_token_trend = AsyncMock(return_value=mock_trend)

        result = await service.get_ai_credits_trend(months=6, user_email="admin@example.com")

        assert "trend" in result
        assert "months" in result
        assert result["months"] == 6


@pytest.mark.asyncio
async def test_get_ai_credits_trend_service_error():
    """Test AI credits trend when metrics service fails."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service._get_monthly_token_trend = AsyncMock(
            side_effect=Exception("Service error")
        )

        with pytest.raises(AICreditsTrendError):
            await service.get_ai_credits_trend(months=12)


@pytest.mark.asyncio
async def test_get_payment_breakdown_success():
    """Test successful payment breakdown retrieval."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    mock_breakdown = [
        {"month": "2024-01", "trialing": 100, "paid": 50},
        {"month": "2024-02", "trialing": 110, "paid": 55},
    ]

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service.get_trialing_vs_paid_breakdown = AsyncMock(return_value=mock_breakdown)

        result = await service.get_payment_breakdown(months=6, user_email="admin@example.com")

        assert "breakdown" in result
        assert "months" in result
        assert result["months"] == 6


@pytest.mark.asyncio
async def test_get_payment_breakdown_service_error():
    """Test payment breakdown when metrics service fails."""
    mock_db = AsyncMock()
    mock_metrics_service = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db
        service.metrics_service = mock_metrics_service

        mock_metrics_service.get_trialing_vs_paid_breakdown = AsyncMock(
            side_effect=Exception("Service error")
        )

        with pytest.raises(PaymentBreakdownError):
            await service.get_payment_breakdown(months=12)


@pytest.mark.asyncio
async def test_validate_days():
    """Test days parameter validation."""
    mock_db = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db

        service._validate_days(1)
        service._validate_days(30)
        service._validate_days(365)

        with pytest.raises(InvalidDateRangeError):
            service._validate_days(0)

        with pytest.raises(InvalidDateRangeError):
            service._validate_days(400)


@pytest.mark.asyncio
async def test_validate_months():
    """Test months parameter validation."""
    mock_db = AsyncMock()

    with patch.object(DashboardService, "__init__", return_value=None):
        service = DashboardService(mock_db)
        service.db = mock_db

        service._validate_months(1)
        service._validate_months(12)
        service._validate_months(24)

        with pytest.raises(InvalidDateRangeError):
            service._validate_months(0)

        with pytest.raises(InvalidDateRangeError):
            service._validate_months(30)
