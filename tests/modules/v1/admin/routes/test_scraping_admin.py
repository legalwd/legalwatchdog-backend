import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from app.api.core.custom_exceptions.exceptions import SourceNotFoundError
from app.api.modules.v1.admin.routes.scraping_admin import (
    clear_stuck_jobs_endpoint,
    manual_scrape_source_endpoint,
    retry_stuck_jobs_endpoint,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_manual_scrape_source_endpoint_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()
    source_id = str(uuid.uuid4())

    mock_service_result = {
        "source_id": source_id,
        "task_id": "task-123",
        "status": "initiated",
    }

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.manual_scrape_source = AsyncMock(return_value=mock_service_result)

        response = await manual_scrape_source_endpoint(
            source_id=source_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_202_ACCEPTED
        assert response_data["message"] == "Manual scrape task initiated"
        assert response_data["data"]["source_id"] == source_id
        assert response_data["data"]["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_manual_scrape_source_endpoint_source_not_found():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    mock_db = AsyncMock()
    source_id = str(uuid.uuid4())

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.manual_scrape_source = AsyncMock(
            side_effect=SourceNotFoundError("Source not found")
        )

        with pytest.raises(SourceNotFoundError):
            await manual_scrape_source_endpoint(
                source_id=source_id,
                current_user=mock_current_user,
                db=mock_db,
            )


@pytest.mark.asyncio
async def test_retry_stuck_jobs_endpoint_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    mock_service_result = {
        "task_id": "task-456",
        "status": "initiated",
    }

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.retry_stuck_jobs = AsyncMock(return_value=mock_service_result)

        response = await retry_stuck_jobs_endpoint(
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_202_ACCEPTED
        assert response_data["message"] == "Retry stuck jobs task initiated"
        assert response_data["data"]["task_id"] == "task-456"


@pytest.mark.asyncio
async def test_clear_stuck_jobs_endpoint_success():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()
    source_id = str(uuid.uuid4())

    mock_service_result = {
        "cleared_count": 3,
        "source_id": source_id,
    }

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.clear_stuck_jobs = AsyncMock(return_value=mock_service_result)

        response = await clear_stuck_jobs_endpoint(
            source_id=source_id,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "Successfully cleared 3 stuck jobs"
        assert response_data["data"]["cleared_count"] == 3


@pytest.mark.asyncio
async def test_clear_stuck_jobs_endpoint_no_jobs():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()
    mock_current_user.email = "admin@example.com"

    mock_db = AsyncMock()

    mock_service_result = {
        "cleared_count": 0,
        "source_id": None,
    }

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.clear_stuck_jobs = AsyncMock(return_value=mock_service_result)

        response = await clear_stuck_jobs_endpoint(
            source_id=None,
            current_user=mock_current_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())
        assert response_data["status"] == "SUCCESS"
        assert response_data["status_code"] == status.HTTP_200_OK
        assert response_data["message"] == "No stuck jobs found"
        assert response_data["data"]["cleared_count"] == 0


@pytest.mark.asyncio
async def test_clear_stuck_jobs_endpoint_source_not_found():
    mock_current_user = MagicMock(spec=User)
    mock_current_user.id = uuid.uuid4()

    mock_db = AsyncMock()
    source_id = str(uuid.uuid4())

    with patch(
        "app.api.modules.v1.admin.routes.scraping_admin.ScrapingAdminService"
    ) as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.clear_stuck_jobs = AsyncMock(
            side_effect=SourceNotFoundError("Source not found")
        )

        with pytest.raises(SourceNotFoundError):
            await clear_stuck_jobs_endpoint(
                source_id=source_id,
                current_user=mock_current_user,
                db=mock_db,
            )
