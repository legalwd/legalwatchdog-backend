"""Campaign-scoped blog generation orchestration and status helpers."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import ProcessingError, ResourceNotFoundError
from app.api.core.queues import PROCESSING_QUEUE
from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignExecutionLog
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.models.jurisdiction_state import JurisdictionState
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class CampaignContentService:
    """Trigger and summarize campaign-level blog generation workflows."""

    TASK_NAME = "app.api.modules.v1.campaigns.tasks.campaign_tasks.generate_campaign_content_task"
    ACTIVE_STATUSES = {"PENDING", "IN_PROGRESS"}
    TERMINAL_PHASE_TO_STATUS = {
        "content_pipeline_completed": "COMPLETED",
        "content_pipeline_completed_with_errors": "COMPLETED_WITH_ERRORS",
        "content_pipeline_failed": "FAILED",
    }
    VALID_MODES = {"run", "retry_failed", "backfill_missing"}
    ACTIVE_WINDOW_SECONDS = 1800

    def __init__(self, db: AsyncSession):
        """Initialize the service with an injected async database session."""
        self.db = db

    @staticmethod
    def merge_content_pipeline_stats(
        stats: dict[str, Any] | None,
        *,
        status: str,
        run_id: str | None = None,
        task_id: str | None = None,
        mode: str | None = None,
        generated_count: int | None = None,
        skipped_count: int | None = None,
        failed_count: int | None = None,
        missing_state_count: int | None = None,
        eligible_jurisdictions: int | None = None,
        total_jurisdictions: int | None = None,
        error_summary: str | None = None,
        countries: list[str] | None = None,
        states: list[str] | None = None,
    ) -> dict[str, Any]:
        """Merge campaign content-pipeline metadata into the campaign stats JSON."""
        new_stats = dict(stats) if isinstance(stats, dict) else {}
        content_pipeline = dict(new_stats.get("content_pipeline") or {})
        content_pipeline["status"] = status
        content_pipeline["updated_at"] = datetime.now(timezone.utc).isoformat()

        if run_id is not None:
            content_pipeline["run_id"] = run_id
        if task_id is not None:
            content_pipeline["task_id"] = task_id
        if mode is not None:
            content_pipeline["mode"] = mode
        if generated_count is not None:
            content_pipeline["generated_count"] = generated_count
        if skipped_count is not None:
            content_pipeline["skipped_count"] = skipped_count
        if failed_count is not None:
            content_pipeline["failed_count"] = failed_count
        if missing_state_count is not None:
            content_pipeline["missing_state_count"] = missing_state_count
        if eligible_jurisdictions is not None:
            content_pipeline["eligible_jurisdictions"] = eligible_jurisdictions
        if total_jurisdictions is not None:
            content_pipeline["total_jurisdictions"] = total_jurisdictions
        if error_summary is not None:
            content_pipeline["error_summary"] = error_summary
        if countries is not None:
            content_pipeline["target_countries"] = countries
        if states is not None:
            content_pipeline["target_states"] = states

        new_stats["content_pipeline"] = content_pipeline
        return new_stats

    @classmethod
    def _is_recent_active_pipeline(cls, payload: dict[str, Any]) -> bool:
        """Return True when content pipeline metadata still looks actively owned."""
        if payload.get("status") not in cls.ACTIVE_STATUSES:
            return False

        updated_at_raw = payload.get("updated_at")
        if not isinstance(updated_at_raw, str) or not updated_at_raw:
            return True

        try:
            updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return True

        return (datetime.now(timezone.utc) - updated_at).total_seconds() < cls.ACTIVE_WINDOW_SECONDS

    async def trigger_content_pipeline(
        self,
        campaign_id: UUID,
        *,
        mode: str,
        countries: list[str] | None = None,
        states: list[str] | None = None,
    ) -> dict[str, Any]:
        """Queue campaign blog generation in a dedicated downstream task."""
        if mode not in self.VALID_MODES:
            raise ProcessingError(message=f"Unsupported campaign content mode '{mode}'.")

        campaign = await self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise ResourceNotFoundError(message="Campaign not found")

        existing_pipeline = campaign.stats.get("content_pipeline", {}) if campaign.stats else {}
        if isinstance(existing_pipeline, dict) and self._is_recent_active_pipeline(
            existing_pipeline
        ):
            return {
                "status": "already_running",
                "task_id": str(existing_pipeline.get("task_id") or ""),
                "run_id": str(existing_pipeline.get("run_id") or ""),
                "mode": str(existing_pipeline.get("mode") or mode),
            }

        run_id = str(uuid4())
        task = celery_app.send_task(
            self.TASK_NAME,
            args=[str(campaign_id), run_id, mode],
            kwargs={"countries": countries, "states": states},
            queue=PROCESSING_QUEUE,
        )

        campaign.stats = self.merge_content_pipeline_stats(
            campaign.stats,
            status="PENDING",
            run_id=run_id,
            task_id=task.id,
            mode=mode,
            countries=countries,
            states=states,
        )
        self.db.add(campaign)
        await self.db.commit()

        return {
            "status": "queued",
            "task_id": task.id,
            "run_id": run_id,
            "mode": mode,
        }

    async def build_content_summary(
        self, campaign_id: UUID, stats: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Compute campaign-level blog generation readiness and latest-run metadata."""
        total_jurisdictions_result = await self.db.execute(
            select(func.count())
            .select_from(Jurisdiction)
            .where(Jurisdiction.campaign_id == campaign_id)
        )
        total_jurisdictions = int(total_jurisdictions_result.scalar() or 0)

        state_count_result = await self.db.execute(
            select(func.count(func.distinct(JurisdictionState.jurisdiction_id)))
            .select_from(JurisdictionState)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionState.jurisdiction_id)
            .where(Jurisdiction.campaign_id == campaign_id)
        )
        jurisdictions_with_state = int(state_count_result.scalar() or 0)

        blog_count_result = await self.db.execute(
            select(func.count())
            .select_from(JurisdictionBlogPost)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(Jurisdiction.campaign_id == campaign_id)
        )
        blog_count = int(blog_count_result.scalar() or 0)

        latest_content_log_result = await self.db.execute(
            select(CampaignExecutionLog)
            .where(
                CampaignExecutionLog.campaign_id == campaign_id,
                CampaignExecutionLog.phase.like("content_pipeline%"),
            )
            .order_by(CampaignExecutionLog.started_at.desc())
        )
        latest_content_log = latest_content_log_result.scalars().first()

        content_pipeline = stats.get("content_pipeline", {}) if isinstance(stats, dict) else {}
        if not isinstance(content_pipeline, dict):
            content_pipeline = {}

        content_pipeline_status = str(content_pipeline.get("status") or "")
        if not content_pipeline_status and latest_content_log:
            content_pipeline_status = self.TERMINAL_PHASE_TO_STATUS.get(
                latest_content_log.phase,
                "NOT_STARTED",
            )
        if not content_pipeline_status:
            content_pipeline_status = "NOT_STARTED"

        log_payload = (
            latest_content_log.error_log
            if latest_content_log and latest_content_log.error_log
            else {}
        )
        if not isinstance(log_payload, dict):
            log_payload = {}

        missing_blog_count = max(jurisdictions_with_state - blog_count, 0)

        return {
            "total_jurisdictions": total_jurisdictions,
            "jurisdictions_with_state": jurisdictions_with_state,
            "blog_count": blog_count,
            "missing_blog_count": missing_blog_count,
            "last_run_mode": str(content_pipeline.get("mode") or log_payload.get("mode") or ""),
            "last_run_generated": int(
                content_pipeline.get("generated_count") or log_payload.get("generated_count") or 0
            ),
            "last_run_skipped": int(
                content_pipeline.get("skipped_count") or log_payload.get("skipped_count") or 0
            ),
            "last_run_failed": int(
                content_pipeline.get("failed_count") or log_payload.get("failed_count") or 0
            ),
            "last_run_missing_state": int(
                content_pipeline.get("missing_state_count")
                or log_payload.get("missing_state_count")
                or 0
            ),
            "eligible_jurisdictions": int(
                content_pipeline.get("eligible_jurisdictions")
                or log_payload.get("eligible_jurisdictions")
                or jurisdictions_with_state
            ),
            "content_pipeline_status": content_pipeline_status,
            "last_run_id": str(content_pipeline.get("run_id") or log_payload.get("run_id") or ""),
            "last_error_summary": str(
                content_pipeline.get("error_summary") or log_payload.get("message") or ""
            ),
        }
