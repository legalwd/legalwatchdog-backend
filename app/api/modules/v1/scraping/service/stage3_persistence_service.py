"""Stage 3: Database persistence and result finalization.

Responsibilities:
- Update Source last_scraped_at and next_scrape_time
- Update ScrapeJob status to COMPLETED
- Link DataRevision to job
- Trigger Stage 4 for change detection and notifications
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlmodel import Session, select

from app.api.core.custom_exceptions.exceptions import (
    ProcessingError,
)
from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source

logger = logging.getLogger(__name__)


class Stage3PersistenceService:
    """Orchestrates Stage 3: Database persistence."""

    def execute(self, source_id: str, job_id: str, revision_id: str) -> Dict[str, Any]:
        """Execute Stage 3 persistence pipeline.

        Args:
            source_id (str): UUID of the source.
            job_id (str): UUID of the ScrapeJob.
            revision_id (str): UUID of the DataRevision.

        Returns:
            dict: Status with keys:
                - status: 'completed' or 'failed'
                - revision_id: UUID of revision
                - content_hash: SHA-256 hash

        Raises:
            Exception: Propagated to Celery for retry logic.

        Examples:
            >>> service = Stage3PersistenceService()
            >>> result = service.execute("source-uuid", "job-uuid", "revision-uuid")
        """
        with SyncSessionLocal() as db:
            return self._execute_with_db(db, source_id, job_id, revision_id)

    def _execute_with_db(
        self, db: Session, source_id: str, job_id: str, revision_id: str
    ) -> Dict[str, Any]:
        """Execute persistence with database session.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.
            job_id (str): Job UUID.
            revision_id (str): Revision UUID.

        Returns:
            dict: Persistence result.
        """
        job = db.exec(select(ScrapeJob).where(ScrapeJob.id == job_id)).first()

        if not job:
            logger.error(f"ScrapeJob {job_id} not found")
            return {"status": "failed", "reason": "job_not_found"}

        revision = db.exec(select(DataRevision).where(DataRevision.id == revision_id)).first()

        if not revision:
            logger.error(f"DataRevision {revision_id} not found")
            self._fail_job(db, job, "DataRevision not found")
            return {"status": "failed", "reason": "revision_not_found"}

        source = db.exec(select(Source).where(Source.id == source_id)).first()

        if not source:
            logger.error(f"Source {source_id} not found")
            self._fail_job(db, job, "Source not found")
            return {"status": "failed", "reason": "source_not_found"}

        try:
            self._update_source(db, source)

            self._complete_job(db, job, revision)

            logger.info(f"Stage 3 complete for {source_id}: job={job_id}, revision={revision_id}")

            return {
                "status": "completed",
                "revision_id": str(revision_id),
                "content_hash": revision.content_hash,
            }

        except Exception as e:
            logger.exception(f"Stage 3 failed: {e}")
            self._fail_job(db, job, "An unexpected error occurred during persistence.")
            raise ProcessingError("Failed to persist data. Please try again.")

    @staticmethod
    def _update_source(db: Session, source: Source) -> None:
        """Update source metadata.

        Args:
            db (Session): Database session.
            source (Source): Source to update.
        """
        source.last_scraped_at = datetime.now(timezone.utc)
        source.next_scrape_time = get_next_scrape_time(
            datetime.now(timezone.utc), source.scrape_frequency
        )
        db.add(source)
        db.commit()

    @staticmethod
    def _complete_job(db: Session, job: ScrapeJob, revision: DataRevision) -> None:
        """Complete job and link revision.

        Args:
            db (Session): Database session.
            job (ScrapeJob): Job to complete.
            revision (DataRevision): Associated revision.
        """
        job.status = ScrapeJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.data_revision_id = revision.id
        job.result = {
            "status": "success",
            "revision_id": str(revision.id),
            "content_hash": revision.content_hash,
            "confidence_score": revision.ai_confidence_score,
        }
        db.add(job)
        db.commit()

    @staticmethod
    def _fail_job(db: Session, job: ScrapeJob, error: str) -> None:
        """Fail job with error message.

        Args:
            db (Session): Database session.
            job (ScrapeJob): Job to fail.
            error (str): Error message.
        """
        from app.api.modules.v1.scraping.service.error_types import analyze_error

        _, user_message, _ = analyze_error(Exception(error))

        job.status = ScrapeJobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = user_message
        job.result = {
            "error": error,
            "user_message": user_message,
        }
        db.add(job)
        db.commit()


def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculate next scrape time.

    Args:
        current_time (datetime): Current time anchor.
        frequency (ScrapeFrequency): Scrape frequency.

    Returns:
        datetime: Next scheduled scrape time.
    """
    frequency_map = {
        ScrapeFrequency.DAILY: timedelta(days=1),
        ScrapeFrequency.WEEKLY: timedelta(weeks=1),
        ScrapeFrequency.MONTHLY: timedelta(days=30),
        ScrapeFrequency.HOURLY: timedelta(hours=1),
    }
    delta = frequency_map.get(frequency, timedelta(days=1))
    return current_time + delta
