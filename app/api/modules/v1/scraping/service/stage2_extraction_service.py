"""Stage 2: LLM-based extraction processing.

Responsibilities:
- Load content from MinIO
- Update DataRevision extraction_status
- Call LLM service (OpenRouter) for structured extraction
- Store extracted data, summaries, and confidence scores
- Chain to Stage 3 for persistence
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    LLMExtractionError,
    ProcessingError,
    StorageError,
)
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.scraping.models.data_revision import (
    DataRevision,
    ExtractionStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.llm_service import (
    AIExtractionService,
    AIExtractionServiceError,
)
from app.api.modules.v1.scraping.storage.minio_storage import get_content_from_minio

logger = logging.getLogger(__name__)


class Stage2ExtractionService:
    """Orchestrates Stage 2: LLM extraction processing."""

    def __init__(self):
        """Initialize Stage 2 service."""
        self.llm_service = None

    async def execute(
        self,
        source_id: str,
        job_id: str,
        content_hash: str,
        minio_key: str,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Execute Stage 2 extraction pipeline.

        Args:
            source_id (str): UUID of the source.
            job_id (str): UUID of the ScrapeJob.
            content_hash (str): Hash of the scraped content.
            minio_key (str): MinIO object key for content.
            db (Optional[AsyncSession]): Database session. If provided, uses this session
                                       instead of creating a new global one.

        Returns:
            dict: Status with keys:
                - status: 'completed' or 'failed'
                - extraction_count: Number of extracted key-value pairs

        Raises:
            Exception: Propagated to Celery for retry logic.
        """
        if db:
            return await self._execute_with_db(db, source_id, job_id, content_hash, minio_key)

        async with AsyncSessionLocal() as db_session:
            return await self._execute_with_db(
                db_session, source_id, job_id, content_hash, minio_key
            )

    async def _execute_with_db(
        self,
        db: AsyncSession,
        source_id: str,
        job_id: str,
        content_hash: str,
        minio_key: str,
    ) -> Dict[str, Any]:
        """Execute extraction with database session.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.
            job_id (str): Job UUID.
            content_hash (str): Content hash.
            minio_key (str): MinIO key.

        Returns:
            dict: Extraction result.
        """

        try:
            revision_query = await db.execute(
                select(DataRevision)
                .where(
                    DataRevision.source_id == source_id,
                    DataRevision.content_hash == content_hash,
                )
                .order_by(DataRevision.scraped_at.desc())
                .limit(1)
            )
            revision = revision_query.scalar_one_or_none()

            if not revision:
                logger.warning(
                    f"No DataRevision found for source {source_id} with hash {content_hash}, "
                    "proceeding to create after LLM processing"
                )

            is_baseline = False
            if not revision:
                baseline_check = await db.execute(
                    select(DataRevision).where(DataRevision.source_id == source_id).limit(1)
                )
                is_baseline = baseline_check.scalar_one_or_none() is None

            if revision:
                revision.extraction_status = ExtractionStatus.EXTRACTING
                await db.commit()

                logger.info(
                    f"Processing existing DataRevision {revision.id} for source {source_id}"
                )
            else:
                logger.info(
                    f"Processing new content for source {source_id}, "
                    f"will create DataRevision after LLM"
                )

            try:
                content = self._load_content(minio_key)

                content = self._load_content(minio_key)

                source = (
                    (
                        await db.execute(
                            select(Source)
                            .where(Source.id == source_id)
                            .options(
                                selectinload(Source.jurisdiction).selectinload(Jurisdiction.project)
                            )
                        )
                    )
                    .scalars()
                    .first()
                )

                if not source:
                    raise ValueError(f"Source {source_id} not found")

                project_prompt, jurisdiction_prompt = self._get_extraction_context(source)
                extraction_data = await self._run_llm_extraction(
                    db,
                    content,
                    project_prompt,
                    jurisdiction_prompt,
                    source,
                )

                if revision:
                    revision.extracted_data = extraction_data.get("extracted_data", {})
                    revision.ai_summary = extraction_data.get("summary")
                    revision.ai_markdown_summary = extraction_data.get("markdown_summary")
                    revision.ai_confidence_score = extraction_data.get("confidence_score")
                    revision.extraction_status = ExtractionStatus.COMPLETED
                else:
                    revision = DataRevision(
                        id=uuid4(),
                        source_id=source_id,
                        minio_object_key=minio_key,
                        content_hash=content_hash,
                        extracted_data=extraction_data.get("extracted_data", {}),
                        ai_summary=extraction_data.get("summary"),
                        ai_markdown_summary=extraction_data.get("markdown_summary"),
                        ai_confidence_score=extraction_data.get("confidence_score"),
                        extraction_status=ExtractionStatus.COMPLETED,
                        scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        is_baseline=is_baseline,
                    )
                    db.add(revision)

                await db.commit()

                logger.info(
                    f"Stage 2 complete for {revision.id}: confidence={revision.ai_confidence_score}"
                )

                kv_count = len(extraction_data.get("extracted_data", {}).get("key_value_pairs", []))
                return {
                    "status": "completed",
                    "extraction_count": kv_count,
                    "revision_id": str(revision.id),
                }

            except AIExtractionServiceError as e:
                if revision:
                    logger.error(
                        f"Stage 2 LLM extraction failed for {revision.id}: {e.technical_message}",
                        extra={
                            "error_category": e.error_category.value,
                            "should_retry": e.should_retry,
                        },
                        exc_info=True,
                    )
                    revision.extraction_status = ExtractionStatus.EXTRACTION_FAILED
                    await db.commit()
                else:
                    logger.error(
                        f"Stage 2 LLM extraction failed for source {source_id}: "
                        f"{e.technical_message}",
                        extra={
                            "error_category": e.error_category.value,
                            "should_retry": e.should_retry,
                        },
                        exc_info=True,
                    )

                job = (
                    (await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id)))
                    .scalars()
                    .first()
                )
                if job:
                    job.status = ScrapeJobStatus.FAILED
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = e.user_message
                    job.result = {
                        "status": "failed",
                        "reason": e.error_category.value,
                        "user_message": e.user_message,
                        "should_retry": e.should_retry,
                    }
                    db.add(job)
                    await db.commit()

                if e.should_retry:
                    raise

                return {
                    "status": "failed",
                    "reason": e.error_category.value,
                    "user_message": e.user_message,
                }

            except (LLMExtractionError, StorageError) as e:
                if revision:
                    logger.error(
                        f"Stage 2 failed for {revision.id}: {type(e).__name__}: {e.message}"
                    )
                    revision.extraction_status = ExtractionStatus.EXTRACTION_FAILED
                    await db.commit()
                else:
                    logger.error(
                        f"Stage 2 failed for source {source_id}: {type(e).__name__}: {e.message}"
                    )
                raise

            except Exception as e:
                if revision:
                    logger.exception(f"Unexpected error in Stage 2 for {revision.id}: {e}")
                    revision.extraction_status = ExtractionStatus.EXTRACTION_FAILED
                    await db.commit()
                else:
                    logger.exception(f"Unexpected error in Stage 2 for source {source_id}: {e}")

                job = (
                    (await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id)))
                    .scalars()
                    .first()
                )
                if job:
                    job.status = ScrapeJobStatus.FAILED
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = "An unexpected error occurred during extraction."
                    job.result = {
                        "status": "failed",
                        "reason": "extraction_failed",
                        "error": "PROCESSING_ERROR",
                        "user_message": (
                            "An unexpected error occurred during content "
                            "extraction. Please try again."
                        ),
                    }
                    db.add(job)
                    await db.commit()

                raise ProcessingError("Failed to extract data. Please try again.")
        except IntegrityError as e:
            logger.error(
                f"Database integrity error in Stage 2 for job {job_id}: {e}", exc_info=True
            )

            job = (
                (await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id)))
                .scalars()
                .first()
            )
            if job:
                job.status = ScrapeJobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = (
                    "Database error occurred. Please contact support if this persists."
                )
                job.result = {
                    "status": "failed",
                    "reason": "database_integrity_error",
                    "error": "DATABASE_ERROR",
                    "user_message": (
                        "Database error occurred. Please contact support if this persists."
                    ),
                }
                db.add(job)

            await db.commit()
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Stage 2 for job {job_id}: {e}", exc_info=True)

            job = (
                (await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id)))
                .scalars()
                .first()
            )
            if job:
                job.status = ScrapeJobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = "An unexpected error occurred. Our team has been notified."
                job.result = {
                    "status": "failed",
                    "reason": "unexpected_error",
                    "error": "PROCESSING_ERROR",
                    "user_message": "An unexpected error occurred. Our team has been notified.",
                }
                db.add(job)

            await db.commit()
            raise

    @staticmethod
    def _load_content(minio_key: str) -> str:
        """Load content from MinIO.

        Args:
            minio_key (str): MinIO object key.

        Returns:
            str: Content text.

        Raises:
            ValueError: If content is empty.
        """
        content = get_content_from_minio(minio_key, settings.MINIO_BUCKET)

        if not content:
            raise ValueError(f"Empty content from MinIO: {minio_key}")

        return content

    @staticmethod
    def _get_extraction_context(source: Source) -> tuple[str, str]:
        """Get extraction context prompts from source.

        Args:
            source (Source): Source model.

        Returns:
            tuple: (project_prompt, jurisdiction_prompt)
        """
        project_prompt = "Monitor legal changes"
        if (
            source.jurisdiction
            and source.jurisdiction.project
            and source.jurisdiction.project.master_prompt
        ):
            project_prompt = source.jurisdiction.project.master_prompt

        jurisdiction_prompt = "General jurisdiction"
        if source.jurisdiction:
            if source.jurisdiction.prompt:
                jurisdiction_prompt = source.jurisdiction.prompt
            else:
                jurisdiction_prompt = source.jurisdiction.name

        return project_prompt, jurisdiction_prompt

    @staticmethod
    async def _run_llm_extraction(
        db: Session, content: str, project_prompt: str, jurisdiction_prompt: str, source: Source
    ) -> Dict[str, Any]:
        """Run LLM extraction with cost tracking and field name consistency.

        Args:
            db (Session): Database session for cost tracking.
            content (str): Content to extract from.
            project_prompt (str): Project monitoring goal.
            jurisdiction_prompt (str): Jurisdiction context.
            source (Source): Source model with project relationship.

        Returns:
            dict: Extracted data with keys:
                - summary
                - markdown_summary
                - extracted_data
                - confidence_score
        """
        llm_service = AIExtractionService(db=db, use_openrouter=True)

        project_id = None
        organization_id = None
        if source.jurisdiction and source.jurisdiction.project:
            project_id = str(source.jurisdiction.project.id)
            organization_id = str(source.jurisdiction.project.org_id)
            logger.debug(
                f"Extracted IDs for LLM logging: org_id={organization_id}, project_id={project_id}"
            )
        else:
            logger.warning(
                f"Missing jurisdiction or project for source {source.id}: "
                f"jurisdiction={source.jurisdiction}, "
                f"project={source.jurisdiction.project if source.jurisdiction else 'N/A'}"
            )

        extraction_data = await llm_service.run_llm_analysis_with_openrouter(
            cleaned_text=content,
            project_prompt=project_prompt,
            jurisdiction_prompt=jurisdiction_prompt,
            source_id=str(source.id),
            user_id=None,
            organization_id=organization_id,
            project_id=project_id,
            endpoint="/celery/scraping/stage2",
        )

        return extraction_data
