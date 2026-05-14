"""Unit tests for campaign_tasks module — Redis progress publishing."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import redis
import redis.asyncio as aioredis

import app.api.modules.v1.campaigns.tasks.campaign_tasks as campaign_tasks_module
from app.api.modules.v1.campaigns.models.campaign_model import CampaignStatus
from app.api.modules.v1.campaigns.tasks.campaign_tasks import (
    FORCE_FAIL_AFTER_RETRIES,
    _make_async_redis_client,
    _publish_progress,
    _retry_sources_async,
    _select_campaign_blog_target_ids,
    dispatch_campaign_scrapes_task,
    generate_campaign_content_task,
    publish_campaign_blogs_task,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import JurisdictionScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.source_verification_service import (
    VerificationResult,
    VerificationStatus,
)


@pytest.fixture(autouse=True)
def unmock_redis():
    """Bypass the global conftest.py Redis mock for these unit tests."""

    class FakeConnectionPool:
        def __init__(self, **kwargs):
            self.connection_kwargs = kwargs
            self.max_connections = kwargs.get("max_connections")

        @classmethod
        def from_url(cls, url, **kwargs):
            return cls(**kwargs)

    class FakeRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool

    with (
        patch(
            "app.api.modules.v1.campaigns.tasks.campaign_tasks.aioredis.ConnectionPool",
            FakeConnectionPool,
        ),
        patch(
            "app.api.modules.v1.campaigns.tasks.campaign_tasks.aioredis.Redis",
            FakeRedis,
        ),
    ):
        yield


class TestProgressPool:
    """Verify that the module-level connection pool has production-grade settings."""

    def test_pool_is_connection_pool(self):
        """The progress pool must be a synchronous ConnectionPool instance."""
        assert isinstance(campaign_tasks_module._progress_pool, redis.ConnectionPool)

    def test_pool_has_keepalive(self):
        """socket_keepalive must be enabled to avoid silent dead connections."""
        kwargs = campaign_tasks_module._progress_pool.connection_kwargs
        assert kwargs.get("socket_keepalive") is True

    def test_pool_has_socket_timeout(self):
        """A socket_timeout must be set so stale sockets are detected promptly."""
        kwargs = campaign_tasks_module._progress_pool.connection_kwargs
        assert kwargs.get("socket_timeout") is not None

    def test_pool_has_health_check_interval(self):
        """health_check_interval must be set for long-running pipeline workers."""
        kwargs = campaign_tasks_module._progress_pool.connection_kwargs
        assert kwargs.get("health_check_interval", 0) > 0

    def test_pool_retries_on_timeout(self):
        """retry_on_timeout must be enabled for transient network resilience."""
        kwargs = campaign_tasks_module._progress_pool.connection_kwargs
        assert kwargs.get("retry_on_timeout") is True

    def test_pool_caps_max_connections(self):
        """max_connections must be explicitly capped (not left at the library default)."""
        assert campaign_tasks_module._progress_pool.max_connections is not None


class TestMakeAsyncRedisClient:
    """Verify the async Redis client factory produces a properly configured client."""

    def test_returns_async_redis_instance(self):
        """The factory must return an aioredis.Redis client."""
        client = _make_async_redis_client()
        assert isinstance(client, aioredis.Redis)

    def test_async_pool_has_keepalive(self):
        """The async client pool must have socket_keepalive enabled."""
        client = _make_async_redis_client()
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs.get("socket_keepalive") is True

    def test_async_pool_has_socket_timeout(self):
        """The async client pool must have a socket_timeout configured."""
        client = _make_async_redis_client()
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs.get("socket_timeout") is not None

    def test_async_pool_has_health_check_interval(self):
        """The async client pool must have a health_check_interval > 0."""
        client = _make_async_redis_client()
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs.get("health_check_interval", 0) > 0

    def test_async_pool_retries_on_timeout(self):
        """The async client pool must have retry_on_timeout enabled."""
        client = _make_async_redis_client()
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs.get("retry_on_timeout") is True

    def test_async_pool_caps_max_connections(self):
        """Each factory call must produce a client with an explicit max_connections cap."""
        client = _make_async_redis_client()
        assert client.connection_pool.max_connections is not None

    def test_each_call_creates_independent_pool(self):
        """Two factory calls must return clients with independent connection pools."""
        client_a = _make_async_redis_client()
        client_b = _make_async_redis_client()
        assert client_a.connection_pool is not client_b.connection_pool


class TestPublishProgress:
    """Verify _publish_progress behaviour for correctness and fault-tolerance."""

    def test_publishes_correct_channel_and_payload(self):
        """A successful publish sends the right channel and a valid JSON payload."""
        mock_client = MagicMock()

        with patch.object(campaign_tasks_module, "_sync_redis_client", mock_client):
            _publish_progress("abc-123", "taxonomy", 1, 5)

        mock_client.publish.assert_called_once()
        channel, raw_payload = mock_client.publish.call_args[0]

        assert channel == "campaign_progress:abc-123"

        payload = json.loads(raw_payload)
        assert payload["phase"] == "taxonomy"
        assert payload["completed"] == 1
        assert payload["total"] == 5
        assert payload["pct"] == pytest.approx(20.0)
        assert "ts" in payload

    def test_zero_total_does_not_raise(self):
        """Edge-case: total=0 must not raise ZeroDivisionError and must yield pct=0.0."""
        mock_client = MagicMock()

        with patch.object(campaign_tasks_module, "_sync_redis_client", mock_client):
            _publish_progress("abc-123", "taxonomy", 0, 0)

        _, raw_payload = mock_client.publish.call_args[0]
        payload = json.loads(raw_payload)
        assert payload["pct"] == 0.0

    def test_redis_failure_does_not_raise(self):
        """A Redis error must be swallowed so pipeline tasks are not aborted."""
        mock_client = MagicMock()
        mock_client.publish.side_effect = redis.exceptions.ConnectionError("Redis down")

        with patch.object(campaign_tasks_module, "_sync_redis_client", mock_client):
            # Must NOT raise — progress publishing is best-effort.
            _publish_progress("abc-123", "hydration", 3, 10)

    def test_redis_failure_is_logged_as_warning(self, caplog):
        """A Redis error must emit a WARNING log so operators can detect Redis issues."""
        mock_client = MagicMock()
        mock_client.publish.side_effect = redis.exceptions.ConnectionError("Redis down")

        with (
            patch.object(campaign_tasks_module, "_sync_redis_client", mock_client),
            patch.object(campaign_tasks_module, "logger") as mock_logger,
        ):
            _publish_progress("abc-123", "hydration", 3, 10)

        mock_logger.warning.assert_called_once()
        # The code uses string formatting like warning("... %s", campaign_id)
        assert (
            "abc-123" in mock_logger.warning.call_args[0]
            or "abc-123" in mock_logger.warning.call_args.args
        )


class TestDispatchCampaignScrapesTask:
    """Dispatch should only run for jurisdictions with discovered sources."""

    def test_filters_to_discovered_jurisdictions(self):
        campaign_id = uuid4()
        discovered = MagicMock(id=uuid4(), discovery_status=DiscoveryStatus.DISCOVERED)
        requires_manual = MagicMock(
            id=uuid4(),
            discovery_status=DiscoveryStatus.REQUIRES_MANUAL_SOURCES,
        )
        campaign = MagicMock(
            id=campaign_id,
            status=CampaignStatus.DISCOVERING_SOURCES,
            jurisdictions=[discovered, requires_manual],
        )

        mock_db = MagicMock()
        mock_db.exec.return_value = MagicMock(first=MagicMock(return_value=campaign))
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_session.__exit__.return_value = False

        with (
            patch.object(campaign_tasks_module, "SyncSessionLocal", return_value=mock_session),
            patch.object(campaign_tasks_module.celery_app, "send_task") as mock_send_task,
            patch.object(campaign_tasks_module, "_publish_progress"),
        ):
            result = dispatch_campaign_scrapes_task.run(str(campaign_id))

        assert result["dispatched"] == 1
        assert result["eligible_jurisdictions"] == 1
        mock_send_task.assert_called_once_with(
            "app.api.modules.v1.scraping.service.tasks.dispatch_single_jurisdiction_scrape",
            args=[str(discovered.id)],
            queue="processing",
        )


class TestPublishCampaignBlogsTask:
    """Publish task should force-fail stuck jobs once the retry budget is exhausted."""

    def test_force_fails_stuck_jobs_after_retry_threshold(self):
        campaign_id = uuid4()
        active_job = MagicMock(
            status=JurisdictionScrapeJobStatus.SCRAPING,
            completed_at=None,
            error_message=None,
        )
        campaign = MagicMock(
            id=campaign_id,
            status=CampaignStatus.PUBLISHING,
            updated_at=datetime.now(timezone.utc),
            jurisdictions=[],
        )

        mock_db = MagicMock()
        mock_db.exec.side_effect = [
            MagicMock(first=MagicMock(return_value=campaign)),
            MagicMock(all=MagicMock(return_value=[active_job])),
            MagicMock(all=MagicMock(return_value=[active_job])),
        ]
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_session.__exit__.return_value = False

        original_retries = publish_campaign_blogs_task.request.retries
        publish_campaign_blogs_task.request.retries = FORCE_FAIL_AFTER_RETRIES

        try:
            with (
                patch.object(campaign_tasks_module, "SyncSessionLocal", return_value=mock_session),
                patch.object(campaign_tasks_module, "_enqueue_sitemap_rebuild"),
            ):
                result = publish_campaign_blogs_task.run(str(campaign_id))
        finally:
            publish_campaign_blogs_task.request.retries = original_retries

        assert result["status"] == "completed"
        assert active_job.status == JurisdictionScrapeJobStatus.FAILED
        assert active_job.error_message == "Force-failed: exceeded campaign completion timeout"
        assert campaign.status == CampaignStatus.MONITORING

    def test_generate_campaign_content_task_generates_missing_blogs(self):
        """Dedicated campaign content task should generate blogs from existing state."""
        campaign_id = uuid4()
        jurisdiction_id = uuid4()
        campaign = MagicMock(id=campaign_id, stats=None)

        mock_db = MagicMock()
        mock_db.exec.side_effect = [
            MagicMock(first=MagicMock(return_value=campaign)),
            MagicMock(all=MagicMock(return_value=[jurisdiction_id])),
            MagicMock(all=MagicMock(return_value=[jurisdiction_id])),
        ]
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_db
        mock_session.__exit__.return_value = False

        with (
            patch.object(campaign_tasks_module, "SyncSessionLocal", return_value=mock_session),
            patch.object(campaign_tasks_module, "syncify_generate_blog") as mock_generate_blog,
            patch.object(campaign_tasks_module, "_publish_progress") as mock_publish_progress,
        ):
            mock_generate_blog.return_value = {"status": "success"}

            result = generate_campaign_content_task.run(
                str(campaign_id),
                "run-1",
                "backfill_missing",
            )

            assert result["status"] == "completed"
            assert result["total"] == 1
            assert result["success"] == 1
            assert result["skipped"] == 0
            mock_generate_blog.assert_called_once_with(mock_db, jurisdiction_id)
            assert mock_publish_progress.call_count == 3
            assert mock_publish_progress.call_args_list[0].kwargs["status"] == "IN_PROGRESS"
            assert mock_publish_progress.call_args_list[-1].kwargs["status"] == "COMPLETED"

    def test_select_campaign_blog_target_ids_uses_batched_queries(self):
        """Target selection should execute one set-based query per mode."""
        campaign_id = uuid4()
        jurisdiction_id = uuid4()
        mock_db = MagicMock()
        mock_db.exec.return_value = MagicMock(all=MagicMock(return_value=[jurisdiction_id]))

        result = _select_campaign_blog_target_ids(mock_db, campaign_id, "run")

        assert result == [jurisdiction_id]
        mock_db.exec.assert_called_once()


class TestRetrySourcesAsync:
    """Regression coverage for retrying source verification."""

    @pytest.mark.asyncio
    async def test_retries_sources_via_public_verification_api(self):
        """Retry flow should call SourceVerificationService.verify_single and persist updates."""
        campaign_id = uuid4()
        source = Source(
            id=uuid4(),
            jurisdiction_id=uuid4(),
            name="Test Source",
            url="https://example.gov/rules",
            verification_status=VerificationStatus.TIMEOUT.value,
            verification_attempts=1,
        )

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [source]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db_session = AsyncMock()
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        with patch(
            "app.api.modules.v1.scraping.service.source_verification_service."
            "SourceVerificationService.verify_single",
            new=AsyncMock(
                return_value=VerificationResult(status=VerificationStatus.VERIFIED),
            ),
        ) as mock_verify_single:
            result = await _retry_sources_async(mock_db_session, [source.id], campaign_id)

        assert result == {"retried_count": 1, "success_count": 1, "failure_count": 0}
        assert source.verification_status == VerificationStatus.VERIFIED.value
        assert source.verification_attempts == 2
        assert source.last_verification_at is not None
        mock_verify_single.assert_awaited_once_with(
            url="https://example.gov/rules",
            attempt_count=2,
        )
        mock_db_session.add.assert_called_once_with(source)
        mock_db_session.commit.assert_awaited_once()
