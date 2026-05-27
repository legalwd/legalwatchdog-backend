import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignExecutionLog
from app.api.modules.v1.campaigns.service.campaign_content_service import CampaignContentService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_session_mock():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


class TestCampaignContentService:
    async def test_trigger_content_pipeline_queues_task_and_updates_stats(self, db_session_mock):
        """Queueing a campaign content run should persist task metadata."""
        campaign_id = uuid.uuid4()
        campaign = Campaign(
            id=campaign_id,
            organization_id=uuid.uuid4(),
            name="Test Campaign",
        )
        db_session_mock.get = AsyncMock(return_value=campaign)

        service = CampaignContentService(db_session_mock)

        with patch(
            "app.api.modules.v1.campaigns.service.campaign_content_service.celery_app.send_task"
        ) as mock_send_task:
            mock_send_task.return_value.id = "content-task-id"

            result = await service.trigger_content_pipeline(campaign_id, mode="backfill_missing")

        assert result["status"] == "queued"
        assert result["task_id"] == "content-task-id"
        assert result["mode"] == "backfill_missing"
        assert campaign.stats["content_pipeline"]["status"] == "PENDING"
        assert campaign.stats["content_pipeline"]["task_id"] == "content-task-id"
        db_session_mock.commit.assert_awaited_once()

    async def test_build_content_summary_uses_db_counts_and_latest_log(self, db_session_mock):
        """Summary should combine persisted counts with latest content execution metadata."""
        service = CampaignContentService(db_session_mock)
        campaign_id = uuid.uuid4()
        latest_log = CampaignExecutionLog(
            campaign_id=campaign_id,
            phase="content_pipeline_completed_with_errors",
            error_log={
                "run_id": "run-123",
                "mode": "backfill_missing",
                "generated_count": 12,
                "skipped_count": 3,
                "failed_count": 2,
                "missing_state_count": 5,
                "eligible_jurisdictions": 17,
                "message": "Campaign blog generation completed with errors.",
            },
        )

        def _scalar_result(value):
            result = MagicMock()
            result.scalar.return_value = value
            return result

        log_result = MagicMock()
        log_result.scalars.return_value.first.return_value = latest_log

        db_session_mock.execute = AsyncMock(
            side_effect=[
                _scalar_result(25),
                _scalar_result(17),
                _scalar_result(10),
                log_result,
            ]
        )

        summary = await service.build_content_summary(campaign_id, stats={})

        assert summary["total_jurisdictions"] == 25
        assert summary["jurisdictions_with_state"] == 17
        assert summary["blog_count"] == 10
        assert summary["missing_blog_count"] == 7
        assert summary["content_pipeline_status"] == "COMPLETED_WITH_ERRORS"
        assert summary["last_run_mode"] == "backfill_missing"
        assert summary["last_run_failed"] == 2
        assert summary["last_error_summary"] == "Campaign blog generation completed with errors."

    async def test_trigger_content_pipeline_with_geographic_filters(self, db_session_mock):
        """Passing countries/states filters should forward to Celery and store in stats."""
        campaign_id = uuid.uuid4()
        campaign = Campaign(
            id=campaign_id,
            organization_id=uuid.uuid4(),
            name="Test Campaign",
        )
        db_session_mock.get = AsyncMock(return_value=campaign)

        service = CampaignContentService(db_session_mock)

        with patch(
            "app.api.modules.v1.campaigns.service.campaign_content_service.celery_app.send_task"
        ) as mock_send_task:
            mock_send_task.return_value.id = "content-task-id"

            result = await service.trigger_content_pipeline(
                campaign_id,
                mode="run",
                countries=["MX", "Canada"],
                states=["CA-BC", "Nuevo Leon"],
            )

        assert result["status"] == "queued"
        assert result["task_id"] == "content-task-id"
        assert result["mode"] == "run"
        assert campaign.stats["content_pipeline"]["status"] == "PENDING"
        assert campaign.stats["content_pipeline"]["task_id"] == "content-task-id"
        assert campaign.stats["content_pipeline"]["target_countries"] == ["MX", "Canada"]
        assert campaign.stats["content_pipeline"]["target_states"] == ["CA-BC", "Nuevo Leon"]

        mock_send_task.assert_called_once_with(
            "app.api.modules.v1.campaigns.tasks.campaign_tasks.generate_campaign_content_task",
            args=[str(campaign_id), mock_send_task.call_args[1]["args"][1], "run"],
            kwargs={"countries": ["MX", "Canada"], "states": ["CA-BC", "Nuevo Leon"]},
            queue="processing",
        )
        db_session_mock.commit.assert_awaited_once()
