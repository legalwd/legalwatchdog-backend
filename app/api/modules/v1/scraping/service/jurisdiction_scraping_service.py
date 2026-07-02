"""Service for orchestrating jurisdiction-wide scraping operations.

This service manages the lifecycle of bulk scraping for jurisdictions, including:
1. Triggering batch scrapes for all sources in a jurisdiction.
2. Tracking progress of the batch.
3. Consolidating results once all sources are processed.
"""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.api.core.custom_exceptions.exceptions import (
    JobNotFoundError,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.api.modules.v1.scraping.utils.hash_utils import calculate_jurisdiction_content_hash

# from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class JurisdictionScrapingService:
    """Orchestrator for jurisdiction-level scraping."""

    def __init__(self, db_session: Session):
        """Initialize service.

        Args:
            db_session (Session): Database session.
        """
        self.db = db_session

    def trigger_jurisdiction_scrape(self, jurisdiction_id: UUID) -> JurisdictionScrapeJob:
        """Trigger a scrape for all sources in a jurisdiction.

        Args:
            jurisdiction_id (UUID): ID of the jurisdiction to scrape.

        Returns:
            JurisdictionScrapeJob: The created job tracking the batch operation.

        Raises:
            ValueError: If jurisdiction not found or has no active sources.
        """
        jurisdiction = self.db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction:
            raise JobNotFoundError("Jurisdiction not found.")

        sources = self.db.exec(
            select(Source).where(
                Source.jurisdiction_id == jurisdiction_id,
                Source.is_active == True,  # noqa: E712
                Source.is_deleted == False,  # noqa: E712
            )
        ).all()

        if not sources:
            logger.info(
                f"No active sources found for jurisdiction {jurisdiction_id}. "
                "Moving to CONSOLIDATING."
            )
            job = JurisdictionScrapeJob(
                jurisdiction_id=jurisdiction_id,
                status=JurisdictionScrapeJobStatus.CONSOLIDATING,
                total_sources=0,
                successful_sources=0,
                started_at=datetime.now(timezone.utc),
                content_hash="empty_no_sources",
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)

            from app.celery_app import celery_app  # Lazy import

            celery_app.send_task(
                "app.api.modules.v1.scraping.service.tasks.consolidate_jurisdiction_content",
                args=[str(job.id)],
                queue="processing",
            )
            return job

        job = JurisdictionScrapeJob(
            jurisdiction_id=jurisdiction_id,
            status=JurisdictionScrapeJobStatus.SCRAPING,
            total_sources=len(sources),
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self._dispatch_sources(job, sources)

        return job

    def _dispatch_sources(self, job: JurisdictionScrapeJob, sources: List[Source]) -> int:
        """Dispatch Stage 1 scraping tasks for each source.

        Args:
            job (JurisdictionScrapeJob): The parent job.
            sources (List[Source]): List of sources to scrape.

        Returns:
            int: Number of tasks dispatched.

        Raises:
            ScrapeAlreadyInProgressError: If any source already has an active scrape job.
        """
        for source in sources:
            existing_job = self.db.exec(
                select(ScrapeJob)
                .where(ScrapeJob.source_id == source.id)
                .where(ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]))
            ).first()

            if existing_job:
                from app.api.core.custom_exceptions.exceptions import ScrapeAlreadyInProgressError

                raise ScrapeAlreadyInProgressError(
                    f"A scrape is already in progress for {source.name}. "
                    f"Please wait for it to complete before starting a new one."
                )

        jobs_to_dispatch = []
        for source in sources:
            scrape_job_id = uuid4()
            scrape_job = ScrapeJob(
                id=scrape_job_id,
                source_id=source.id,
                jurisdiction_scrape_job_id=job.id,
                status=ScrapeJobStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(scrape_job)

            if source.scrape_frequency:
                source.next_scrape_time = self._calculate_next_scrape_time(
                    datetime.now(timezone.utc), source.scrape_frequency
                )
                self.db.add(source)

            jobs_to_dispatch.append((source, scrape_job))

        self.db.commit()

        dispatched_count = 0
        failed_jobs = []
        for source, scrape_job in jobs_to_dispatch:
            try:
                from app.celery_app import celery_app  # Lazy import

                celery_app.send_task(
                    "app.api.modules.v1.scraping.service.tasks.scrape_source_stage1",
                    args=[str(source.id), str(scrape_job.id)],
                    queue="scraping",
                )
                dispatched_count += 1

            except Exception:
                logger.exception(
                    "Failed to dispatch source %s for jurisdiction job %s",
                    source.id,
                    job.id,
                )
                failed_jobs.append(scrape_job)
                scrape_job.status = ScrapeJobStatus.FAILED
                scrape_job.error_message = "Dispatch failed due to an internal processing error."
                scrape_job.completed_at = datetime.now(timezone.utc)
                self.db.add(scrape_job)

        if failed_jobs:
            self.db.commit()

        if dispatched_count == 0 and sources:
            logger.warning(
                "All source dispatches failed for jurisdiction job %s. Marking parent as FAILED.",
                job.id,
            )
            job.status = JurisdictionScrapeJobStatus.FAILED
            job.error_message = "All source dispatches failed"
            job.completed_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()

        logger.info(
            f"Dispatched {dispatched_count}/{len(sources)} sources for Jurisdiction Job {job.id}"
        )
        return dispatched_count

    def check_batch_completion(self, jurisdiction_job_id: UUID) -> bool:
        """Check if all sources in the batch have completed.

        If all are complete, triggers the Consolidation stage.

        Args:
            jurisdiction_job_id (UUID): ID of the jurisdiction job.

        Returns:
            bool: True if batch is complete, False otherwise.
        """
        job = self.db.get(JurisdictionScrapeJob, jurisdiction_job_id)
        if not job or job.status != JurisdictionScrapeJobStatus.SCRAPING:
            return False

        incomplete_count = self.db.exec(
            select(ScrapeJob).where(
                ScrapeJob.jurisdiction_scrape_job_id == jurisdiction_job_id,
                ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]),
            )
        ).first()

        if incomplete_count:
            return False

        completed_jobs = self.db.exec(
            select(ScrapeJob).where(
                ScrapeJob.jurisdiction_scrape_job_id == jurisdiction_job_id,
                ScrapeJob.status == ScrapeJobStatus.COMPLETED,
            )
        ).all()

        if not completed_jobs:
            # All jobs failed — mark jurisdiction job as FAILED so pipeline can unblock
            logger.warning(
                f"All source scrape jobs failed for jurisdiction job {jurisdiction_job_id}. "
                "Marking as FAILED."
            )
            job.status = JurisdictionScrapeJobStatus.FAILED
            job.error_message = "All source scrape jobs failed"
            job.completed_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()
            return False

        logger.info(
            f"All sources completed for Jurisdiction Job "
            f"{jurisdiction_job_id}. Moving to CONSOLIDATING."
        )

        jurisdiction = self.db.get(Jurisdiction, job.jurisdiction_id)
        jurisdiction_prompt = (jurisdiction.prompt if jurisdiction else None) or ""

        job.content_hash = calculate_jurisdiction_content_hash(completed_jobs, jurisdiction_prompt)
        job.successful_sources = len(completed_jobs)
        job.status = JurisdictionScrapeJobStatus.CONSOLIDATING
        self.db.add(job)
        self.db.commit()

        logger.info(
            f"Calculated content hash for jurisdiction job {jurisdiction_job_id}: "
            f"{job.content_hash[:16]}..."
        )

        from app.celery_app import celery_app  # Lazy import

        celery_app.send_task(
            "app.api.modules.v1.scraping.service.tasks.consolidate_jurisdiction_content",
            args=[str(jurisdiction_job_id)],
            queue="processing",
        )

        return True

    @staticmethod
    def _calculate_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
        """Calculate next scrape time (helper, similar to tasks.py but reusable)."""
        from datetime import timedelta

        frequency_map = {
            ScrapeFrequency.DAILY: timedelta(days=1),
            ScrapeFrequency.WEEKLY: timedelta(weeks=1),
            ScrapeFrequency.MONTHLY: timedelta(days=30),
            ScrapeFrequency.HOURLY: timedelta(hours=1),
        }
        delta = frequency_map.get(frequency, timedelta(days=1))
        return current_time + delta
