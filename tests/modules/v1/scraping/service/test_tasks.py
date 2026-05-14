from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.tasks import (
    dispatch_due_sources,
    get_next_scrape_time,
    monitor_stalled_jobs,
)


def mock_exec_side_effect(session):
    """Translates SQLModel's db.exec() into SQLAlchemy's db.execute().scalars()."""

    def side_effect(statement):
        return session.execute(statement).scalars()

    return side_effect


@pytest.fixture
def sync_session(pg_sync_session):
    return pg_sync_session


@pytest.mark.parametrize(
    "frequency, expected_delta",
    [
        ("DAILY", timedelta(days=1)),
        ("WEEKLY", timedelta(weeks=1)),
        ("MONTHLY", timedelta(days=30)),
        ("HOURLY", timedelta(hours=1)),
        ("UNKNOWN", timedelta(days=1)),
    ],
)
def test_get_next_scrape_time(frequency, expected_delta):
    now = datetime.now(timezone.utc)
    next_time = get_next_scrape_time(now, frequency)
    assert abs((next_time - now) - expected_delta) < timedelta(seconds=1)


# NOTE: test_scrape_source_success has been disabled because the scrape_source
# function was refactored into a 4-stage pipeline (scrape_source_stage1, etc.)
# This test should be re-written to test the new pipeline architecture.
# def test_scrape_source_success(sync_session: Session):
#     """Tests the successful scraping of a source."""
#
#     organization = Organization(
#         name="Test Organization",
#     )
#     sync_session.add(organization)
#     sync_session.commit()
#     sync_session.refresh(organization)
#
#     project = Project(
#         org_id=organization.id,
#         title="Test Project",
#         description="Test project description",
#     )
#     sync_session.add(project)
#     sync_session.commit()
#     sync_session.refresh(project)
#
#     jurisdiction = Jurisdiction(
#         project_id=project.id,
#         name="Test Jurisdiction",
#         description="Test description",
#     )
#     sync_session.add(jurisdiction)
#     sync_session.commit()
#     sync_session.refresh(jurisdiction)
#
#     source = Source(
#         jurisdiction_id=jurisdiction.id,
#         name="Test Source",
#         url="http://example.com",
#         scrape_frequency="HOURLY",
#         next_scrape_time=datetime.now(timezone.utc) - timedelta(hours=1),
#     )
#     sync_session.add(source)
#     sync_session.commit()
#     sync_session.refresh(source)
#
#     with (
#         patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls,
#         patch(
#             "app.api.modules.v1.scraping.service.scraper_service.ScraperService"
#         ) as mock_scraper_cls,
#     ):
#         mock_db = MagicMock()
#
#         async def mock_execute(stmt):
#             result = MagicMock()
#             result.scalars.return_value.first.return_value = (
#                 sync_session.execute(stmt).scalars().first()
#             )
#             return result
#
#         mock_db.execute = AsyncMock(side_effect=mock_execute)
#         mock_db.add = MagicMock(side_effect=sync_session.add)
#         mock_db.commit = AsyncMock(side_effect=lambda: sync_session.commit())
#         mock_db.refresh = AsyncMock(side_effect=lambda obj: sync_session.refresh(obj))
#
#         # Context manager for AsyncSessionLocal()
#         mock_session_ctx = AsyncMock()
#         mock_session_ctx.__aenter__.return_value = mock_db
#         mock_session_ctx.__aexit__.return_value = None
#         mock_session_cls.return_value = mock_session_ctx
#
#         mock_scraper_instance = MagicMock()
#         mock_scraper_instance.execute_scrape_job = AsyncMock(
#             return_value={
#                 "status": "success",
#                 "change_detected": False,
#                 "change_summary": "No material changes detected",
#             }
#         )
#         mock_scraper_cls.return_value = mock_scraper_instance
#
#         mock_context = MagicMock()
#         mock_context.retries = 0
#         scrape_source.push_request(mock_context)
#
#         try:
#             result = scrape_source.run(str(source.id))
#         finally:
#             scrape_source.pop_request()
#
#     sync_session.refresh(source)
#
#     next_scrape_time = source.next_scrape_time
#     if next_scrape_time.tzinfo is None:
#         next_scrape_time = next_scrape_time.replace(tzinfo=timezone.utc)
#
#     assert "scraped successfully" in result
#     assert "no changes" in result
#     assert next_scrape_time > datetime.now(timezone.utc)


# NOTE: test_scrape_source_not_found has been disabled because the scrape_source
# function was refactored into a 4-stage pipeline (scrape_source_stage1, etc.)
# This test should be re-written to test the new pipeline architecture.
# def test_scrape_source_not_found(sync_session: Session):
#     """Tests the case where the source ID does not exist."""
#     non_existent_id = uuid.uuid4()
#
#     with patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls:
#         mock_db = MagicMock()
#         mock_session_cls.return_value.__aenter__.return_value = mock_db
#         mock_db.execute = AsyncMock()
#
#         async def mock_execute(stmt):
#             result = MagicMock()
#             result.scalars.return_value.first.return_value = (
#                 sync_session.execute(stmt).scalars().first()
#             )
#             return result
#
#         mock_db.execute.side_effect = mock_execute
#
#         result = scrape_source.run(str(non_existent_id))
#
#     assert "not found" in result


# NOTE: test_scrape_source_dlq_on_max_retries has been disabled because the scrape_source
# function and CELERY_DLQ_KEY were removed during refactoring to a 4-stage pipeline.
# This test should be re-written to test the new pipeline architecture and error handling.
# def test_scrape_source_dlq_on_max_retries(sync_session: Session):
#     """Tests that a failed scrape_source task is moved to DLQ after max retries."""
#
#     organization = Organization(
#         name="Test Organization",
#     )
#     sync_session.add(organization)
#     sync_session.commit()
#     sync_session.refresh(organization)
#
#     project = Project(
#         org_id=organization.id,
#         title="Test Project",
#         description="Test project description",
#     )
#     sync_session.add(project)
#     sync_session.commit()
#     sync_session.refresh(project)
#
#     jurisdiction = Jurisdiction(
#         project_id=project.id,
#         name="Test Jurisdiction",
#         description="Test description",
#     )
#     sync_session.add(jurisdiction)
#     sync_session.commit()
#     sync_session.refresh(jurisdiction)
#
#     source = Source(
#         jurisdiction_id=jurisdiction.id,
#         name="DLQ Test Source",
#         url="http://dlq.com",
#         scrape_frequency="HOURLY",
#         next_scrape_time=datetime.now(timezone.utc) - timedelta(hours=1),
#     )
#     sync_session.add(source)
#     sync_session.commit()
#     sync_session.refresh(source)
#
#     with (
#         patch("app.api.modules.v1.scraping.service.tasks.AsyncSessionLocal") as mock_session_cls,
#         patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
#         patch(
#             "app.api.modules.v1.scraping.service.scraper_service.ScraperService"
#         ) as mock_scraper_cls,
#     ):
#         mock_db = MagicMock()
#         mock_session_cls.return_value.__aenter__.return_value = mock_db
#         mock_db.execute = AsyncMock()
#         mock_db.add = MagicMock(side_effect=sync_session.add)
#         mock_db.commit = AsyncMock(side_effect=lambda: sync_session.commit())
#         mock_db.refresh = AsyncMock(side_effect=lambda obj: sync_session.refresh(obj))
#
#         async def mock_execute(stmt):
#             result = MagicMock()
#             result.scalars.return_value.first.return_value = (
#                 sync_session.execute(stmt).scalars().first()
#             )
#             return result
#
#         mock_db.execute.side_effect = mock_execute
#
#         # Mock ScraperService to raise an exception (simulating scraping failure)
#         mock_scraper_instance = MagicMock()
#         mock_scraper_instance.execute_scrape_job = AsyncMock(
#             side_effect=Exception("Simulated scraping failure")
#         )
#         mock_scraper_cls.return_value = mock_scraper_instance
#
#         mock_redis_client = MagicMock()
#         mock_redis_cls.return_value = mock_redis_client
#
#         for i in range(settings.SCRAPE_MAX_RETRIES):
#             scrape_source.push_request(id="test_task_id", args=[str(source.id)], retries=i)
#             with pytest.raises(Exception):
#                 scrape_source.run(str(source.id))
#             scrape_source.pop_request()
#
#         scrape_source.push_request(
#             id="test_task_id", args=[str(source.id)], retries=settings.SCRAPE_MAX_RETRIES
#         )
#
#         result = scrape_source.run(str(source.id))
#         scrape_source.pop_request()
#
#         assert "moved to DLQ" in result
#         mock_redis_client.lpush.assert_called_once()
#
#         called_args, _ = mock_redis_client.lpush.call_args
#         assert called_args[0] == CELERY_DLQ_KEY
#         dlq_entry = json.loads(called_args[1])
#         assert dlq_entry["task_id"] == "test_task_id"


def test_dispatch_due_sources_acquires_lock_and_dispatches(
    sync_session: Session, mock_redis: MagicMock
):
    """Tests that the dispatcher acquires a lock and dispatches tasks."""

    organization1 = Organization(
        name="Test Organization 1",
    )
    organization2 = Organization(
        name="Test Organization 2",
    )
    sync_session.add_all([organization1, organization2])
    sync_session.commit()
    sync_session.refresh(organization1)
    sync_session.refresh(organization2)

    project1 = Project(
        org_id=organization1.id,
        title="Test Project 1",
        description="Test project description 1",
    )
    project2 = Project(
        org_id=organization2.id,
        title="Test Project 2",
        description="Test project description 2",
    )
    sync_session.add_all([project1, project2])
    sync_session.commit()
    sync_session.refresh(project1)
    sync_session.refresh(project2)

    jurisdiction1 = Jurisdiction(
        project_id=project1.id,
        name="Test Jurisdiction 1",
        description="Test description 1",
    )
    jurisdiction2 = Jurisdiction(
        project_id=project2.id,
        name="Test Jurisdiction 2",
        description="Test description 2",
    )
    sync_session.add_all([jurisdiction1, jurisdiction2])
    sync_session.commit()
    sync_session.refresh(jurisdiction1)
    sync_session.refresh(jurisdiction2)

    now = datetime.now(timezone.utc)
    source1 = Source(
        jurisdiction_id=jurisdiction1.id,
        name="Due Source 1",
        url="http://due1.com",
        next_scrape_time=now - timedelta(hours=1),
    )
    source2 = Source(
        jurisdiction_id=jurisdiction2.id,
        name="Due Source 2",
        url="http://due2.com",
        next_scrape_time=now - timedelta(minutes=30),
    )
    sync_session.add_all([source1, source2])
    sync_session.commit()

    with (
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch("app.api.modules.v1.scraping.service.tasks.SyncSessionLocal") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_cls.return_value = mock_redis_instance

        # Mock SyncSessionLocal as a synchronous context manager
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_session_cls.return_value.__exit__.return_value = None

        mock_db.execute = MagicMock()
        mock_db.exec = MagicMock()
        mock_db.add = MagicMock(side_effect=sync_session.add)
        mock_db.commit = MagicMock(side_effect=lambda: sync_session.commit())

        def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = (
                sync_session.execute(stmt).scalars().all()
            )
            return result

        mock_db.execute.side_effect = mock_execute

        mock_app.send_task = MagicMock()

        result = dispatch_due_sources.run()

    assert "Dispatched 2 sources" in result
    assert mock_redis_instance.set.call_count == 1
    assert mock_app.send_task.call_count == 2


def test_dispatch_due_sources_lock_already_held():
    """Tests that the dispatcher skips if the lock is already held."""
    with patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls:
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = False

        mock_redis_cls.return_value = mock_redis_instance

        result = dispatch_due_sources.run()

    assert "Skipped" in result
    assert mock_redis_instance.set.call_count == 1


def test_dispatch_due_sources_no_due_sources(sync_session: Session):
    """Tests that the dispatcher does nothing if no sources are due."""

    organization = Organization(
        name="Test Organization",
    )
    sync_session.add(organization)
    sync_session.commit()
    sync_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Test Project",
        description="Test project description",
    )
    sync_session.add(project)
    sync_session.commit()
    sync_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test description",
    )
    sync_session.add(jurisdiction)
    sync_session.commit()
    sync_session.refresh(jurisdiction)

    source = Source(
        jurisdiction_id=jurisdiction.id,
        name="Future Source",
        url="http://future.com",
        next_scrape_time=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    sync_session.add(source)
    sync_session.commit()

    with (
        patch("app.api.modules.v1.scraping.service.tasks.redis.Redis") as mock_redis_cls,
        patch("app.api.modules.v1.scraping.service.tasks.SyncSessionLocal") as mock_session_cls,
        patch.object(dispatch_due_sources, "app") as mock_app,
    ):
        mock_redis_instance = MagicMock()
        mock_redis_instance.set.return_value = True
        mock_redis_cls.return_value = mock_redis_instance

        # Mock SyncSessionLocal as a synchronous context manager
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db
        mock_session_cls.return_value.__exit__.return_value = None

        mock_db.execute = MagicMock()

        def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = (
                sync_session.execute(stmt).scalars().all()
            )
            return result

        mock_db.execute.side_effect = mock_execute

        mock_app.send_task = MagicMock()

        result = dispatch_due_sources.run()

    assert result == "Dispatched 0 sources."


def test_monitor_stalled_jobs_reaps_stalled_jurisdiction_jobs(sync_session: Session, monkeypatch):
    """Stalled JurisdictionScrapeJob rows should be force-failed by the monitor task."""
    monkeypatch.setattr(
        "app.api.modules.v1.scraping.service.tasks.settings.JURISDICTION_JOB_TIMEOUT_SECONDS",
        1800,
    )

    organization = Organization(name="Stalled Jobs Org")
    sync_session.add(organization)
    sync_session.commit()
    sync_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Stalled Jobs Project",
        description="Project for stalled jurisdiction monitoring test",
    )
    sync_session.add(project)
    sync_session.commit()
    sync_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Stalled Jurisdiction",
        description="Testing stalled jurisdiction job reaper",
    )
    sync_session.add(jurisdiction)
    sync_session.commit()
    sync_session.refresh(jurisdiction)

    job = JurisdictionScrapeJob(
        jurisdiction_id=jurisdiction.id,
        status=JurisdictionScrapeJobStatus.SCRAPING,
        started_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    sync_session.add(job)
    sync_session.commit()
    sync_session.refresh(job)

    result = monitor_stalled_jobs.run()

    refreshed_job = sync_session.exec(
        select(JurisdictionScrapeJob).where(JurisdictionScrapeJob.id == job.id)
    ).first()
    assert "1 stalled jurisdiction job(s) marked as failed" in result
    assert refreshed_job is not None
    assert refreshed_job.status == JurisdictionScrapeJobStatus.FAILED
    assert refreshed_job.error_message == "Stalled: no completion after timeout"
