"""Tests for LLM monitoring routes with service layer."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from app.api.core.custom_exceptions.exceptions import (
    InvalidDateRangeError,
    LLMProviderError,
    LLMQueryError,
)
from app.api.modules.v1.admin.routes.llm_monitoring import (
    get_cost_breakdown,
    get_detailed_logs,
    get_llm_usage_stats,
    get_provider_health,
    get_usage_by_endpoint,
    get_usage_by_model,
    get_usage_by_organization,
    get_usage_by_project,
    get_usage_by_provider,
    get_usage_by_user,
    get_usage_trends,
)
from app.api.modules.v1.admin.routes.llm_monitoring import (
    test_llm_connection as llm_connection_route,
)
from app.api.modules.v1.admin.services.llm_monitoring_service import LLMMonitoringService
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_get_llm_usage_stats_success():
    """Test successful LLM usage stats retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_stats = {
        "total_requests": 1000,
        "total_tokens": 50000,
        "total_cost": 25.50,
        "avg_cost_per_request": 0.0255,
    }

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.return_value = mock_stats
        mock_service_class.return_value = mock_service

        response = await get_llm_usage_stats(
            start_date="2024-01-01",
            end_date="2024-01-31",
            user_id=None,
            organization_id=None,
            provider=None,
            model=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_stats


@pytest.mark.asyncio
async def test_get_llm_usage_stats_invalid_date():
    """Test LLM usage stats with invalid date."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.side_effect = InvalidDateRangeError("Invalid date format")
        mock_service_class.return_value = mock_service

        with pytest.raises(InvalidDateRangeError):
            await get_llm_usage_stats(
                start_date="invalid-date",
                end_date="2024-01-31",
                db=mock_db,
                current_user=mock_current_user,
            )


@pytest.mark.asyncio
async def test_get_usage_by_provider_success():
    """Test successful usage by provider retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_usage = [
        {"provider": "openrouter", "requests": 500, "cost": 15.00},
        {"provider": "gemini", "requests": 300, "cost": 10.50},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_provider.return_value = mock_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_provider(
            days=30,
            organization_id=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_usage


@pytest.mark.asyncio
async def test_get_usage_by_provider_error():
    """Test usage by provider with service error."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_provider.side_effect = LLMQueryError("Database error")
        mock_service_class.return_value = mock_service

        with pytest.raises(LLMQueryError):
            await get_usage_by_provider(
                days=30,
                organization_id=None,
                db=mock_db,
                current_user=mock_current_user,
            )


@pytest.mark.asyncio
async def test_get_usage_by_model_success():
    """Test successful usage by model retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_usage = [
        {"model": "gpt-4", "requests": 200, "cost": 10.00},
        {"model": "claude-3", "requests": 150, "cost": 7.50},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_model.return_value = mock_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_model(
            days=30,
            provider=None,
            organization_id=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_usage


@pytest.mark.asyncio
async def test_get_usage_by_endpoint_success():
    """Test successful usage by endpoint retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_usage = [
        {"endpoint": "/api/v1/scraping", "requests": 400, "cost": 12.00},
        {"endpoint": "/api/v1/search", "requests": 200, "cost": 8.00},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_endpoint.return_value = mock_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_endpoint(
            days=30,
            organization_id=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_usage


@pytest.mark.asyncio
async def test_get_usage_trends_success():
    """Test successful usage trends retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_trends = [
        {"date": "2024-01-01", "requests": 50, "cost": 2.50},
        {"date": "2024-01-02", "requests": 60, "cost": 3.00},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_trends.return_value = mock_trends
        mock_service_class.return_value = mock_service

        response = await get_usage_trends(
            days=30,
            granularity="day",
            organization_id=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_trends


@pytest.mark.asyncio
async def test_get_usage_trends_invalid_granularity():
    """Test usage trends with invalid granularity."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_trends.side_effect = InvalidDateRangeError(
            "Granularity must be one of: hour, day, week, month"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(InvalidDateRangeError):
            await get_usage_trends(
                days=30,
                granularity="invalid",
                organization_id=None,
                db=mock_db,
                current_user=mock_current_user,
            )


@pytest.mark.asyncio
async def test_get_provider_health_success():
    """Test successful provider health retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_health_data = [
        {"provider": "openrouter", "is_available": True},
        {"provider": "gemini", "is_available": True},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_provider_health.return_value = mock_health_data
        mock_service_class.return_value = mock_service

        response = await get_provider_health(db=mock_db, current_user=mock_current_user)

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"]["providers"] == mock_health_data


@pytest.mark.asyncio
async def test_get_cost_breakdown_success():
    """Test successful cost breakdown retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_breakdown = [
        {"provider": "openrouter", "cost": 15.00, "percentage": 60.0},
        {"model": "gpt-4", "cost": 10.00, "percentage": 40.0},
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_cost_breakdown.return_value = mock_breakdown
        mock_service_class.return_value = mock_service

        response = await get_cost_breakdown(
            days=30,
            organization_id=None,
            group_by="provider",
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_breakdown


@pytest.mark.asyncio
async def test_get_usage_by_organization_success():
    """Test successful LLM usage by organization retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_org_usage = [
        {
            "organization_id": "org-1",
            "organization_name": "Org 1",
            "plan": "premium",
            "unique_users": 10,
            "request_count": 1000,
            "total_tokens": 500000,
            "total_cost_usd": 50.00,
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_organization.return_value = mock_org_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_organization(
            days=30,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert len(response_data["data"]["organizations"]) == 1


@pytest.mark.asyncio
async def test_get_usage_by_user_success():
    """Test successful detailed user usage retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_user_usage = [
        {
            "user_id": "user-1",
            "user_name": "User 1",
            "user_email": "user1@example.com",
            "organization_id": "org-1",
            "organization_name": "Org 1",
            "request_count": 100,
            "total_tokens": 50000,
            "total_cost_usd": 10.00,
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_user.return_value = mock_user_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_user(
            days=30,
            organization_id=None,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert len(response_data["data"]["users"]) == 1


@pytest.mark.asyncio
async def test_get_usage_by_project_success():
    """Test successful LLM usage by project retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_proj_usage = [
        {
            "project_id": "proj-1",
            "project_name": "Project A",
            "organization_id": "org-1",
            "request_count": 500,
            "total_tokens": 250000,
            "total_cost_usd": 25.00,
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_project.return_value = mock_proj_usage
        mock_service_class.return_value = mock_service

        response = await get_usage_by_project(
            organization_id=None,
            days=30,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert len(response_data["data"]["projects"]) == 1


@pytest.mark.asyncio
async def test_get_detailed_logs_success():
    """Test successful LLM detailed logs retrieval."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_logs_data = {
        "total": 150,
        "limit": 100,
        "offset": 0,
        "logs": [
            {
                "id": "log-1",
                "provider": "openrouter",
                "model": "gpt-4",
                "user": {"id": "user-1", "name": "User 1", "email": "u1@e.com"},
                "organization": {"id": "org-1", "name": "Org 1"},
                "project": {"id": "proj-1", "name": "Project A"},
                "tokens": 1000,
                "cost_usd": 0.05,
                "created_at": "2024-01-01T12:00:00Z",
            }
        ],
    }

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_detailed_logs.return_value = mock_logs_data
        mock_service_class.return_value = mock_service

        response = await get_detailed_logs(
            user_id=None,
            organization_id=None,
            project_id=None,
            days=7,
            limit=10,
            offset=0,
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"]["total"] == 150
        assert len(response_data["data"]["logs"]) == 1


@pytest.mark.asyncio
async def test_llm_connection_route_success():
    """Test successful LLM connection test route."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    mock_result = {
        "provider": "openrouter",
        "model": "gpt-4",
        "latency_ms": 500,
        "status": "connected",
        "response_preview": "OK",
    }

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.test_connection.return_value = mock_result
        mock_service_class.return_value = mock_service

        response = await llm_connection_route(
            provider="openrouter",
            model="gpt-4",
            db=mock_db,
            current_user=mock_current_user,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["data"]["status"] == "connected"


@pytest.mark.asyncio
async def test_llm_connection_route_failure():
    """Test LLM connection test route failure."""
    mock_db = AsyncMock()
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid4()

    with patch(
        "app.api.modules.v1.admin.routes.llm_monitoring.LLMMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.test_connection.side_effect = LLMProviderError("Connection timeout")
        mock_service_class.return_value = mock_service

        with pytest.raises(LLMProviderError):
            await llm_connection_route(
                provider="openrouter",
                db=mock_db,
                current_user=mock_current_user,
            )


@pytest.mark.asyncio
async def test_service_validate_date_range():
    """Test service date range validation - use mocked database."""
    mock_db = AsyncMock()
    service = LLMMonitoringService(mock_db)

    start_dt = datetime.now(timezone.utc) - timedelta(days=1)
    end_dt = datetime.now(timezone.utc)
    service._validate_date_range(start_dt, end_dt)

    with pytest.raises(InvalidDateRangeError):
        service._validate_date_range(end_dt, start_dt)

    start_dt = datetime.now(timezone.utc) - timedelta(days=400)
    with pytest.raises(InvalidDateRangeError):
        service._validate_date_range(start_dt, end_dt)


@pytest.mark.asyncio
async def test_service_date_parsing():
    """Test service date parsing methods - use mocked database."""
    mock_db = AsyncMock()
    service = LLMMonitoringService(mock_db)

    start_date = "2024-01-01"
    parsed_start = service._parse_start_date(start_date)
    assert parsed_start.year == 2024
    assert parsed_start.month == 1
    assert parsed_start.day == 1

    end_date = "2024-01-31"
    parsed_end = service._parse_end_date(end_date)
    assert parsed_end.year == 2024
    assert parsed_end.month == 1
    assert parsed_end.day == 31

    default_start = service._parse_start_date(None)
    expected_start = datetime.now(timezone.utc) - timedelta(days=30)
    assert (default_start - expected_start).total_seconds() < 1

    default_end = service._parse_end_date(None)
    expected_end = datetime.now(timezone.utc)
    assert (default_end - expected_end).total_seconds() < 1
