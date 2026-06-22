"""Campaign Orchestration Service for Celery pipeline."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from celery import chain
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import ProcessingError, ResourceNotFoundError
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignStatus,
)
from app.api.modules.v1.campaigns.pipelines.base import CampaignPipelineRunner
from app.api.modules.v1.campaigns.service.campaign_content_service import CampaignContentService
from app.api.modules.v1.campaigns.tasks.campaign_tasks import (
    campaign_pipeline_error_handler,
    discover_sources_task,
    dispatch_campaign_scrapes_task,
    generate_taxonomy_task,
    hydrate_campaign_task,
    publish_campaign_blogs_task,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
    DiscoveryStatus,
    Jurisdiction,
)
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class CampaignOrchestrationService(CampaignPipelineRunner):
    """Orchestrates campaign pipeline using Celery."""

    _BILLING_ERROR_MARKERS = (
        "payment required",
        "http 402",
        "requires more credits",
        "upgrade to a paid account",
        "insufficient",
    )

    def __init__(self, db: AsyncSession, celery_control: Any | None = None):
        self.db = db
        self.celery_control = celery_control or celery_app.control

    @staticmethod
    def _base_pipeline_for_campaign(campaign_id: UUID, run_id: str | None = None):
        """Build immutable signatures for the full campaign chain."""
        str_id = str(campaign_id)
        return [
            generate_taxonomy_task.si(str_id, run_id),
            hydrate_campaign_task.si(str_id, run_id),
            discover_sources_task.si(str_id, run_id),
            dispatch_campaign_scrapes_task.si(str_id, run_id),
            publish_campaign_blogs_task.si(str_id, run_id),
        ]

    @classmethod
    def _pipeline_from_status(
        cls,
        campaign_id: UUID,
        resume_from_status: CampaignStatus,
        run_id: str | None = None,
    ):
        """Build a resume chain starting from the given status."""
        pipeline = cls._base_pipeline_for_campaign(campaign_id, run_id)
        status_to_start_index = {
            CampaignStatus.GENERATING_TAXONOMY: 0,
            CampaignStatus.HYDRATING: 1,
            CampaignStatus.DISCOVERING_SOURCES: 2,
            CampaignStatus.SCRAPING: 3,
            CampaignStatus.PUBLISHING: 4,
        }
        start_index = status_to_start_index.get(resume_from_status)
        if start_index is None:
            raise ProcessingError(
                message=f"Cannot resume from phase '{resume_from_status.value}'.",
            )
        return pipeline[start_index:]

    @staticmethod
    def _task_id_list_from_stats(stats: dict[str, Any] | None) -> list[str]:
        """Extract task ids from campaign stats payload."""
        if not isinstance(stats, dict):
            return []
        pipeline_control = stats.get("pipeline_control", {})
        task_ids = pipeline_control.get("task_ids", [])
        if not isinstance(task_ids, list):
            return []
        return [tid for tid in task_ids if isinstance(tid, str) and tid]

    @staticmethod
    def _upsert_pipeline_control(
        stats: dict[str, Any] | None,
        *,
        task_ids: list[str],
        last_started_status: CampaignStatus,
        run_id: str | None = None,
        paused_from_status: str | None = None,
        paused_at: str | None = None,
    ) -> dict[str, Any]:
        """Merge orchestration control metadata into campaign stats.

        Maintains a bounded ``run_history`` list (configurable, default 5)
        so that repeated retries and resets do not bloat the JSONB column.
        """
        from app.api.core.config import settings

        new_stats = dict(stats) if isinstance(stats, dict) else {}
        pipeline_control: dict[str, Any] = dict(new_stats.get("pipeline_control") or {})
        pipeline_control["task_ids"] = task_ids
        pipeline_control["last_started_status"] = last_started_status.value
        pipeline_control["updated_at"] = datetime.now(timezone.utc).isoformat()
        if run_id:
            pipeline_control["run_id"] = run_id
        if paused_from_status is not None:
            pipeline_control["paused_from_status"] = paused_from_status
        if paused_at is not None:
            pipeline_control["paused_at"] = paused_at

        run_history: list[dict[str, Any]] = list(pipeline_control.get("run_history") or [])
        run_history.append(
            {
                "run_id": run_id,
                "task_ids": list(task_ids),
                "status": last_started_status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        max_history = getattr(settings, "CAMPAIGN_MAX_PIPELINE_HISTORY", 5)
        pipeline_control["run_history"] = run_history[-max_history:]

        new_stats["pipeline_control"] = pipeline_control
        return new_stats

    @staticmethod
    def _collect_chain_task_ids(root_result: AsyncResult) -> list[str]:
        """Collect all known task ids from a chain result."""
        task_ids: list[str] = []
        current: AsyncResult | None = root_result
        while current is not None:
            if current.id:
                task_ids.append(current.id)
            children = current.children or []
            current = children[0] if children else None
        return list(dict.fromkeys(task_ids))

    @classmethod
    def _classify_failure_from_error_text(cls, error_text: str) -> dict[str, Any] | None:
        """Classify known pipeline errors into frontend-friendly failure payloads."""
        if not error_text:
            return None

        normalized = error_text.lower()
        if any(marker in normalized for marker in cls._BILLING_ERROR_MARKERS):
            return {
                "category": "billing",
                "error_code": "LLM_BILLING_LIMIT",
                "message": (
                    "Campaign failed because LLM credits are insufficient. "
                    "Upgrade OpenRouter credits or reduce token limits."
                ),
                "retryable": False,
            }

        return {
            "category": "processing",
            "error_code": "CAMPAIGN_PIPELINE_FAILED",
            "message": "Campaign pipeline failed. Please review logs and retry.",
            "retryable": True,
        }

    @staticmethod
    def _failure_from_execution_log(log: CampaignExecutionLog) -> dict[str, Any] | None:
        """Build a status payload from structured execution-log metadata."""
        if not isinstance(log.error_log, dict):
            return None

        if log.phase == "pipeline_completed_with_errors":
            failed_jurisdiction_count = log.error_log.get("failed_jurisdiction_count")
            failure: dict[str, Any] = {
                "category": "partial_failure",
                "error_code": "CAMPAIGN_PIPELINE_PARTIAL_FAILURE",
                "message": (
                    log.error_log.get("message")
                    or "Campaign reached monitoring with partial scraping failures."
                ),
                "retryable": True,
            }
            if isinstance(failed_jurisdiction_count, int):
                failure["failed_jurisdiction_count"] = failed_jurisdiction_count
            return failure

        return None

    def _revoke_task_chain(self, task_ids: list[str]) -> None:
        """Revoke pending tasks without terminating running tasks."""
        for task_id in task_ids:
            self.celery_control.revoke(task_id, terminate=False)

    async def run(self, campaign_id: UUID, **kwargs) -> dict[str, str]:
        """Launch the full campaign pipeline as a Celery chain.

        Campaigns can be launched from DRAFT (full pipeline), TAXONOMY_READY
        (skips taxonomy, starts at hydration), or any in-progress phase
        (HYDRATING / DISCOVERING_SOURCES / SCRAPING / PUBLISHING) for targeted
        recovery relaunch.

        Args:
            campaign_id: Campaign identifier.
            **kwargs: Optional runtime metadata such as ``launched_by``.

        Returns:
            dict with ``backend`` and ``task_id`` keys.

        Raises:
            ResourceNotFoundError: Campaign does not exist.
            ProcessingError: Campaign state is not launchable.
        """
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        launchable_statuses = {
            CampaignStatus.DRAFT,
            CampaignStatus.TAXONOMY_READY,
            CampaignStatus.GENERATING_TAXONOMY,
            CampaignStatus.HYDRATING,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
        }
        if campaign.status not in launchable_statuses:
            raise ProcessingError(
                message=(
                    "Campaign can only be launched from DRAFT, TAXONOMY_READY, "
                    "or active recovery phases."
                ),
            )

        launched_by = kwargs.get("launched_by")
        if launched_by is not None:
            campaign.launched_by = launched_by

        provided_run_id = kwargs.get("run_id")
        run_id = str(provided_run_id).strip() if provided_run_id else str(uuid4())

        # ── Idempotency guard ─────────────────────────────────────────────────
        # For any in-progress status, return the existing task chain rather than
        # dispatching a second parallel chain.  DISCOVERING_SOURCES is included
        # here because a soft-time-limit retry will have reset the status to
        # DISCOVERING_SOURCES before re-launching — if run() is called again
        # before the retry fires we should not double-dispatch.
        in_progress_statuses = {
            CampaignStatus.GENERATING_TAXONOMY,
            CampaignStatus.HYDRATING,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
        }
        if campaign.status in in_progress_statuses:
            pipeline_control = (
                campaign.stats.get("pipeline_control", {})
                if isinstance(campaign.stats, dict)
                else {}
            )
            has_pipeline_metadata = isinstance(pipeline_control, dict) and bool(pipeline_control)
            existing_task_ids = self._task_id_list_from_stats(campaign.stats)
            existing_run_id = ""
            if isinstance(campaign.stats, dict):
                existing_run_id = str(
                    (campaign.stats.get("pipeline_control") or {}).get("run_id") or ""
                )
            if existing_task_ids:
                return {
                    "backend": "celery",
                    "task_id": existing_task_ids[0],
                    "run_id": existing_run_id or run_id,
                }
            if has_pipeline_metadata and campaign.updated_at is not None:
                elapsed = (datetime.now(timezone.utc) - campaign.updated_at).total_seconds()
                if elapsed < 300:
                    return {
                        "backend": "celery",
                        "task_id": str(campaign.id),
                        "run_id": existing_run_id or run_id,
                    }

        # ── Determine which pipeline slice to run and what status to set ──────
        if campaign.status in {CampaignStatus.TAXONOMY_READY, CampaignStatus.HYDRATING}:
            first_phase = CampaignStatus.HYDRATING
            campaign.status = CampaignStatus.HYDRATING
            task_chain = self._base_pipeline_for_campaign(campaign_id, run_id)[1:]

        elif campaign.status == CampaignStatus.DISCOVERING_SOURCES:
            # Recovery launch: pick up from source discovery.  Status is already
            # DISCOVERING_SOURCES (set by _reset_campaign_for_discovery_retry or
            # reset_to_discovery); leave it as-is so _validate_status() passes.
            first_phase = CampaignStatus.DISCOVERING_SOURCES
            # status already correct — no change needed
            task_chain = self._base_pipeline_for_campaign(campaign_id, run_id)[2:]

        elif campaign.status == CampaignStatus.SCRAPING:
            # Recovery launch from scraping phase after explicit reset.
            first_phase = CampaignStatus.SCRAPING
            task_chain = self._base_pipeline_for_campaign(campaign_id, run_id)[3:]

        elif campaign.status == CampaignStatus.PUBLISHING:
            # Recovery launch from publishing phase after explicit reset.
            first_phase = CampaignStatus.PUBLISHING
            task_chain = self._base_pipeline_for_campaign(campaign_id, run_id)[4:]

        else:
            # DRAFT or GENERATING_TAXONOMY → full pipeline
            first_phase = CampaignStatus.GENERATING_TAXONOMY
            campaign.status = CampaignStatus.GENERATING_TAXONOMY
            task_chain = self._base_pipeline_for_campaign(campaign_id, run_id)

        campaign.updated_at = datetime.now(timezone.utc)
        self.db.add(campaign)
        await self.db.commit()

        pipeline = chain(*task_chain).on_error(
            campaign_pipeline_error_handler.s(str(campaign_id), run_id)
        )
        try:
            async_result = pipeline.apply_async()
        except Exception as exc:
            await self.db.rollback()
            campaign.status = CampaignStatus.FAILED
            campaign.updated_at = datetime.now(timezone.utc)
            execution_log = CampaignExecutionLog(
                campaign_id=campaign_id,
                phase="pipeline_error",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                error_log={
                    "exception": str(exc),
                    "source": "orchestration_run",
                    "run_id": run_id,
                },
            )
            self.db.add(campaign)
            self.db.add(execution_log)
            await self.db.commit()
            raise

        task_ids = self._collect_chain_task_ids(async_result)
        if async_result.id and async_result.id not in task_ids:
            task_ids.insert(0, async_result.id)

        campaign.stats = self._upsert_pipeline_control(
            campaign.stats,
            task_ids=task_ids,
            last_started_status=first_phase,
            run_id=run_id,
        )
        self.db.add(campaign)
        await self.db.commit()

        return {"backend": "celery", "task_id": async_result.id, "run_id": run_id}

    async def get_status(self, campaign_id: UUID) -> dict[str, Any]:
        """Return current pipeline status for a campaign."""
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        snapshot = campaign.generation_config_snapshot or {}
        task_id = snapshot.get("taxonomy_task_id")
        pipeline_control = (
            campaign.stats.get("pipeline_control", {}) if isinstance(campaign.stats, dict) else {}
        )
        run_id = pipeline_control.get("run_id") if isinstance(pipeline_control, dict) else None
        pipeline_failure = (
            pipeline_control.get("failure") if isinstance(pipeline_control, dict) else None
        )

        failure: dict[str, Any] | None = None
        if isinstance(pipeline_failure, dict):
            failure = pipeline_failure

        snapshot_failure = snapshot.get("failure") if isinstance(snapshot, dict) else None
        if failure is None and isinstance(snapshot_failure, dict):
            failure = snapshot_failure
        else:
            last_error = snapshot.get("last_error") if isinstance(snapshot, dict) else None
            if failure is None and isinstance(last_error, str) and last_error.strip():
                failure = self._classify_failure_from_error_text(last_error)

        latest_log_with_error: CampaignExecutionLog | None = None
        if failure is None or not run_id:
            result = await self.db.execute(
                select(CampaignExecutionLog)
                .where(CampaignExecutionLog.campaign_id == campaign_id)
                .order_by(CampaignExecutionLog.started_at.desc())
            )
            execution_logs = result.scalars().all()
            for log in execution_logs:
                if isinstance(log.error_log, dict):
                    latest_log_with_error = log
                    if failure is None:
                        failure = self._failure_from_execution_log(log)
                    break

        latest_error_log = latest_log_with_error.error_log if latest_log_with_error else None

        if not run_id and isinstance(latest_error_log, dict):
            log_run_id = latest_error_log.get("run_id")
            run_id = str(log_run_id) if log_run_id else None

        if failure is None and isinstance(latest_error_log, dict):
            exception_text = latest_error_log.get("exception")
            if isinstance(exception_text, str) and exception_text.strip():
                failure = self._classify_failure_from_error_text(exception_text)

        content_service = CampaignContentService(self.db)
        content_summary = await content_service.build_content_summary(
            campaign_id,
            campaign.stats if isinstance(campaign.stats, dict) else {},
        )

        return {
            "status": campaign.status.value,
            "campaign_id": str(campaign_id),
            "taxonomy_task_id": str(task_id) if task_id else "",
            "run_id": str(run_id) if run_id else "",
            "failure": failure,
            "content_pipeline_status": content_summary.get(
                "content_pipeline_status",
                "NOT_STARTED",
            ),
            "content_summary": content_summary,
        }

    async def pause(self, campaign_id: UUID) -> None:
        """Pause a campaign by revoking pending task chain work."""
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        pauseable_states = {
            CampaignStatus.GENERATING_TAXONOMY,
            CampaignStatus.HYDRATING,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
        }
        if campaign.status not in pauseable_states:
            raise ProcessingError(
                message=f"Campaign cannot be paused from state {campaign.status.value}.",
            )

        task_ids = self._task_id_list_from_stats(campaign.stats)
        self._revoke_task_chain(task_ids)

        paused_from = campaign.status.value
        campaign.stats = self._upsert_pipeline_control(
            campaign.stats,
            task_ids=task_ids,
            last_started_status=campaign.status,
            paused_from_status=paused_from,
            paused_at=datetime.now(timezone.utc).isoformat(),
        )
        campaign.status = CampaignStatus.PAUSED
        campaign.updated_at = datetime.now(timezone.utc)

        self.db.add(campaign)
        await self.db.commit()

        logger.info("Paused campaign %s (was %s)", campaign_id, paused_from)

    async def resume(self, campaign_id: UUID) -> None:
        """Resume a paused campaign from the recorded paused phase."""
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        if campaign.status != CampaignStatus.PAUSED:
            raise ProcessingError(message="Campaign is not paused")

        pipeline_control = (
            campaign.stats.get("pipeline_control", {}) if isinstance(campaign.stats, dict) else {}
        )
        paused_from_raw = pipeline_control.get("paused_from_status")
        if not isinstance(paused_from_raw, str):
            raise ProcessingError(message="Campaign is paused without resume metadata")

        try:
            paused_from_status = CampaignStatus(paused_from_raw)
        except ValueError as exc:
            raise ProcessingError(message="Campaign has invalid resume metadata") from exc

        run_id = str(uuid4())
        resumed_chain = self._pipeline_from_status(campaign_id, paused_from_status, run_id)
        pipeline = chain(*resumed_chain).on_error(
            campaign_pipeline_error_handler.s(str(campaign_id), run_id)
        )
        async_result = pipeline.apply_async()
        task_ids = self._collect_chain_task_ids(async_result)
        if async_result.id and async_result.id not in task_ids:
            task_ids.insert(0, async_result.id)

        campaign.status = paused_from_status
        campaign.updated_at = datetime.now(timezone.utc)
        campaign.stats = self._upsert_pipeline_control(
            campaign.stats,
            task_ids=task_ids,
            last_started_status=paused_from_status,
            run_id=run_id,
        )

        self.db.add(campaign)
        await self.db.commit()

        logger.info("Resumed campaign %s from %s", campaign_id, paused_from_status.value)

    async def cancel(self, campaign_id: UUID) -> None:
        """Cancel a campaign and revoke pending orchestration tasks."""
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        if campaign.status in {
            CampaignStatus.COMPLETED,
            CampaignStatus.MONITORING,
            CampaignStatus.CANCELLED,
        }:
            raise ProcessingError(
                message=f"Cannot cancel campaign in state {campaign.status.value}.",
            )

        task_ids = self._task_id_list_from_stats(campaign.stats)
        self._revoke_task_chain(task_ids)

        campaign.status = CampaignStatus.CANCELLED
        campaign.updated_at = datetime.now(timezone.utc)
        campaign.stats = self._upsert_pipeline_control(
            campaign.stats,
            task_ids=task_ids,
            last_started_status=CampaignStatus.CANCELLED,
        )

        self.db.add(campaign)
        await self.db.commit()

        logger.info("Cancelled campaign %s", campaign_id)

    async def reset_to_discovery(self, campaign_id: UUID) -> None:
        """Reset a failed or stuck campaign back to source discovery phase.

        This recovery action allows campaigns that failed during discovery or
        got stuck in intermediate/terminal states to be retried without
        re-running the taxonomy and hydration phases.

        Args:
            campaign_id: Campaign identifier.

        Raises:
            ResourceNotFoundError: Campaign does not exist.
            ProcessingError: Campaign is in a non-recoverable state.
        """
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        resettable_states = {
            CampaignStatus.FAILED,
            CampaignStatus.CANCELLED,
            CampaignStatus.MONITORING,
            CampaignStatus.HYDRATING,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
            CampaignStatus.PAUSED,
        }
        if campaign.status not in resettable_states:
            raise ProcessingError(
                message=(
                    f"Campaign in state '{campaign.status.value}' cannot be reset. "
                    "Only FAILED, CANCELLED, MONITORING, HYDRATING, DISCOVERING_SOURCES, "
                    "SCRAPING, PUBLISHING, or PAUSED campaigns can be recovered."
                )
            )

        previous_status = campaign.status.value

        task_ids = self._task_id_list_from_stats(campaign.stats)
        if task_ids:
            self._revoke_task_chain(task_ids)
            logger.info("Revoked %d pending tasks for campaign %s", len(task_ids), campaign_id)

        campaign.status = CampaignStatus.DISCOVERING_SOURCES
        campaign.updated_at = datetime.now(timezone.utc)

        if isinstance(campaign.stats, dict):
            stats = dict(campaign.stats)
            stats.pop("pipeline_control", None)
            campaign.stats = stats

        self.db.add(campaign)
        await self.db.commit()

        logger.info(
            "Reset campaign %s to DISCOVERING_SOURCES for recovery (was %s).",
            campaign_id,
            previous_status,
        )

    async def reset_to_status(self, campaign_id: UUID, target_status: CampaignStatus) -> None:
        """Reset a failed or stuck campaign back to a specific target status.

        Args:
            campaign_id: Campaign identifier.
            target_status: The pipeline phase to reset the campaign to.

        Raises:
            ResourceNotFoundError: Campaign does not exist.
            ProcessingError: Target state invalid or campaign in non-recoverable state.
        """
        valid_targets = {
            CampaignStatus.DRAFT,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
        }
        if target_status not in valid_targets:
            raise ProcessingError(
                message=f"Cannot reset to {target_status.value}. Invalid target status."
            )

        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        resettable_states = {
            CampaignStatus.FAILED,
            CampaignStatus.CANCELLED,
            CampaignStatus.MONITORING,
            CampaignStatus.HYDRATING,
            CampaignStatus.DISCOVERING_SOURCES,
            CampaignStatus.SCRAPING,
            CampaignStatus.PUBLISHING,
            CampaignStatus.PAUSED,
        }
        if campaign.status not in resettable_states:
            raise ProcessingError(
                message=(
                    f"Campaign in state '{campaign.status.value}' cannot be reset. "
                    "Only FAILED, CANCELLED, MONITORING, HYDRATING, DISCOVERING_SOURCES, "
                    "SCRAPING, PUBLISHING, or PAUSED campaigns can be recovered."
                )
            )

        previous_status = campaign.status.value

        task_ids = self._task_id_list_from_stats(campaign.stats)
        if task_ids:
            self._revoke_task_chain(task_ids)
            logger.info("Revoked %d pending tasks for campaign %s", len(task_ids), campaign_id)

        campaign.status = target_status
        campaign.updated_at = datetime.now(timezone.utc)

        if isinstance(campaign.stats, dict):
            stats = dict(campaign.stats)
            stats.pop("pipeline_control", None)
            campaign.stats = stats

        # Full reset to DRAFT: wipe taxonomy and approval data so the campaign
        # can be re-configured and re-launched from scratch.
        if target_status == CampaignStatus.DRAFT:
            campaign.taxonomy_json = None
            campaign.generation_model = None
            campaign.generation_config_snapshot = None
            campaign.taxonomy_approved_by = None
            campaign.taxonomy_approved_at = None

        self.db.add(campaign)
        await self.db.commit()

        logger.info(
            "Reset campaign %s to %s for recovery (was %s).",
            campaign_id,
            target_status.value,
            previous_status,
        )

    async def smart_reset(self, campaign_id: UUID) -> dict[str, str]:
        """Automatically detect the failed pipeline phase and reset to it.

        Args:
            campaign_id: Campaign identifier.

        Returns:
            dict containing the chosen target status.

        Raises:
            ResourceNotFoundError: Campaign does not exist.
            ProcessingError: If no eligible reset state can be determined.
        """
        campaign = await self.db.get(Campaign, campaign_id)
        if not campaign:
            raise ResourceNotFoundError(message="Campaign not found")

        jurisdictions_result = await self.db.execute(
            select(Jurisdiction).where(Jurisdiction.campaign_id == campaign_id)
        )
        jurisdictions = jurisdictions_result.scalars().all()

        incomplete_discovery = any(
            j.discovery_status in {DiscoveryStatus.DISCOVERY_FAILED, DiscoveryStatus.PENDING}
            for j in jurisdictions
        )

        scrape_jobs_result = await self.db.execute(
            select(JurisdictionScrapeJob)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionScrapeJob.jurisdiction_id)
            .where(Jurisdiction.campaign_id == campaign_id)
        )
        scrape_jobs = scrape_jobs_result.scalars().all()

        incomplete_scraping = any(
            job.status != JurisdictionScrapeJobStatus.COMPLETED for job in scrape_jobs
        )

        target_status = None
        if incomplete_discovery:
            target_status = CampaignStatus.DISCOVERING_SOURCES
        elif incomplete_scraping:
            target_status = CampaignStatus.SCRAPING
        else:
            target_status = CampaignStatus.PUBLISHING

        await self.reset_to_status(campaign_id, target_status)
        return {"target_status": target_status.value}
