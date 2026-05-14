"""Unit tests for Stage3PersistenceService."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.api.modules.v1.scraping.service.stage3_persistence_service import Stage3PersistenceService


@pytest.fixture
def test_source_id():
    """Generate a test source ID."""
    return str(uuid4())


@pytest.fixture
def test_job_id():
    """Generate a test job ID."""
    return str(uuid4())


@pytest.fixture
def test_revision_id():
    """Generate a test revision ID."""
    return str(uuid4())


class TestStage3PersistenceService:
    """Test suite for Stage3PersistenceService."""

    def test_execute_successful_persistence(self, test_source_id, test_job_id, test_revision_id):
        """Test successful job completion and source updates."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.id = uuid4()
            mock_revision.content_hash = "abc123"
            mock_revision.ai_confidence_score = 0.85

            mock_source = MagicMock(spec=Source)
            mock_source.scrape_frequency = ScrapeFrequency.DAILY

            mock_session.exec.return_value.first.side_effect = [
                mock_job,
                mock_revision,
                mock_source,
            ]
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            service = Stage3PersistenceService()
            result = service.execute(test_source_id, test_job_id, test_revision_id)

            assert result["status"] == "completed"
            assert result["revision_id"] == str(test_revision_id)
            assert result["content_hash"] == mock_revision.content_hash

            # Verify job completion
            assert mock_job.status == ScrapeJobStatus.COMPLETED
            assert mock_job.completed_at is not None
            assert mock_job.data_revision_id == mock_revision.id
            assert mock_job.result["status"] == "success"
            assert mock_job.result["revision_id"] == str(mock_revision.id)
            assert mock_job.result["content_hash"] == mock_revision.content_hash
            assert mock_job.result["confidence_score"] == mock_revision.ai_confidence_score

            # Verify source updates
            assert mock_source.last_scraped_at is not None
            assert mock_source.next_scrape_time is not None

    def test_execute_job_not_found(self, test_source_id, test_job_id, test_revision_id):
        """Test handling when job doesn't exist."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            mock_session.exec.return_value.first.return_value = None  # Job not found
            mock_session_factory.return_value = mock_session

            service = Stage3PersistenceService()
            result = service.execute(test_source_id, test_job_id, test_revision_id)

            assert result["status"] == "failed"
            assert result["reason"] == "job_not_found"

    def test_execute_revision_not_found(self, test_source_id, test_job_id, test_revision_id):
        """Test handling when revision doesn't exist."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_session.exec.return_value.first.side_effect = [
                mock_job,
                None,
            ]  # Revision not found
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            service = Stage3PersistenceService()
            result = service.execute(test_source_id, test_job_id, test_revision_id)

            assert result["status"] == "failed"
            assert result["reason"] == "revision_not_found"

            # Verify job was marked as failed
            assert mock_job.status == ScrapeJobStatus.FAILED
            assert mock_job.completed_at is not None
            assert mock_job.result["error"] == "DataRevision not found"

    def test_execute_source_not_found(self, test_source_id, test_job_id, test_revision_id):
        """Test handling when source doesn't exist."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_revision = MagicMock(spec=DataRevision)
            mock_session.exec.return_value.first.side_effect = [
                mock_job,
                mock_revision,
                None,
            ]  # Source not found
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            service = Stage3PersistenceService()
            result = service.execute(test_source_id, test_job_id, test_revision_id)

            assert result["status"] == "failed"
            assert result["reason"] == "source_not_found"

            # Verify job was marked as failed
            assert mock_job.status == ScrapeJobStatus.FAILED
            assert mock_job.completed_at is not None
            assert mock_job.result["error"] == "Source not found"

    def test_execute_database_error_handling(self, test_source_id, test_job_id, test_revision_id):
        """Test handling of database errors during persistence."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_revision = MagicMock(spec=DataRevision)
            mock_source = MagicMock(spec=Source)

            mock_session.exec.return_value.first.side_effect = [
                mock_job,
                mock_revision,
                mock_source,
            ]
            mock_session.commit.side_effect = Exception("Database connection lost")
            mock_session_factory.return_value = mock_session

            service = Stage3PersistenceService()

            with pytest.raises(Exception, match="Database connection lost"):
                service.execute(test_source_id, test_job_id, test_revision_id)

    def test_execute_error_recovery_job_update(self, test_source_id, test_job_id, test_revision_id):
        """Test that job status is updated even when main persistence fails."""
        with patch(
            "app.api.modules.v1.scraping.service.stage3_persistence_service.SyncSessionLocal"
        ) as mock_session_factory:
            # First session for main logic
            mock_session1 = MagicMock()
            mock_session1.__enter__ = MagicMock(return_value=mock_session1)
            mock_session1.__exit__ = MagicMock(return_value=None)

            mock_job = MagicMock(spec=ScrapeJob)
            mock_revision = MagicMock(spec=DataRevision)
            mock_source = MagicMock(spec=Source)

            mock_session1.exec.return_value.first.side_effect = [
                mock_job,
                mock_revision,
                mock_source,
            ]
            mock_session1.commit.side_effect = Exception("Database error")

            # Second session for error handling
            mock_session2 = MagicMock()
            mock_session2.__enter__ = MagicMock(return_value=mock_session2)
            mock_session2.__exit__ = MagicMock(return_value=None)

            mock_job2 = MagicMock(spec=ScrapeJob)
            mock_session2.exec.return_value.first.return_value = mock_job2
            mock_session2.commit = MagicMock()

            # Return different sessions
            mock_session_factory.side_effect = [mock_session1, mock_session2]

            service = Stage3PersistenceService()

            with pytest.raises(Exception, match="Database error"):
                service.execute(test_source_id, test_job_id, test_revision_id)

            # Verify job was failed
            assert mock_job.status == ScrapeJobStatus.FAILED
            assert mock_job.completed_at is not None
            assert "unexpected error" in mock_job.result["error"].lower()

    def test_get_next_scrape_time(self):
        """Test calculation of next scrape time."""
        from app.api.modules.v1.scraping.service.stage3_persistence_service import (
            get_next_scrape_time,
        )

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
