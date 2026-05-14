"""Unit tests for Stage1ScrapingService."""

import hashlib
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.scraping.models.data_revision import (
    DataRevision,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.stage1_scraping_service import Stage1ScrapingService


@pytest.fixture
def test_source_id():
    """Generate a test source ID."""
    return str(uuid4())


@pytest.fixture
def test_job_id():
    """Generate a test job ID."""
    return str(uuid4())


@pytest.fixture
def test_task_request_id():
    """Generate a test task request ID."""
    return "test-task-123"


class TestStage1ScrapingService:
    """Test suite for Stage1ScrapingService."""

    def test_execute_successful_new_content(
        self, test_source_id, test_job_id, test_task_request_id
    ):
        """Test successful scraping with new content."""
        content = "Important legal update from jurisdiction"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            # Setup mocks
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = True
            mock_redis_instance.get.return_value = test_task_request_id.encode()
            mock_redis.return_value = mock_redis_instance

            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_job.jurisdiction_scrape_job_id = None
            mock_source = MagicMock(spec=Source)
            mock_source.id = uuid4()
            mock_source.url = "https://example.com/legal"
            mock_source.organization_id = uuid4()

            mock_result = MagicMock()
            mock_result.first.side_effect = [mock_job, mock_source, None]
            mock_session.exec.return_value = mock_result
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_extract_instance = MagicMock()
            mock_extract_instance.extract_and_save = MagicMock(
                return_value={
                    "full_text": content,
                    "clean_key": f"{test_source_id}/test.md",
                    "title": "Legal Update",
                }
            )
            mock_extract_service.return_value = mock_extract_instance

            # Create service with mocked extractor and db session gets mocked via SyncSessionLocal
            service = Stage1ScrapingService()

            result = service.execute(test_source_id, test_job_id, test_task_request_id)

            assert result["status"] == "completed"
            assert result["reason"] == "new_content_scraped"
            assert result["content_hash"] == content_hash
            assert result["minio_key"] == f"{test_source_id}/test.md"

            mock_redis_instance.set.assert_called_once()

            assert mock_job.status == ScrapeJobStatus.COMPLETED

    def test_execute_duplicate_content_skipped(
        self, test_source_id, test_job_id, test_task_request_id
    ):
        """Test skipping when content is unchanged."""
        content = "Legal update text"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = True
            mock_redis_instance.get.return_value = test_task_request_id.encode()
            mock_redis.return_value = mock_redis_instance

            mock_job = MagicMock(spec=ScrapeJob)
            mock_source = MagicMock(spec=Source)
            mock_source.id = uuid4()
            mock_source.url = "https://example.com/legal"
            mock_source.organization_id = uuid4()  # Required for parallel extractor

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.content_hash = content_hash
            mock_revision.id = uuid4()
            mock_revision.minio_object_key = f"{test_source_id}/test.md"

            # Setup session mock
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            # Mock exec calls: job, source, last_revision (this time with a match)
            mock_result = MagicMock()
            mock_result.first.side_effect = [mock_job, mock_source, mock_revision]
            mock_session.exec.return_value = mock_result
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_extract_instance = MagicMock()
            mock_extract_instance.extract_and_save = MagicMock(
                return_value={"full_text": content, "clean_key": f"{test_source_id}/test.md"}
            )
            mock_extract_service.return_value = mock_extract_instance

            service = Stage1ScrapingService()
            result = service.execute(test_source_id, test_job_id, test_task_request_id)

            assert result["status"] == "completed"
            assert result["reason"] == "content_unchanged"
            assert result["content_hash"] == content_hash
            assert result["revision_id"] != str(mock_revision.id)  # New revision created
            assert result["inherited_from"] == str(mock_revision.id)

            assert mock_job.result is not None
            assert mock_job.result["status"] == "content_unchanged"
            assert mock_job.result["content_hash"] == content_hash
            assert mock_job.result["minio_key"] == f"{test_source_id}/test.md"

    def test_execute_concurrent_scrape_locked(
        self, test_source_id, test_job_id, test_task_request_id
    ):
        """Test handling of concurrent scrape lock."""
        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = False  # Lock not acquired
            mock_redis.return_value = mock_redis_instance

            mock_extract_instance = MagicMock()
            mock_extract_service.return_value = mock_extract_instance

            # Create service with mocked extractor
            with patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService",
                return_value=mock_extract_instance,
            ):
                service = Stage1ScrapingService()
                result = service.execute(test_source_id, test_job_id, test_task_request_id)

            assert result["status"] == "skipped"
            assert result["reason"] == "concurrent_scrape_in_progress"

    def test_execute_job_already_claimed(self, test_source_id, test_job_id, test_task_request_id):
        """Test handling when job is already claimed."""
        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = True
            mock_redis.return_value = mock_redis_instance

            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            mock_session.exec.return_value.first.return_value = None  # Job not found
            mock_session_factory.return_value = mock_session

            mock_extract_instance = MagicMock()
            mock_extract_service.return_value = mock_extract_instance

            # Create service with mocked extractor
            with patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService",
                return_value=mock_extract_instance,
            ):
                service = Stage1ScrapingService()
                result = service.execute(test_source_id, test_job_id, test_task_request_id)

            assert result["status"] == "skipped"
            assert result["reason"] == "job_already_claimed"

    def test_execute_source_not_found(self, test_source_id, test_job_id, test_task_request_id):
        """Test handling when source doesn't exist."""
        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = True
            mock_redis.return_value = mock_redis_instance

            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_session.exec.return_value.first.side_effect = [mock_job, None]  # Source not found
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_extract_instance = MagicMock()
            mock_extract_service.return_value = mock_extract_instance

            # Create service with mocked extractor
            with patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService",
                return_value=mock_extract_instance,
            ):
                service = Stage1ScrapingService()
                result = service.execute(test_source_id, test_job_id, test_task_request_id)

            assert result["status"] == "failed"
            assert result["reason"] == "source_not_found"
            assert mock_job.status == ScrapeJobStatus.FAILED

    def test_execute_extraction_failure(self, test_source_id, test_job_id, test_task_request_id):
        """Test handling of extraction service failure."""
        with (
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.redis.Redis"
            ) as mock_redis,
            patch("app.api.db.database.SyncSessionLocal") as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService"
            ) as mock_extract_service,
        ):
            mock_redis_instance = MagicMock()
            mock_redis_instance.set.return_value = True
            mock_redis.return_value = mock_redis_instance

            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_source = MagicMock(spec=Source)
            mock_source.id = uuid4()
            mock_source.url = "https://example.com/legal"

            mock_session.exec.return_value.first.side_effect = [mock_job, mock_source]
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_extract_instance = MagicMock()
            mock_extract_instance.extract_and_save.side_effect = Exception("Network timeout")
            mock_extract_service.return_value = mock_extract_instance

            # Create service with mocked extractor
            with patch(
                "app.api.modules.v1.scraping.service.stage1_scraping_service.ParallelExtractService",
                return_value=mock_extract_instance,
            ):
                service = Stage1ScrapingService()
                with pytest.raises(ProcessingError):
                    service.execute(test_source_id, test_job_id, test_task_request_id)
            assert mock_job.status == ScrapeJobStatus.FAILED

    def test_get_next_scrape_time(self):
        """Test calculation of next scrape time."""
        from datetime import datetime, timedelta, timezone

        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency
        from app.api.modules.v1.scraping.service.stage1_scraping_service import get_next_scrape_time

        base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Test daily frequency
        next_time = get_next_scrape_time(base_time, ScrapeFrequency.DAILY)
        assert next_time == base_time + timedelta(days=1)

        # Test weekly frequency
        next_time = get_next_scrape_time(base_time, ScrapeFrequency.WEEKLY)
        assert next_time == base_time + timedelta(weeks=1)

        # Test monthly frequency
        next_time = get_next_scrape_time(base_time, ScrapeFrequency.MONTHLY)
        assert next_time == base_time + timedelta(days=30)

        # Test hourly frequency
        next_time = get_next_scrape_time(base_time, ScrapeFrequency.HOURLY)
        assert next_time == base_time + timedelta(hours=1)

    def test_release_lock_uses_atomic_lua_script(self):
        """Redis locks must be released atomically to avoid deleting another worker's lock."""
        mock_redis = MagicMock()

        Stage1ScrapingService._release_lock(mock_redis, "lock:key", "owner-token")

        mock_redis.eval.assert_called_once()
        script, key_count, lock_key, lock_value = mock_redis.eval.call_args.args
        assert 'redis.call("get", KEYS[1]) == ARGV[1]' in script
        assert key_count == 1
        assert lock_key == "lock:key"
        assert lock_value == "owner-token"
        mock_redis.delete.assert_not_called()
