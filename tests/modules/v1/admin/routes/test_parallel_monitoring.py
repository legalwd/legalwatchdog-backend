import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status

from app.api.core.custom_exceptions.exceptions import (
    InvalidDateRangeError,
    ParallelProviderError,
    ParallelUsageError,
)
from app.api.modules.v1.admin.routes.parallel_monitoring import (
    get_parallel_cost_breakdown,
    get_parallel_detailed_logs,
    get_parallel_usage_by_endpoint,
    get_parallel_usage_by_organization,
    get_parallel_usage_by_project,
    get_parallel_usage_by_user,
    get_parallel_usage_stats,
    get_recent_parallel_errors,
)


class MockQuery:
    def __init__(self, default=None, **kwargs):
        self.default = default

    def __call__(self):
        return self.default

    def __str__(self):
        return str(self.default) if self.default is not None else ""


def convert_uuid_to_str(data):
    """Recursively convert UUID objects to strings in test data."""
    if isinstance(data, dict):
        return {k: convert_uuid_to_str(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_uuid_to_str(item) for item in data]
    elif isinstance(data, UUID):
        return str(data)
    else:
        return data


@pytest.mark.asyncio
async def test_get_parallel_usage_stats_success():
    mock_db = AsyncMock()

    mock_stats = {
        "total_requests": 1250,
        "successful_requests": 1180,
        "failed_requests": 70,
        "success_rate": 94.4,
        "total_cost": "1.25",
        "avg_latency_ms": 1340,
        "total_content_mb": 45.2,
        "avg_content_kb": 37.5,
    }

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.return_value = mock_stats
        mock_service_class.return_value = mock_service

        response = await get_parallel_usage_stats(
            days=30,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_stats


@pytest.mark.asyncio
async def test_get_parallel_usage_stats_invalid_days():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.side_effect = InvalidDateRangeError(
            "Days must be between 1 and 365"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(InvalidDateRangeError):
            await get_parallel_usage_stats(
                days=400,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_parallel_usage_stats_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_usage_stats(
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_parallel_usage_stats_usage_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_stats.side_effect = ParallelUsageError("Database connection failed")
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelUsageError):
            await get_parallel_usage_stats(
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_usage_by_endpoint_success():
    mock_db = AsyncMock()

    mock_endpoint_usage = [
        {
            "endpoint_name": "scrape_source",
            "request_count": 450,
            "successful_requests": 430,
            "failed_requests": 20,
            "total_cost": "0.450",
            "avg_latency_ms": 1250,
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_endpoint.return_value = mock_endpoint_usage
        mock_service_class.return_value = mock_service

        response = await get_parallel_usage_by_endpoint(
            days=30,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"]["endpoint_usage"] == mock_endpoint_usage


@pytest.mark.asyncio
async def test_get_usage_by_endpoint_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_endpoint.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_usage_by_endpoint(
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_usage_by_user_success():
    mock_db = AsyncMock()

    user_id = uuid4()
    mock_user_usage = [
        {
            "user_id": user_id,
            "email": "user@example.com",
            "request_count": 120,
            "successful_requests": 115,
            "failed_requests": 5,
            "total_cost": "0.120",
            "avg_latency_ms": 1300,
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_user.return_value = mock_user_usage
        mock_service_class.return_value = mock_service

        response = await get_parallel_usage_by_user(
            days=30,
            limit=20,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK

        expected_data = convert_uuid_to_str(mock_user_usage)
        actual_data = convert_uuid_to_str(response_data["data"]["user_usage"])
        assert actual_data == expected_data


@pytest.mark.asyncio
async def test_get_usage_by_user_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_user.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_usage_by_user(
                days=30,
                limit=20,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_cost_breakdown_success():
    mock_db = AsyncMock()

    mock_daily_costs = [
        {
            "date": "2025-12-18",
            "request_count": 45,
            "successful_requests": 43,
            "failed_requests": 2,
            "total_cost": "0.045",
        }
    ]

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_cost_breakdown.return_value = mock_daily_costs
        mock_service_class.return_value = mock_service

        response = await get_parallel_cost_breakdown(
            days=30,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"]["daily_costs"] == mock_daily_costs


@pytest.mark.asyncio
async def test_get_cost_breakdown_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_cost_breakdown.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_cost_breakdown(
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_recent_errors_success():
    mock_db = AsyncMock()

    error_id = uuid4()
    user_id = uuid4()
    mock_recent_errors = [
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

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_recent_errors.return_value = mock_recent_errors
        mock_service_class.return_value = mock_service

        response = await get_recent_parallel_errors(
            limit=50,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK

        # Convert UUIDs to strings for comparison
        expected_data = convert_uuid_to_str(mock_recent_errors)
        actual_data = convert_uuid_to_str(response_data["data"]["recent_errors"])
        assert actual_data == expected_data


@pytest.mark.asyncio
async def test_get_recent_errors_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_recent_errors.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_recent_parallel_errors(
                limit=50,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_usage_by_organization_success():
    mock_db = AsyncMock()

    org_id = uuid4()
    mock_org_usage = [
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

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_organization.return_value = mock_org_usage
        mock_service_class.return_value = mock_service

        response = await get_parallel_usage_by_organization(
            days=30,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK

        # Convert UUIDs to strings for comparison
        expected_data = convert_uuid_to_str(mock_org_usage)
        actual_data = convert_uuid_to_str(response_data["data"]["organization_usage"])
        assert actual_data == expected_data


@pytest.mark.asyncio
async def test_get_usage_by_organization_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_organization.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_usage_by_organization(
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_usage_by_project_success():
    mock_db = AsyncMock()
    org_id = uuid4()
    project_id = uuid4()

    mock_proj_usage = [
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

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_project.return_value = mock_proj_usage
        mock_service_class.return_value = mock_service

        response = await get_parallel_usage_by_project(
            organization_id=str(org_id),
            days=30,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK

        # Convert UUIDs to strings for comparison
        expected_data = convert_uuid_to_str(mock_proj_usage)
        actual_data = convert_uuid_to_str(response_data["data"]["project_usage"])
        assert actual_data == expected_data


@pytest.mark.asyncio
async def test_get_usage_by_project_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_usage_by_project.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with pytest.raises(ParallelProviderError):
            await get_parallel_usage_by_project(
                organization_id=str(uuid4()),
                days=30,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_get_detailed_logs_success():
    mock_db = AsyncMock()

    user_uuid = str(uuid4())
    org_uuid = str(uuid4())
    project_uuid = str(uuid4())
    log_uuid = str(uuid4())

    mock_logs_data = {
        "total": 250,
        "limit": 100,
        "offset": 0,
        "logs": [
            {
                "id": log_uuid,
                "url_extracted": "https://example.com/page",
                "endpoint_name": "scrape_source",
                "user": {
                    "id": user_uuid,
                    "name": "John Doe",
                    "email": "john@example.com",
                },
                "organization": {
                    "id": org_uuid,
                    "name": "Acme Corp",
                },
                "project": {
                    "id": project_uuid,
                    "name": "Legal Monitoring",
                },
                "success": True,
                "cost_usd": 0.001,
                "latency_ms": 1250,
                "content_size_bytes": 15000,
                "error_message": None,
                "created_at": "2025-12-29T15:30:00Z",
            }
        ],
    }

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_detailed_logs.return_value = mock_logs_data
        mock_service_class.return_value = mock_service

        with patch("app.api.modules.v1.admin.routes.parallel_monitoring.Query", MockQuery):
            response = await get_parallel_detailed_logs(
                user_id=None,
                organization_id=None,
                project_id=None,
                days=7,
                limit=100,
                offset=0,
                db=mock_db,
            )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["data"] == mock_logs_data


@pytest.mark.asyncio
async def test_get_detailed_logs_provider_error():
    mock_db = AsyncMock()

    with patch(
        "app.api.modules.v1.admin.routes.parallel_monitoring.ParallelMonitoringService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service.get_detailed_logs.side_effect = ParallelProviderError(
            "Parallel.ai service is currently unavailable"
        )
        mock_service_class.return_value = mock_service

        with patch("app.api.modules.v1.admin.routes.parallel_monitoring.Query", MockQuery):
            with pytest.raises(ParallelProviderError):
                await get_parallel_detailed_logs(
                    user_id=None,
                    organization_id=None,
                    project_id=None,
                    days=7,
                    limit=100,
                    offset=0,
                    db=mock_db,
                )
