"""Celery tasks for the scraping module - thin orchestration layer.

This module defines Celery tasks that delegate to specialized service classes.
Each task is a thin wrapper that calls the appropriate service method.

Services:
- Stage1ScrapingService: Web scraping with deduplication
- Stage2ExtractionService: LLM-based extraction
- Stage3PersistenceService: Database persistence
- DiffAndNotificationService: Change detection and notifications
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import redis
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import EmptyContentError, InvalidSourceError
from app.api.db.database import CeleryAsyncSessionLocal, SyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency, Source
from app.api.modules.v1.scraping.service.consolidated_extraction_service import (
    ConsolidatedExtractionService,
)
from app.api.modules.v1.scraping.service.diff_and_notification_service import (
    DiffAndNotificationService,
)
from app.api.modules.v1.scraping.service.error_types import analyze_error
from app.api.modules.v1.scraping.service.jurisdiction_scraping_service import (
    JurisdictionScrapingService,
)
from app.api.modules.v1.scraping.service.llm_service import AIExtractionServiceError
from app.api.modules.v1.scraping.service.stage1_scraping_service import Stage1ScrapingService
from app.api.modules.v1.scraping.service.stage2_extraction_service import Stage2ExtractionService
from app.api.modules.v1.scraping.service.stage3_persistence_service import Stage3PersistenceService
from app.api.utils.celery_utils import retry_on_db_exhaustion, syncify
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

DISPATCH_LOCK_KEY = "celery:dispatch_due_sources_lock"


# ============================================================================
# 3-Stage Pipeline Tasks
# ============================================================================


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_source_stage1(self, source_id: str, job_id: str) -> dict:
    """Execute Stage 1: Web scraping with content deduplication.

    This is an orchestration wrapper that delegates actual processing to
    Stage1ScrapingService.

    Args:
        source_id (str): UUID of the source to scrape.
        job_id (str): UUID of the ScrapeJob to update.

    Returns:
        dict: Status information containing content hash and minio key if successful.

    Raises:
        Exception: Propagated to Celery for retry logic.
    """

    logger.info(f"Stage 1 started: source={source_id}, job={job_id}, task_id={self.request.id}")
    try:
        with SyncSessionLocal() as db_session:
            service = Stage1ScrapingService(redis_pool=redis_pool, db_session=db_session)
            result = service.execute(source_id, job_id, task_request_id=self.request.id)

            current_job = db_session.get(ScrapeJob, job_id)
            is_jurisdiction_batch = current_job and current_job.jurisdiction_scrape_job_id

            if (
                result.get("status") == "completed"
                and result.get("reason") == "new_content_scraped"
            ):
                if is_jurisdiction_batch:
                    logger.info(
                        f"Skipping Stage 2 for job {job_id} - part of jurisdiction batch "
                        f"{current_job.jurisdiction_scrape_job_id}"
                    )
                else:
                    logger.info(
                        f"Dispatching Stage 2 for new content with hash {result['content_hash']}"
                    )
                    process_extraction_stage2.delay(
                        source_id, job_id, result["content_hash"], result["minio_key"]
                    )

            if is_jurisdiction_batch:
                logger.info(
                    f"Checking batch completion for jurisdiction job "
                    f"{current_job.jurisdiction_scrape_job_id}"
                )
                jurisdiction_service = JurisdictionScrapingService(db_session)
                jurisdiction_service.check_batch_completion(current_job.jurisdiction_scrape_job_id)

            logger.info(f"Stage 1 completed for job {job_id}: {result}")

            return {
                "status": result.get("status", "unknown"),
                "message": result.get("message", "Stage 1 completed"),
                "job_id": job_id,
                "source_id": source_id,
                "content_hash": result.get("content_hash"),
                "minio_key": result.get("minio_key"),
            }
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return {"status": "retrying", "job_id": job_id, "source_id": source_id}
        raise
    except Exception as e:
        non_retryable = (EmptyContentError, InvalidSourceError)
        if isinstance(e, non_retryable):
            logger.warning(
                f"Stage 1 failed for job {job_id} with non-retryable error "
                f"({type(e).__name__}), marking as FAILED immediately."
            )
            try:
                with SyncSessionLocal() as cleanup_session:
                    failed_job = cleanup_session.get(ScrapeJob, UUID(job_id))
                    if failed_job and failed_job.status not in (
                        ScrapeJobStatus.COMPLETED,
                        ScrapeJobStatus.FAILED,
                    ):
                        failed_job.status = ScrapeJobStatus.FAILED
                        failed_job.error_message = (
                            e.message
                            if hasattr(e, "message")
                            else "Content extraction failed. Please try again later."
                        )
                        failed_job.completed_at = datetime.now(timezone.utc)
                        cleanup_session.add(failed_job)
                        cleanup_session.commit()

                        if failed_job.jurisdiction_scrape_job_id:
                            jurisdiction_service = JurisdictionScrapingService(cleanup_session)
                            jurisdiction_service.check_batch_completion(
                                failed_job.jurisdiction_scrape_job_id
                            )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to mark job {job_id} as FAILED during cleanup: {cleanup_error}",
                    exc_info=True,
                )
            return {
                "status": "failed",
                "message": e.message if hasattr(e, "message") else str(e),
                "job_id": job_id,
                "source_id": source_id,
                "retryable": False,
            }

        logger.error(f"Stage 1 failed for job {job_id}: {str(e)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            try:
                with SyncSessionLocal() as cleanup_session:
                    failed_job = cleanup_session.get(ScrapeJob, UUID(job_id))
                    if failed_job and failed_job.status not in (
                        ScrapeJobStatus.COMPLETED,
                        ScrapeJobStatus.FAILED,
                    ):
                        failed_job.status = ScrapeJobStatus.FAILED
                        failed_job.error_message = (
                            e.message
                            if hasattr(e, "message")
                            else "Content extraction failed. Please try again later."
                        )
                        failed_job.completed_at = datetime.now(timezone.utc)
                        cleanup_session.add(failed_job)
                        cleanup_session.commit()

                        if failed_job.jurisdiction_scrape_job_id:
                            jurisdiction_service = JurisdictionScrapingService(cleanup_session)
                            jurisdiction_service.check_batch_completion(
                                failed_job.jurisdiction_scrape_job_id
                            )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to mark job {job_id} as FAILED during cleanup: {cleanup_error}",
                    exc_info=True,
                )
        else:
            logger.info(
                f"Stage 1 attempt {self.request.retries + 1}/{self.max_retries} failed for "
                f"job {job_id}, will retry."
            )
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def process_extraction_stage2(
    self, source_id: str, job_id: str, content_hash: str, minio_key: str
) -> dict:
    """Execute Stage 2: LLM extraction processing.

    This is an orchestration wrapper that delegates actual processing to
    Stage2ExtractionService.

    Args:
        source_id (str): UUID of the source.
        job_id (str): UUID of the ScrapeJob.
        content_hash (str): Hash of the scraped content.
        minio_key (str): MinIO object key for the content.

    Returns:
        dict: Processing status including revision ID.

    Raises:
        Exception: Propagated to Celery for retry logic.
    """

    async def run_task():
        logger.info(
            f"Stage 2 started: source={source_id}, job={job_id}, "
            f"content_hash={content_hash}, task_id={self.request.id}"
        )
        async with CeleryAsyncSessionLocal() as db_session:
            service = Stage2ExtractionService()
            result = await service.execute(
                source_id, job_id, content_hash, minio_key, db=db_session
            )

            if result and result.get("status") == "completed" and result.get("revision_id"):
                logger.info(f"Dispatching Stage 3 for revision {result['revision_id']}")
                persist_results_stage3.delay(source_id, job_id, result["revision_id"])

            logger.info(f"Stage 2 completed for job {job_id}: {result}")

            return {
                "status": result.get("status", "unknown") if result else "failed",
                "message": (
                    result.get("message", "Stage 2 completed") if result else "Stage 2 failed"
                ),
                "job_id": job_id,
                "source_id": source_id,
                "revision_id": result.get("revision_id") if result else None,
            }

    try:
        return syncify(run_task)()
    except AIExtractionServiceError as e:
        logger.error(
            f"Stage 2 AI extraction failed for job {job_id}: {e.technical_message}",
            extra={
                "error_category": e.error_category.value,
                "should_retry": e.should_retry,
            },
            exc_info=True,
        )

        if e.should_retry and self.request.retries < self.max_retries:
            retry_countdown = 2**self.request.retries * 60
            logger.info(
                f"Retrying Stage 2 for job {job_id} in {retry_countdown}s "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=retry_countdown)
        else:
            logger.info(
                f"Not retrying Stage 2 for job {job_id} - category: {e.error_category.value}"
            )
            _mark_scrape_job_failed(job_id, f"Stage 2 failed: {e.user_message}")
            return {
                "status": "failed",
                "message": e.user_message,
                "job_id": job_id,
                "error_category": e.error_category.value,
            }
    except Exception as e:
        logger.error(f"Stage 2 failed for job {job_id}: {str(e)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            _mark_scrape_job_failed(job_id, f"Stage 2 failed after retries: {str(e)}")
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=180)
def persist_results_stage3(self, source_id: str, job_id: str, revision_id: str) -> dict:
    """Execute Stage 3: Database persistence and finalization.

    This is an orchestration wrapper that delegates actual processing to
    Stage3PersistenceService.

    Args:
        source_id (str): UUID of the source.
        job_id (str): UUID of the ScrapeJob.
        revision_id (str): UUID of the DataRevision.

    Returns:
        dict: Persistence status.

    Raises:
        Exception: Propagated to Celery for retry logic.
    """
    logger.info(
        f"Stage 3 started: source={source_id}, job={job_id}, "
        f"revision={revision_id}, task_id={self.request.id}"
    )
    try:
        service = Stage3PersistenceService()
        result = service.execute(source_id, job_id, revision_id)

        if result.get("status") == "completed":
            logger.info(f"Stage 3 completed successfully for job {job_id}")

        logger.info(f"Stage 3 completed for job {job_id}: {result}")

        return {
            "status": result.get("status", "unknown"),
            "message": result.get("message", "Stage 3 completed"),
            "job_id": job_id,
            "source_id": source_id,
            "revision_id": revision_id,
        }
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=1):
            return {"status": "retrying", "job_id": job_id}
        raise
    except Exception as e:
        logger.error(f"Stage 3 failed for job {job_id}: {str(e)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            _mark_scrape_job_failed(job_id, f"Stage 3 failed: {str(e)}")
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def detect_changes_and_notify_stage4(self, source_id: str, revision_id: str) -> dict:
    """Execute Stage 4: Change detection and notifications.

    This is an orchestration wrapper that delegates actual processing to
    DiffAndNotificationService.

    Args:
        source_id (str): UUID of the source.
        revision_id (str): UUID of the DataRevision.

    Returns:
        dict: Detection and notification status.

    Raises:
        Exception: Propagated to Celery for retry logic.
    """
    logger.info(
        f"Stage 4 started: source={source_id}, revision={revision_id}, task_id={self.request.id}"
    )
    try:
        service = DiffAndNotificationService()
        result = service.execute(source_id, revision_id)
        logger.info(f"Stage 4 completed for revision {revision_id}: {result}")

        return {
            "status": result.get("status", "unknown"),
            "message": result.get("message", "Stage 4 completed"),
            "source_id": source_id,
            "revision_id": revision_id,
        }
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=2):
            return {"status": "retrying", "source_id": source_id, "revision_id": revision_id}
        raise
    except Exception as e:
        logger.error(f"Stage 4 failed for revision {revision_id}: {str(e)}", exc_info=True)
        if self.request.retries >= self.max_retries:
            logger.warning(
                "Stage 4 for revision %s failed after all retries. "
                "ScrapeJob is already COMPLETED; change detection/notifications were skipped.",
                revision_id,
            )
        raise


# ============================================================================
# Manual/Admin Tasks
# ============================================================================


@celery_app.task(bind=True, queue="processing", max_retries=1, default_retry_delay=30)
def dispatch_single_jurisdiction_scrape(self, jurisdiction_id: str) -> dict:
    """Dispatch a scrape for a single jurisdiction through the batch pipeline."""
    logger.info("Dispatching single jurisdiction scrape for %s", jurisdiction_id)
    try:
        with SyncSessionLocal() as db_session:
            service = JurisdictionScrapingService(db_session)
            job = service.trigger_jurisdiction_scrape(UUID(jurisdiction_id))
            return {
                "status": "completed",
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_job_id": str(job.id),
            }
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=2):
            return {"status": "retrying", "jurisdiction_id": jurisdiction_id}
        raise
    except Exception as exc:
        logger.error(
            "Single jurisdiction dispatch failed for %s: %s",
            jurisdiction_id,
            exc,
            exc_info=True,
        )
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def manual_scrape_source(self, source_id: str) -> dict:
    """Manually trigger scraping for a specific source.

    Bypasses the dispatch schedule and immediately creates a job and executes Stage 1.

    Args:
        source_id (str): UUID of the source to scrape.

    Returns:
        dict: Scraping result status.

    Raises:
        Exception: Propagated to Celery for retry logic.
    """
    logger.info(f"Manual scrape requested for source {source_id}")

    async def run_task():
        try:
            async with CeleryAsyncSessionLocal() as db_session:
                source = await db_session.get(Source, source_id)
                if not source or not source.is_active:
                    return {
                        "status": "failed",
                        "message": f"Source {source_id} not found or inactive",
                    }

                existing_job = await db_session.exec(
                    select(ScrapeJob).where(
                        ScrapeJob.source_id == source_id,
                        ScrapeJob.status.in_(
                            [ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]
                        ),
                    )
                ).first()

                if existing_job:
                    return {
                        "status": "skipped",
                        "message": f"Scrape already in progress (job {existing_job.id})",
                        "job_id": str(existing_job.id),
                    }

                job_id = uuid4()
                new_job = ScrapeJob(
                    id=job_id,
                    source_id=source_id,
                    status=ScrapeJobStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                )
                db_session.add(new_job)
                await db_session.commit()

                service = Stage1ScrapingService(redis_pool=redis_pool, db_session=db_session)
                result = await service.execute(
                    source_id, str(job_id), task_request_id=self.request.id
                )

                logger.info(f"Manual scrape completed for source {source_id}: {result}")
                return result

        except OperationalError:
            if retry_on_db_exhaustion(self, initial_delay=15, max_retries=1):
                return {"status": "retrying", "source_id": source_id}
            raise
        except Exception as e:
            logger.error(f"Manual scrape failed for source {source_id}: {str(e)}", exc_info=True)
            raise

    return syncify(run_task)()


@celery_app.task(bind=True)
def retry_stuck_jobs(self) -> str:
    """Retry stuck PENDING or IN_PROGRESS jobs.

    Finds jobs that have been stuck for more than 5 minutes and retries them,
    up to a maximum retry limit.

    Returns:
        str: Status message with count of jobs retried.
    """
    MAX_RETRIES = 3

    logger.info("Starting stuck job retry")
    try:
        with SyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            stuck_threshold = now - timedelta(minutes=5)

            stuck_jobs = db.exec(
                select(ScrapeJob).where(
                    ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]),
                    ScrapeJob.created_at <= stuck_threshold,
                    ScrapeJob.retry_count < MAX_RETRIES,
                )
            ).all()

            count = 0
            for job in stuck_jobs:
                logger.info(
                    f"Retrying stuck job {job.id} for source {job.source_id} "
                    f"(attempt {job.retry_count + 1}/{MAX_RETRIES})"
                )

                job.retry_count += 1
                db.add(job)
                db.commit()

                self.app.send_task(
                    "app.api.modules.v1.scraping.service.tasks.scrape_source_stage1",
                    args=[str(job.source_id), str(job.id)],
                    queue="scraping",
                )
                count += 1

            if count > 0:
                logger.info(f"Retried {count} stuck jobs")

            return f"Retried {count} stuck job(s)."

    except Exception as e:
        logger.error(f"Error during stuck job retry: {str(e)}", exc_info=True)
        return "Aborted: An error occurred during job retry"


# ============================================================================
# Job Monitoring Tasks (Celery Beat)
# ============================================================================


@celery_app.task(bind=True)
def monitor_stalled_jobs(self) -> str:
    """Monitor and mark stalled jobs as failed.

    Celery Beat task that periodically checks for jobs exceeding the timeout
    threshold.

    Returns:
        str: Status message with count of jobs marked as stalled.
    """
    logger.info("Starting stalled job monitoring")
    try:
        with SyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            timeout_threshold = now - timedelta(seconds=settings.SCRAPE_JOB_TIMEOUT_SECONDS)
            jurisdiction_timeout_threshold = now - timedelta(
                seconds=settings.JURISDICTION_JOB_TIMEOUT_SECONDS
            )

            stalled_jobs = db.exec(
                select(ScrapeJob).where(
                    ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]),
                    ScrapeJob.created_at <= timeout_threshold,
                )
            ).all()

            count = 0
            for job in stalled_jobs:
                logger.warning(
                    f"Marking stalled job {job.id} as FAILED. "
                    f"Status: {job.status}, Created: {job.created_at}, "
                    f"Now: {now}"
                )
                job.status = ScrapeJobStatus.FAILED
                job.error_message = (
                    f"Job timeout: No activity after {settings.SCRAPE_JOB_TIMEOUT_SECONDS} seconds"
                )
                job.completed_at = now
                db.add(job)
                count += 1

            stalled_jurisdiction_jobs = db.exec(
                select(JurisdictionScrapeJob).where(
                    JurisdictionScrapeJob.status.in_(
                        [
                            JurisdictionScrapeJobStatus.PENDING,
                            JurisdictionScrapeJobStatus.SCRAPING,
                            JurisdictionScrapeJobStatus.CONSOLIDATING,
                            JurisdictionScrapeJobStatus.FILTERING,
                            JurisdictionScrapeJobStatus.ANALYZING,
                        ]
                    ),
                    JurisdictionScrapeJob.started_at <= jurisdiction_timeout_threshold,
                )
            ).all()

            jurisdiction_count = 0
            for job in stalled_jurisdiction_jobs:
                logger.warning(
                    "Marking stalled jurisdiction job %s as FAILED. Status:%s, Started: %s, Now:%s",
                    job.id,
                    job.status,
                    job.started_at,
                    now,
                )
                job.status = JurisdictionScrapeJobStatus.FAILED
                job.error_message = "Stalled: no completion after timeout"
                job.completed_at = now
                db.add(job)
                jurisdiction_count += 1

            if count > 0 or jurisdiction_count > 0:
                db.commit()
                logger.info(
                    "Marked %d stalled scrape jobs and %d stalled jurisdiction jobs as FAILED",
                    count,
                    jurisdiction_count,
                )

            return (
                "Monitored jobs: "
                f"{count} stalled scrape job(s) and "
                f"{jurisdiction_count} stalled jurisdiction job(s) marked as failed."
            )

    except Exception as e:
        logger.error(f"Error during job monitoring: {str(e)}", exc_info=True)
        return "Aborted: An error occurred during job monitoring"


# ============================================================================
# Dispatch Task (Celery Beat)
# ============================================================================


@celery_app.task(bind=True)
def dispatch_due_sources(self) -> str:
    """Query and dispatch due sources to Stage 1.

    Celery Beat task that runs periodically to find sources needing scraping.
    Uses distributed Redis lock to prevent overlapping dispatches.

    Returns:
        str: Status message indicating number of sources dispatched.
    """
    logger.info("Starting dispatch of due sources")
    redis_client = None

    try:
        redis_client = redis.Redis(connection_pool=redis_pool)

        lock_acquired = redis_client.set(
            DISPATCH_LOCK_KEY, "locked", nx=True, ex=settings.SCRAPE_DISPATCH_LOCK_TIMEOUT
        )

        if not lock_acquired:
            logger.debug("Dispatch task already locked, skipping")
            return "Skipped: Dispatch task locked."

        total_dispatched = _dispatch_due_sources_sync(self.app)
        logger.info(f"Dispatch completed: {total_dispatched} sources dispatched")
        return f"Dispatched {total_dispatched} sources."

    except redis.RedisError as e:
        logger.error(f"Redis error during dispatch: {e}", exc_info=True)
        return "Aborted: Redis failure."

    except Exception as e:
        logger.error(f"Unexpected error during dispatch: {e}", exc_info=True)
        return "Aborted: An error occurred"

    finally:
        if redis_client:
            try:
                redis_client.delete(DISPATCH_LOCK_KEY)
            except Exception as cleanup_err:
                logger.error(f"Failed to release dispatch lock: {cleanup_err}")


@celery_app.task(bind=True, queue="processing")
def dispatch_due_jurisdictions(self) -> str:
    """Query and dispatch due jurisdictions for batch scraping.

    Celery Beat task that runs periodically.
    """
    logger.info("Starting dispatch of due jurisdictions")
    redis_client = None
    lock_key = "celery:dispatch_due_jurisdictions_lock"
    lock_value = str(uuid4())

    try:
        redis_client = redis.Redis(connection_pool=redis_pool)
        lock_acquired = redis_client.set(lock_key, lock_value, nx=True, ex=300)

        if not lock_acquired:
            logger.debug("Dispatch jurisdiction task already locked, skipping")
            return "Skipped: Dispatch task locked."

        count = 0
        with SyncSessionLocal() as db:
            now = datetime.now(timezone.utc)

            query = (
                select(Jurisdiction)
                .where(
                    (Jurisdiction.next_scrape_time <= now)
                    | (Jurisdiction.next_scrape_time.is_(None)),
                    Jurisdiction.enable_auto_scrape,
                    ~Jurisdiction.is_deleted,
                )
                .limit(10)
            )

            jurisdictions = db.exec(query).all()

            if not jurisdictions:
                return "No due jurisdictions."

            service = JurisdictionScrapingService(db)
            dispatched_jurisdictions = []

            for jurisdiction in jurisdictions:
                logger.info(f"Dispatching scrape for jurisdiction {jurisdiction.id}")
                try:
                    service.trigger_jurisdiction_scrape(jurisdiction.id)
                    count += 1
                    next_time = service._calculate_next_scrape_time(
                        now, jurisdiction.scrape_frequency or ScrapeFrequency.DAILY
                    )
                    jurisdiction.next_scrape_time = next_time
                    jurisdiction.last_scraped_at = now
                    dispatched_jurisdictions.append(jurisdiction)
                except Exception as e:
                    logger.error(
                        f"Failed to dispatch jurisdiction {jurisdiction.id}: {e}", exc_info=True
                    )

            for jurisdiction in dispatched_jurisdictions:
                db.add(jurisdiction)

            if dispatched_jurisdictions:
                db.commit()

        return f"Dispatched {count} jurisdictions."

    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return "Retrying: DB pool exhaustion."
        raise
    except Exception as e:
        logger.error(f"Error during jurisdiction dispatch: {e}", exc_info=True)
        return "Aborted: An error occurred"

    finally:
        if redis_client:
            try:
                Stage1ScrapingService._release_lock(redis_client, lock_key, lock_value)
            except Exception:
                pass


@celery_app.task(
    bind=True,
    queue="processing",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def consolidate_jurisdiction_content(self, jurisdiction_job_id: str) -> dict:
    """Execute Stage 2 (Consolidated): Content consolidation and analysis.

    Triggered when all sources in a Jurisdiction Batch are complete.
    """
    logger.info(f"Consolidation task started for job {jurisdiction_job_id}")
    try:
        with SyncSessionLocal() as db:
            service = ConsolidatedExtractionService(db)
            result = service.execute(UUID(jurisdiction_job_id))

            logger.info(f"Consolidation for job {jurisdiction_job_id} completed successfully.")
            return result

    except Exception as e:
        logger.error(
            f"Error during consolidation for job {jurisdiction_job_id}: {e}", exc_info=True
        )

        _, user_message, should_retry = analyze_error(e)

        if should_retry and self.request.retries < self.max_retries:
            logger.info(
                f"Retrying consolidation for job {jurisdiction_job_id} "
                f"(attempt {self.request.retries + 1}/{self.max_retries})"
            )
            raise self.retry(exc=e, countdown=self.default_retry_delay)

        try:
            with SyncSessionLocal() as db:
                job = db.get(JurisdictionScrapeJob, UUID(jurisdiction_job_id))
                if job:
                    job.status = JurisdictionScrapeJobStatus.FAILED
                    job.error_message = user_message
                    logger.error(f"Error on scraping jurisdiction sources: {e}")
                    job.completed_at = datetime.now(timezone.utc)
                    db.add(job)
                    db.commit()
                    if not should_retry:
                        logger.info(
                            f"Marked jurisdiction job {jurisdiction_job_id} as FAILED "
                            f"immediately due to non-retryable error: {user_message}"
                        )
                    else:
                        logger.info(
                            f"Marked jurisdiction job {jurisdiction_job_id} as FAILED "
                            f"after {self.max_retries} retries"
                        )
        except Exception as db_error:
            logger.error(f"Failed to mark job as FAILED: {db_error}", exc_info=True)

        return {"status": "error", "message": f"Consolidation failed. {user_message}"}


# ============================================================================
# Helper Functions
# ============================================================================


def _mark_scrape_job_failed(job_id: str, error_message: str) -> None:
    """Mark a ScrapeJob as FAILED and trigger batch completion check.

    Used as cleanup when a stage fails after retries are exhausted so that
    the jurisdiction batch pipeline is never left in a stuck IN_PROGRESS state.

    Args:
        job_id: UUID string of the ScrapeJob.
        error_message: Human-readable error to store on the job.
    """
    try:
        with SyncSessionLocal() as cleanup_session:
            failed_job = cleanup_session.get(ScrapeJob, UUID(job_id))
            if failed_job and failed_job.status not in (
                ScrapeJobStatus.COMPLETED,
                ScrapeJobStatus.FAILED,
            ):
                failed_job.status = ScrapeJobStatus.FAILED
                failed_job.error_message = error_message
                failed_job.completed_at = datetime.now(timezone.utc)
                cleanup_session.add(failed_job)
                cleanup_session.commit()

                if failed_job.jurisdiction_scrape_job_id:
                    jurisdiction_service = JurisdictionScrapingService(cleanup_session)
                    jurisdiction_service.check_batch_completion(
                        failed_job.jurisdiction_scrape_job_id
                    )
    except Exception as cleanup_error:
        logger.error(
            "Failed to mark job %s as FAILED during cleanup: %s",
            job_id,
            cleanup_error,
            exc_info=True,
        )


def _dispatch_due_sources_sync(app) -> int:
    """Query due sources and dispatch Stage 1 tasks.

    Args:
        app: The Celery application instance.

    Returns:
        int: Total number of sources dispatched.
    """
    with SyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        total_dispatched = 0
        batch_size = settings.SCRAPE_BATCH_SIZE

        while True:
            query = (
                select(Source)
                .where(
                    (Source.next_scrape_time <= now) | (Source.next_scrape_time.is_(None)),
                    Source.is_active,
                    Source.is_deleted.is_(False),
                )
                .order_by(Source.next_scrape_time, Source.id)
                .limit(batch_size)
            )
            result = db.execute(query)
            due_sources = result.scalars().all()

            if not due_sources:
                break

            for src in due_sources:
                logger.debug(f"Dispatching source {src.id} (next_scrape: {src.next_scrape_time})")
                in_progress_time = get_next_scrape_time(now, src.scrape_frequency)
                src.next_scrape_time = in_progress_time

                new_job = ScrapeJob(
                    id=uuid4(),
                    source_id=src.id,
                    status=ScrapeJobStatus.PENDING,
                    created_at=now,
                )
                db.add(new_job)
                db.add(src)

            db.commit()

            for src in due_sources:
                job_query = (
                    select(ScrapeJob)
                    .where(
                        ScrapeJob.source_id == src.id,
                        ScrapeJob.status == ScrapeJobStatus.PENDING,
                    )
                    .order_by(ScrapeJob.created_at.desc())
                )
                job_result = db.exec(job_query)
                matching_job = job_result.first()

                if matching_job:
                    logger.info(f"Sending Stage 1 task for source {src.id}, job {matching_job.id}")
                    app.send_task(
                        "app.api.modules.v1.scraping.service.tasks.scrape_source_stage1",
                        args=[str(src.id), str(matching_job.id)],
                        queue="scraping",
                    )
                    total_dispatched += 1
                else:
                    logger.warning(f"No PENDING job found for dispatched source {src.id}")

            logger.info(f"Dispatched batch of {len(due_sources)} sources to Stage 1.")

        if total_dispatched == 0:
            logger.debug("No due sources found for dispatch")
        else:
            logger.info(f"Total sources dispatched: {total_dispatched}")

        return total_dispatched


def get_next_scrape_time(current_time: datetime, frequency: ScrapeFrequency) -> datetime:
    """Calculate next scrape time based on frequency.

    Args:
        current_time (datetime): The current time anchor.
        frequency (ScrapeFrequency): The frequency enum.

    Returns:
        datetime: The calculated next execution time.
    """
    frequency_map = {
        ScrapeFrequency.DAILY: timedelta(days=1),
        ScrapeFrequency.WEEKLY: timedelta(weeks=1),
        ScrapeFrequency.MONTHLY: timedelta(days=30),
        ScrapeFrequency.HOURLY: timedelta(hours=1),
    }
    delta = frequency_map.get(frequency, timedelta(days=1))
    return current_time + delta
