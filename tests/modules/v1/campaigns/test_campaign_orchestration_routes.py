import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import require_approved_user, require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignStatus
from app.api.modules.v1.campaigns.pipelines.factory import get_pipeline_runner
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.users_model import User
from main import app


async def _mock_superadmin() -> User:
    """Return a synthetic superadmin for dependency overrides."""
    unique_token = uuid.uuid4().hex[:12]
    return User(
        id=uuid.uuid4(),
        email=f"admin-{unique_token}@example.com",
        name="Superadmin",
        is_active=True,
        is_approved=True,
        is_superadmin=True,
    )


@pytest.fixture
def mock_runner() -> AsyncMock:
    """Create async pipeline runner mock."""
    runner = AsyncMock()
    runner.run = AsyncMock(return_value={"backend": "celery", "task_id": "123"})
    runner.get_status = AsyncMock(return_value={"status": "HYDRATING", "campaign_id": "uuid-here"})
    runner.pause = AsyncMock(return_value=None)
    runner.resume = AsyncMock(return_value=None)
    runner.cancel = AsyncMock(return_value=None)
    return runner


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession, mock_runner: AsyncMock):
    """Create async test client with auth, db, and pipeline overrides."""

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
        yield client

    app.dependency_overrides.pop(require_approved_user, None)
    app.dependency_overrides.pop(require_superadmin, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_pipeline_runner, None)


@pytest_asyncio.fixture
async def superadmin_user(db_session: AsyncSession) -> User:
    """Persist superadmin user fixture in test database."""
    user = await _mock_superadmin()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_campaign(db_session: AsyncSession, superadmin_user: User) -> Campaign:
    """Persist draft campaign fixture for route tests."""
    unique_token = uuid.uuid4().hex[:12]
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        email=f"org-{unique_token}@test.com",
    )
    db_session.add(org)
    await db_session.flush()

    campaign = Campaign(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Test Campaign for Routes",
        industry="Tech",
        status=CampaignStatus.DRAFT,
        created_by=superadmin_user.id,
    )
    db_session.add(campaign)
    await db_session.flush()
    return campaign


class TestCampaignOrchestrationRoutes:
    async def test_launch_campaign(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
        mock_runner: AsyncMock,
    ) -> None:
        """Test launch route returns accepted response and task id."""
        mock_runner.run.return_value = {"backend": "celery", "task_id": "test-task"}

        response = await async_client.post(f"/api/v1/campaigns/{sample_campaign.id}/launch")

        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "SUCCESS"
        assert payload["status_code"] == 202
        assert payload["data"]["task_id"] == "test-task"
        mock_runner.run.assert_awaited_once()

    async def test_get_campaign_status(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
        mock_runner: AsyncMock,
    ) -> None:
        """Test status route returns pipeline status payload."""
        mock_runner.get_status.return_value = {
            "status": "HYDRATING",
            "campaign_id": str(sample_campaign.id),
        }

        response = await async_client.get(f"/api/v1/campaigns/{sample_campaign.id}/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["data"]["status"] == "HYDRATING"
        mock_runner.get_status.assert_awaited_once_with(sample_campaign.id)

    async def test_run_campaign_content(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test manual campaign content runs are queued through the content service."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignContentService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.trigger_content_pipeline = AsyncMock(
                return_value={
                    "status": "queued",
                    "task_id": "content-task-1",
                    "run_id": "run-1",
                    "mode": "run",
                }
            )

            response = await async_client.post(
                f"/api/v1/campaigns/{sample_campaign.id}/content/run"
            )

        assert response.status_code == 202
        payload = response.json()
        assert payload["message"] == "Campaign content pipeline queued."
        assert payload["data"]["task_id"] == "content-task-1"
        mock_service.trigger_content_pipeline.assert_awaited_once_with(
            sample_campaign.id,
            mode="run",
            countries=None,
            states=None,
        )

    async def test_run_campaign_content_with_geo_payload(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test campaign content run triggers with optional country/state payload."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignContentService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.trigger_content_pipeline = AsyncMock(
                return_value={
                    "status": "queued",
                    "task_id": "content-task-1",
                    "run_id": "run-1",
                    "mode": "run",
                }
            )

            response = await async_client.post(
                f"/api/v1/campaigns/{sample_campaign.id}/content/run",
                json={"countries": ["US"], "states": ["CA"]},
            )

        assert response.status_code == 202
        payload = response.json()
        assert payload["message"] == "Campaign content pipeline queued."
        mock_service.trigger_content_pipeline.assert_awaited_once_with(
            sample_campaign.id,
            mode="run",
            countries=["US"],
            states=["CA"],
        )

    async def test_retry_failed_campaign_content(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test failed content retries are queued through the content service."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignContentService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.trigger_content_pipeline = AsyncMock(
                return_value={
                    "status": "queued",
                    "task_id": "content-task-2",
                    "run_id": "run-2",
                    "mode": "retry_failed",
                }
            )

            response = await async_client.post(
                f"/api/v1/campaigns/{sample_campaign.id}/content/retry-failed"
            )

        assert response.status_code == 202
        payload = response.json()
        assert payload["message"] == "Failed campaign content jobs queued for retry."
        assert payload["data"]["mode"] == "retry_failed"
        mock_service.trigger_content_pipeline.assert_awaited_once_with(
            sample_campaign.id,
            mode="retry_failed",
            countries=None,
            states=None,
        )

    async def test_backfill_campaign_content(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test missing blog backfills are queued through the content service."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignContentService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.trigger_content_pipeline = AsyncMock(
                return_value={
                    "status": "queued",
                    "task_id": "content-task-3",
                    "run_id": "run-3",
                    "mode": "backfill_missing",
                }
            )

            response = await async_client.post(
                f"/api/v1/campaigns/{sample_campaign.id}/content/backfill-missing"
            )

        assert response.status_code == 202
        payload = response.json()
        assert payload["message"] == "Missing campaign blog generation queued."
        assert payload["data"]["mode"] == "backfill_missing"
        mock_service.trigger_content_pipeline.assert_awaited_once_with(
            sample_campaign.id,
            mode="backfill_missing",
            countries=None,
            states=None,
        )

    async def test_publish_campaign_blogs(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test campaign blog batch publishing delegates to the campaign service."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.batch_publish_campaign_blogs = AsyncMock(
                return_value={
                    "campaign_id": str(sample_campaign.id),
                    "action": "published",
                    "requested_count": 2,
                    "matched_count": 2,
                    "processed_count": 2,
                    "failed_count": 0,
                    "items": [],
                }
            )

            response = await async_client.post(
                f"/api/v1/campaigns/{sample_campaign.id}/blogs/publish",
                json={"publish_all": True, "is_published": True},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["message"] == "Campaign blog batch publish completed."
        assert payload["data"]["processed_count"] == 2
        mock_service.batch_publish_campaign_blogs.assert_awaited_once()

    async def test_preview_campaign_blog(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
    ) -> None:
        """Test campaign blog preview returns rendered HTML."""
        with patch(
            "app.api.modules.v1.campaigns.routes.campaign_routes.CampaignService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.render_campaign_blog_preview = AsyncMock(
                return_value="<html><body><h1>Preview</h1></body></html>"
            )

            response = await async_client.get(
                f"/api/v1/campaigns/{sample_campaign.id}/blogs/{uuid.uuid4()}/preview"
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Preview" in response.text
        assert response.headers["x-robots-tag"] == "noindex, nofollow"

    async def test_pause_campaign(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
        mock_runner: AsyncMock,
    ) -> None:
        """Test pause route delegates to runner and returns success."""
        response = await async_client.post(f"/api/v1/campaigns/{sample_campaign.id}/pause")

        assert response.status_code == 200
        assert response.json()["message"] == "Campaign paused."
        mock_runner.pause.assert_awaited_once_with(sample_campaign.id)

    async def test_resume_campaign(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
        mock_runner: AsyncMock,
    ) -> None:
        """Test resume route delegates to runner and returns success."""
        response = await async_client.post(f"/api/v1/campaigns/{sample_campaign.id}/resume")

        assert response.status_code == 200
        assert response.json()["message"] == "Campaign resumed."
        mock_runner.resume.assert_awaited_once_with(sample_campaign.id)

    async def test_cancel_campaign(
        self,
        async_client: AsyncClient,
        sample_campaign: Campaign,
        mock_runner: AsyncMock,
    ) -> None:
        """Test cancel route delegates to runner and returns success."""
        response = await async_client.post(f"/api/v1/campaigns/{sample_campaign.id}/cancel")

        assert response.status_code == 200
        assert response.json()["message"] == "Campaign cancelled."
        mock_runner.cancel.assert_awaited_once_with(sample_campaign.id)
