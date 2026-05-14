"""Tests for CampaignHydrationService — fully mocked DB, no real connections."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.service.campaign_hydration_service import (
    _BATCH_SIZE,
    CampaignHydrationService,
    _resolve_scrape_frequency,
)

CAMPAIGN_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
PROJECT_ID = uuid.uuid4()


def _make_campaign(
    status: CampaignStatus = CampaignStatus.TAXONOMY_READY,
    taxonomy_json: Optional[Dict[str, Any]] = None,
    project_id: Optional[uuid.UUID] = None,
    monitor_cadence: Optional[str] = "daily",
    max_jurisdictions: int = 15000,
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
        monitor_cadence=monitor_cadence,
        sources_per_jurisdiction=5,
        max_jurisdictions=max_jurisdictions,
        status=status,
        taxonomy_json=taxonomy_json or _simple_taxonomy(),
        project_id=project_id,
        created_by=USER_ID,
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    return campaign


def _simple_taxonomy() -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "name": "United States",
                "description": "Federal EOR regulations",
                "suggested_prompt": "Extract US federal EOR compliance data",
                "suggested_search_queries": ["US federal employment law 2026"],
                "children": [],
            },
            {
                "name": "Nigeria",
                "description": "Nigerian employment regulations",
                "suggested_prompt": "Extract Nigerian EOR compliance data",
                "suggested_search_queries": ["Nigeria employment law 2026"],
                "children": [],
            },
        ]
    }


def _nested_taxonomy() -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "name": "United States",
                "description": "US federal",
                "suggested_prompt": "US prompt",
                "suggested_search_queries": [],
                "children": [
                    {
                        "name": "California",
                        "description": "CA state",
                        "suggested_prompt": "CA prompt",
                        "suggested_search_queries": [],
                        "children": [
                            {
                                "name": "Los Angeles",
                                "description": "LA city",
                                "suggested_prompt": "LA prompt",
                                "suggested_search_queries": [],
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
    }


@asynccontextmanager
async def _ok_nested():
    yield None


@asynccontextmanager
async def _fail_nested():
    raise IntegrityError("uix_project_name", {}, Exception("duplicate"))
    yield  # pragma: no cover


def _make_db(
    campaign: Campaign,
    project_id: Optional[uuid.UUID] = None,
    extra_execute_results: Optional[List[Any]] = None,
    begin_nested_factory=None,
) -> AsyncMock:
    """Build a minimal AsyncMock db session.

    The first ``execute`` call returns the campaign.  Subsequent calls return
    ``None``.  ``refresh`` populates the ``id`` field of Project objects.
    ``begin_nested`` uses ``_ok_nested`` by default.

    Args:
        campaign: Campaign fixture to return from the first execute call.
        project_id: ID to assign during ``refresh`` (defaults to ``PROJECT_ID``).
        extra_execute_results: Additional execute return values consumed in order
            after the initial campaign lookup.
        begin_nested_factory: Callable producing the async context manager for
            ``begin_nested``; defaults to ``_ok_nested``.
    """
    resolved_project_id = project_id or PROJECT_ID
    results: List[Any] = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=campaign)),
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]
    if extra_execute_results:
        results.extend(extra_execute_results)

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

    return db


def _auto_id_add(collected: Optional[List[Any]] = None):
    """Return an ``add`` side-effect that assigns ``uuid4()`` to Jurisdiction objects."""

    def _add(obj):
        if hasattr(obj, "project_id") and hasattr(obj, "parent_id") and hasattr(obj, "name"):
            object.__setattr__(obj, "id", uuid.uuid4())
            if collected is not None:
                collected.append(obj)

    return MagicMock(side_effect=_add)


class TestHydrateCreatesProject:
    """hydrate() creates exactly one Project per campaign."""

    @pytest.mark.asyncio
    async def test_hydrate_creates_project(self):
        campaign = _make_campaign()
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add()

        service = CampaignHydrationService(db)
        result = await service.hydrate(CAMPAIGN_ID)

        assert campaign.project_id == PROJECT_ID
        assert isinstance(result, list)


class TestHydrateCreatesJurisdictionHierarchy:
    """parent_id links are correct for nested nodes."""

    @pytest.mark.asyncio
    async def test_hydrate_creates_jurisdiction_hierarchy(self):
        campaign = _make_campaign(taxonomy_json=_nested_taxonomy())
        jurisdictions: List[Any] = []
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add(collected=jurisdictions)

        service = CampaignHydrationService(db)
        result = await service.hydrate(CAMPAIGN_ID)

        jur_objects = [
            o for o in jurisdictions if hasattr(o, "project_id") and hasattr(o, "parent_id")
        ]
        assert len(jur_objects) == 3

        us = next(j for j in jur_objects if j.name == "United States")
        ca = next(j for j in jur_objects if j.name == "California")
        la = next(j for j in jur_objects if j.name == "Los Angeles")

        assert us.parent_id is None
        assert ca.parent_id == us.id
        assert la.parent_id == ca.id
        assert len(result) == 3


class TestHydrateSetsCampaignId:
    """All created Jurisdiction records must have campaign_id set."""

    @pytest.mark.asyncio
    async def test_hydrate_sets_campaign_id_on_jurisdictions(self):
        campaign = _make_campaign()
        jurisdictions: List[Any] = []
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add(collected=jurisdictions)

        service = CampaignHydrationService(db)
        await service.hydrate(CAMPAIGN_ID)

        jur_objects = [
            o for o in jurisdictions if hasattr(o, "campaign_id") and hasattr(o, "project_id")
        ]
        assert len(jur_objects) == 2
        assert all(j.campaign_id == CAMPAIGN_ID for j in jur_objects)


class TestHydrateAutoAccept:
    """Jurisdictions must have auto_accept_changes=True and enable_auto_scrape=True."""

    @pytest.mark.asyncio
    async def test_hydrate_sets_auto_accept_true(self):
        campaign = _make_campaign()
        jurisdictions: List[Any] = []
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add(collected=jurisdictions)

        service = CampaignHydrationService(db)
        await service.hydrate(CAMPAIGN_ID)

        jur_objects = [o for o in jurisdictions if hasattr(o, "auto_accept_changes")]
        assert len(jur_objects) >= 1
        assert all(j.auto_accept_changes is True for j in jur_objects)
        assert all(j.enable_auto_scrape is True for j in jur_objects)


class TestHydrateIdempotentRerun:
    """Second run skips duplicates without error and returns existing IDs."""

    @pytest.mark.asyncio
    async def test_hydrate_idempotent_rerun(self):
        campaign = _make_campaign()
        existing_jur_id = uuid.uuid4()

        existing_row = MagicMock()
        existing_row.parent_id = None
        existing_row.name = "United States"
        existing_row.id = existing_jur_id

        existing_row2 = MagicMock()
        existing_row2.parent_id = None
        existing_row2.name = "Nigeria"
        existing_row2.id = existing_jur_id

        existing_result = MagicMock()
        existing_result.__iter__ = MagicMock(return_value=iter([existing_row, existing_row2]))

        execute_results = [
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
                object.__setattr__(obj, "id", PROJECT_ID)

        db.refresh = AsyncMock(side_effect=_refresh)
        db.begin_nested = MagicMock(side_effect=_fail_nested)

        service = CampaignHydrationService(db)
        result = await service.hydrate(CAMPAIGN_ID)

        assert result.count(existing_jur_id) == 2
        db.commit.assert_called_once()


class TestHydrateBatchCommit:
    """flush() is issued at least once per BATCH_SIZE jurisdictions."""

    @pytest.mark.asyncio
    async def test_hydrate_batch_commit_every_100(self):
        n = _BATCH_SIZE + 1
        nodes = [
            {
                "name": f"Country_{i}",
                "description": f"Desc {i}",
                "suggested_prompt": f"Prompt {i}",
                "suggested_search_queries": [],
                "children": [],
            }
            for i in range(n)
        ]
        campaign = _make_campaign(
            taxonomy_json={"nodes": nodes},
            max_jurisdictions=n + 10,
        )

        flush_calls: List[str] = []

        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add()

        async def _flush():
            flush_calls.append("flush")

        db.flush = AsyncMock(side_effect=_flush)

        service = CampaignHydrationService(db)
        await service.hydrate(CAMPAIGN_ID)

        assert len(flush_calls) >= 2


class TestHydrateUpdatesExecutionLog:
    """Campaign.stats is updated with total_jurisdictions and hydration_completed_at."""

    @pytest.mark.asyncio
    async def test_hydrate_updates_execution_log_progress(self):
        campaign = _make_campaign()
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add()

        service = CampaignHydrationService(db)
        await service.hydrate(CAMPAIGN_ID)

        assert campaign.stats is not None
        assert campaign.stats["total_jurisdictions"] == 2
        datetime.fromisoformat(campaign.stats["hydration_completed_at"])


class TestHydrateMaxJurisdictionsCap:
    """hydrate() stops when max_jurisdictions is reached."""

    @pytest.mark.asyncio
    async def test_hydrate_respects_max_jurisdictions_cap(self):
        campaign = _make_campaign(max_jurisdictions=1)
        db = _make_db(campaign, project_id=PROJECT_ID)
        db.add = _auto_id_add()

        service = CampaignHydrationService(db)
        result = await service.hydrate(CAMPAIGN_ID)

        assert len(result) == 1
        assert campaign.stats["total_jurisdictions"] == 1


class TestHydrateStatusGuards:
    """Status validation and not-found error handling."""

    @pytest.mark.asyncio
    async def test_rejects_non_taxonomy_ready_campaign(self):
        campaign = _make_campaign(status=CampaignStatus.DRAFT)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )

        service = CampaignHydrationService(db)

        from app.api.core.custom_exceptions.exceptions import ResourceLockedError

        with pytest.raises(ResourceLockedError):
            await service.hydrate(CAMPAIGN_ID)

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_campaign(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        service = CampaignHydrationService(db)

        from app.api.core.custom_exceptions.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await service.hydrate(uuid.uuid4())


class TestResolveFrequency:
    """Unit tests for _resolve_scrape_frequency."""

    def test_daily_maps_correctly(self):
        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency

        assert _resolve_scrape_frequency("daily") == ScrapeFrequency.DAILY

    def test_weekly_maps_correctly(self):
        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency

        assert _resolve_scrape_frequency("weekly") == ScrapeFrequency.WEEKLY

    def test_case_insensitive(self):
        from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency

        assert _resolve_scrape_frequency("DAILY") == ScrapeFrequency.DAILY

    def test_unknown_returns_none(self):
        assert _resolve_scrape_frequency("fortnightly") is None

    def test_none_returns_none(self):
        assert _resolve_scrape_frequency(None) is None
