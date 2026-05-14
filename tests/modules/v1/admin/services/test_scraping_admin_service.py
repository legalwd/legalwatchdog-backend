import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    ClearStuckJobsError,
    ManualScrapeError,
    SourceNotFoundError,
    StuckJobRetryError,
    TaskInitiationError,
)
from app.api.modules.v1.admin.services.scraping_admin_service import ScrapingAdminService


class MockScalarsResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


class MockExecuteResult:
    def __init__(
        self, scalar=None, scalars_items=None, fetchone_result=None, scalar_one_result=None
    ):
        self.scalar_value = scalar
        self.scalars_items = scalars_items
        self.fetchone_result = fetchone_result
        self.scalar_one_result = scalar_one_result

    def scalar(self):
        return self.scalar_value

    def scalars(self):
        return MockScalarsResult(self.scalars_items)

    def fetchone(self):
        return self.fetchone_result

    def scalar_one_or_none(self):
        return self.scalar_one_result


@pytest.mark.asyncio
async def test_manual_scrape_source_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    mock_source = MagicMock()
    mock_source.id = source_id

    async def execute_side_effect(query):
        return MockExecuteResult(scalar_one_result=mock_source)

    mock_db.execute.side_effect = execute_side_effect

    with patch(
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source.delay"
    ) as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task

        result = await service.manual_scrape_source(source_id, user_id)

    assert result["source_id"] == source_id
    assert result["task_id"] == "task-123"
    assert result["status"] == "initiated"


@pytest.mark.asyncio
async def test_manual_scrape_source_not_found():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    async def execute_side_effect(query):
        return MockExecuteResult(scalar_one_result=None)

    mock_db.execute.side_effect = execute_side_effect

    with patch(
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source.delay"
    ) as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task

        with pytest.raises(SourceNotFoundError):
            await service.manual_scrape_source(source_id, user_id)


@pytest.mark.asyncio
async def test_manual_scrape_source_task_init_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    mock_source = MagicMock()
    mock_source.id = source_id

    async def execute_side_effect(query):
        return MockExecuteResult(scalar_one_result=mock_source)

    mock_db.execute.side_effect = execute_side_effect

    with patch(
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source.delay"
    ) as mock_delay:
        mock_delay.return_value = None

        with pytest.raises(TaskInitiationError):
            await service.manual_scrape_source(source_id, user_id)


@pytest.mark.asyncio
async def test_retry_stuck_jobs_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = ScrapingAdminService(mock_db)

    with patch("app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-456"
        mock_delay.return_value = mock_task

        result = await service.retry_stuck_jobs(user_id)

    assert result["task_id"] == "task-456"
    assert result["status"] == "initiated"


@pytest.mark.asyncio
async def test_retry_stuck_jobs_task_init_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = ScrapingAdminService(mock_db)

    with patch("app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs.delay") as mock_delay:
        mock_delay.return_value = None

        with pytest.raises(TaskInitiationError):
            await service.retry_stuck_jobs(user_id)


@pytest.mark.asyncio
async def test_clear_stuck_jobs_success():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    mock_source = MagicMock()
    mock_source.id = source_id

    mock_jobs = [MagicMock(), MagicMock(), MagicMock()]
    for job in mock_jobs:
        job.status = "PENDING"
        job.source_id = source_id

    async def execute_side_effect(query):
        if "sources" in str(query):
            return MockExecuteResult(scalar_one_result=mock_source)
        else:
            return MockExecuteResult(scalars_items=mock_jobs)

    mock_db.execute.side_effect = execute_side_effect
    mock_db.commit = AsyncMock()

    result = await service.clear_stuck_jobs(source_id, user_id)

    assert result["cleared_count"] == 3
    assert result["source_id"] == source_id


@pytest.mark.asyncio
async def test_clear_stuck_jobs_no_source_filter():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = ScrapingAdminService(mock_db)

    mock_jobs = []

    async def execute_side_effect(query):
        return MockExecuteResult(scalars_items=mock_jobs)

    mock_db.execute.side_effect = execute_side_effect

    result = await service.clear_stuck_jobs(None, user_id)

    assert result["cleared_count"] == 0
    assert result["source_id"] is None


@pytest.mark.asyncio
async def test_clear_stuck_jobs_source_not_found():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    async def execute_side_effect(query):
        if "sources" in str(query):
            return MockExecuteResult(scalar_one_result=None)
        return MockExecuteResult(scalars_items=[])

    mock_db.execute.side_effect = execute_side_effect

    with pytest.raises(SourceNotFoundError):
        await service.clear_stuck_jobs(source_id, user_id)


@pytest.mark.asyncio
async def test_clear_stuck_jobs_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = ScrapingAdminService(mock_db)

    mock_db.execute.side_effect = Exception("Database error")

    with pytest.raises(ClearStuckJobsError):
        await service.clear_stuck_jobs(None, user_id)


@pytest.mark.asyncio
async def test_manual_scrape_source_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = str(uuid.uuid4())

    service = ScrapingAdminService(mock_db)

    mock_db.execute.side_effect = Exception("Database error")

    with patch(
        "app.api.modules.v1.scraping.service.tasks.manual_scrape_source.delay"
    ) as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-123"
        mock_delay.return_value = mock_task

        with pytest.raises(ManualScrapeError):
            await service.manual_scrape_source(source_id, user_id)


@pytest.mark.asyncio
async def test_retry_stuck_jobs_error():
    mock_db = AsyncMock()
    user_id = uuid.uuid4()

    service = ScrapingAdminService(mock_db)

    with patch(
        "app.api.modules.v1.scraping.service.tasks.retry_stuck_jobs.delay",
        side_effect=Exception("Task error"),
    ):
        with pytest.raises(StuckJobRetryError):
            await service.retry_stuck_jobs(user_id)
