"""Unit tests for jurisdiction scraping orchestration edge cases."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.jurisdiction_scraping_service import (
    JurisdictionScrapingService,
)


def test_dispatch_sources_marks_parent_failed_when_all_dispatches_fail():
    """If every Celery dispatch fails, the parent jurisdiction job must fail immediately."""
    jurisdiction_id = uuid4()
    source = Source(
        jurisdiction_id=jurisdiction_id,
        name="Official Gazette",
        url="https://example.com/gazette",
    )
    job = JurisdictionScrapeJob(
        jurisdiction_id=jurisdiction_id,
        status=JurisdictionScrapeJobStatus.SCRAPING,
        total_sources=1,
    )

    mock_db = MagicMock()
    mock_db.exec.return_value = MagicMock(first=MagicMock(return_value=None))
    service = JurisdictionScrapingService(mock_db)

    with patch(
        "app.api.modules.v1.scraping.service.jurisdiction_scraping_service.celery_app.send_task",
        side_effect=RuntimeError("broker unavailable"),
    ):
        dispatched = service._dispatch_sources(job, [source])

    assert dispatched == 0
    assert job.status == JurisdictionScrapeJobStatus.FAILED
    assert job.error_message == "All source dispatches failed"
    assert mock_db.commit.call_count == 3


def test_dispatch_sources_commits_jobs_once_before_celery_dispatch():
    """Scrape jobs should be durable before Celery workers can load them."""
    jurisdiction_id = uuid4()
    sources = [
        Source(
            jurisdiction_id=jurisdiction_id,
            name="Official Gazette",
            url="https://example.com/gazette",
        ),
        Source(
            jurisdiction_id=jurisdiction_id,
            name="Regulator",
            url="https://example.com/regulator",
        ),
    ]
    job = JurisdictionScrapeJob(
        jurisdiction_id=jurisdiction_id,
        status=JurisdictionScrapeJobStatus.SCRAPING,
        total_sources=2,
    )

    mock_db = MagicMock()
    mock_db.exec.return_value = MagicMock(first=MagicMock(return_value=None))
    service = JurisdictionScrapingService(mock_db)

    with patch(
        "app.api.modules.v1.scraping.service.jurisdiction_scraping_service.celery_app.send_task"
    ) as mock_send_task:
        dispatched = service._dispatch_sources(job, sources)

    assert dispatched == 2
    assert mock_db.commit.call_count == 1
    assert mock_send_task.call_count == 2
