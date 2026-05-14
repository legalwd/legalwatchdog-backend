from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.jurisdictions.models.jurisdiction_state import JurisdictionState
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.service.consolidated_extraction_service import (
    ConsolidatedExtractionService,
)


@pytest.fixture
def mock_db_session():
    """Mock synchronous DB session."""
    session = MagicMock()
    return session


@pytest.fixture
def service(mock_db_session):
    return ConsolidatedExtractionService(mock_db_session)


@pytest.fixture
def mock_job():
    job = JurisdictionScrapeJob(
        id=uuid4(),
        jurisdiction_id=uuid4(),
        status=JurisdictionScrapeJobStatus.ANALYZING,
        created_at=datetime.now(timezone.utc),
    )
    return job


@pytest.fixture
def sample_analysis_result():
    return {
        "extracted_data": {
            "key_value_pairs": {
                "field1": {"value": "value1", "sources": ["url1"]},
                "field2": "value2",
            }
        },
        "summary": "Analysis complete",
    }


class TestDayOneAutoAccept:
    """Test suite for Day 1 Auto-Accept logic in ConsolidatedExtractionService."""

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.JurisdictionStateService"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._detect_changes_with_ai"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._filter_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._consolidate_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._gather_content"
    )
    def test_day_one_auto_accept_success(
        self,
        mock_gather,
        mock_consolidate,
        mock_filter,
        mock_detect,
        MockStateService,
        service,
        mock_db_session,
        mock_job,
        sample_analysis_result,
    ):
        """Verify that Day 1 (empty ledger) triggers auto-accept and skips standard detection."""
        mock_db_session.get.side_effect = lambda model, id: (
            mock_job if model == JurisdictionScrapeJob else MagicMock()
        )
        mock_gather.return_value = []
        mock_filter.return_value = []
        mock_consolidate.return_value = "consolidated text"

        service.llm_service = MagicMock()
        service.llm_service.run_consolidated_analysis.return_value = (sample_analysis_result, None)
        service.llm_service.check_source_relevance.return_value = True

        mock_state_instance = MockStateService.return_value
        mock_state_instance.get_jurisdiction_state.return_value = {}  # Empty -> Day 1
        mock_state_instance.initialize_state.return_value = [
            JurisdictionState(),
            JurisdictionState(),
        ]

        result = service.execute(mock_job.id)

        assert result["auto_accepted_day_1"] is True
        assert result["changes_detected"] is False

        mock_state_instance.initialize_state.assert_called_once_with(
            jurisdiction_id=mock_job.jurisdiction_id,
            data=sample_analysis_result["extracted_data"]["key_value_pairs"],
            originating_job_id=mock_job.id,
            user_id=None,
        )

        mock_detect.assert_not_called()

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.JurisdictionStateService"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._detect_changes_with_ai"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._filter_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._consolidate_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._gather_content"
    )
    def test_day_one_logic_skipped_if_ledger_exists(
        self,
        mock_gather,
        mock_consolidate,
        mock_filter,
        mock_detect,
        MockStateService,
        service,
        mock_db_session,
        mock_job,
        sample_analysis_result,
    ):
        """Verify existing ledger data prevents auto-accept and runs standard change detection."""

        mock_db_session.get.side_effect = lambda model, id: (
            mock_job if model == JurisdictionScrapeJob else MagicMock()
        )
        mock_gather.return_value = []
        mock_filter.return_value = []
        service.llm_service = MagicMock()
        service.llm_service.run_consolidated_analysis.return_value = (sample_analysis_result, None)

        mock_state_instance = MockStateService.return_value
        mock_state_instance.get_jurisdiction_state.return_value = {"some_key": JurisdictionState()}

        mock_detect.return_value = (
            True,
            MagicMock(
                has_changed=True,
                change_summary="Changes detected",
                risk_level="low",
                field_changes=[],
            ),
        )

        service.execute(mock_job.id)

        mock_state_instance.initialize_state.assert_not_called()

        mock_detect.assert_called_once()

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.JurisdictionStateService"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._detect_changes_with_ai"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._filter_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._consolidate_content"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.ConsolidatedExtractionService._gather_content"
    )
    def test_fallback_on_auto_accept_failure(
        self,
        mock_gather,
        mock_consolidate,
        mock_filter,
        mock_detect,
        MockStateService,
        service,
        mock_db_session,
        mock_job,
        sample_analysis_result,
    ):
        """Verify that if auto-accept raises an exception, we fall back to standard detection."""

        mock_db_session.get.side_effect = lambda model, id: (
            mock_job if model == JurisdictionScrapeJob else MagicMock()
        )
        mock_gather.return_value = []
        mock_filter.return_value = []
        service.llm_service = MagicMock()
        service.llm_service.run_consolidated_analysis.return_value = (sample_analysis_result, None)

        mock_state_instance = MockStateService.return_value
        mock_state_instance.get_jurisdiction_state.return_value = {}

        mock_state_instance.initialize_state.side_effect = Exception("DB Connection Lost")

        mock_detect.return_value = (False, None)

        result = service.execute(mock_job.id)

        mock_state_instance.initialize_state.assert_called_once()

        mock_detect.assert_called_once()

        assert result.get("auto_accepted_day_1") is None
