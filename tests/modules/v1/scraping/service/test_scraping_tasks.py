"""Unit tests for scraping Celery task orchestration."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import app.api.modules.v1.scraping.service.tasks as scraping_tasks_module
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency
from app.api.modules.v1.scraping.service.tasks import dispatch_due_jurisdictions


def test_dispatch_due_jurisdictions_commits_schedule_updates_once():
    """Due jurisdiction dispatch should batch schedule updates after task fanout."""
    jurisdiction_a = MagicMock(
        id=uuid4(),
        scrape_frequency=ScrapeFrequency.DAILY,
        next_scrape_time=None,
        last_scraped_at=None,
    )
    jurisdiction_b = MagicMock(
        id=uuid4(),
        scrape_frequency=ScrapeFrequency.WEEKLY,
        next_scrape_time=None,
        last_scraped_at=None,
    )

    mock_db = MagicMock()
    mock_db.exec.return_value = MagicMock(
        all=MagicMock(return_value=[jurisdiction_a, jurisdiction_b])
    )
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_db
    mock_session.__exit__.return_value = False

    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    mock_service = MagicMock()
    mock_service._calculate_next_scrape_time.return_value = datetime.now(timezone.utc)

    with (
        patch.object(scraping_tasks_module.redis, "Redis", return_value=mock_redis),
        patch.object(scraping_tasks_module, "SyncSessionLocal", return_value=mock_session),
        patch.object(
            scraping_tasks_module,
            "JurisdictionScrapingService",
            return_value=mock_service,
        ),
        patch.object(scraping_tasks_module.Stage1ScrapingService, "_release_lock") as release_lock,
    ):
        result = dispatch_due_jurisdictions.run()

    assert result == "Dispatched 2 jurisdictions."
    assert mock_service.trigger_jurisdiction_scrape.call_count == 2
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_called_once()
    mock_redis.delete.assert_not_called()
    release_lock.assert_called_once()
    _, lock_key, lock_value = release_lock.call_args.args
    assert lock_key == "celery:dispatch_due_jurisdictions_lock"
    assert isinstance(lock_value, str)
