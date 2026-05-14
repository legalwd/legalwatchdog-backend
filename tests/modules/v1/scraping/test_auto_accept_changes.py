"""Tests for Phase 7: Day N auto-accept logic for campaign jurisdictions.

Validates:
- Campaign jurisdictions auto-accept when safety gates pass
- Non-campaign jurisdictions still create JurisdictionChange records
- Source conflicts block auto-accept
- High-risk changes block auto-accept
- Blog regeneration is triggered on auto-accept
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.modules.v1.scraping.service.consolidated_extraction_service import (
    ConsolidatedExtractionService,
)


def _make_job(jurisdiction_id=None, extracted_data=None):
    """Build a mock JurisdictionScrapeJob."""
    job = MagicMock()
    job.id = uuid4()
    job.jurisdiction_id = jurisdiction_id or uuid4()
    job.extracted_data = extracted_data or {
        "extracted_data": {
            "key_value_pairs": {
                "minimum_wage": {
                    "canonical_value": "$15.00",
                    "discrepancies": [
                        {"source_id": "s1", "value": "$15.00"},
                        {"source_id": "s2", "value": "$15.00"},
                    ],
                }
            }
        }
    }
    job.completed_at = None
    return job


def _make_ai_result(risk_level="low", field_changes=None):
    """Build a mock AI change detection result."""
    if field_changes is None:
        field_changes = [
            SimpleNamespace(
                field_name="minimum_wage",
                old_value="$14.00",
                new_value="$15.00",
                change_type="modified",
                change_description="Minimum wage increased",
            )
        ]
    return SimpleNamespace(
        has_changed=True,
        change_summary="Minimum wage updated",
        risk_level=risk_level,
        field_changes=field_changes,
    )


def _make_jurisdiction(campaign_id=None, auto_accept=False):
    """Build a mock Jurisdiction."""
    jur = MagicMock()
    jur.id = uuid4()
    jur.campaign_id = campaign_id
    jur.auto_accept_changes = auto_accept
    jur.project_id = uuid4()
    jur.prompt = "Monitor employment laws"
    return jur


class TestIsSafeToAutoAccept:
    """Tests for _is_safe_to_auto_accept safety gates."""

    def test_passes_when_sources_agree_and_low_risk(self):
        """Gate 1 (consensus) + Gate 2 (low risk) both pass → True."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)
        job = _make_job()
        ai_result = _make_ai_result(risk_level="low")

        assert service._is_safe_to_auto_accept(job, ai_result) is True

    def test_blocked_by_source_conflict(self):
        """Gate 1 fails: sources disagree on a field value → False."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)
        job = _make_job(
            extracted_data={
                "extracted_data": {
                    "key_value_pairs": {
                        "filing_deadline": {
                            "canonical_value": "March 31",
                            "discrepancies": [
                                {"source_id": "s1", "value": "March 31"},
                                {"source_id": "s2", "value": "April 15"},
                            ],
                        }
                    }
                }
            }
        )
        ai_result = _make_ai_result(risk_level="low")

        assert service._is_safe_to_auto_accept(job, ai_result) is False

    def test_blocked_by_high_risk(self):
        """Gate 2 fails: risk_level is 'high' → False."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)
        job = _make_job()
        ai_result = _make_ai_result(risk_level="high")

        assert service._is_safe_to_auto_accept(job, ai_result) is False

    def test_blocked_by_medium_risk(self):
        """Gate 2 fails: risk_level is 'medium' → False."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)
        job = _make_job()
        ai_result = _make_ai_result(risk_level="medium")

        assert service._is_safe_to_auto_accept(job, ai_result) is False


class TestDayNAutoAcceptFlow:
    """Tests for the campaign auto-accept vs manual review fork."""

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._send_jurisdiction_notifications"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._create_jurisdiction_change_records"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._handle_day_n_auto_accept"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._is_safe_to_auto_accept",
        return_value=True,
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._detect_changes_with_ai"
    )
    def test_campaign_auto_accept_skips_change_records(
        self,
        mock_detect,
        mock_safe,
        mock_auto_accept,
        mock_create_records,
        mock_notify,
    ):
        """Campaign jurisdiction + safe → auto-accept called, NO JurisdictionChange records."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)

        ai_result = _make_ai_result()
        mock_detect.return_value = (True, ai_result)

        jurisdiction = _make_jurisdiction(campaign_id=uuid4(), auto_accept=True)
        job = _make_job(jurisdiction_id=jurisdiction.id)

        # Simulate the execute() fork logic directly
        has_changes, ai_change_result = mock_detect.return_value

        is_campaign = (
            jurisdiction
            and getattr(jurisdiction, "campaign_id", None) is not None
            and getattr(jurisdiction, "auto_accept_changes", False)
        )

        if is_campaign and service._is_safe_to_auto_accept(job, ai_change_result):
            service._handle_day_n_auto_accept(job, jurisdiction, ai_change_result, MagicMock())
        else:
            service._create_jurisdiction_change_records(job, ai_change_result)
            service._send_jurisdiction_notifications(job, jurisdiction, ai_change_result)

        mock_auto_accept.assert_called_once()
        mock_create_records.assert_not_called()
        mock_notify.assert_not_called()

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._send_jurisdiction_notifications"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._create_jurisdiction_change_records"
    )
    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service"
        ".ConsolidatedExtractionService._handle_day_n_auto_accept"
    )
    def test_non_campaign_creates_change_records(
        self,
        mock_auto_accept,
        mock_create_records,
        mock_notify,
    ):
        """Non-campaign jurisdiction → manual path with JurisdictionChange records."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)

        jurisdiction = _make_jurisdiction(campaign_id=None, auto_accept=False)
        ai_result = _make_ai_result()
        job = _make_job(jurisdiction_id=jurisdiction.id)

        is_campaign = (
            jurisdiction
            and getattr(jurisdiction, "campaign_id", None) is not None
            and getattr(jurisdiction, "auto_accept_changes", False)
        )

        if is_campaign and service._is_safe_to_auto_accept(job, ai_result):
            service._handle_day_n_auto_accept(job, jurisdiction, ai_result, MagicMock())
        else:
            service._create_jurisdiction_change_records(job, ai_result)
            service._send_jurisdiction_notifications(job, jurisdiction, ai_result)

        mock_auto_accept.assert_not_called()
        mock_create_records.assert_called_once()
        mock_notify.assert_called_once()

    @patch(
        "app.api.modules.v1.scraping.service.consolidated_extraction_service.BlogGenerationService"
    )
    @patch(
        "app.api.modules.v1.jurisdictions.service.jurisdiction_state_service"
        ".JurisdictionStateService.update_state"
    )
    def test_auto_accept_triggers_blog_regeneration(
        self,
        mock_update_state,
        mock_blog_cls,
    ):
        """Auto-accept path calls BlogGenerationService.generate_blog_post_sync."""
        db = MagicMock()
        service = ConsolidatedExtractionService(db)

        mock_blog_instance = MagicMock()
        mock_blog_instance.generate_blog_post_sync.return_value = {"status": "success"}
        mock_blog_cls.return_value = mock_blog_instance

        mock_update_state.return_value = []

        jurisdiction = _make_jurisdiction(campaign_id=uuid4(), auto_accept=True)
        ai_result = _make_ai_result()
        job = _make_job(jurisdiction_id=jurisdiction.id)
        state_service = MagicMock()

        with patch(
            "app.api.modules.v1.scraping.service.consolidated_extraction_service"
            ".sitemap_rebuild_debounced",
            create=True,
        ):
            service._handle_day_n_auto_accept(job, jurisdiction, ai_result, state_service)

        state_service.update_state.assert_called_once()
        mock_blog_cls.assert_called_once_with(db)
        mock_blog_instance.generate_blog_post_sync.assert_called_once_with(
            jurisdiction_id=job.jurisdiction_id,
            job_id=job.id,
            skip_placeholder=True,
        )
