import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import (
    ClearStuckJobsError,
    ManualScrapeError,
    SourceNotFoundError,
    StuckJobRetryError,
    TaskInitiationError,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.tasks import manual_scrape_source, retry_stuck_jobs

logger = logging.getLogger(__name__)


class ScrapingAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def manual_scrape_source(self, source_id: str, user_id: UUID) -> Dict:
        try:
            query = select(Source).where(Source.id == source_id)
            result = await self.db.execute(query)
            source = result.scalar_one_or_none()

            if not source:
                raise SourceNotFoundError(f"Source with ID {source_id} not found")

            task = manual_scrape_source.delay(source_id)

            if not task or not task.id:
                raise TaskInitiationError("Failed to initiate manual scrape task")

            logger.info(
                f"User {user_id} manually triggered scrape "
                "for source {source_id}, task_id: {task.id}"
            )

            return {
                "source_id": source_id,
                "task_id": task.id,
                "status": "initiated",
            }

        except (SourceNotFoundError, TaskInitiationError):
            raise
        except Exception as e:
            logger.error(
                f"User {user_id} manual scrape error for source {source_id}: {e}", exc_info=True
            )
            raise ManualScrapeError(f"Failed to initiate manual scrape for source {source_id}")

    async def retry_stuck_jobs(self, user_id: UUID) -> Dict:
        try:
            task = retry_stuck_jobs.delay()

            if not task or not task.id:
                raise TaskInitiationError("Failed to initiate retry stuck jobs task")

            logger.info(f"User {user_id} initiated retry of stuck jobs, task_id: {task.id}")

            return {
                "task_id": task.id,
                "status": "initiated",
            }

        except TaskInitiationError:
            raise
        except Exception as e:
            logger.error(f"User {user_id} retry stuck jobs error: {e}", exc_info=True)
            raise StuckJobRetryError("Failed to initiate retry of stuck jobs")

    async def clear_stuck_jobs(self, source_id: Optional[str], user_id: UUID) -> Dict:
        try:
            if source_id:
                query = select(Source).where(Source.id == source_id)
                result = await self.db.execute(query)
                source = result.scalar_one_or_none()

                if not source:
                    raise SourceNotFoundError(f"Source with ID {source_id} not found")

            job_query = select(ScrapeJob).where(
                ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS])
            )

            if source_id:
                job_query = job_query.where(ScrapeJob.source_id == source_id)

            result = await self.db.execute(job_query)
            stuck_jobs = result.scalars().all()

            if not stuck_jobs:
                return {"cleared_count": 0, "source_id": source_id}

            now = datetime.now(timezone.utc)
            count = 0
            for job in stuck_jobs:
                job.status = ScrapeJobStatus.FAILED
                job.completed_at = now
                job.error_message = f"Manually cleared by admin user {user_id}"
                job.result = {
                    "status": "failed",
                    "reason": "manually_cleared",
                    "message": "Job was stuck and cleared by admin",
                    "cleared_by": str(user_id),
                }
                self.db.add(job)
                count += 1

            await self.db.commit()

            logger.info(f"Cleared {count} stuck jobs (source_filter={source_id})")

            return {
                "cleared_count": count,
                "source_id": source_id,
            }

        except SourceNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Clear stuck jobs error: {e}", exc_info=True)
            raise ClearStuckJobsError("Failed to clear stuck jobs")
