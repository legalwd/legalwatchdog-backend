"""Stage 1: Web scraping with content deduplication.

Responsibilities:
- Acquire Redis distributed lock to prevent duplicate scrapes
- Call Parallel.ai Extract API (network I/O)
- Calculate SHA-256 content hash
- Check for duplicate content via deduplication
- Create DataRevision with pending_extraction status
- Chain to Stage 2 if content changed
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

import redis
from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.core.constants import ErrorCodes
from app.api.core.custom_exceptions.exceptions import (
    EmptyContentError,
    ParallelExtractionError,
    ProcessingError,
    ScrapingError,
    StorageError,
)
from app.api.modules.v1.scraping.models.data_revision import (
    DataRevision,
    ExtractionStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.api.modules.v1.scraping.service.parallel_extract_service import (
    ParallelExtractService,
)

logger = logging.getLogger(__name__)

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class Stage1ScrapingService:
    """Orchestrates Stage 1: Web scraping and deduplication."""

    def __init__(
        self,
        redis_pool: Optional[redis.ConnectionPool] = None,
        db_session: Optional[Session] = None,
    ):
        """Initialize Stage 1 service.

        Args:
            redis_pool (Optional[redis.ConnectionPool]): Redis connection pool.
                If None, creates from settings.REDIS_URL.
            db_session (Optional[Session]): Sync database session for usage logging.
        """
        if redis_pool is None:
            redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
        self.redis_pool = redis_pool
        self.db_session = db_session
        self.parallel_extractor = ParallelExtractService(db_session=db_session)

    def execute(
        self, source_id: str, job_id: str, task_request_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Execute Stage 1 scraping pipeline.

        Args:
            source_id (str): UUID of the source to scrape.
            job_id (str): UUID of the ScrapeJob to update.
            task_request_id (str): Celery task request ID for lock value.

        Returns:
            dict: Status with keys:
                - status: 'completed', 'skipped', or 'failed'
                - reason: Human-readable explanation
                - revision_id: UUID of DataRevision (if applicable)
                - content_hash: SHA-256 hash (if applicable)

        Raises:
            Exception: Propagated to Celery for retry logic.

        Examples:
            >>> service = Stage1ScrapingService()
            >>> result = service.execute("source-uuid", "job-uuid", "task-id")
            >>> print(result['status'])
            'completed'
        """
        redis_client = redis.Redis(connection_pool=self.redis_pool)
        lock_key = f"scrape_lock:{source_id}"
        lock_value = task_request_id or "unknown"
        lock_timeout = 300

        try:
            lock_acquired = redis_client.set(lock_key, lock_value, nx=True, ex=lock_timeout)

            if not lock_acquired:
                logger.warning(f"Source {source_id} already being scraped (lock held)")
                return {"status": "skipped", "reason": "concurrent_scrape_in_progress"}

            if self.db_session:
                return self._execute_with_lock(self.db_session, source_id, job_id)
            else:
                from app.api.db.database import SyncSessionLocal

                with SyncSessionLocal() as db:
                    return self._execute_with_lock(db, source_id, job_id)

        finally:
            self._release_lock(redis_client, lock_key, lock_value)

    def _execute_with_lock(self, db: Session, source_id: str, job_id: str) -> Dict[str, str]:
        """Execute scraping with lock held using sync session.

        Args:
            db (Session): Database session.
            source_id (str): UUID of source.
            job_id (str): UUID of job.

        Returns:
            dict: Execution result.
        """
        job = self._claim_job(db, job_id)
        if not job:
            logger.warning(f"Job {job_id} not found or already claimed")
            return {"status": "skipped", "reason": "job_already_claimed"}

        job.status = ScrapeJobStatus.IN_PROGRESS
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        source = db.exec(select(Source).where(Source.id == source_id)).first()

        if not source:
            job.status = ScrapeJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.result = {"error": "Source not found"}
            db.add(job)
            db.commit()
            return {"status": "failed", "reason": "source_not_found"}

        try:
            content, minio_key = self._extract_content_sync(source)
            content_hash = self._compute_hash(content)

            last_revision = self._get_last_revision(db, source_id)

            if last_revision and last_revision.content_hash == content_hash:
                return self._handle_unchanged_content(db, source, job, last_revision)

            logger.info(
                f"Stage 1 complete for {source_id}: content scraped, hash={content_hash[:8]}"
            )

            job.status = ScrapeJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.result = {
                "status": "scraped",
                "reason": "new_content_scraped",
                "content_hash": content_hash,
                "minio_key": minio_key,
            }

            if job.jurisdiction_scrape_job_id:
                revision = self._create_revision(db, source_id, content_hash, minio_key)
                job.result["revision_id"] = str(revision.id)
                logger.info(
                    f"Created revision {revision.id} for source {source_id} "
                    f"(jurisdiction batch job {job.jurisdiction_scrape_job_id})"
                )

            db.add(job)
            db.commit()

            return {
                "status": "completed",
                "reason": "new_content_scraped",
                "content_hash": content_hash,
                "minio_key": minio_key,
            }

        except (ParallelExtractionError, EmptyContentError, ScrapingError, StorageError) as e:
            logger.error(f"Stage 1 failed for {source_id}: {type(e).__name__}: {e.message}")

            job.status = ScrapeJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = e.message
            job.result = {
                "error": e.code,
                "message": e.message,
                "status_code": 500,
                "errors": {},
            }
            db.add(job)
            db.commit()
            raise

        except Exception as e:
            logger.exception(f"Unexpected error in Stage 1 for {source_id}: {e}")

            job.status = ScrapeJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = "An unexpected error occurred during scraping."
            job.result = {
                "error": ErrorCodes.EXTRACTION_FAILED,
                "message": (
                    "Content extraction failed due to a technical issue. Please try again later."
                ),
                "status_code": 500,
                "errors": {},
            }
            db.add(job)
            db.commit()
            raise ProcessingError("Failed to scrape content. Please try again.")

    def _claim_job(self, db: Session, job_id: str) -> Optional[ScrapeJob]:
        """Claim job with FOR UPDATE SKIP LOCKED.

        Args:
            db (Session): Database session.
            job_id (str): Job UUID.

        Returns:
            Optional[ScrapeJob]: Claimed job or None.
        """
        stmt = (
            select(ScrapeJob)
            .where(ScrapeJob.id == job_id, ScrapeJob.status == ScrapeJobStatus.PENDING)
            .with_for_update(skip_locked=True)
        )
        return db.exec(stmt).first()

    @staticmethod
    def _compute_hash(content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content (str): Content to hash.

        Returns:
            str: Hex digest of SHA-256.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_last_revision(db: Session, source_id: str) -> Optional[DataRevision]:
        """Get last revision for source.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.

        Returns:
            Optional[DataRevision]: Last revision or None.
        """
        stmt = (
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .order_by(DataRevision.scraped_at.desc())
            .limit(1)
        )
        return db.exec(stmt).first()

    @staticmethod
    def _handle_unchanged_content(
        db: Session, source: Source, job: ScrapeJob, last_revision: DataRevision
    ) -> Dict[str, str]:
        """Handle case where content is unchanged.

        Creates a new revision that inherits the extraction data from the previous
        revision to ensure frontend consistency. This way, every scrape has a
        revision with populated AI fields, even when content hasn't changed.

        Args:
            db (Session): Database session.
            source (Source): Source being scraped.
            job (ScrapeJob): Scrape job to update.
            last_revision (DataRevision): Last revision with same hash.

        Returns:
            dict: Result with new revision info.

        Raises:
            Exception: On database errors.

        Examples:
            >>> result = service._handle_unchanged_content(db, source, job, revision)
            >>> result['status']
            'completed'
            >>> result['revision_id'] != str(revision.id)
            True
        """
        logger.info(
            f"Source {source.id}: Content unchanged, creating revision with inherited extraction"
        )

        new_revision = DataRevision(
            id=uuid4(),
            source_id=source.id,
            minio_object_key=last_revision.minio_object_key,
            content_hash=last_revision.content_hash,
            extracted_data=last_revision.extracted_data,
            ai_summary=last_revision.ai_summary,
            ai_markdown_summary=last_revision.ai_markdown_summary,
            ai_confidence_score=last_revision.ai_confidence_score,
            extraction_status=ExtractionStatus.COMPLETED,
            scraped_at=datetime.utcnow(),
            was_change_detected=False,
            is_baseline=False,
        )

        db.add(new_revision)

        job.status = ScrapeJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.result = {
            "status": "content_unchanged",
            "revision_id": str(new_revision.id),
            "inherited_from": str(last_revision.id),
            "content_hash": last_revision.content_hash,
            "minio_key": last_revision.minio_object_key,
        }
        db.add(job)

        source.last_scraped_at = datetime.now(timezone.utc)
        source.next_scrape_time = get_next_scrape_time(
            datetime.now(timezone.utc), source.scrape_frequency
        )
        db.add(source)

        db.commit()
        db.refresh(new_revision)

        logger.info(
            f"Created unchanged revision {new_revision.id} inheriting extraction "
            f"from {last_revision.id} for source {source.id}"
        )

        return {
            "status": "completed",
            "reason": "content_unchanged",
            "revision_id": str(new_revision.id),
            "content_hash": new_revision.content_hash,
            "minio_key": new_revision.minio_object_key,
            "inherited_from": str(last_revision.id),
        }

    def _extract_content_sync(self, source: Source) -> tuple[str, str]:
        """Extract content from source URL using Parallel.ai (sync).

        Args:
            source (Source): Source to scrape.

        Returns:
            tuple[str, str]: (content, minio_key) where content is the extracted markdown
                and minio_key is where it was saved in MinIO.

        Raises:
            ParallelExtractError: If extraction fails.
            ParallelRateLimitError: If rate limit exceeded.
        """
        clean_bucket = settings.MINIO_BUCKET
        clean_key = f"source_{source.id}/raw_{datetime.now(timezone.utc).isoformat()}.md"

        organization_id = None
        project_id = None
        if source.jurisdiction:
            project_id = source.jurisdiction.project_id
            if source.jurisdiction.project:
                organization_id = source.jurisdiction.project.org_id

        result = self.parallel_extractor.extract_and_save(
            url=source.url,
            clean_bucket=clean_bucket,
            clean_key=clean_key,
            user_id=None,
            organization_id=organization_id,
            project_id=project_id,
            endpoint_name="scrape_source",
        )

        return result["full_text"], result["clean_key"]

    @staticmethod
    def _create_revision(
        db: Session, source_id: str, content_hash: str, minio_key: str
    ) -> DataRevision:
        """Create new data revision.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.
            content_hash (str): SHA-256 hash of content.
            minio_key (str): MinIO object key for the stored content.

        Returns:
            DataRevision: Created revision.
        """
        last_revision = db.exec(
            select(DataRevision)
            .where(DataRevision.source_id == source_id)
            .order_by(DataRevision.scraped_at.desc())
            .limit(1)
        ).first()

        revision = DataRevision(
            id=uuid4(),
            source_id=source_id,
            minio_object_key=minio_key,
            content_hash=content_hash,
            extraction_status=ExtractionStatus.PENDING_EXTRACTION,
            scraped_at=datetime.utcnow(),
            is_baseline=not bool(last_revision),
        )
        db.add(revision)
        db.commit()
        db.refresh(revision)

        return revision

    @staticmethod
    def _release_lock(redis_client: redis.Redis, lock_key: str, lock_value: str) -> None:
        """Release Redis lock.

        Args:
            redis_client (redis.Redis): Redis client.
            lock_key (str): Lock key.
            lock_value (str): Expected lock value.
        """
        try:
            redis_client.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_value)
        except Exception as err:
            logger.warning(f"Failed to release lock {lock_key}: {err}")


def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculate next scrape time based on frequency.

    Args:
        current_time (datetime): Current time anchor.
        frequency (ScrapeFrequency): Scrape frequency.

    Returns:
        datetime: Next scheduled scrape time.
    """
    from datetime import timedelta

    frequency_map = {
        ScrapeFrequency.DAILY: timedelta(days=1),
        ScrapeFrequency.WEEKLY: timedelta(weeks=1),
        ScrapeFrequency.MONTHLY: timedelta(days=30),
        ScrapeFrequency.HOURLY: timedelta(hours=1),
    }
    delta = frequency_map.get(frequency, timedelta(days=1))
    return current_time + delta
