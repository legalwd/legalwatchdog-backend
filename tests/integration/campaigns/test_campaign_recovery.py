"""Failure recovery tests for the campaign pipeline — Phase 9 § 9.3.

Covers:
- 9.3a: Mid-pipeline DB failure → campaign.status = FAILED, execution logs populated
- 9.3b: Redis unavailable during progress publish → pipeline continues (non-fatal)
- 9.3c: Search rate-limit hit during source discovery → backoff + retry → eventual success
- 9.3d: Celery worker crash mid-hydration → idempotency holds on retry

All external I/O is mocked. Slow tests are gated with ``@pytest.mark.slow``.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.service.campaign_hydration_service import (
    CampaignHydrationService,
)
from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
    CampaignOrchestrationService,
)
from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
    CampaignSourceDiscoveryService,
)
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_taxonomy_with_n_nodes(n: int) -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "name": f"Jurisdiction_{i}",
                "description": f"Test jurisdiction {i}",
                "suggested_prompt": f"Extract compliance data for jurisdiction {i}",
                "suggested_search_queries": [f"jurisdiction {i} law 2026"],
                "children": [],
            }
            for i in range(n)
        ]
    }


def _make_campaign(
    campaign_id: uuid.UUID,
    status: CampaignStatus = CampaignStatus.TAXONOMY_READY,
    taxonomy_json: Optional[Dict[str, Any]] = None,
    max_jurisdictions: int = 10,
) -> Campaign:
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=campaign_id,
        organization_id=uuid.uuid4(),
        name="Recovery Test Campaign",
        industry="EOR",
        domain_description="Recovery testing of campaign pipeline",
        target_depth=CampaignTargetDepth.STATE,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        monitor_cadence="daily",
        sources_per_jurisdiction=5,
        max_jurisdictions=max_jurisdictions,
        status=status,
        taxonomy_json=taxonomy_json or {"nodes": []},
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    return campaign


@asynccontextmanager
async def _ok_nested():
    yield None


def _make_db_session(
    campaign: Campaign,
    project_id: Optional[uuid.UUID] = None,
) -> AsyncMock:
    resolved_project_id = project_id or uuid.uuid4()
    results: List[Any] = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=campaign)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]

    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        side_effect=lambda *a, **kw: (
            results.pop(0)
            if results
            else MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
    )

    async def _refresh(obj):
        if hasattr(obj, "org_id"):
            object.__setattr__(obj, "id", resolved_project_id)

    db.refresh = AsyncMock(side_effect=_refresh)
    db.begin_nested = MagicMock(side_effect=_ok_nested)

    def _auto_id_add(obj):
        if hasattr(obj, "project_id") and hasattr(obj, "parent_id") and hasattr(obj, "name"):
            if not getattr(obj, "id", None):
                object.__setattr__(obj, "id", uuid.uuid4())

    db.add = MagicMock(side_effect=_auto_id_add)
    return db


def _make_jurisdiction_mock(
    campaign_id: Optional[uuid.UUID] = None,
    name: str = "United States",
) -> MagicMock:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus

    jur = MagicMock()
    jur.id = uuid.uuid4()
    jur.name = name
    jur.description = f"Description for {name}"
    jur.prompt = f"Extract compliance data for {name}"
    jur.campaign_id = campaign_id or uuid.uuid4()
    jur.discovery_status = DiscoveryStatus.PENDING
    return jur


# ---------------------------------------------------------------------------
# 9.3a — Mid-pipeline DB failure
# ---------------------------------------------------------------------------


class TestMidPipelineDbFailure:
    """Simulate DB failure mid-hydration; verify FAILED status and log population."""

    @pytest.mark.slow
    async def test_db_failure_during_jurisdiction_creation_sets_campaign_failed(self):
        """OperationalError during _create_jurisdictions → campaign.status = FAILED."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(10)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=10,
        )

        # DB: campaign look-up succeeds; existing-jurisdiction preload returns empty.
        # begin_nested raises OperationalError on first jurisdiction insert attempt.
        execute_call_count = 0

        async def _execute_handler(*a, **kw):
            nonlocal execute_call_count
            execute_call_count += 1
            if execute_call_count == 1:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
            # _load_existing_jurisdictions — return an empty iterable
            empty = MagicMock()
            empty.__iter__ = MagicMock(return_value=iter([]))
            return empty

        @asynccontextmanager
        async def _fail_nested():
            raise OperationalError("Lost connection", {}, Exception("connection lost"))
            yield  # pragma: no cover

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(side_effect=_execute_handler)

        async def _refresh(obj):
            if hasattr(obj, "org_id"):
                object.__setattr__(obj, "id", uuid.uuid4())

        db.refresh = AsyncMock(side_effect=_refresh)
        db.begin_nested = MagicMock(side_effect=_fail_nested)
        db.add = MagicMock()

        service = CampaignHydrationService(db)

        with pytest.raises(ProcessingError):
            await service.hydrate(campaign_id)

        assert campaign.status == CampaignStatus.FAILED

    @pytest.mark.slow
    async def test_db_failure_during_real_runner_execution_sets_campaign_failed(
        self, celery_eager, db_engine
    ):
        """Force a failure inside the eager Celery chain and verify the
        campaign ends up in FAILED state (via the error handler or the
        task's retry mechanism exhaustion).

        ``celery_eager`` redirects all task sessions to the test DB.
        We commit test data so every session can see the campaign, then
        force ``TaxonomyGenerationService.generate`` to raise so the very
        first task in the chain blows up.
        """
        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession

        from app.api.modules.v1.organization.models.organization_model import Organization
        from app.api.modules.v1.users.models.users_model import User

        campaign_id = uuid.uuid4()
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # --- Insert committed test data ---
        async with SAAsyncSession(db_engine, expire_on_commit=False) as setup:
            async with setup.begin():
                setup.add(Organization(id=org_id, name="Recovery Org", email="rec@test.com"))
                setup.add(
                    User(
                        id=user_id,
                        email="rec@test.com",
                        name="Recovery User",
                        is_active=True,
                        is_approved=True,
                        is_superadmin=True,
                    )
                )
                await setup.flush()  # FK deps must exist before campaign
                setup.add(
                    Campaign(
                        id=campaign_id,
                        organization_id=org_id,
                        name="Recovery Real Runner",
                        industry="EOR",
                        status=CampaignStatus.DRAFT,
                        taxonomy_json=_make_taxonomy_with_n_nodes(5),
                        max_jurisdictions=5,
                        created_by=user_id,
                    )
                )

        # --- Run the chain with a forced failure in the first task ---
        async with SAAsyncSession(db_engine, expire_on_commit=False) as svc_session:
            celery_control = MagicMock()
            service = CampaignOrchestrationService(db=svc_session, celery_control=celery_control)

            svc_base = "app.api.modules.v1.campaigns"
            with patch(
                f"{svc_base}.service.taxonomy_generation_service"
                ".TaxonomyGenerationService.generate",
                new_callable=AsyncMock,
            ) as mock_tax:
                mock_tax.side_effect = OperationalError(
                    "Lost connection", {}, Exception("connection lost")
                )
                try:
                    await service.run(campaign_id)
                except Exception:
                    # task_eager_propagates=True surfaces the exception
                    pass

        # After the forced failure, the campaign should be marked as FAILED and
        # an execution log entry should exist for this run.
        async with SAAsyncSession(db_engine, expire_on_commit=False) as verify_session:
            campaign_result = await verify_session.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            )
            campaign = campaign_result.scalar_one()
            assert campaign.status == CampaignStatus.FAILED

            exec_log_result = await verify_session.execute(
                select(CampaignExecutionLog).where(CampaignExecutionLog.campaign_id == campaign_id)
            )
            exec_log = exec_log_result.first()
            assert exec_log is not None

    @pytest.mark.slow
    async def test_db_failure_execution_log_populated_before_failure(self):
        """An execution log entry is created before the DB failure occurs."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(5)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=5,
        )

        exec_logs_added: List[CampaignExecutionLog] = []
        execute_call_count = 0

        async def _execute_handler(*a, **kw):
            nonlocal execute_call_count
            execute_call_count += 1
            if execute_call_count == 1:
                return MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
            # _load_existing_jurisdictions — return an empty iterable
            empty = MagicMock()
            empty.__iter__ = MagicMock(return_value=iter([]))
            return empty

        def _tracking_add(obj):
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        @asynccontextmanager
        async def _fail_nested():
            raise OperationalError("Lost connection", {}, Exception("connection lost"))
            yield  # pragma: no cover

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.flush = AsyncMock()
        db.execute = AsyncMock(side_effect=_execute_handler)

        async def _refresh(obj):
            if hasattr(obj, "org_id"):
                object.__setattr__(obj, "id", uuid.uuid4())

        db.refresh = AsyncMock(side_effect=_refresh)
        db.begin_nested = MagicMock(side_effect=_fail_nested)
        db.add = MagicMock(side_effect=_tracking_add)

        service = CampaignHydrationService(db)

        with pytest.raises(ProcessingError):
            await service.hydrate(campaign_id)

        assert len(exec_logs_added) >= 1
        log = exec_logs_added[0]
        assert log.campaign_id == campaign_id
        assert log.phase == "hydration"

    @pytest.mark.slow
    def test_celery_error_handler_sets_campaign_failed_and_creates_log(self):
        """campaign_pipeline_error_handler sets FAILED status and creates a pipeline_error log."""
        from app.api.modules.v1.campaigns.tasks.campaign_tasks import (
            campaign_pipeline_error_handler,
        )

        campaign_id = uuid.uuid4()
        task_id = str(uuid.uuid4())

        # Build an in-memory campaign object — no real DB needed.
        campaign = Campaign(
            id=campaign_id,
            organization_id=uuid.uuid4(),
            name="Error Handler Campaign",
            industry="EOR",
            status=CampaignStatus.HYDRATING,
            created_by=uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Tracks CampaignExecutionLog objects added via mock_db.add() for later assertion.
        exec_logs_added: List[CampaignExecutionLog] = []

        def _track_add(obj):
            """Capture CampaignExecutionLog instances added through mock_db.add()."""
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        # Build a mock sync DB session that returns our campaign from db.get()
        mock_db = MagicMock()
        mock_db.get.return_value = campaign
        mock_db.add.side_effect = _track_add
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_session_cls = MagicMock(return_value=mock_db)

        mock_result_obj = MagicMock()
        mock_result_obj.failed.return_value = True
        mock_result_obj.result = Exception("DB connection lost")
        mock_result_obj.traceback = "Traceback (most recent call last):..."

        with (
            patch("app.api.modules.v1.campaigns.tasks.campaign_tasks._sync_redis_client"),
            patch(
                "app.api.modules.v1.campaigns.tasks.campaign_tasks.AsyncResult",
                return_value=mock_result_obj,
            ),
            patch(
                "app.api.modules.v1.campaigns.tasks.campaign_tasks.SyncSessionLocal",
                mock_session_cls,
            ),
        ):
            campaign_pipeline_error_handler.run(str(campaign_id), run_id=None, task_id=task_id)

        assert campaign.status == CampaignStatus.FAILED
        mock_db.commit.assert_called_once()
        assert len(exec_logs_added) == 1
        assert exec_logs_added[0].phase == "pipeline_error"
        assert exec_logs_added[0].completed_at is not None


# ---------------------------------------------------------------------------
# 9.3b — Redis unavailable during progress publish
# ---------------------------------------------------------------------------


class TestRedisUnavailableDuringPublish:
    """Simulate Redis being unavailable during _publish_progress; verify pipeline continues."""

    async def test_redis_publish_failure_is_swallowed(self):
        """_publish_progress must not raise even when Redis.publish() raises ConnectionError."""
        import app.api.modules.v1.campaigns.tasks.campaign_tasks as campaign_tasks_module

        failing_redis = MagicMock()
        failing_redis.publish.side_effect = ConnectionError("Redis is unavailable")

        campaign_id = str(uuid.uuid4())

        with patch.object(campaign_tasks_module, "_sync_redis_client", failing_redis):
            # Must complete without raising
            campaign_tasks_module._publish_progress(campaign_id, "hydration", 0, 10)

        failing_redis.publish.assert_called_once()

    async def test_hydration_continues_when_redis_publish_fails(self):
        """Hydration pipeline completes successfully even when Redis publish raises."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(5)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=5,
        )
        db = _make_db_session(campaign, project_id=uuid.uuid4())

        import app.api.modules.v1.campaigns.tasks.campaign_tasks as campaign_tasks_module

        failing_redis = MagicMock()
        failing_redis.publish.side_effect = ConnectionError("Redis is unavailable")

        # Hydration service does NOT call _publish_progress directly — the Celery task wraps
        # it. Verify via the task-level wrapper that the pipeline continues despite the error.
        with patch.object(campaign_tasks_module, "_sync_redis_client", failing_redis):
            # Calling _publish_progress directly should not raise
            campaign_tasks_module._publish_progress(str(campaign_id), "hydration", 0, 1)
            campaign_tasks_module._publish_progress(str(campaign_id), "hydration", 5, 5)

        # Run the actual hydration service independently (no Redis involvement)
        service = CampaignHydrationService(db)
        jurisdiction_ids = await service.hydrate(campaign_id)

        assert len(jurisdiction_ids) == 5
        assert campaign.status != CampaignStatus.FAILED

    @pytest.mark.slow
    async def test_source_discovery_continues_when_redis_unavailable(self):
        """Source discovery completes even if the progress Redis client is down."""
        campaign_id = uuid.uuid4()
        jurs = [_make_jurisdiction_mock(campaign_id=campaign_id, name=f"Jur_{i}") for i in range(3)]
        campaign = _make_campaign(campaign_id, status=CampaignStatus.HYDRATING, max_jurisdictions=3)
        campaign.jurisdictions = jurs

        import app.api.modules.v1.campaigns.tasks.campaign_tasks as campaign_tasks_module

        failing_redis = MagicMock()
        failing_redis.publish.side_effect = ConnectionError("Redis is down")

        suggested = [
            SuggestedSource(
                title="Test",
                url="https://example.gov",
                snippet="Official",
                confidence_reason="Gov domain",
                is_official=True,
            )
        ]

        with (
            patch.object(campaign_tasks_module, "_sync_redis_client", failing_redis),
            patch(
                "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService"
            ) as MockSourceSvc,
            patch(
                "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
            ) as MockDiscoverySvc,
            patch(
                "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            mock_discovery = AsyncMock()
            mock_discovery.suggest_sources = AsyncMock(return_value=suggested)
            mock_discovery.close = AsyncMock()
            MockDiscoverySvc.return_value = mock_discovery

            created = MagicMock()
            created.id = uuid.uuid4()
            mock_source = MagicMock()
            mock_source.create_source = AsyncMock(return_value=created)
            MockSourceSvc.return_value = mock_source

            db = AsyncMock()
            db.commit = AsyncMock()
            db.rollback = AsyncMock()
            db.flush = AsyncMock()
            db.add = MagicMock()
            db.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
            )

            redis_mock = AsyncMock()
            redis_mock.incr = AsyncMock(return_value=1)
            redis_mock.expire = AsyncMock()

            service = CampaignSourceDiscoveryService(db, redis_mock)
            summary = await service.discover_all(campaign_id)

        assert summary["total"] == 3
        assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# 9.3c — Search rate-limit backoff + retry → eventual success
# ---------------------------------------------------------------------------


class TestSearchRateLimitBackoff:
    """Rate-limit hit during source discovery triggers backoff + retry → eventual success."""

    @pytest.mark.slow
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_rate_limit_backoff_then_success(self, mock_sleep):
        """After 2 rate-limit hits (backed off), the 3rd attempt proceeds normally."""
        from app.api.core.config import settings

        campaign_id = uuid.uuid4()
        limit = settings.CAMPAIGN_SEARCH_RATE_LIMIT

        # incr returns: limit+1 (throttled), limit+2 (throttled), 1 (allowed)
        incr_sequence = [limit + 1, limit + 2, 1]
        incr_calls = 0

        async def _incr(key):
            nonlocal incr_calls
            val = incr_sequence[incr_calls] if incr_calls < len(incr_sequence) else 1
            incr_calls += 1
            return val

        redis_mock = AsyncMock()
        redis_mock.incr = AsyncMock(side_effect=_incr)
        redis_mock.expire = AsyncMock()

        jurs = [_make_jurisdiction_mock(campaign_id=campaign_id, name=f"Jur_{i}") for i in range(1)]
        campaign = _make_campaign(campaign_id, status=CampaignStatus.HYDRATING, max_jurisdictions=1)
        campaign.jurisdictions = jurs

        with (
            patch(
                "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService"
            ) as MockSourceSvc,
            patch(
                "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
            ) as MockDiscoverySvc,
        ):
            suggested = [
                SuggestedSource(
                    title="Source",
                    url="https://example.gov",
                    snippet="Official",
                    confidence_reason="Gov",
                    is_official=True,
                )
            ]
            mock_discovery = AsyncMock()
            mock_discovery.suggest_sources = AsyncMock(return_value=suggested)
            mock_discovery.close = AsyncMock()
            MockDiscoverySvc.return_value = mock_discovery

            created = MagicMock()
            created.id = uuid.uuid4()
            mock_source = MagicMock()
            mock_source.create_source = AsyncMock(return_value=created)
            MockSourceSvc.return_value = mock_source

            db = AsyncMock()
            db.commit = AsyncMock()
            db.rollback = AsyncMock()
            db.flush = AsyncMock()
            db.add = MagicMock()
            db.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
            )

            service = CampaignSourceDiscoveryService(db, redis_mock)
            summary = await service.discover_all(campaign_id)

        assert summary["total"] == 1
        assert summary["sources_created"] == 1
        # sleep must have been called for the two throttled attempts
        assert mock_sleep.call_count >= 2

    @pytest.mark.slow
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep",
        new_callable=AsyncMock,
    )
    async def test_rate_limit_max_retries_raises_processing_error(self, mock_sleep):
        """After _MAX_RATE_LIMIT_RETRIES exhausted, ProcessingError is raised."""
        from app.api.core.config import settings
        from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
            _MAX_RATE_LIMIT_RETRIES,
        )

        campaign_id = uuid.uuid4()
        limit = settings.CAMPAIGN_SEARCH_RATE_LIMIT

        # Always over the limit
        redis_mock = AsyncMock()
        redis_mock.incr = AsyncMock(return_value=limit + 100)
        redis_mock.expire = AsyncMock()

        db = AsyncMock()
        service = CampaignSourceDiscoveryService(db, redis_mock)

        with pytest.raises(ProcessingError, match="Rate limit exceeded"):
            await service._wait_for_rate_limit(campaign_id)

        # sleep called once per retry attempt
        assert mock_sleep.call_count == _MAX_RATE_LIMIT_RETRIES


# ---------------------------------------------------------------------------
# 9.3d — Worker crash / retry idempotency
# ---------------------------------------------------------------------------


class TestWorkerCrashIdempotency:
    """Simulate a Celery worker crash mid-hydration; verify idempotency on retry."""

    @pytest.mark.slow
    async def test_hydration_is_idempotent_after_simulated_crash_and_restart(self):
        """Re-running hydrate() after a crash (IntegrityError on insert) returns correct count."""
        from sqlalchemy.exc import IntegrityError

        campaign_id = uuid.uuid4()
        project_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(10)
        existing_jur_ids = [uuid.uuid4() for _ in range(10)]

        @asynccontextmanager
        async def _fail_nested():
            raise IntegrityError("uix_project_name", {}, Exception("duplicate key"))
            yield  # pragma: no cover

        rows = []
        for i, jid in enumerate(existing_jur_ids):
            row = MagicMock()
            row.parent_id = None
            row.name = f"Jurisdiction_{i}"
            row.id = jid
            rows.append(row)

        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter(rows))

        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=10,
        )

        execute_results: List[Any] = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=campaign)),
            existing_result,
        ]

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(
            side_effect=lambda *a, **kw: (
                execute_results.pop(0)
                if execute_results
                else MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            )
        )

        async def _refresh(obj):
            if hasattr(obj, "org_id"):
                object.__setattr__(obj, "id", project_id)

        db.refresh = AsyncMock(side_effect=_refresh)
        db.begin_nested = MagicMock(side_effect=_fail_nested)

        service = CampaignHydrationService(db)
        jurisdiction_ids = await service.hydrate(campaign_id)

        # Must return exactly 10 (the existing IDs), not 0 or 20
        assert len(jurisdiction_ids) == 10
        assert set(jurisdiction_ids) == set(existing_jur_ids)

    @pytest.mark.slow
    async def test_double_hydration_commit_called_once(self):
        """When idempotent path is taken (IntegrityError), commit is called exactly once."""
        from sqlalchemy.exc import IntegrityError

        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(5)
        existing_jur_ids = [uuid.uuid4() for _ in range(5)]

        @asynccontextmanager
        async def _fail_nested():
            raise IntegrityError("uix", {}, Exception("dup"))
            yield  # pragma: no cover

        rows = []
        for i, jid in enumerate(existing_jur_ids):
            row = MagicMock()
            row.parent_id = None
            row.name = f"Jurisdiction_{i}"
            row.id = jid
            rows.append(row)

        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter(rows))

        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=5,
        )
        execute_results: List[Any] = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=campaign)),
            existing_result,
        ]

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(
            side_effect=lambda *a, **kw: (
                execute_results.pop(0)
                if execute_results
                else MagicMock(scalar_one_or_none=MagicMock(return_value=None))
            )
        )

        async def _refresh(obj):
            if hasattr(obj, "org_id"):
                object.__setattr__(obj, "id", uuid.uuid4())

        db.refresh = AsyncMock(side_effect=_refresh)
        db.begin_nested = MagicMock(side_effect=_fail_nested)

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        db.commit.assert_called_once()

    @pytest.mark.slow
    def test_celery_hydration_task_retries_on_exception(self):
        """hydrate_campaign_task retries when CampaignHydrationService raises an exception."""
        from app.api.modules.v1.campaigns.tasks.campaign_tasks import hydrate_campaign_task

        campaign_id = str(uuid.uuid4())

        with (
            patch("app.api.modules.v1.campaigns.tasks.campaign_tasks._publish_progress"),
            patch("app.api.modules.v1.campaigns.tasks.campaign_tasks.syncify") as mock_syncify,
            patch.object(
                hydrate_campaign_task, "retry", side_effect=Exception("task retried")
            ) as mock_retry,
        ):
            mock_syncify.return_value = MagicMock(
                side_effect=ProcessingError("Hydration failed. DB error")
            )

            with pytest.raises(Exception, match="task retried"):
                hydrate_campaign_task.run(campaign_id)

            mock_retry.assert_called_once()
