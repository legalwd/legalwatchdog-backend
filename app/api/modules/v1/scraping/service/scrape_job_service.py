"""
Service layer for scrape job operations.

Handles background scrape execution and job lifecycle management.
"""

import logging
import uuid

from fastapi import status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.events.builders import build_scrape_job_event
from app.api.events.factory import get_event_publisher
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob as ScrapeJobModel
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.schemas.scrape_job_schema import ScrapeJobResponse
from app.api.modules.v1.scraping.service.tasks import scrape_source_stage1
from app.api.modules.v1.scraping.validators.exception import (
    JobNotFoundError,
    ScrapeAlreadyInProgressError,
    SourceInactiveError,
    SourceNotFoundError,
)
from app.api.utils.pagination import calculate_pagination

logger = logging.getLogger("app")


class ScrapeJobService:
    """Service for managing scrape jobs and background execution."""

    @staticmethod
    def queue_scrape_job(job_id: uuid.UUID, source_id: uuid.UUID) -> None:
        """
        Queue a scrape job for background execution using Celery workers.

        Uses Celery task for distributed processing and proper job lifecycle management.

        Args:
            job_id (uuid.UUID): The scrape job ID.
            source_id (uuid.UUID): The source ID to scrape.
        """
        try:
            scrape_source_stage1.delay(str(source_id), str(job_id))
            logger.info(f"Queued scrape job {job_id} for source {source_id} with Celery")
        except Exception as e:
            logger.error(f"Failed to queue scrape job {job_id} with Celery: {str(e)}")
            raise

    @staticmethod
    async def manual_scrape_trigger(db, source_id: uuid.UUID, current_user) -> dict:
        """Create a scrape job for a source (validates source, enforces concurrency) and queue it.

        Returns a dict with status_code, message, and data for the route to return.
        Raises domain exceptions on error.
        """

        try:
            query = select(Source).where(Source.id == source_id)
            result = await db.execute(query)
            source = result.scalars().first()

            if not source:
                raise SourceNotFoundError("Source not found")

            if not source.is_active:
                raise SourceInactiveError("Cannot scrape inactive source. Please enable it first.")

            try:
                job = ScrapeJobModel(
                    source_id=source_id,
                    status=ScrapeJobStatus.PENDING,
                )
                db.add(job)
                await db.commit()
                await db.refresh(job)
            except IntegrityError:
                await db.rollback()

                raise ScrapeAlreadyInProgressError(
                    "A scrape is already in progress for this source. "
                    "Please wait for it to complete."
                )

            ScrapeJobService.queue_scrape_job(job.id, source_id)

            return {
                "status_code": status.HTTP_202_ACCEPTED,
                "message": "Scrape job queued successfully",
                "data": {
                    "job_id": str(job.id),
                    "source_id": str(source_id),
                    "status": job.status.value,
                },
            }
        except (ScrapeAlreadyInProgressError, SourceInactiveError, SourceNotFoundError):
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to scrape manually: %s", e)
            raise ProcessingError("An unexpected error occured while accepting sources")

    @staticmethod
    async def get_active_scrape_job(db, source_id: uuid.UUID, current_user) -> dict:
        """Return active job for source or 204 if none.

        Returns a dict with status_code, message, data.
        Raises SourceNotFoundError when source missing.
        """

        try:
            source_query = select(Source).where(Source.id == source_id)
            source_result = await db.execute(source_query)
            source = source_result.scalars().first()

            if not source:
                raise SourceNotFoundError("Source not found")

            job_query = select(ScrapeJobModel).where(
                ScrapeJobModel.source_id == source_id,
                ScrapeJobModel.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS]),
            )
            job_result = await db.execute(job_query)
            active_job = job_result.scalars().first()

            if not active_job:
                return {
                    "status_code": status.HTTP_204_NO_CONTENT,
                    "message": "No active scrape job found for this source",
                    "data": None,
                }

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Active scrape job found for this source",
                "data": ScrapeJobResponse.model_validate(active_job).model_dump(mode="json"),
            }
        except SourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve scrape job %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving scrape job")

    @staticmethod
    async def list_scrape_jobs(
        db, source_id: uuid.UUID, page: int, limit: int, current_user
    ) -> dict:
        """Return paginated list of scrape jobs for a source.

        Returns dict with status_code, message, data containing items and pagination.
        Raises SourceNotFoundError when source missing.
        """

        try:
            source_query = select(Source).where(Source.id == source_id)
            source_result = await db.execute(source_query)
            source = source_result.scalars().first()

            if not source:
                raise SourceNotFoundError("Source not found")

            count_query = (
                select(func.count())
                .select_from(ScrapeJobModel)
                .where(ScrapeJobModel.source_id == source_id)
            )
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            jobs_query = (
                select(ScrapeJobModel)
                .where(ScrapeJobModel.source_id == source_id)
                .order_by(ScrapeJobModel.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )

            jobs_result = await db.execute(jobs_query)
            jobs = jobs_result.scalars().all()

            jobs_data = [
                ScrapeJobResponse.model_validate(job).model_dump(mode="json") for job in jobs
            ]
            pagination = calculate_pagination(total, page, limit)

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Scrape jobs retrieved successfully",
                "data": {"items": jobs_data, "pagination": pagination},
            }

        except SourceNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve scrape jobs %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving scrape jobs")

    @staticmethod
    async def get_scrape_job_status(
        db, source_id: uuid.UUID, job_id: uuid.UUID, current_user
    ) -> dict:
        """Return the status and details for a specific scrape job.

        Raises JobNotFoundError when the job doesn't exist or doesn't belong to the source.
        """

        try:
            query = select(ScrapeJobModel).where(
                ScrapeJobModel.id == job_id,
                ScrapeJobModel.source_id == source_id,
            )
            result = await db.execute(query)
            job = result.scalars().first()

            if not job:
                raise JobNotFoundError("Scrape job not found")

            return {
                "status_code": status.HTTP_200_OK,
                "message": "Scrape job status retrieved successfully",
                "data": ScrapeJobResponse.model_validate(job).model_dump(mode="json"),
            }
        except JobNotFoundError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.info("Failed to retrieve scrape job status %s", e)
            raise ProcessingError("An unexpected error occurred while retrieving status")

    @staticmethod
    async def _publish_scrape_job_update(job: ScrapeJobModel) -> None:
        """Publish scrape job updates over websockets when enabled.

        Args:
            job (ScrapeJob): The job instance that changed state.

        Returns:
            None

        Raises:
            RuntimeError: If the event publisher cannot be created.

        Examples:
            >>> await ScrapeJobService._publish_scrape_job_update(job)
        """

        if not settings.ENABLE_REALTIME_WEBSOCKETS:
            return
        publisher = await get_event_publisher()
        event = build_scrape_job_event(job)
        await publisher.publish(event)
