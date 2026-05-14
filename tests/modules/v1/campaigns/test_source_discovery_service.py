"""Tests for CampaignSourceDiscoveryService — fully mocked DB / Redis / Parallel.ai."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
    INTER_JURISDICTION_DELAY_SECONDS,
    CampaignSourceDiscoveryService,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
    DiscoveryStatus,
    Jurisdiction,
)
from app.api.modules.v1.scraping.schemas.source_discovery_schema import SuggestedSource
from app.api.modules.v1.scraping.validators.exception import DuplicateSourceError

CAMPAIGN_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()
JUR_ID_1 = uuid.uuid4()
JUR_ID_2 = uuid.uuid4()


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_jurisdiction(
    jur_id: uuid.UUID = None,
    name: str = "United States",
    prompt: str = "Extract US federal EOR compliance data",
) -> MagicMock:
    jur = MagicMock()
    jur.id = jur_id or uuid.uuid4()
    jur.name = name
    jur.prompt = prompt
    jur.campaign_id = CAMPAIGN_ID
    jur.discovery_status = DiscoveryStatus.PENDING
    return jur


def _make_campaign(
    status: CampaignStatus = CampaignStatus.HYDRATING,
    jurisdictions: Optional[List[Any]] = None,
    sources_per_jurisdiction: int = 5,
) -> Campaign:
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=CAMPAIGN_ID,
        organization_id=ORG_ID,
        name="EOR Compliance",
        industry="EOR",
        domain_description="Employer of Record regulatory tracking",
        target_depth=CampaignTargetDepth.STATE,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        monitor_cadence="daily",
        sources_per_jurisdiction=sources_per_jurisdiction,
        max_jurisdictions=15000,
        status=status,
        taxonomy_json={"nodes": []},
        project_id=PROJECT_ID,
        created_by=USER_ID,
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    # Attach mock jurisdictions via the relationship list
    campaign.jurisdictions = jurisdictions or [
        _make_jurisdiction(jur_id=JUR_ID_1, name="United States"),
        _make_jurisdiction(jur_id=JUR_ID_2, name="Nigeria"),
    ]
    return campaign


def _make_suggested_source(
    title: str = "Gov Website",
    url: str = "https://example.gov/laws",
) -> SuggestedSource:
    return SuggestedSource(
        title=title,
        url=url,
        snippet="Official source",
        confidence_reason="Government domain",
        is_official=True,
    )


def _make_source_read(source_id: uuid.UUID = None) -> MagicMock:
    sr = MagicMock()
    sr.id = source_id or uuid.uuid4()
    return sr


def _make_db(campaign: Campaign) -> AsyncMock:
    """Build a minimal AsyncMock db session.

    The first ``execute`` call returns the campaign (via scalar_one_or_none).
    """
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    def _make_scalar_result(value: Any) -> MagicMock:
        return MagicMock(scalar_one_or_none=MagicMock(return_value=value))

    async def _execute(statement: Any) -> MagicMock:
        column_descriptions = getattr(statement, "column_descriptions", [])
        entity = None
        if column_descriptions:
            entity = column_descriptions[0].get("entity")

        if entity is Campaign:
            return _make_scalar_result(campaign)

        if entity is Jurisdiction:
            jurisdictions = campaign.jurisdictions or []
            jurisdiction = jurisdictions[0] if jurisdictions else None
            return _make_scalar_result(jurisdiction)

        return _make_scalar_result(campaign)

    db.execute = AsyncMock(side_effect=_execute)
    db.refresh = AsyncMock()

    @asynccontextmanager
    async def _begin_nested():
        yield

    db.begin_nested = MagicMock(side_effect=lambda: _begin_nested())
    return db


def _make_redis(acquire_result: int = 1) -> AsyncMock:
    """Build a minimal AsyncMock Redis client.

    ``eval`` returns ``1`` when a token is acquired.
    """
    redis_mock = AsyncMock()
    redis_mock.eval = AsyncMock(return_value=acquire_result)
    return redis_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDiscoverForJurisdictionSuccess:
    """suggest_sources returns sources and they are created correctly."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_creates_sources_for_jurisdiction(self, MockDiscoverySvc, MockSourceSvc):
        campaign = _make_campaign()
        jur = campaign.jurisdictions[0]

        suggested = [
            _make_suggested_source(title="Source A", url="https://a.gov"),
            _make_suggested_source(title="Source B", url="https://b.gov"),
        ]

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=suggested)
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        created_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(
            side_effect=[_make_source_read(created_ids[0]), _make_source_read(created_ids[1])]
        )
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)
        result = await service.discover_for_jurisdiction(jur.id, CAMPAIGN_ID)

        assert len(result) == 2
        assert result == created_ids
        assert mock_source_instance.create_source.call_count == 2
        mock_discovery_instance.close.assert_called_once()


class TestDiscoverAllProcessesAllJurisdictions:
    """discover_all iterates over every jurisdiction in the campaign."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep")
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_processes_all_jurisdictions(self, MockDiscoverySvc, MockSourceSvc, mock_sleep):
        mock_sleep.return_value = None

        campaign = _make_campaign()

        suggested = [_make_suggested_source()]

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=suggested)
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(return_value=_make_source_read())
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)
        result = await service.discover_all(CAMPAIGN_ID)

        assert result["total"] == 2
        assert result["discovered"] == 2
        assert result["failed"] == 0
        assert result["sources_created"] == 2
        assert mock_discovery_instance.suggest_sources.call_count == 2


class TestDiscoverPersistenceDoesNotSleep:
    """Persistence should not apply the inter-jurisdiction discovery delay."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep")
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_persistence_loop_does_not_sleep_between_jurisdictions(
        self, MockDiscoverySvc, MockSourceSvc, mock_sleep
    ):
        mock_sleep.return_value = None

        campaign = _make_campaign()

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=[])
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        mock_source_instance = MagicMock()
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)
        await service.discover_all(CAMPAIGN_ID)

        sleep_calls = [
            call
            for call in mock_sleep.call_args_list
            if call.args[0] == INTER_JURISDICTION_DELAY_SECONDS
        ]
        assert sleep_calls == []


class TestDiscoverFailureContinuesWithNext:
    """One jurisdiction failure does not stop the batch."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep")
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_failure_continues_batch(self, MockDiscoverySvc, MockSourceSvc, mock_sleep):
        mock_sleep.return_value = None
        campaign = _make_campaign()

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(
            side_effect=[
                Exception("Parallel.ai timeout"),
                [_make_suggested_source()],
            ]
        )
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(return_value=_make_source_read())
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)
        result = await service.discover_all(CAMPAIGN_ID)

        assert result["failed"] == 1
        assert result["discovered"] == 1
        assert result["sources_created"] == 1
        assert result["total"] == 2


class TestDiscoverUpdatesExecutionLog:
    """CampaignExecutionLog is created with correct phase and counts."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep")
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_execution_log_updated(self, MockDiscoverySvc, MockSourceSvc, mock_sleep):
        mock_sleep.return_value = None
        campaign = _make_campaign()

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=[_make_suggested_source()])
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(return_value=_make_source_read())
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        # Track objects added to db
        added_objects: List[Any] = []
        db.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        service = CampaignSourceDiscoveryService(db, redis_mock)
        await service.discover_all(CAMPAIGN_ID)

        exec_logs = [o for o in added_objects if isinstance(o, CampaignExecutionLog)]
        assert len(exec_logs) >= 1

        log = exec_logs[0]
        assert log.phase == "source_discovery"
        assert log.total_items == 2
        assert log.completed_items == 2
        assert log.failed_items == 0

        # Campaign stats should include source_discovery_completed_at
        assert "source_discovery_completed_at" in campaign.stats
        assert campaign.stats["total_sources_created"] == 2


class TestDiscoverIdempotent:
    """DuplicateSourceError during create_source is caught and counted as skip."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.asyncio.sleep")
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_duplicate_source_skipped_not_failed(
        self, MockDiscoverySvc, MockSourceSvc, mock_sleep
    ):
        mock_sleep.return_value = None
        campaign = _make_campaign(
            jurisdictions=[_make_jurisdiction(jur_id=JUR_ID_1, name="United States")]
        )

        suggested = [
            _make_suggested_source(title="Source A", url="https://a.gov"),
            _make_suggested_source(title="Source B", url="https://b.gov"),
        ]

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=suggested)
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance

        mock_source_instance = MagicMock()
        mock_source_instance.create_source = AsyncMock(
            side_effect=[
                _make_source_read(),
                DuplicateSourceError("Already exists"),
            ]
        )
        MockSourceSvc.return_value = mock_source_instance

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)
        result = await service.discover_all(CAMPAIGN_ID)

        assert result["sources_created"] == 1
        assert result["skipped_duplicate"] == 1
        assert result["failed"] == 0
        assert result["discovered"] == 1


class TestDiscoverStatusGuards:
    """Status validation prevents discovery from wrong state."""

    @pytest.mark.asyncio
    async def test_rejects_draft_campaign(self):
        campaign = _make_campaign(status=CampaignStatus.DRAFT)

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)

        from app.api.core.custom_exceptions.exceptions import ResourceLockedError

        with pytest.raises(ResourceLockedError):
            await service.discover_all(CAMPAIGN_ID)

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_campaign(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)

        from app.api.core.custom_exceptions.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await service.discover_all(uuid.uuid4())


class TestBuildSearchQuery:
    """Unit tests for _build_search_query."""

    def test_name_only(self):
        jur = _make_jurisdiction(prompt=None)
        result = CampaignSourceDiscoveryService._build_search_query(jur)
        assert result == jur.name

    def test_name_plus_prompt(self):
        jur = _make_jurisdiction(prompt="Extract EOR data")
        result = CampaignSourceDiscoveryService._build_search_query(jur)
        assert result == f"{jur.name} Extract EOR data"

    def test_prompt_truncated_at_200(self):
        long_prompt = "A" * 300
        jur = _make_jurisdiction(prompt=long_prompt)
        result = CampaignSourceDiscoveryService._build_search_query(jur)
        # Name + space + 200 chars of prompt
        assert len(result) == len(jur.name) + 1 + 200


class TestGenerateFallbackQueries:
    """Unit tests for progressive discovery query broadening."""

    def test_progressively_broadens_query(self):
        jur = _make_jurisdiction(name="Lagos", prompt="Track labor circulars and agency updates")

        queries = CampaignSourceDiscoveryService._generate_fallback_queries(
            jur,
            campaign_name="Africa Employment Compliance",
        )

        assert queries == [
            "Lagos Track labor circulars and agency updates",
            "Lagos Africa Employment Compliance",
            "Lagos",
        ]

    def test_deduplicates_when_prompt_and_campaign_are_missing(self):
        jur = _make_jurisdiction(name="California", prompt=None)

        queries = CampaignSourceDiscoveryService._generate_fallback_queries(jur)

        assert queries == ["California"]


class TestDiscoveryStatusPersistence:
    """Discovery outcomes should persist an explicit jurisdiction eligibility state."""

    @pytest.mark.asyncio
    @patch("app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceService")
    @patch(
        "app.api.modules.v1.campaigns.service.campaign_source_discovery_service.SourceDiscoveryService"
    )
    async def test_zero_results_marks_requires_manual_sources(
        self,
        MockDiscoverySvc,
        MockSourceSvc,
    ):
        campaign = _make_campaign(
            jurisdictions=[_make_jurisdiction(jur_id=JUR_ID_1, name="Nigeria", prompt=None)]
        )
        jurisdiction = campaign.jurisdictions[0]

        mock_discovery_instance = AsyncMock()
        mock_discovery_instance.suggest_sources = AsyncMock(return_value=[])
        mock_discovery_instance.close = AsyncMock()
        MockDiscoverySvc.return_value = mock_discovery_instance
        MockSourceSvc.return_value = MagicMock()

        db = _make_db(campaign)
        redis_mock = _make_redis()

        service = CampaignSourceDiscoveryService(db, redis_mock)

        source_ids = await service.discover_for_jurisdiction(jurisdiction.id, CAMPAIGN_ID)

        assert source_ids == []
        assert jurisdiction.discovery_status == DiscoveryStatus.REQUIRES_MANUAL_SOURCES
