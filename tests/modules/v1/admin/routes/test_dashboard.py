"""Tests for superadmin dashboard routes."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.core.custom_exceptions.exceptions import DashboardOverviewError
from app.api.modules.v1.admin.routes.dashboard import (
    get_ai_credits_trend,
    get_dashboard_overview,
    get_payment_breakdown,
    get_revenue_trend,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_get_dashboard_overview_success():
    """Test successful dashboard overview retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_dashboard_data = {
        "revenue": {"total": 150000.00},
        "users": {"new_users": 45},
        "ai_credits": {"total_tokens": 1500000},
        "parallel_ai": {"total_requests": 1250},
        "payment_breakdown": {"paid": 200, "trialing": 120},
        "date_range": {"days": 30},
    }

    with patch("app.api.modules.v1.admin.routes.dashboard.DashboardService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_dashboard_overview = AsyncMock(return_value=mock_dashboard_data)

        response = await get_dashboard_overview(current_user=mock_current_user, db=mock_db, days=30)

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert "revenue" in response_data["data"]
        assert "users" in response_data["data"]


@pytest.mark.asyncio
async def test_get_dashboard_overview_error():
    """Test dashboard overview route handles service errors."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    with patch("app.api.modules.v1.admin.routes.dashboard.DashboardService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_dashboard_overview = AsyncMock(
            side_effect=DashboardOverviewError()
        )

        with pytest.raises(DashboardOverviewError):
            await get_dashboard_overview(current_user=mock_current_user, db=mock_db, days=30)


@pytest.mark.asyncio
async def test_get_revenue_trend_success():
    """Test successful revenue trend retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_trend_data = {
        "trend": [
            {"month": "2024-01", "revenue": 10000.00},
            {"month": "2024-02", "revenue": 12000.00},
        ],
        "months": 12,
    }

    with patch("app.api.modules.v1.admin.routes.dashboard.DashboardService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_revenue_trend = AsyncMock(return_value=mock_trend_data)

        response = await get_revenue_trend(current_user=mock_current_user, db=mock_db, months=12)

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert "trend" in response_data["data"]


@pytest.mark.asyncio
async def test_get_ai_credits_trend_success():
    """Test successful AI credits trend retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_trend_data = {
        "trend": [
            {"month": "2024-01", "tokens": 150000},
            {"month": "2024-02", "tokens": 180000},
        ],
        "months": 12,
    }

    with patch("app.api.modules.v1.admin.routes.dashboard.DashboardService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_ai_credits_trend = AsyncMock(return_value=mock_trend_data)

        response = await get_ai_credits_trend(current_user=mock_current_user, db=mock_db, months=12)

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert "trend" in response_data["data"]


@pytest.mark.asyncio
async def test_get_payment_breakdown_success():
    """Test successful payment breakdown retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_breakdown_data = {
        "breakdown": [
            {"month": "2024-01", "trialing": 100, "paid": 50},
            {"month": "2024-02", "trialing": 110, "paid": 55},
        ],
        "months": 12,
    }

    with patch("app.api.modules.v1.admin.routes.dashboard.DashboardService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_class.return_value = mock_service_instance
        mock_service_instance.get_payment_breakdown = AsyncMock(return_value=mock_breakdown_data)

        response = await get_payment_breakdown(
            current_user=mock_current_user, db=mock_db, months=12
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert "breakdown" in response_data["data"]
