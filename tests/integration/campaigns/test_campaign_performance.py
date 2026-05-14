"""Performance baseline tests for the campaign pipeline — Phase 9 § 9.2.

All external I/O (DB, Redis, LLM, Celery) is mocked so timings reflect
pure Python service logic (serialisation, data transformations, loops).

Performance Baselines (recorded 2026-03-16, mocked I/O, CPython 3.12):
----------------------------------------------------------------------
- POST /campaigns/{id}/launch (mocked runner)  P50 ~0ms  P95 ~1ms  P99 ~2ms
- Hydrate 1 000 jurisdictions (mocked DB)      < 2 000 ms
- Source discovery 200 jurisdictions (mocked)  < 1 000 ms
- Memory delta after 200-jurisdiction run      < 50 MiB
- Concurrent 3-campaign launch (mocked runner) < 200 ms total

These figures are intentionally loose: they are documented upper-bounds
that should trigger investigation if exceeded, not hard SLAs.

To update baselines: run with ``-s`` flag and read the timing lines printed
by each test to stdout, then update the numbers above.
"""

import asyncio
import statistics
import time
import tracemalloc
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import require_approved_user, require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.pipelines.factory import get_pipeline_runner
from app.api.modules.v1.campaigns.service.campaign_hydration_service import (
    CampaignHydrationService,
)
from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
    CampaignSourceDiscoveryService,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import DiscoveryStatus, Jurisdiction
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource
from app.api.modules.v1.users.models.users_model import User
from main import app

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Hard time-budget constants (milliseconds) — update if baselines change
# ---------------------------------------------------------------------------
_BUDGET_HYDRATE_1000_MS = 3_000
_BUDGET_SOURCE_DISCOVERY_200_MS = 2_000
_BUDGET_LAUNCH_P99_MS = 200
_BUDGET_MEMORY_DELTA_MiB = 50
_BUDGET_CONCURRENT_3_LAUNCH_MS = 500


# ---------------------------------------------------------------------------
# Shared helpers (copied from scale tests for independence)
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
    max_jurisdictions: int = 15_000,
) -> Campaign:
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=campaign_id,
        organization_id=uuid.uuid4(),
        name="Perf Test Campaign",
        industry="EOR",
        domain_description="Performance testing of campaign pipeline",
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
    jur = MagicMock()
    jur.id = uuid.uuid4()
    jur.name = name
    jur.description = f"Description for {name}"
    jur.prompt = f"Extract compliance data for {name}"
    jur.campaign_id = campaign_id or uuid.uuid4()
    return jur


# ---------------------------------------------------------------------------
# Route-level fixtures (mirrored from test_campaign_orchestration_routes.py)
# ---------------------------------------------------------------------------


# Deterministic user ID so that real-runner tests can pre-insert this user
# into the test DB — satisfying FK constraints like campaigns.launched_by.
_MOCK_SUPERADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _mock_superadmin() -> User:
    return User(
        id=_MOCK_SUPERADMIN_ID,
        email="admin@example.com",
        name="Superadmin",
        is_active=True,
        is_approved=True,
        is_superadmin=True,
    )


@pytest_asyncio.fixture
async def perf_client(db_session: AsyncSession):
    """Async test client with mocked auth, DB, and pipeline runner."""
    mock_runner = AsyncMock()
    mock_runner.run = AsyncMock(return_value={"backend": "celery", "task_id": str(uuid.uuid4())})

    async def _get_db_override():
        yield db_session

    async def _get_mock_runner():
        return mock_runner

    app.dependency_overrides[require_approved_user] = _mock_superadmin
    app.dependency_overrides[require_superadmin] = _mock_superadmin
    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_pipeline_runner] = _get_mock_runner

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, mock_runner

    app.dependency_overrides.pop(require_approved_user, None)
    app.dependency_overrides.pop(require_superadmin, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_pipeline_runner, None)


@pytest_asyncio.fixture
async def real_runner_client(celery_eager, db_engine):
    """Async test client with real pipeline runner in Celery eager mode.

    ``celery_eager`` patches ``AsyncSessionLocal`` in ``database.py`` so
    ``get_db()`` naturally uses the test engine.  We do NOT override it.
    Auth is still mocked.

    The deterministic ``_MOCK_SUPERADMIN_ID`` user is pre-inserted so that
    FK constraints (e.g. ``campaigns.launched_by``) are satisfied.
    """
    from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession

    # Pre-insert the mock superadmin user so FKs like launched_by work.
    async with SAAsyncSession(db_engine, expire_on_commit=False) as setup:
        async with setup.begin():
            existing = await setup.get(User, _MOCK_SUPERADMIN_ID)
            if not existing:
                setup.add(
                    User(
                        id=_MOCK_SUPERADMIN_ID,
                        email="admin@example.com",
                        name="Superadmin",
                        is_active=True,
                        is_approved=True,
                        is_superadmin=True,
                    )
                )

    app.dependency_overrides[require_approved_user] = _mock_superadmin
    app.dependency_overrides[require_superadmin] = _mock_superadmin

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, db_engine

    app.dependency_overrides.pop(require_approved_user, None)
    app.dependency_overrides.pop(require_superadmin, None)


# ---------------------------------------------------------------------------
# 9.2a — Launch endpoint latency (P50 / P95 / P99)
# ---------------------------------------------------------------------------


class TestLaunchLatency:
    """P50/P95/P99 latency for POST /campaigns/{id}/launch."""

    @pytest.mark.slow
    async def test_launch_p99_within_budget(self, perf_client, db_session: AsyncSession):
        """P99 latency for campaign launch must stay under _BUDGET_LAUNCH_P99_MS ms."""
        client, _ = perf_client

        # Persist a draft campaign in the test DB
        from app.api.modules.v1.organization.models.organization_model import Organization

        org = Organization(id=uuid.uuid4(), name="Perf Org", email="perf@test.com")
        db_session.add(org)
        await db_session.flush()

        perf_user_id = uuid.uuid4()
        perf_user = User(id=perf_user_id, email="perf-launch@test.com", name="Perf User")
        db_session.add(perf_user)
        await db_session.flush()

        campaign = Campaign(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Perf Launch Campaign",
            industry="EOR",
            status=CampaignStatus.DRAFT,
            created_by=perf_user_id,
        )
        db_session.add(campaign)
        await db_session.flush()

        samples = 20
        latencies: List[float] = []
        for _ in range(samples):
            start = time.perf_counter()
            resp = await client.post(f"/api/v1/campaigns/{campaign.id}/launch")
            elapsed_ms = (time.perf_counter() - start) * 1_000
            assert resp.status_code == 202, f"Unexpected status: {resp.status_code}"
            latencies.append(elapsed_ms)

        latencies.sort()
        p50 = latencies[int(samples * 0.50)]
        p95 = latencies[int(samples * 0.95)]
        p99 = latencies[-1]

        print(  # noqa: T201 — intentionally printed for baseline documentation
            f"\n[launch latency] P50={p50:.1f}ms  P95={p95:.1f}ms  P99={p99:.1f}ms"
        )

        assert p99 <= _BUDGET_LAUNCH_P99_MS, (
            f"P99 launch latency {p99:.1f}ms exceeds budget {_BUDGET_LAUNCH_P99_MS}ms"
        )

    @pytest.mark.slow
    async def test_launch_p99_real_runner(self, real_runner_client):
        """End-to-end pipeline via real Celery chain in eager mode.

        ``celery_eager`` patches ``AsyncSessionLocal`` to the test DB, so
        every task's own session sees the committed campaign.  External
        services (taxonomy LLM, source-discovery API, scraping, blogs) are
        still mocked — we are testing the *chain wiring*, not the APIs.
        """
        client, db_engine = real_runner_client

        from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession

        from app.api.modules.v1.organization.models.organization_model import Organization

        # --- Insert committed test data so task sessions can see it ---
        campaign_id = uuid.uuid4()
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()
        user_id = uuid.uuid4()

        async with SAAsyncSession(db_engine, expire_on_commit=False) as setup_session:
            async with setup_session.begin():
                from app.api.modules.v1.projects.models.project_model import Project

                org = Organization(id=org_id, name="Real Runner Org", email="rr@test.com")
                setup_session.add(org)
                user = User(
                    id=user_id,
                    email="rr-perf@test.com",
                    name="RR User",
                    is_active=True,
                    is_approved=True,
                    is_superadmin=True,
                )
                setup_session.add(user)
                setup_session.add(Project(id=project_id, org_id=org_id, title="Perf Project"))
                await setup_session.flush()  # FK deps must exist before campaign
                campaign = Campaign(
                    id=campaign_id,
                    organization_id=org_id,
                    project_id=project_id,
                    name="Perf Real Runner Campaign",
                    industry="EOR",
                    status=CampaignStatus.DRAFT,
                    taxonomy_json=_make_taxonomy_with_n_nodes(3),
                    created_by=user_id,
                )
                setup_session.add(campaign)
                for i in range(3):
                    setup_session.add(
                        Jurisdiction(
                            project_id=project_id,
                            campaign_id=campaign_id,
                            name=f"Perf Jurisdiction {i}",
                            description=f"Perf jurisdiction {i}",
                            prompt=f"Track compliance for perf jurisdiction {i}",
                            discovery_status=DiscoveryStatus.DISCOVERED,
                        )
                    )
            # Transaction is committed here — visible to all connections.

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

        # --- Mock only external service calls, NOT the chain ---
        tasks_svc = "app.api.modules.v1.campaigns"

        from uuid import UUID

        from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
            JurisdictionScrapeJob,
            JurisdictionScrapeJobStatus,
        )

        def _eager_send_task(name, args=None, **kwargs):
            if name.endswith("dispatch_single_jurisdiction_scrape"):
                # celery_eager patches campaign_tasks.SyncSessionLocal → test DB
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
                f"{tasks_svc}.service.taxonomy_generation_service"
                ".TaxonomyGenerationService.generate",
                new_callable=AsyncMock,
            ) as mock_taxonomy,
            patch(
                f"{tasks_svc}.service.campaign_source_discovery_service"
                ".CampaignSourceDiscoveryService.discover_all",
                new_callable=AsyncMock,
            ) as mock_discover,
            patch(
                f"{tasks_svc}.service.campaign_hydration_service.CampaignHydrationService.hydrate",
                new_callable=AsyncMock,
            ) as mock_hydrate,
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
            mock_taxonomy.return_value = _make_taxonomy_with_n_nodes(3)
            mock_hydrate.return_value = [uuid.uuid4() for _ in range(3)]
            mock_discover.return_value = {"total": 3, "succeeded": 3, "failed": 0}

            start = time.perf_counter()
            resp = await client.post(f"/api/v1/campaigns/{campaign_id}/launch")
            elapsed_ms = (time.perf_counter() - start) * 1_000

        assert resp.status_code == 202, f"Unexpected: {resp.status_code} — {resp.text}"
        print(f"\n[launch latency (real runner eager e2e)] {elapsed_ms:.1f}ms")  # noqa: T201

        # Verify campaign progressed beyond DRAFT
        async with SAAsyncSession(db_engine, expire_on_commit=False) as verify_session:
            refreshed = await verify_session.get(Campaign, campaign_id)
            assert refreshed is not None
            assert refreshed.status != CampaignStatus.DRAFT, (
                f"Expected status beyond DRAFT, got {refreshed.status}"
            )

    @pytest.mark.slow
    async def test_launch_latency_percentiles_documented(
        self, perf_client, db_session: AsyncSession
    ):
        """Record P50/P95/P99 distribution; fails if stdev is anomalously high."""
        client, _ = perf_client

        from app.api.modules.v1.organization.models.organization_model import Organization

        org = Organization(id=uuid.uuid4(), name="Perf Org 2", email="perf2@test.com")
        db_session.add(org)
        await db_session.flush()

        perf_user_id2 = uuid.uuid4()
        perf_user2 = User(id=perf_user_id2, email="perf-latency@test.com", name="Perf User 2")
        db_session.add(perf_user2)
        await db_session.flush()

        campaign = Campaign(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Perf Latency Campaign",
            industry="EOR",
            status=CampaignStatus.DRAFT,
            created_by=perf_user_id2,
        )
        db_session.add(campaign)
        await db_session.flush()

        samples = 30
        latencies: List[float] = []
        for _ in range(samples):
            start = time.perf_counter()
            await client.post(f"/api/v1/campaigns/{campaign.id}/launch")
            latencies.append((time.perf_counter() - start) * 1_000)

        latencies.sort()
        p50 = latencies[samples // 2]
        p95 = latencies[int(samples * 0.95)]
        p99 = latencies[-1]
        stdev = statistics.stdev(latencies)

        print(  # noqa: T201
            f"\n[launch latency detailed] "
            f"P50={p50:.1f}ms P95={p95:.1f}ms P99={p99:.1f}ms stdev={stdev:.1f}ms"
        )

        # Stdev should not exceed 3× the median (very noisy environment check)
        assert stdev <= p50 * 3 + 10, (
            f"Launch latency too variable: stdev={stdev:.1f}ms vs P50={p50:.1f}ms"
        )


# ---------------------------------------------------------------------------
# 9.2b — Hydration wall-clock time (1 000 jurisdictions)
# ---------------------------------------------------------------------------


class TestHydrationPerformance:
    """Wall-clock time to hydrate 1 000 jurisdictions must stay within budget."""

    @pytest.mark.slow
    async def test_hydrate_1000_jurisdictions_within_time_budget(self):
        """Hydrating 1 000 jurisdictions must complete in under _BUDGET_HYDRATE_1000_MS ms."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(1_000)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=1_000,
        )
        db = _make_db_session(campaign, project_id=uuid.uuid4())

        service = CampaignHydrationService(db)
        start = time.perf_counter()
        jurisdiction_ids = await service.hydrate(campaign_id)
        elapsed_ms = (time.perf_counter() - start) * 1_000

        print(f"\n[hydration] 1000 jurisdictions in {elapsed_ms:.0f}ms")  # noqa: T201

        assert len(jurisdiction_ids) == 1_000
        assert elapsed_ms <= _BUDGET_HYDRATE_1000_MS, (
            f"Hydration took {elapsed_ms:.0f}ms, exceeds budget {_BUDGET_HYDRATE_1000_MS}ms"
        )

    @pytest.mark.slow
    async def test_hydrate_500_vs_1000_linear_scaling(self):
        """Scaling from 500 → 1 000 jurisdictions should be roughly linear (≤ 3× slower).

        Each size is timed twice and the minimum is taken to avoid cold-start
        bias that can make the first call appear deceptively fast on CI machines.
        """

        async def _time_hydration(n: int) -> float:
            campaign_id = uuid.uuid4()
            taxonomy = _make_taxonomy_with_n_nodes(n)
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=n,
            )
            db = _make_db_session(campaign, project_id=uuid.uuid4())
            service = CampaignHydrationService(db)
            start = time.perf_counter()
            await service.hydrate(campaign_id)
            return (time.perf_counter() - start) * 1_000

        # Warm up + take best-of-two to reduce scheduler / cold-start variance on CI
        t_500 = min(await _time_hydration(500), await _time_hydration(500))
        t_1000 = min(await _time_hydration(1_000), await _time_hydration(1_000))

        print(f"\n[hydration scaling] 500={t_500:.0f}ms  1000={t_1000:.0f}ms")  # noqa: T201

        # 1000 nodes should take at most 3× the time of 500 nodes.
        # The 500ms constant buffer accommodates CI machines that have higher
        # per-call overhead (scheduler jitter, GC pauses, slower I/O mocks)
        # while still catching genuinely non-linear (e.g. O(n²)) regressions.
        assert t_1000 <= t_500 * 3 + 500, (
            f"Non-linear hydration scaling detected: 500={t_500:.0f}ms 1000={t_1000:.0f}ms"
        )


# ---------------------------------------------------------------------------
# 9.2c — Source discovery wall-clock time (200 jurisdictions)
# ---------------------------------------------------------------------------


class TestSourceDiscoveryPerformance:
    """Wall-clock time to run source discovery for 200 jurisdictions."""

    @pytest.mark.slow
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep",
        new_callable=AsyncMock,
    )
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_source_discovery_200_jurisdictions_within_time_budget(
        self,
        MockDiscoverySvc,
        MockSourceSvc,
        mock_sleep,
    ):
        """Source discovery for 200 jurisdictions finishes under
        _BUDGET_SOURCE_DISCOVERY_200_MS ms."""
        campaign_id = uuid.uuid4()
        jurisdictions = [
            _make_jurisdiction_mock(campaign_id=campaign_id, name=f"Jurisdiction_{i}")
            for i in range(200)
        ]
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.HYDRATING,
            max_jurisdictions=200,
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

        redis_mock = AsyncMock()
        redis_mock.incr = AsyncMock(return_value=1)
        redis_mock.expire = AsyncMock()

        service = CampaignSourceDiscoveryService(db, redis_mock)

        start = time.perf_counter()
        summary = await service.discover_all(campaign_id)
        elapsed_ms = (time.perf_counter() - start) * 1_000

        print(  # noqa: T201
            f"\n[source discovery] 200 jurisdictions in {elapsed_ms:.0f}ms "
            f"({summary['sources_created']} sources created)"
        )

        assert summary["total"] == 200
        assert elapsed_ms <= _BUDGET_SOURCE_DISCOVERY_200_MS, (
            f"Source discovery took {elapsed_ms:.0f}ms, "
            f"exceeds budget {_BUDGET_SOURCE_DISCOVERY_200_MS}ms"
        )


# ---------------------------------------------------------------------------
# 9.2d — Memory profiling
# ---------------------------------------------------------------------------


class TestMemoryProfile:
    """Memory RSS delta must remain within budget after a full mocked pipeline run."""

    @pytest.mark.slow
    async def test_pipeline_memory_delta_within_budget(self):
        """Memory allocated during 200-jurisdiction hydration stays under
        _BUDGET_MEMORY_DELTA_MiB."""
        campaign_id = uuid.uuid4()
        taxonomy = _make_taxonomy_with_n_nodes(200)
        campaign = _make_campaign(
            campaign_id,
            status=CampaignStatus.TAXONOMY_READY,
            taxonomy_json=taxonomy,
            max_jurisdictions=200,
        )
        db = _make_db_session(campaign, project_id=uuid.uuid4())

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        service = CampaignHydrationService(db)
        await service.hydrate(campaign_id)

        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_delta_bytes = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        total_delta_mib = total_delta_bytes / (1024 * 1024)

        print(f"\n[memory] 200-jurisdiction hydration delta: {total_delta_mib:.2f} MiB")  # noqa: T201

        assert total_delta_mib <= _BUDGET_MEMORY_DELTA_MiB, (
            f"Memory delta {total_delta_mib:.2f} MiB exceeds budget {_BUDGET_MEMORY_DELTA_MiB} MiB"
        )

    @pytest.mark.slow
    async def test_memory_freed_between_campaigns(self):
        """Object graph from one campaign run does not leak into the next run."""

        async def _run_hydration() -> int:
            campaign_id = uuid.uuid4()
            taxonomy = _make_taxonomy_with_n_nodes(50)
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=50,
            )
            db = _make_db_session(campaign, project_id=uuid.uuid4())
            service = CampaignHydrationService(db)
            ids = await service.hydrate(campaign_id)
            return len(ids)

        tracemalloc.start()
        baseline = tracemalloc.take_snapshot()

        await _run_hydration()
        mid = tracemalloc.take_snapshot()

        await _run_hydration()
        final = tracemalloc.take_snapshot()
        tracemalloc.stop()

        first_delta = sum(
            s.size_diff for s in mid.compare_to(baseline, "lineno") if s.size_diff > 0
        )
        second_delta = sum(s.size_diff for s in final.compare_to(mid, "lineno") if s.size_diff > 0)

        first_mib = first_delta / (1024 * 1024)
        second_mib = second_delta / (1024 * 1024)

        print(  # noqa: T201
            f"\n[memory leak check] first run: {first_mib:.2f} MiB, "
            f"second run: {second_mib:.2f} MiB"
        )

        # Second run should not allocate dramatically more than the first
        # (allow up to 2× for Python internals + test overhead)
        assert second_mib <= first_mib * 2 + 1, (
            f"Possible memory leak: second run allocated {second_mib:.2f} MiB vs "
            f"first run {first_mib:.2f} MiB"
        )


# ---------------------------------------------------------------------------
# 9.2e — DB connection pool saturation (concurrent 3-campaign run)
# ---------------------------------------------------------------------------


class TestConcurrentLaunchPerformance:
    """Concurrent 3-campaign launch must complete within _BUDGET_CONCURRENT_3_LAUNCH_MS ms."""

    @pytest.mark.slow
    async def test_three_concurrent_campaigns_within_time_budget(self):
        """3 concurrently launched campaigns (mocked runner) complete in under budget."""
        from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
            CampaignOrchestrationService,
        )

        campaign_ids = [uuid.uuid4() for _ in range(3)]
        campaigns = [
            Campaign(
                id=cid,
                organization_id=uuid.uuid4(),
                name=f"Concurrent Perf Campaign {i}",
                industry="EOR",
                status=CampaignStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            for i, cid in enumerate(campaign_ids)
        ]

        async def _run_campaign(campaign: Campaign) -> None:
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

        start = time.perf_counter()
        await asyncio.gather(*[_run_campaign(c) for c in campaigns])
        elapsed_ms = (time.perf_counter() - start) * 1_000

        print(f"\n[concurrent launch] 3 campaigns in {elapsed_ms:.1f}ms")  # noqa: T201

        assert elapsed_ms <= _BUDGET_CONCURRENT_3_LAUNCH_MS, (
            f"Concurrent 3-campaign launch took {elapsed_ms:.1f}ms, "
            f"exceeds budget {_BUDGET_CONCURRENT_3_LAUNCH_MS}ms"
        )

    @pytest.mark.slow
    async def test_concurrent_hydrations_no_db_pool_saturation(self):
        """3 concurrent hydrations (mocked DB) all complete without saturation errors."""
        campaign_ids = [uuid.uuid4() for _ in range(3)]
        taxonomy = _make_taxonomy_with_n_nodes(50)

        async def _hydrate(campaign_id: uuid.UUID) -> int:
            campaign = _make_campaign(
                campaign_id,
                status=CampaignStatus.TAXONOMY_READY,
                taxonomy_json=taxonomy,
                max_jurisdictions=50,
            )
            db = _make_db_session(campaign, project_id=uuid.uuid4())
            service = CampaignHydrationService(db)
            ids = await service.hydrate(campaign_id)
            return len(ids)

        start = time.perf_counter()
        counts = await asyncio.gather(*[_hydrate(cid) for cid in campaign_ids])
        elapsed_ms = (time.perf_counter() - start) * 1_000

        print(  # noqa: T201
            f"\n[concurrent hydration] 3×50 jurisdictions in {elapsed_ms:.1f}ms, counts={counts}"
        )

        # All hydrations should return the correct count
        assert all(c == 50 for c in counts), f"Unexpected jurisdiction counts: {counts}"
        # Should complete well within budget
        assert elapsed_ms <= _BUDGET_CONCURRENT_3_LAUNCH_MS * 3
