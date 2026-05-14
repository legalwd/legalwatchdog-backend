"""Unit tests for DiffAndNotificationService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.diff_and_notification_service import (
    DiffAndNotificationService,
)


@pytest.fixture
def test_source_id():
    """Generate a test source ID."""
    return str(uuid4())


@pytest.fixture
def test_revision_id():
    """Generate a test revision ID."""
    return str(uuid4())


class TestDiffAndNotificationService:
    """Test suite for DiffAndNotificationService."""

    def test_execute_change_detected_and_notified(self, test_source_id, test_revision_id):
        """Test successful change detection and notification."""
        # Mock change result object
        change_result = MagicMock()
        change_result.has_changed = True
        change_result.change_summary = "Effective date changed"
        change_result.risk_level = "medium"

        with (
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.DiffAIService"
            ) as mock_diff_service,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.send_revision_notifications_task"
            ) as mock_notification_task,
        ):
            # Setup mocks
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.id = uuid4()
            mock_revision.is_baseline = False
            mock_revision.extracted_data = {"extracted_data": {"effective_date": "2024-02-01"}}
            mock_revision.ai_confidence_score = 0.9

            mock_source = MagicMock(spec=Source)
            mock_source.id = uuid4()
            mock_source.jurisdiction = MagicMock()
            mock_source.jurisdiction.project = MagicMock()
            mock_source.jurisdiction.project.master_prompt = "Monitor legal changes"
            mock_source.jurisdiction.name = "Test Jurisdiction"

            mock_previous_revision = MagicMock(spec=DataRevision)
            mock_previous_revision.extracted_data = {
                "extracted_data": {"effective_date": "2024-01-01"}
            }

            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                mock_source,
                mock_previous_revision,
                mock_previous_revision,
            ]

            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            mock_session.query.return_value = mock_query

            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session.refresh = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_diff_instance = MagicMock()
            mock_diff_instance.detect_semantic_change = AsyncMock(return_value=change_result)
            mock_diff_service.return_value = mock_diff_instance

            service = DiffAndNotificationService()
            result = service.execute(test_source_id, test_revision_id)

            # Verify change detection was called
            mock_diff_instance.detect_semantic_change.assert_called_once()

            # Verify ChangeDiff was created
            assert mock_session.add.call_count == 1

            # Verify notifications were triggered
            mock_notification_task.delay.assert_called_once()

            # Verify result
            assert result["status"] == "completed"
            assert result["change_detected"] is True
            assert "change_summary" in result

    def test_execute_no_changes_detected(self, test_source_id, test_revision_id):
        """Test when no changes are detected."""
        # Mock change result object with no changes
        change_result = MagicMock()
        change_result.has_changed = False
        change_result.change_summary = "No changes detected"
        change_result.risk_level = "low"

        with (
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.DiffAIService"
            ) as mock_diff_service,
        ):
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.is_baseline = False
            mock_revision.extracted_data = {"extracted_data": {"effective_date": "2024-01-01"}}

            mock_source = MagicMock(spec=Source)
            mock_source.jurisdiction = MagicMock()
            mock_source.jurisdiction.project = MagicMock()
            mock_source.jurisdiction.project.master_prompt = "Monitor legal changes"
            mock_source.jurisdiction.name = "Test Jurisdiction"

            mock_previous_revision = MagicMock(spec=DataRevision)
            mock_previous_revision.extracted_data = {
                "extracted_data": {"effective_date": "2024-01-01"}
            }

            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                mock_source,
                mock_previous_revision,
            ]
            mock_session_factory.return_value = mock_session

            mock_diff_instance = MagicMock()
            mock_diff_instance.detect_semantic_change = AsyncMock(return_value=change_result)
            mock_diff_service.return_value = mock_diff_instance

            service = DiffAndNotificationService()
            result = service.execute(test_source_id, test_revision_id)

            # Verify change detection was called
            mock_diff_instance.detect_semantic_change.assert_called_once()

            # Verify no ChangeDiff was created
            mock_session.add.assert_not_called()

            # Verify result indicates no changes
            assert result["status"] == "completed"
            assert result["change_detected"] is False

    def test_execute_baseline_revision(self, test_source_id, test_revision_id):
        """Test handling of baseline revisions (first scrape)."""
        with patch(
            "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.is_baseline = True

            mock_source = MagicMock(spec=Source)
            mock_source.project = MagicMock()
            mock_source.jurisdiction = MagicMock()

            mock_session.exec.return_value.first.side_effect = [mock_revision, mock_source, None]
            mock_session_factory.return_value = mock_session

            service = DiffAndNotificationService()
            result = service.execute(test_source_id, test_revision_id)

            # For baseline revisions, no change detection should occur
            assert result["status"] == "completed"
            assert result["change_detected"] is False
            assert result["reason"] == "baseline_scrape"

    def test_execute_revision_not_found(self, test_source_id, test_revision_id):
        """Test handling when revision doesn't exist."""
        with patch(
            "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)
            mock_session.exec.return_value.first.return_value = None  # Revision not found
            mock_session_factory.return_value = mock_session

            service = DiffAndNotificationService()

            result = service.execute(test_source_id, test_revision_id)

            assert result["status"] == "failed"
            assert result["reason"] == "revision_not_found"

    def test_execute_source_not_found(self, test_source_id, test_revision_id):
        """Test handling when source doesn't exist."""
        with patch(
            "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
        ) as mock_session_factory:
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                None,
            ]  # Source not found
            mock_session_factory.return_value = mock_session

            service = DiffAndNotificationService()

            result = service.execute(test_source_id, test_revision_id)

            assert result["status"] == "failed"
            assert result["reason"] == "source_not_found"

    def test_execute_auto_ticket_disabled(self, test_source_id, test_revision_id):
        """Test when auto-ticket creation is disabled."""
        # Mock change result object
        change_result = MagicMock()
        change_result.has_changed = True
        change_result.change_summary = "Effective date changed"
        change_result.risk_level = "medium"

        with (
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.DiffAIService"
            ) as mock_diff_service,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.send_revision_notifications_task"
            ) as mock_notification_task,
        ):
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.is_baseline = False
            mock_revision.extracted_data = {"extracted_data": {"effective_date": "2024-02-01"}}
            mock_revision.ai_confidence_score = 0.9

            mock_source = MagicMock(spec=Source)
            mock_source.auto_create_tickets = False
            mock_source.jurisdiction = MagicMock()
            mock_source.jurisdiction.project = MagicMock()
            mock_source.jurisdiction.project.master_prompt = "Monitor legal changes"
            mock_source.jurisdiction.name = "Test Jurisdiction"

            mock_previous_revision = MagicMock(spec=DataRevision)
            mock_previous_revision.extracted_data = {
                "extracted_data": {"effective_date": "2024-01-01"}
            }

            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                mock_source,
                mock_previous_revision,
            ]

            # Mock the query for checking existing ChangeDiff (should return None for new diff)
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None
            mock_session.query.return_value = mock_query

            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_diff_instance = MagicMock()
            mock_diff_instance.detect_semantic_change = AsyncMock(return_value=change_result)
            mock_diff_service.return_value = mock_diff_instance

            service = DiffAndNotificationService()
            service.execute(test_source_id, test_revision_id)

            mock_notification_task.delay.assert_called_once()

            assert mock_session.add.call_count == 1

    def test_execute_no_project_auto_ticket_setting(self, test_source_id, test_revision_id):
        """Test when project has no auto_create_tickets setting."""
        change_result = MagicMock()
        change_result.has_changed = True
        change_result.change_summary = "Effective date changed"
        change_result.risk_level = "medium"

        with (
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.DiffAIService"
            ) as mock_diff_service,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.send_revision_notifications_task"
            ) as mock_notification_task,
        ):
            # Setup mocks
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.is_baseline = False
            mock_revision.extracted_data = {"extracted_data": {"effective_date": "2024-02-01"}}
            mock_revision.ai_confidence_score = 0.9

            mock_source = MagicMock(spec=Source)
            mock_source.jurisdiction = MagicMock()
            mock_source.jurisdiction.project = MagicMock()
            mock_source.jurisdiction.project.master_prompt = "Monitor legal changes"
            mock_source.jurisdiction.name = "Test Jurisdiction"

            mock_previous_revision = MagicMock(spec=DataRevision)
            mock_previous_revision.extracted_data = {
                "extracted_data": {"effective_date": "2024-01-01"}
            }

            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                mock_source,
                mock_previous_revision,
            ]
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()
            mock_session_factory.return_value = mock_session

            mock_diff_instance = MagicMock()
            mock_diff_instance.detect_semantic_change = AsyncMock(return_value=change_result)
            mock_diff_service.return_value = mock_diff_instance

            service = DiffAndNotificationService()
            result = service.execute(test_source_id, test_revision_id)

            # Verify notifications were triggered
            mock_notification_task.delay.assert_called_once()

            # Verify result
            assert result["status"] == "completed"
            assert result["change_detected"] is True

    def test_execute_diff_service_failure(self, test_source_id, test_revision_id):
        """Test handling of diff service failures."""
        with (
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.SyncSessionLocal"
            ) as mock_session_factory,
            patch(
                "app.api.modules.v1.scraping.service.diff_and_notification_service.DiffAIService"
            ) as mock_diff_service,
        ):
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=None)

            mock_revision = MagicMock(spec=DataRevision)
            mock_revision.is_baseline = False
            mock_revision.extracted_data = {"extracted_data": {"effective_date": "2024-01-01"}}

            mock_source = MagicMock(spec=Source)
            mock_source.jurisdiction = MagicMock()
            mock_source.jurisdiction.project = MagicMock()
            mock_source.jurisdiction.project.master_prompt = "Monitor legal changes"
            mock_source.jurisdiction.name = "Test Jurisdiction"

            mock_previous_revision = MagicMock(spec=DataRevision)
            mock_previous_revision.extracted_data = {
                "extracted_data": {"effective_date": "2024-01-01"}
            }

            mock_session.exec.return_value.first.side_effect = [
                mock_revision,
                mock_source,
                mock_previous_revision,
            ]
            mock_session_factory.return_value = mock_session

            mock_diff_instance = MagicMock()
            mock_diff_instance.detect_semantic_change = AsyncMock(
                side_effect=Exception("Diff service error")
            )
            mock_diff_service.return_value = mock_diff_instance

            service = DiffAndNotificationService()

            # Should raise exception (handled by Celery retry logic)
            with pytest.raises(Exception, match="Diff service error"):
                service.execute(test_source_id, test_revision_id)
