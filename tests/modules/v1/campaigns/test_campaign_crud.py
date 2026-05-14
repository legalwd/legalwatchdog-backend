"""Tests for Campaign CRUD endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.custom_exceptions.exceptions import NotFoundError, ResourceLockedError
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

_SUPERADMIN_USER: User | None = None

ORG_ID = uuid.uuid4()
CAMPAIGN_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def make_campaign(status: CampaignStatus = CampaignStatus.DRAFT) -> Campaign:
    """Build a Campaign fixture for testing."""
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=CAMPAIGN_ID,
        organization_id=ORG_ID,
        project_id=None,
        name="Test Campaign",
        industry="Technology",
        domain_description="Test description",
        target_depth=CampaignTargetDepth.COUNTRY,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        monitor_cadence=None,
        sources_per_jurisdiction=5,
        max_jurisdictions=15000,
        status=status,
        created_by=USER_ID,
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    return campaign


async def _mock_superadmin():
    """Return a stub superadmin user."""
    user = User(
        id=USER_ID,
        email="admin@example.com",
        name="Superadmin",
        is_active=True,
        is_approved=True,
    )
    return user


async def _mock_non_superadmin():
    """Simulate require_superadmin rejecting a non-superadmin user."""
    from fastapi import HTTPException

    raise HTTPException(status_code=403, detail="Forbidden")


async def _mock_get_db():
    """Yield a stub database session."""
    yield MagicMock()


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_create_campaign_success(auth_client):
    """POST /campaigns returns 201 with DRAFT campaign."""
    campaign = make_campaign()
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.create_campaign = AsyncMock(return_value=campaign)

        payload = {
            "organization_id": str(ORG_ID),
            "name": "Test Campaign",
            "industry": "Technology",
            "target_depth": "COUNTRY",
            "monitor_backend": "CELERY_BEAT",
            "sources_per_jurisdiction": 5,
            "max_jurisdictions": 15000,
        }
        response = await auth_client.post("/api/v1/campaigns", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["status_code"] == 201
    assert body["data"]["status"] == "DRAFT"
    assert body["data"]["name"] == "Test Campaign"


@pytest.mark.asyncio
async def test_create_campaign_missing_required_fields(auth_client):
    """POST /campaigns with missing required fields returns 422."""
    response = await auth_client.post(
        "/api/v1/campaigns",
        json={"industry": "Technology"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_campaign_non_superadmin_forbidden(client):
    """POST /campaigns without superadmin returns 403."""
    app.dependency_overrides[require_superadmin] = _mock_non_superadmin
    app.dependency_overrides[get_db] = _mock_get_db

    payload = {
        "organization_id": str(ORG_ID),
        "name": "Blocked Campaign",
        "industry": "Tech",
        "target_depth": "COUNTRY",
        "monitor_backend": "CELERY_BEAT",
    }
    response = await client.post("/api/v1/campaigns", json=payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_campaign_success(auth_client):
    """GET /campaigns/{id} returns 200 with campaign data."""
    campaign = make_campaign()
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.get_campaign = AsyncMock(return_value=campaign)

        response = await auth_client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["data"]["id"] == str(CAMPAIGN_ID)


@pytest.mark.asyncio
async def test_get_campaign_not_found(auth_client):
    """GET /campaigns/{id} returns 404 when campaign does not exist."""
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.get_campaign = AsyncMock(side_effect=NotFoundError("Campaign not found."))

        response = await auth_client.get(f"/api/v1/campaigns/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_campaigns_paginated(auth_client):
    """GET /campaigns returns paginated list."""
    campaigns = [make_campaign(), make_campaign()]
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.list_campaigns = AsyncMock(
            return_value={
                "items": campaigns,
                "total": 2,
                "page": 1,
                "limit": 20,
                "total_pages": 1,
            }
        )

        response = await auth_client.get("/api/v1/campaigns?page=1&limit=20")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["total"] == 2
    assert len(body["data"]["campaigns"]) == 2


@pytest.mark.asyncio
async def test_list_campaigns_filter_by_status(auth_client):
    """GET /campaigns?status=DRAFT filters campaigns by status."""
    campaign = make_campaign()
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.list_campaigns = AsyncMock(
            return_value={
                "items": [campaign],
                "total": 1,
                "page": 1,
                "limit": 20,
                "total_pages": 1,
            }
        )

        response = await auth_client.get("/api/v1/campaigns?status=DRAFT")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["data"]["total"] == 1
    assert body["data"]["campaigns"][0]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_update_campaign_in_draft(auth_client):
    """PATCH /campaigns/{id} succeeds when campaign is in DRAFT."""
    updated = make_campaign()
    updated.name = "Updated Name"
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.update_campaign = AsyncMock(return_value=updated)

        response = await auth_client.patch(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            json={"name": "Updated Name"},
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["data"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_campaign_not_in_draft_rejected(auth_client):
    """PATCH /campaigns/{id} returns 423 when campaign is not in DRAFT."""
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.update_campaign = AsyncMock(
            side_effect=ResourceLockedError("Campaign can only be updated while in DRAFT status.")
        )

        response = await auth_client.patch(
            f"/api/v1/campaigns/{CAMPAIGN_ID}",
            json={"name": "Won't Update"},
        )

    assert response.status_code == status.HTTP_423_LOCKED
    body = response.json()
    assert body["error_code"] == "RESOURCE_LOCKED"


@pytest.mark.asyncio
async def test_delete_campaign_in_draft(auth_client):
    """DELETE /campaigns/{id} succeeds when campaign is in DRAFT."""
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.delete_campaign = AsyncMock(return_value=None)

        response = await auth_client.delete(f"/api/v1/campaigns/{CAMPAIGN_ID}")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["message"] == "Campaign deleted successfully."


@pytest.mark.asyncio
async def test_delete_campaign_not_in_draft_rejected(auth_client):
    """DELETE /campaigns/{id} returns 423 when campaign is not in DRAFT."""
    with patch(
        "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
    ) as MockService:
        instance = MockService.return_value
        instance.delete_campaign = AsyncMock(
            side_effect=ResourceLockedError("Campaign can only be deleted while in DRAFT status.")
        )

        response = await auth_client.delete(f"/api/v1/campaigns/{CAMPAIGN_ID}")

    assert response.status_code == status.HTTP_423_LOCKED
    body = response.json()
    assert body["error_code"] == "RESOURCE_LOCKED"
