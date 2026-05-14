"""Scale tests for the campaign pipeline — Phase 9 § 9.1 & 9.4.

Covers:
- 9.1a: Small campaign (500 jurisdictions) completes without errors, stats populated
- 9.1b: 3 concurrent campaigns with no campaign_id cross-contamination
- 9.1c: Hydration idempotency under concurrent double-trigger
- 9.1d: Celery Beat dispatch_due_jurisdictions enqueues all overdue jobs without duplicates
- 9.4:  Monitoring assertions (status endpoint, execution log completed_at, Redis pub/sub)

All external I/O (DB, Redis, LLM, Celery) is mocked. Slow tests are gated with
``@pytest.mark.slow``.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

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
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus, Jurisdiction
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_taxonomy_with_n_nodes(n: int) -> Dict[str, Any]:
    """Create a flat taxonomy with *n* top-level jurisdiction nodes."""
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
    max_jurisdictions: int = 15000,
    sources_per_jurisdiction: int = 5,
) -> Campaign:
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=campaign_id,
        organization_id=uuid.uuid4(),
        name="Scale Test Campaign",
        industry="EOR",
        domain_description="Scale testing of campaign pipeline",
        target_depth=CampaignTargetDepth.STATE,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        monitor_cadence="daily",
        sources_per_jurisdiction=sources_per_jurisdiction,
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
    begin_nested_factory=None,
) -> AsyncMock:
    """Build a minimal mocked async DB session for hydration tests."""
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
    db.begin_nested = MagicMock(side_effect=begin_nested_factory or _ok_nested)

    def _auto_id_add(obj):
        if hasattr(obj, "project_id") and hasattr(obj, "parent_id") and hasattr(obj, "name"):
            if not getattr(obj, "id", None):
                object.__setattr__(obj, "id", uuid.uuid4())

    db.add = MagicMock(side_effect=_auto_id_add)
    return db


def _make_jurisdiction_mock(
    jur_id: Optional[uuid.UUID] = None,
    campaign_id: Optional[uuid.UUID] = None,
    name: str = "United States",
    prompt: str = "Extract US compliance data",
) -> MagicMock:
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus

    jur = MagicMock()
    jur.id = jur_id or uuid.uuid4()
    jur.name = name
    jur.prompt = prompt
    jur.campaign_id = campaign_id or uuid.uuid4()
    jur.discovery_status = DiscoveryStatus.PENDING
    return jur


def _make_redis_mock(incr_value: int = 1) -> AsyncMock:
    redis_mock = AsyncMock()
    redis_mock.incr = AsyncMock(return_value=incr_value)
    redis_mock.expire = AsyncMock()
    return redis_mock


# ---------------------------------------------------------------------------
# 9.1a — Small campaign execution (500 jurisdictions)
# ---------------------------------------------------------------------------


class TestSmallCampaignExecution:
    """Test a 500-jurisdiction campaign completes without errors, stats populated."""

    @pytest.mark.slow
    async def test_hydration_500_jurisdictions_completes_successfully(self):
        """1 campaign × 500 jurisdictions hydrates without raising any exception."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(500)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=500,
        )
        db = _make_db_session(campaign, project_id=uuid.uuid4())

        service = CampaignHydrationService(db)
        jurisdiction_ids = await service.hydrate(campaign_id)

        assert len(jurisdiction_ids) == 500
        assert campaign.status != CampaignStatus.FAILED

    @pytest.mark.slow
    async def test_small_campaign_execution_real_runner(self, celery_eager, db_engine):
        """End-to-end campaign execution via the real Celery chain in eager mode.

        Test data is committed to the test DB so every task's own session
        (via the patched ``AsyncSessionLocal`` / ``SyncSessionLocal``) can
        find the campaign.  External services are still mocked.
        """
        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession

        from app.api.modules.v1.organization.models.organization_model import Organization

        campaign_id = uuid.uuid4()
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # --- Insert committed test data ---
        async with SAAsyncSession(db_engine, expire_on_commit=False) as setup:
            async with setup.begin():
                setup.add(Organization(id=org_id, name="Scale Org", email="scale@test.com"))
                from app.api.modules.v1.projects.models.project_model import Project
                from app.api.modules.v1.users.models.users_model import User

                setup.add(
                    User(
                        id=user_id,
                        email="scale@test.com",
                        name="Scale User",
                        is_active=True,
                        is_approved=True,
                        is_superadmin=True,
                    )
                )
                setup.add(
                    Project(
                        id=project_id,
                        org_id=org_id,
                        title="Scale Project",
                    )
                )
                await setup.flush()  # FK deps must exist before campaign
                setup.add(
                    Campaign(
                        id=campaign_id,
                        organization_id=org_id,
                        project_id=project_id,
                        name="Scale Real Runner",
                        industry="EOR",
                        status=CampaignStatus.DRAFT,
                        taxonomy_json=_make_taxonomy_with_n_nodes(5),
                        max_jurisdictions=5,
                        created_by=user_id,
                    )
                )
                for i in range(5):
                    setup.add(
                        Jurisdiction(
                            project_id=project_id,
                            campaign_id=campaign_id,
                            name=f"Preseeded Jurisdiction {i}",
                            description=f"Preseeded test jurisdiction {i}",
                            prompt=f"Collect compliance rules for jurisdiction {i}",
                            discovery_status=DiscoveryStatus.DISCOVERED,
                        )
                    )

        # --- Create orchestration service with a real session ---
        async with SAAsyncSession(db_engine, expire_on_commit=False) as svc_session:
            celery_control = MagicMock()
            service = CampaignOrchestrationService(db=svc_session, celery_control=celery_control)

            def _fake_trigger_jurisdiction_scrape(service_self, jurisdiction_id):
                from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
                    JurisdictionScrapeJob,
                    JurisdictionScrapeJobStatus,
                )

                now = datetime.now(timezone.utc)
                job = JurisdictionScrapeJob(
                    jurisdiction_id=jurisdiction_id,
                    status=JurisdictionScrapeJobStatus.COMPLETED,
                    total_sources=0,
                    successful_sources=0,
                    started_at=now,
                    completed_at=now,
                )
                service_self.db.add(job)
                service_self.db.commit()
                return job

            # Mock only external service calls
            svc_base = "app.api.modules.v1.campaigns"

            from uuid import UUID

            from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
                JurisdictionScrapeJob,
                JurisdictionScrapeJobStatus,
            )

            def _eager_send_task(name, args=None, **kwargs):
                if name.endswith("dispatch_single_jurisdiction_scrape"):
                    from app.api.modules.v1.campaigns.tasks.campaign_tasks import (
                        SyncSessionLocal,
                    )

                    jurisdiction_id = UUID(args[0])
                    now = datetime.now(timezone.utc)
                    with SyncSessionLocal() as db:
                        job = JurisdictionScrapeJob(
                            jurisdiction_id=jurisdiction_id,
                            status=JurisdictionScrapeJobStatus.COMPLETED,
                            total_sources=0,
                            successful_sources=0,
                            started_at=now,
                            completed_at=now,
                        )
                        db.add(job)
                        db.commit()

            with (
                patch(
                    f"{svc_base}.service.taxonomy_generation_service"
                    ".TaxonomyGenerationService.generate",
                    new_callable=AsyncMock,
                ) as m_tax,
                patch(
                    f"{svc_base}.service.campaign_hydration_service"
                    ".CampaignHydrationService.hydrate",
                    new_callable=AsyncMock,
                ) as m_hyd,
                patch(
                    f"{svc_base}.service.campaign_source_discovery_service"
                    ".CampaignSourceDiscoveryService.discover_all",
                    new_callable=AsyncMock,
                ) as m_disc,
                patch(
                    "app.api.modules.v1.scraping.service.jurisdiction_scraping_service"
                    ".JurisdictionScrapingService.trigger_jurisdiction_scrape",
                    new=_fake_trigger_jurisdiction_scrape,
                ),
                patch(
                    "app.api.modules.v1.jurisdictions.service.blog_generation_service"
                    ".BlogGenerationService.generate_blog_post_sync"
                ),
                patch(
                    "app.api.modules.v1.campaigns.tasks.campaign_tasks.celery_app.send_task",
                    side_effect=_eager_send_task,
                ),
            ):
                m_tax.return_value = _make_taxonomy_with_n_nodes(5)
                m_hyd.return_value = [uuid.uuid4() for _ in range(5)]
                m_disc.return_value = {"total": 5, "succeeded": 5, "failed": 0}

                await service.run(campaign_id)

        # Verify campaign progressed past DRAFT
        async with SAAsyncSession(db_engine, expire_on_commit=False) as verify:
            refreshed = await verify.get(Campaign, campaign_id)
            assert refreshed is not None
            assert refreshed.status != CampaignStatus.DRAFT
            assert refreshed.status != CampaignStatus.FAILED

    @pytest.mark.slow
    async def test_stats_populated_correctly_after_large_hydration(self):
        """Campaign.stats contains total_jurisdictions and hydration_completed_at
        after hydration."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(500)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=500,
        )
        db = _make_db_session(campaign, project_id=uuid.uuid4())

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        assert campaign.stats is not None
        assert campaign.stats["total_jurisdictions"] == 500
        assert "hydration_completed_at" in campaign.stats
        datetime.fromisoformat(campaign.stats["hydration_completed_at"])

    @pytest.mark.slow
    async def test_execution_log_completed_items_matches_jurisdiction_count(self):
        """CampaignExecutionLog.completed_items equals the number of created jurisdictions."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(500)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=500,
        )

        exec_logs_added: List[CampaignExecutionLog] = []
        db = _make_db_session(campaign, project_id=uuid.uuid4())
        original_add = db.add.side_effect

        def _tracking_add(obj):
            if original_add:
                original_add(obj)
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        db.add.side_effect = _tracking_add

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        assert len(exec_logs_added) >= 1
        assert exec_logs_added[0].completed_items == 500

    @pytest.mark.slow
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep",
        new_callable=AsyncMock,
    )
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_source_discovery_500_jurisdictions_completes_without_5xx(
        self,
        MockDiscoverySvc,
        MockSourceSvc,
        mock_sleep,
    ):
        """Source discovery for 500 jurisdictions completes without ProcessingError."""
        campaign_id = uuid.uuid4()
        jurisdictions = [
            _make_jurisdiction_mock(campaign_id=campaign_id, name=f"Jurisdiction_{i}")
            for i in range(500)
        ]
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.HYDRATING,
            max_jurisdictions=500,
        )
        campaign.jurisdictions = jurisdictions

        suggested = [
            SuggestedSource(
                title="Test Source",
                url="https://example.gov/laws",
                snippet="Official source",
                confidence_reason="Government domain",
                is_official=True,
            )
        ]

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=suggested)
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        created_source = MagicMock()
        created_source.id = uuid.uuid4()
        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(return_value=created_source)
        MockSourceSvc.return_value = mock_source_instance

        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        redis_mock = _make_redis_mock(incr_value=1)

        service = CampaignSourceDiscoveryService(db, redis_mock)
        summary = await service.discover_all(campaign_id)

        assert summary["total"] == 500
        assert summary["sources_created"] == 500
        assert summary["failed"] == 0


# ---------------------------------------------------------------------------
# 9.1b — Concurrent campaigns (no cross-contamination)
# ---------------------------------------------------------------------------


class TestConcurrentCampaigns:
    """Launch 3 campaigns simultaneously — assert no cross-contamination of campaign_id."""

    @pytest.mark.slow
    async def test_three_concurrent_campaigns_reach_generating_taxonomy_status(self):
        """3 concurrently launched campaigns all transition to GENERATING_TAXONOMY."""
        campaign_ids = [uuid.uuid4() for _ in range(3)]
        campaigns = [
            Campaign(
                id=cid,
                organization_id=uuid.uuid4(),
                name=f"Concurrent Campaign {i}",
                industry="EOR",
                status=CampaignStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for i, cid in enumerate(campaign_ids)
        ]

        async def _run_campaign(campaign: Campaign) -> Campaign:
            db = AsyncMock()
            db.get = AsyncMock(return_value=campaign)
            db.add = MagicMock()
            db.commit = AsyncMock()
            celery_control = MagicMock()

            with patch(
                "app.api.modules.v1.campaigns.service.campaign_orchestration_service.chain"
            ) as mock_chain:
                mock_result = MagicMock()
                mock_result.id = str(uuid.uuid4())
                mock_result.children = []
                mock_chain.return_value.on_error.return_value.apply_async.return_value = mock_result
                service = CampaignOrchestrationService(db=db, celery_control=celery_control)
                await service.run(campaign.id)

            return campaign

        results = await asyncio.gather(*[_run_campaign(c) for c in campaigns])

        for campaign in results:
            assert campaign.status == CampaignStatus.GENERATING_TAXONOMY

    @pytest.mark.slow
    async def test_jurisdiction_campaign_id_no_cross_contamination(self):
        """Jurisdictions carry the campaign_id of their own campaign, not a sibling's."""
        campaign_ids = [uuid.uuid4() for _ in range(3)]
        taxonomy = _make_taxonomy_with_n_nodes(10)

        async def _hydrate_campaign(campaign_id: uuid.UUID) -> List[Any]:
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=10,
            )
            all_added: List[Any] = []
            db = _make_db_session(campaign, project_id=uuid.uuid4())

            def _tracking_add(obj):
                if (
                    hasattr(obj, "project_id")
                    and hasattr(obj, "parent_id")
                    and hasattr(obj, "name")
                ):
                    if not getattr(obj, "id", None):
                        object.__setattr__(obj, "id", uuid.uuid4())
                    all_added.append(obj)

            db.add.side_effect = _tracking_add

            service = CampaignHydrationService(db)
            await service.hydrate(campaign_id)
            return all_added

        all_results = await asyncio.gather(*[_hydrate_campaign(cid) for cid in campaign_ids])

        for i, campaign_jurs in enumerate(all_results):
            expected_campaign_id = campaign_ids[i]
            for jur in campaign_jurs:
                assert jur.campaign_id == expected_campaign_id, (
                    f"Cross-contamination: jurisdiction campaign_id={jur.campaign_id}, "
                    f"expected={expected_campaign_id}"
                )

    @pytest.mark.slow
    async def test_execution_log_campaign_id_no_cross_contamination(self):
        """CampaignExecutionLog records are scoped to their parent campaign only."""
        campaign_ids = [uuid.uuid4() for _ in range(3)]
        taxonomy = _make_taxonomy_with_n_nodes(5)

        async def _hydrate_campaign(campaign_id: uuid.UUID) -> List[CampaignExecutionLog]:
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=5,
            )
            logs_added: List[CampaignExecutionLog] = []
            db = _make_db_session(campaign, project_id=uuid.uuid4())
            original_add = db.add.side_effect

            def _tracking_add(obj):
                if original_add:
                    original_add(obj)
                if isinstance(obj, CampaignExecutionLog):
                    logs_added.append(obj)

            db.add.side_effect = _tracking_add

            service = CampaignHydrationService(db)
            await service.hydrate(campaign_id)
            return logs_added

        all_logs = await asyncio.gather(*[_hydrate_campaign(cid) for cid in campaign_ids])

        for i, logs in enumerate(all_logs):
            for log in logs:
                assert log.campaign_id == campaign_ids[i], (
                    f"Log campaign_id={log.campaign_id}, expected={campaign_ids[i]}"
                )


# ---------------------------------------------------------------------------
# 9.1c — Hydration idempotency under load
# ---------------------------------------------------------------------------


class TestHydrationIdempotencyUnderLoad:
    """Trigger hydration twice concurrently; assert no duplicate jurisdictions created."""

    @pytest.mark.slow
    async def test_double_hydration_idempotent_via_integrity_error(self):
        """Second concurrent hydration resolves IntegrityErrors to existing IDs (no doubles)."""
        campaign_id = uuid.uuid4()
        project_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(50)
        existing_jur_ids = [uuid.uuid4() for _ in range(50)]

        @asynccontextmanager
        async def _fail_nested():
            raise IntegrityError("uix_project_name", {}, Exception("duplicate"))
            yield  # pragma: no cover

        rows = []
        for i, jur_id in enumerate(existing_jur_ids):
            row = MagicMock()
            row.parent_id = None
            row.name = f"Jurisdiction_{i}"
            row.id = jur_id
            rows.append(row)

        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter(rows))

        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=50,
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
        result = await service.hydrate(campaign_id)

        assert len(result) == 50
        db.commit.assert_called_once()

    @pytest.mark.slow
    async def test_concurrent_double_trigger_no_duplicate_jurisdiction_count(self):
        """Two concurrent hydrations of a 20-node taxonomy each return exactly 20 IDs."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(20)

        async def _run_normal_hydration() -> int:
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=20,
            )
            db = _make_db_session(campaign, project_id=uuid.uuid4())
            service = CampaignHydrationService(db)
            ids = await service.hydrate(campaign_id)
            return len(ids)

        async def _run_idempotent_hydration() -> int:
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=20,
            )
            existing_ids = [uuid.uuid4() for _ in range(20)]

            @asynccontextmanager
            async def _fail_nested():
                raise IntegrityError("uix", {}, Exception("dup"))
                yield  # pragma: no cover

            rows = []
            for i, jid in enumerate(existing_ids):
                row = MagicMock()
                row.parent_id = None
                row.name = f"Jurisdiction_{i}"
                row.id = jid
                rows.append(row)

            existing_result = MagicMock()
            existing_result.__iter__ = MagicMock(return_value=iter(rows))

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
            ids = await service.hydrate(campaign_id)
            return len(ids)

        first_count, second_count = await asyncio.gather(
            _run_normal_hydration(),
            _run_idempotent_hydration(),
        )

        assert first_count == 20
        assert second_count == 20


# ---------------------------------------------------------------------------
# 9.1d — Celery Beat timing
# ---------------------------------------------------------------------------


class TestCeleryBeatDispatch:
    """Assert dispatch_due_jurisdictions enqueues all overdue jobs without duplicates.

    Note: dispatch_due_jurisdictions queries with ``limit(10)`` per Beat cycle.
    For deployments with 1000+ jurisdictions, the task runs every 15 minutes
    and processes up to 10 per cycle. These tests validate correct behavior
    within a single cycle: all 10 queried jurisdictions are dispatched exactly once.
    """

    def test_dispatch_due_jurisdictions_enqueues_all_overdue_jobs(
        self, pg_sync_session, monkeypatch
    ):
        """All 10 due jurisdictions returned by DB query are dispatched in one cycle."""
        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency
        from app.api.modules.v1.scraping.service.tasks import dispatch_due_jurisdictions

        now = datetime.now(timezone.utc)
        mock_jurs = []
        for i in range(10):
            jur = MagicMock()
            jur.id = uuid.uuid4()
            jur.name = f"Jurisdiction_{i}"
            jur.enable_auto_scrape = True
            jur.is_deleted = False
            jur.next_scrape_time = None
            jur.scrape_frequency = ScrapeFrequency.DAILY
            mock_jurs.append(jur)

        pg_sync_session.exec = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=mock_jurs))
        )
        pg_sync_session.add = MagicMock()
        pg_sync_session.commit = MagicMock()

        dispatched_ids: List[uuid.UUID] = []
        mock_scraping_service = MagicMock()
        mock_scraping_service.trigger_jurisdiction_scrape.side_effect = lambda jur_id: (
            dispatched_ids.append(jur_id)
        )
        mock_scraping_service._calculate_next_scrape_time.return_value = now

        mock_sync_redis = MagicMock()
        mock_sync_redis.set.return_value = True
        mock_sync_redis.delete.return_value = 1

        with (
            patch(
                "app.api.modules.v1.scraping.service.tasks.JurisdictionScrapingService",
                return_value=mock_scraping_service,
            ),
            patch("app.api.modules.v1.scraping.service.tasks.redis") as mock_redis_module,
        ):
            mock_redis_module.Redis.return_value = mock_sync_redis
            task_fn = dispatch_due_jurisdictions
            result = task_fn.run()

        assert result.startswith("Dispatched"), f"Expected 'Dispatched ...', got: {result!r}"
        dispatched_count = int(result.split()[1])
        assert dispatched_count == 10

    def test_dispatch_due_jurisdictions_no_duplicate_dispatches(self, pg_sync_session, monkeypatch):
        """Each due jurisdiction is dispatched exactly once per Beat cycle (no duplicates)."""
        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency
        from app.api.modules.v1.scraping.service.tasks import dispatch_due_jurisdictions

        now = datetime.now(timezone.utc)
        jur_ids = set()
        mock_jurs = []
        for i in range(10):
            jur = MagicMock()
            jur_id = uuid.uuid4()
            jur.id = jur_id
            jur.name = f"Jurisdiction_{i}"
            jur.enable_auto_scrape = True
            jur.is_deleted = False
            jur.next_scrape_time = None
            jur.scrape_frequency = ScrapeFrequency.DAILY
            mock_jurs.append(jur)
            jur_ids.add(jur_id)

        pg_sync_session.exec = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=mock_jurs))
        )
        pg_sync_session.add = MagicMock()
        pg_sync_session.commit = MagicMock()

        dispatched_ids: List[uuid.UUID] = []
        mock_scraping_service = MagicMock()
        mock_scraping_service.trigger_jurisdiction_scrape.side_effect = lambda jur_id: (
            dispatched_ids.append(jur_id)
        )
        mock_scraping_service._calculate_next_scrape_time.return_value = now

        mock_sync_redis = MagicMock()
        mock_sync_redis.set.return_value = True
        mock_sync_redis.delete.return_value = 1

        with (
            patch(
                "app.api.modules.v1.scraping.service.tasks.JurisdictionScrapingService",
                return_value=mock_scraping_service,
            ),
            patch("app.api.modules.v1.scraping.service.tasks.redis") as mock_redis_module,
        ):
            mock_redis_module.Redis.return_value = mock_sync_redis
            task_fn = dispatch_due_jurisdictions
            task_fn.run()

        assert len(dispatched_ids) == len(set(dispatched_ids)), (
            "Duplicate jurisdiction dispatches detected in a single Beat cycle"
        )
        assert all(jid in jur_ids for jid in dispatched_ids)

    def test_dispatch_skips_when_lock_held(self, pg_sync_session):
        """Beat task returns early when the distributed lock is already held."""
        from app.api.modules.v1.scraping.service.tasks import dispatch_due_jurisdictions

        mock_sync_redis = MagicMock()
        mock_sync_redis.set.return_value = False  # Lock NOT acquired

        with patch("app.api.modules.v1.scraping.service.tasks.redis") as mock_redis_module:
            mock_redis_module.Redis.return_value = mock_sync_redis
            result = dispatch_due_jurisdictions.run()

        assert "Skipped" in result


# ---------------------------------------------------------------------------
# 9.4 — Monitoring assertions
# ---------------------------------------------------------------------------


class TestMonitoringAssertions:
    """Verify monitoring data integrity during and after a campaign run."""

    async def test_status_endpoint_returns_campaign_id_and_status(self):
        """GET /campaigns/{id}/status returns campaign_id and current status."""
        campaign_id = uuid.uuid4()
        campaign = Campaign(
            id=campaign_id,
            organization_id=uuid.uuid4(),
            name="Monitor Test",
            industry="EOR",
            status=CampaignStatus.HYDRATING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db = AsyncMock()
        db.get = AsyncMock(return_value=campaign)
        db.add = MagicMock()
        db.commit = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        service = CampaignOrchestrationService(db=db, celery_control=MagicMock())
        result = await service.get_status(campaign_id)

        assert result["campaign_id"] == str(campaign_id)
        assert result["status"] == CampaignStatus.HYDRATING.value

    async def test_execution_log_completed_at_non_null_after_hydration(self):
        """CampaignExecutionLog.completed_at is set (non-null) after hydration finishes."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(5)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=5,
        )

        exec_logs_added: List[CampaignExecutionLog] = []
        db = _make_db_session(campaign, project_id=uuid.uuid4())
        original_add = db.add.side_effect

        def _tracking_add(obj):
            if original_add:
                original_add(obj)
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        db.add.side_effect = _tracking_add

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        assert len(exec_logs_added) >= 1
        final_log = exec_logs_added[0]
        assert final_log.completed_at is not None, (
            "CampaignExecutionLog.completed_at must be set after hydration completes"
        )

    async def test_redis_progress_channel_emits_events_during_hydration(self):
        """campaign_progress:{campaign_id} Redis channel receives at least one event per phase."""
        import app.api.modules.v1.campaigns.tasks.campaign_tasks as campaign_tasks_module

        campaign_id = str(uuid.uuid4())
        published_channels: List[str] = []

        mock_sync_client = MagicMock()

        def _capture_publish(channel, payload):
            published_channels.append(channel)

        mock_sync_client.publish.side_effect = _capture_publish

        with patch.object(campaign_tasks_module, "_sync_redis_client", mock_sync_client):
            campaign_tasks_module._publish_progress(campaign_id, "hydration", 1, 5)
            campaign_tasks_module._publish_progress(campaign_id, "source_discovery", 1, 5)
            campaign_tasks_module._publish_progress(campaign_id, "taxonomy", 1, 5)

        expected_channel = f"campaign_progress:{campaign_id}"
        assert all(ch == expected_channel for ch in published_channels)
        assert len(published_channels) == 3

    async def test_execution_log_phase_field_set(self):
        """CampaignExecutionLog.phase is set to 'hydration' for the hydration phase."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(3)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=3,
        )

        exec_logs_added: List[CampaignExecutionLog] = []
        db = _make_db_session(campaign, project_id=uuid.uuid4())
        original_add = db.add.side_effect

        def _tracking_add(obj):
            if original_add:
                original_add(obj)
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        db.add.side_effect = _tracking_add

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        assert len(exec_logs_added) >= 1
        assert exec_logs_added[0].phase == "hydration"

    async def test_execution_log_total_items_set_correctly(self):
        """CampaignExecutionLog.total_items equals the number of jurisdictions processed."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(7)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=7,
        )

        exec_logs_added: List[CampaignExecutionLog] = []
        db = _make_db_session(campaign, project_id=uuid.uuid4())
        original_add = db.add.side_effect

        def _tracking_add(obj):
            if original_add:
                original_add(obj)
            if isinstance(obj, CampaignExecutionLog):
                exec_logs_added.append(obj)

        db.add.side_effect = _tracking_add

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        assert exec_logs_added[0].total_items == 7
