"""Tests for taxonomy route handlers — integration-style tests via HTTPX."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import require_approved_user, require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.users.models.users_model import User
from main import app

CAMPAIGN_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _make_campaign(
    campaign_status: CampaignStatus = CampaignStatus.TAXONOMY_READY,
    taxonomy_json=None,
) -> Campaign:
    """Build a Campaign fixture."""
    now = datetime.now(timezone.utc)
    if taxonomy_json is None:
        taxonomy_json = {
            "nodes": [
                {
                    "name": "United States",
                    "description": "Federal EOR regulations",
                    "suggested_prompt": "Extract US federal data",
                    "suggested_search_queries": ["US law"],
                    "iso_code": "US",
                    "children": [
                        {
                            "name": "California",
                            "description": "CA regulations",
                            "suggested_prompt": "Extract CA data",
                            "suggested_search_queries": ["CA law"],
                            "iso_code": "US-CA",
                            "children": [],
                        }
                    ],
                },
                {
                    "name": "Nigeria",
                    "description": "Nigerian regulations",
                    "suggested_prompt": "Extract NG data",
                    "suggested_search_queries": ["Nigeria law"],
                    "iso_code": "NG",
                    "children": [],
                },
            ]
        }
    campaign = Campaign(
        id=CAMPAIGN_ID,
        organization_id=ORG_ID,
        name="EOR Compliance",
        industry="EOR",
        domain_description="EOR tracking",
        target_depth=CampaignTargetDepth.STATE,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        sources_per_jurisdiction=5,
        max_jurisdictions=15000,
        status=campaign_status,
        taxonomy_json=taxonomy_json,
        created_by=USER_ID,
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    return campaign


async def _mock_superadmin():
    """Return a stub superadmin user."""
    return User(
        id=USER_ID,
        email="admin@example.com",
        name="Superadmin",
        is_active=True,
        is_approved=True,
    )


async def _mock_get_db():
    """Yield a stub database session with awaitable async methods."""
    mock = MagicMock()
    mock.commit = AsyncMock()
    mock.refresh = AsyncMock()
    mock.add = MagicMock()
    yield mock


@pytest_asyncio.fixture
async def auth_client():
    """Client with superadmin auth and stub DB injected."""
    app.dependency_overrides[require_approved_user] = _mock_superadmin
    app.dependency_overrides[require_superadmin] = _mock_superadmin
    app.dependency_overrides[get_db] = _mock_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


class TestGetTaxonomyShowsPreviewStats:
    """test_get_taxonomy_shows_preview_stats — GET returns tree + stats."""

    @pytest.mark.asyncio
    async def test_returns_preview_stats(self, auth_client):
        campaign = _make_campaign()
        campaign.generation_config_snapshot = {
            "geo_stats": {
                "countries_matched": 2,
                "subdivisions_matched": 1,
                "unrecognized_count": 0,
                "distinct_countries": 2,
                "regional_entities_expanded": 1,
                "unrecognized_top_level": 0,
            }
        }
        with patch(
            "app.api.modules.v1.campaigns.routes.taxonomy_routes.CampaignService"
        ) as MockService:
            instance = MockService.return_value
            instance.get_campaign = AsyncMock(return_value=campaign)

            response = await auth_client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}/taxonomy")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        data = body["data"]

        stats = data["preview_stats"]
        assert stats["total_nodes"] == 3
        assert stats["countries"] == 2
        assert stats["distinct_countries"] == 2
        assert stats["states"] == 1
        assert stats["regional_entities_expanded"] == 1
        assert stats["unrecognized_top_level"] == 0

        # Taxonomy tree present
        assert len(data["taxonomy"]) == 2


class TestEditTaxonomyRerunsValidation:
    """test_edit_taxonomy_reruns_validation — PATCH re-runs geo validation."""

    @pytest.mark.asyncio
    async def test_edit_reruns_geo_validation(self, auth_client):
        campaign = _make_campaign(campaign_status=CampaignStatus.TAXONOMY_READY)

        # Mock geo result returned by the service
        mock_geo_result = MagicMock()
        mock_geo_result.normalized_taxonomy = {
            "nodes": [
                {
                    "name": "United States",
                    "description": "Federal regs",
                    "suggested_prompt": "Extract US data",
                    "suggested_search_queries": ["US law"],
                    "iso_code": "US",
                    "children": [],
                }
            ]
        }
        mock_geo_result.warnings = []
        mock_geo_result.stats = {
            "countries_matched": 1,
            "subdivisions_matched": 0,
            "unrecognized_count": 0,
        }

        with patch(
            "app.api.modules.v1.campaigns.routes.taxonomy_routes.TaxonomyGenerationService"
        ) as MockService:
            instance = MockService.return_value
            instance.edit_taxonomy = AsyncMock(return_value=(campaign, mock_geo_result))

            payload = {
                "taxonomy": [
                    {
                        "name": "USA",
                        "description": "Federal regs",
                        "suggested_prompt": "Extract US data",
                        "suggested_search_queries": ["US law"],
                        "children": [],
                    }
                ]
            }
            response = await auth_client.patch(
                f"/api/v1/campaigns/{CAMPAIGN_ID}/taxonomy",
                json=payload,
            )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        data = body["data"]

        assert len(data["taxonomy"]) >= 1
        assert data["preview_stats"]["total_nodes"] >= 1


class TestApproveTaxonomyRecordsAuditFields:
    """test_approve_taxonomy_records_audit_fields."""

    @pytest.mark.asyncio
    async def test_records_approver_and_timestamp(self, auth_client):
        campaign = _make_campaign(campaign_status=CampaignStatus.TAXONOMY_READY)
        campaign.taxonomy_approved_by = USER_ID
        campaign.taxonomy_approved_at = datetime.now(timezone.utc)

        with patch(
            "app.api.modules.v1.campaigns.routes.taxonomy_routes.TaxonomyGenerationService"
        ) as MockService:
            instance = MockService.return_value
            instance.approve_taxonomy = AsyncMock(return_value=campaign)

            response = await auth_client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/approve-taxonomy")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        data = body["data"]

        assert data["taxonomy_approved_by"] == str(USER_ID)
        assert data["taxonomy_approved_at"] is not None
        assert data["status"] == "TAXONOMY_READY"


class TestApproveTaxonomyNotInTaxonomyReadyRejected:
    """test_approve_taxonomy_not_in_taxonomy_ready_rejected — 423."""

    @pytest.mark.asyncio
    async def test_rejects_draft_campaign(self, auth_client):
        from app.api.core.custom_exceptions.exceptions import ResourceLockedError as RLE

        with patch(
            "app.api.modules.v1.campaigns.routes.taxonomy_routes.TaxonomyGenerationService"
        ) as MockService:
            instance = MockService.return_value
            instance.approve_taxonomy = AsyncMock(
                side_effect=RLE("Taxonomy can only be approved while in TAXONOMY_READY status.")
            )

            response = await auth_client.post(f"/api/v1/campaigns/{CAMPAIGN_ID}/approve-taxonomy")

        assert response.status_code == status.HTTP_423_LOCKED
        body = response.json()
        assert body["error_code"] == "RESOURCE_LOCKED"
