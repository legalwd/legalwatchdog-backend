from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import (
    InvalidDateRangeError,
    ParallelProviderConnectionError,  # Changed from ParallelProviderError
    ParallelUsageError,
)
from app.api.modules.v1.admin.services.parallel_monitoring_service import (
    ParallelMonitoringService,
)


@pytest.mark.asyncio
async def test_get_usage_stats_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    mock_stats = {
        "total_requests": 1250,
        "successful_requests": 1180,
        "failed_requests": 70,
        "success_rate": 94.4,
        "total_cost_usd": 1.25,
        "avg_latency_ms": 1340,
        "total_content_mb": 45.2,
    }

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_stats.return_value = mock_stats

        result = await service.get_usage_stats(days=30)

        assert result["total_requests"] == 1250
        assert result["success_rate"] == 94.4
        assert result["total_cost"] == "1.25"

        expected_avg_content_kb = round((45.2 * 1024) / 1250, 2)
        assert result["avg_content_kb"] == expected_avg_content_kb


@pytest.mark.asyncio
async def test_get_usage_stats_invalid_days():
    mock_db = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = AsyncMock()

        with pytest.raises(InvalidDateRangeError):
            await service.get_usage_stats(days=400)


@pytest.mark.asyncio
async def test_get_usage_stats_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_stats.side_effect = ConnectionError("Service unavailable")

        with pytest.raises(ParallelProviderConnectionError) as exc_info:
            await service.get_usage_stats(days=30)

        assert "Parallel.ai service is currently unavailable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_usage_stats_tracker_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_stats.side_effect = Exception("DB error")

        with pytest.raises(ParallelUsageError):
            await service.get_usage_stats(days=30)


@pytest.mark.asyncio
async def test_get_usage_by_endpoint_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    mock_endpoint_data = [
        {
            "endpoint_name": "scrape_source",
            "request_count": 450,
            "successful_requests": 430,
            "failed_requests": 20,
            "total_cost_usd": 0.45,
            "avg_latency_ms": 1250,
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_endpoint.return_value = mock_endpoint_data

        result = await service.get_usage_by_endpoint(days=30)

        assert len(result) == 1
        assert result[0]["endpoint_name"] == "scrape_source"
        assert result[0]["total_cost"] == "0.45"
        assert "total_cost_usd" not in result[0]


@pytest.mark.asyncio
async def test_get_usage_by_endpoint_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_endpoint.side_effect = ConnectionError("Service down")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_usage_by_endpoint(days=30)


@pytest.mark.asyncio
async def test_get_usage_by_user_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    user_id = uuid4()
    mock_user_data = [
        {
            "user_id": user_id,
            "user_email": "user@example.com",
            "request_count": 120,
            "successful_requests": 115,
            "failed_requests": 5,
            "total_cost_usd": 0.12,
            "avg_latency_ms": 1300,
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_user_detailed.return_value = mock_user_data

        result = await service.get_usage_by_user(days=30, limit=20)

        assert len(result) == 1
        assert result[0]["user_id"] == user_id
        assert result[0]["email"] == "user@example.com"
        assert result[0]["total_cost"] == "0.12"


@pytest.mark.asyncio
async def test_get_usage_by_user_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_user_detailed.side_effect = ConnectionError("Network error")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_usage_by_user(days=30, limit=20)


@pytest.mark.asyncio
async def test_get_cost_breakdown_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    mock_cost_data = [
        {
            "date": "2025-12-18",
            "request_count": 45,
            "successful_requests": 43,
            "failed_requests": 2,
            "total_cost_usd": 0.045,
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_daily_cost_breakdown.return_value = mock_cost_data

        result = await service.get_cost_breakdown(days=30)

        assert len(result) == 1
        assert result[0]["date"] == "2025-12-18"
        assert result[0]["total_cost"] == "0.045"


@pytest.mark.asyncio
async def test_get_cost_breakdown_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_daily_cost_breakdown.side_effect = ConnectionError("Timeout")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_cost_breakdown(days=30)


@pytest.mark.asyncio
async def test_get_recent_errors_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    error_id = uuid4()
    user_id = uuid4()
    mock_error_data = [
        {
            "id": error_id,
            "user_id": user_id,
            "url_extracted": "https://example.com/page",
            "endpoint_name": "scrape_source",
            "error_message": "Request timeout",
            "latency_ms": 30000,
            "created_at": "2025-12-18T10:30:00Z",
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_recent_errors.return_value = mock_error_data

        result = await service.get_recent_errors(limit=50)

        assert len(result) == 1
        assert result[0]["id"] == error_id
        assert result[0]["error_message"] == "Request timeout"


@pytest.mark.asyncio
async def test_get_recent_errors_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_recent_errors.side_effect = ConnectionError("Service down")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_recent_errors(limit=50)


@pytest.mark.asyncio
async def test_validate_days():
    mock_db = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)

        service._validate_days(1)
        service._validate_days(30)
        service._validate_days(365)
        service._validate_days(7, max_days=90)

        with pytest.raises(InvalidDateRangeError):
            service._validate_days(0)

        with pytest.raises(InvalidDateRangeError):
            service._validate_days(400)

        with pytest.raises(InvalidDateRangeError):
            service._validate_days(100, max_days=90)


@pytest.mark.asyncio
async def test_validate_limit():
    mock_db = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)

        service._validate_limit(1, max_limit=100)
        service._validate_limit(50, max_limit=100)
        service._validate_limit(100, max_limit=100)

        with pytest.raises(InvalidDateRangeError):
            service._validate_limit(0, max_limit=100)

        with pytest.raises(InvalidDateRangeError):
            service._validate_limit(150, max_limit=100)


@pytest.mark.asyncio
async def test_get_detailed_logs_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    mock_logs_data = {
        "total": 250,
        "limit": 100,
        "offset": 0,
        "logs": [
            {
                "id": uuid4(),
                "url_extracted": "https://example.com/page",
                "endpoint_name": "scrape_source",
                "user": {"id": uuid4(), "name": "John Doe", "email": "john@example.com"},
                "organization": {"id": uuid4(), "name": "Acme Corp"},
                "project": {"id": uuid4(), "name": "Legal Monitoring"},
                "success": True,
                "cost_usd": 0.001,
                "latency_ms": 1250,
                "content_size_bytes": 15000,
                "error_message": None,
                "created_at": "2025-12-29T15:30:00Z",
            }
        ],
    }

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_detailed_logs.return_value = mock_logs_data

        result = await service.get_detailed_logs(days=7, limit=100, offset=0)

        assert result["total"] == 250
        assert len(result["logs"]) == 1
        assert result["logs"][0]["success"] is True


@pytest.mark.asyncio
async def test_get_detailed_logs_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_detailed_logs.side_effect = ConnectionError("Network error")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_detailed_logs(days=7, limit=100, offset=0)


@pytest.mark.asyncio
async def test_get_detailed_logs_invalid_parameters():
    mock_db = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = AsyncMock()

        with pytest.raises(InvalidDateRangeError):
            await service.get_detailed_logs(days=100, limit=50)

        with pytest.raises(InvalidDateRangeError):
            await service.get_detailed_logs(days=7, limit=600)


@pytest.mark.asyncio
async def test_get_usage_by_organization_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    org_id = uuid4()
    mock_org_data = [
        {
            "organization_id": org_id,
            "organization_name": "Acme Corp",
            "plan": "premium",
            "unique_users": 15,
            "request_count": 450,
            "successful_requests": 430,
            "failed_requests": 20,
            "total_cost_usd": 0.45,
            "total_content_mb": 12.5,
            "last_request_at": "2025-12-29T15:30:00Z",
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_organization_detailed.return_value = mock_org_data

        result = await service.get_usage_by_organization(days=30)

        assert len(result) == 1
        assert result[0]["organization_id"] == org_id
        assert result[0]["organization_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_get_usage_by_organization_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_organization_detailed.side_effect = ConnectionError(
            "Service unavailable"
        )

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_usage_by_organization(days=30)


@pytest.mark.asyncio
async def test_get_usage_by_project_success():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    org_id = uuid4()
    project_id = uuid4()
    mock_project_data = [
        {
            "project_id": project_id,
            "project_name": "Legal Monitoring",
            "organization_id": org_id,
            "request_count": 120,
            "successful_requests": 115,
            "failed_requests": 5,
            "total_cost_usd": 0.12,
            "total_content_mb": 3.5,
        }
    ]

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_project.return_value = mock_project_data

        result = await service.get_usage_by_project(organization_id=org_id, days=30)

        assert len(result) == 1
        assert result[0]["project_id"] == project_id
        assert result[0]["project_name"] == "Legal Monitoring"


@pytest.mark.asyncio
async def test_get_usage_by_project_parallel_provider_error():
    mock_db = AsyncMock()
    mock_tracker = AsyncMock()

    with patch.object(ParallelMonitoringService, "__init__", return_value=None):
        service = ParallelMonitoringService(mock_db)
        service.db = mock_db
        service.tracker = mock_tracker
        mock_tracker.get_usage_by_project.side_effect = ConnectionError("Service down")

        with pytest.raises(ParallelProviderConnectionError):
            await service.get_usage_by_project(organization_id=uuid4(), days=30)
