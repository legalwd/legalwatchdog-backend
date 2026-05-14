import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import ProcessingError, ResourceNotFoundError
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignStatus,
)
from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
    CampaignOrchestrationService,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_session_mock():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.stats = {}
    return session


@pytest.fixture
def celery_control_mock():
    control = MagicMock()
    control.revoke = MagicMock()
    return control


@pytest.fixture
def orchestration_service(db_session_mock, celery_control_mock):
    return CampaignOrchestrationService(db=db_session_mock, celery_control=celery_control_mock)


class TestCampaignOrchestrationService:
    @patch("app.api.modules.v1.campaigns.service.campaign_orchestration_service.chain")
    async def test_run_draft_campaign(self, mock_chain, orchestration_service, db_session_mock):
        """Test run launches a full chain from draft campaign state."""
        campaign_id = uuid.uuid4()
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.DRAFT,
            organization_id=uuid.uuid4(),
            name="Test",
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)

        mock_async_result = MagicMock()
        mock_async_result.id = "test-task-id"
        mock_async_result.children = []
        mock_chain.return_value.on_error.return_value.apply_async.return_value = mock_async_result

        result = await orchestration_service.run(campaign_id)

        assert result["backend"] == "celery"
        assert result["task_id"] == "test-task-id"
        assert mock_campaign.status == CampaignStatus.GENERATING_TAXONOMY
        mock_chain.assert_called_once()
        assert db_session_mock.commit.await_count == 2

    async def test_run_non_draft_campaign_rejected(self, orchestration_service, db_session_mock):
        """Test run rejects campaigns in truly invalid statuses (e.g. FAILED)."""
        campaign_id = uuid.uuid4()
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.FAILED,
            organization_id=uuid.uuid4(),
            name="Test",
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)

        with pytest.raises(
            ProcessingError,
            match=(
                "Campaign can only be launched from DRAFT, TAXONOMY_READY, "
                "or active recovery phases."
            ),
        ):
            await orchestration_service.run(campaign_id)

    @patch("app.api.modules.v1.campaigns.service.campaign_orchestration_service.chain")
    async def test_run_taxonomy_ready_campaign(
        self, mock_chain, orchestration_service, db_session_mock
    ):
        """Test status returns campaign status payload."""
        campaign_id = uuid.uuid4()
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.SCRAPING,
            organization_id=uuid.uuid4(),
            name="Test",
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = []
        db_session_mock.execute = AsyncMock(return_value=execute_result)

        with patch(
            "app.api.modules.v1.campaigns.service.campaign_orchestration_service."
            "CampaignContentService.build_content_summary",
            new=AsyncMock(return_value={"content_pipeline_status": "IN_PROGRESS"}),
        ):
            result = await orchestration_service.get_status(campaign_id)

        assert result["status"] == CampaignStatus.SCRAPING.value
        assert result["campaign_id"] == str(campaign_id)
        assert result["content_pipeline_status"] == "IN_PROGRESS"

    async def test_get_status_surfaces_partial_failure_from_execution_log(
        self, orchestration_service, db_session_mock
    ):
        """Status should expose pipeline_completed_with_errors for MONITORING campaigns."""
        campaign_id = uuid.uuid4()
        run_id = str(uuid.uuid4())
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.MONITORING,
            organization_id=uuid.uuid4(),
            name="Test",
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)

        execution_log = CampaignExecutionLog(
            campaign_id=campaign_id,
            phase="pipeline_completed_with_errors",
            error_log={
                "run_id": run_id,
                "failed_jurisdiction_count": 20,
                "message": "Some jurisdiction tasks failed during extraction.",
            },
        )
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [execution_log]
        db_session_mock.execute = AsyncMock(return_value=execute_result)

        with patch(
            "app.api.modules.v1.campaigns.service.campaign_orchestration_service."
            "CampaignContentService.build_content_summary",
            new=AsyncMock(return_value={"content_pipeline_status": "COMPLETED_WITH_ERRORS"}),
        ):
            result = await orchestration_service.get_status(campaign_id)

        assert result["status"] == CampaignStatus.MONITORING.value
        assert result["run_id"] == run_id
        assert result["failure"]["category"] == "partial_failure"
        assert result["content_pipeline_status"] == "COMPLETED_WITH_ERRORS"

    async def test_pause_and_resume(
        self,
        orchestration_service,
        db_session_mock,
        celery_control_mock,
    ):
        """Test pause marks campaign paused and resume relaunches from metadata."""
        campaign_id = uuid.uuid4()
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.HYDRATING,
            organization_id=uuid.uuid4(),
            name="Test",
            stats={"pipeline_control": {"task_ids": ["t1", "t2"]}},
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)

        await orchestration_service.pause(campaign_id)
        assert mock_campaign.status == CampaignStatus.PAUSED
        db_session_mock.commit.assert_awaited_once()
        assert mock_campaign.stats["pipeline_control"]["paused_from_status"] == "HYDRATING"
        assert celery_control_mock.revoke.call_count == 2

        with patch(
            "app.api.modules.v1.campaigns.service.campaign_orchestration_service.chain"
        ) as mock_chain:
            mock_campaign.status = CampaignStatus.PAUSED
            mock_campaign.stats = {"pipeline_control": {"paused_from_status": "HYDRATING"}}
            mock_async_result = MagicMock()
            mock_async_result.id = "resume-task-id"
            mock_async_result.children = []
            mock_chain.return_value.on_error.return_value.apply_async.return_value = (
                mock_async_result
            )
            await orchestration_service.resume(campaign_id)
            assert mock_campaign.status == CampaignStatus.HYDRATING

    async def test_cancel(self, orchestration_service, db_session_mock, celery_control_mock):
        """Test cancel revokes tasks and marks campaign cancelled."""
        campaign_id = uuid.uuid4()
        mock_campaign = Campaign(
            id=campaign_id,
            status=CampaignStatus.HYDRATING,
            organization_id=uuid.uuid4(),
            name="Test",
            stats={"pipeline_control": {"task_ids": ["cancel-task-id"]}},
        )
        db_session_mock.get = AsyncMock(return_value=mock_campaign)

        await orchestration_service.cancel(campaign_id)
        assert mock_campaign.status == CampaignStatus.CANCELLED
        db_session_mock.commit.assert_awaited_once()
        celery_control_mock.revoke.assert_called_once_with("cancel-task-id", terminate=False)

    async def test_run_not_found(self, orchestration_service, db_session_mock):
        """Test run raises not found for unknown campaign id."""
        campaign_id = uuid.uuid4()
        db_session_mock.get = AsyncMock(return_value=None)

        with pytest.raises(ResourceNotFoundError, match="Campaign not found"):
            await orchestration_service.run(campaign_id)
