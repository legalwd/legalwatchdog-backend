"""Service for orchestrating the web scraping pipeline.

Handles the end-to-end flow of fetching content, extracting text,
analyzing with AI, detecting changes, and persisting data revisions.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select

from app.api.core.config import settings
from app.api.core.exceptions import (
    ParallelExtractError,
    ParallelRateLimitError,
)
from app.api.core.security import decrypt_auth_details
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.service.revision_notification_task import (
    send_revision_notifications_task,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.cloudscrapper_service import HTTPClientService
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.modules.v1.scraping.service.extractor_service import TextExtractorService
from app.api.modules.v1.scraping.service.llm_service import AIExtractionService
from app.api.modules.v1.scraping.service.parallel_extract_service import (
    ParallelExtractService,
)
from app.api.modules.v1.scraping.service.pdf_service import PDFService
from app.api.modules.v1.tickets.service.ticket_auto_creation_service import TicketService

logger = logging.getLogger(__name__)


class ScraperService:
    """Orchestrates the scraping, extraction, and analysis pipeline."""

    def __init__(self, db: AsyncSession):
        """Initialize the ScraperService with necessary dependencies.

        Args:
            db (AsyncSession): The asynchronous database session.
        """
        self.db = db
        self.ai_extractor = AIExtractionService()
        self.text_extractor = TextExtractorService()
        self.differ = DiffAIService()
        self.http_client = HTTPClientService()
        self.pdf_service = PDFService()
        self.parallel_extractor = ParallelExtractService(db_session=db)

    async def execute_scrape_job(self, source_id: str) -> Dict[str, Any]:
        """Execute the full scraping pipeline for a given source.

        Fetching -> Archiving -> Cleaning -> Hashing -> AI Extraction -> Diffing -> Persistence.
        If a change is detected AND it is not the first run, it triggers a notification.

        Args:
            source_id (str): The UUID of the source to scrape.

        Returns:
            Dict[str, Any]: A summary of the scrape execution including status and changes.

        Raises:
            ValueError: If the source ID cannot be found.
            Exception: Propagates any errors occurring during the pipeline.
        """
        logger.info(f"Starting pipeline for Source ID: {source_id}")

        query = (
            select(Source)
            .where(Source.id == source_id)
            .options(selectinload(Source.jurisdiction).selectinload(Jurisdiction.project))
        )
        result = await self.db.execute(query)
        source = result.scalars().first()

        if not source:
            logger.warning(f"Source not found for scraping: source_id={source_id}")
            raise ValueError("The data source you're trying to scrape doesn't exist.")

        jurisdiction = source.jurisdiction
        project = jurisdiction.project

        auth_creds = {}
        if source.auth_details_encrypted:
            try:
                auth_creds = decrypt_auth_details(source.auth_details_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt auth details: {e}")

        timestamp_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y%m%d_%H%M%S")
        clean_minio_key = f"clean/{jurisdiction.id}/{source.id}/{timestamp_str}.md"

        master_prompt = project.master_prompt
        context_prompt = jurisdiction.prompt or ""
        extraction_objective = f"{master_prompt}. Context: {context_prompt}"

        clean_text = None
        extraction_result = None
        used_fallback = False

        try:
            logger.info("Attempting extraction using Parallel.ai Extract API...")

            project_id = None
            if source.jurisdiction and source.jurisdiction.project:
                project_id = source.jurisdiction.project.id

            parallel_result = await self.parallel_extractor.extract_and_save(
                url=source.url,
                clean_bucket=settings.MINIO_BUCKET,
                clean_key=clean_minio_key,
                user_id=source.created_by,
                organization_id=source.organization_id,
                project_id=project_id,
                endpoint_name="scrape_source",
                objective=extraction_objective,
            )
            clean_text = parallel_result["full_text"]
            extraction_result = {
                "full_text": clean_text,
                "clean_key": clean_minio_key,
                "raw_key": None,
                "source": "parallel",
            }
            logger.info("Successfully extracted content using Parallel.ai (no raw content stored)")

        except (ParallelExtractError, ParallelRateLimitError) as e:
            if isinstance(e, ParallelRateLimitError):
                logger.warning(
                    f"Parallel.ai rate limit exceeded: {e}. Falling back to CloudScraper."
                )
            else:
                logger.warning(f"Parallel.ai extraction failed: {e}. Falling back to CloudScraper.")
            used_fallback = True

            raw_content_bytes = await self.http_client.fetch_content(source.url, auth_creds)
            content_type = source.scraping_rules.get("expected_type", "text/html").lower()

            is_pdf = self.pdf_service.is_pdf(raw_content_bytes, content_type)
            if is_pdf:
                logger.info("PDF detected. Extracting text...")
                try:
                    text_content = self.pdf_service.extract_text(raw_content_bytes)
                    html_content = f"<html><body><pre>{text_content}</pre></body></html>"
                    raw_content_bytes = html_content.encode("utf-8")
                except Exception as pdf_err:
                    logger.error(f"PDF extraction failed: {pdf_err}")
                    raw_content_bytes = b"<html><body>PDF extraction failed</body></html>"

            raw_minio_key = f"raw/{jurisdiction.id}/{source.id}/{timestamp_str}.html"
            extraction_result = await self.text_extractor.process_pipeline_markdown(
                raw_content=raw_content_bytes,
                raw_bucket=settings.MINIO_BUCKET,
                raw_key=raw_minio_key,
                clean_bucket=settings.MINIO_BUCKET,
                source_id=source.id,
            )
            clean_text = extraction_result["full_text"]
            logger.info("Successfully extracted content using CloudScraper fallback")

        if used_fallback:
            logger.info("Using fallback pipeline (stored raw + clean content)")
        else:
            logger.info("Using Parallel.ai pipeline (stored clean content only)")
        content_hash = hashlib.sha256(clean_text.encode()).hexdigest()

        rev_query = (
            select(DataRevision)
            .where(DataRevision.source_id == source.id)
            .order_by(desc(DataRevision.scraped_at))
            .limit(1)
        )
        rev_result = await self.db.execute(rev_query)
        last_revision = rev_result.scalars().first()

        diff_patch = {}
        was_change_detected = False
        change_result = None

        if last_revision and last_revision.content_hash == content_hash:
            logger.info(f"Content unchanged (hash: {content_hash[:8]}...). Skipping AI.")
            ai_result = last_revision.extracted_data
            diff_patch = {"change_summary": "No material changes detected", "risk_level": "NONE"}
        else:
            logger.info("Content changed. Running AI Extraction...")

            ai_result = await self.ai_extractor.run_llm_analysis(
                cleaned_text=clean_text,
                project_prompt=master_prompt,
                jurisdiction_prompt=context_prompt,
            )

            old_data = (
                last_revision.extracted_data.get("extracted_data", {}) if last_revision else {}
            )
            new_data = ai_result.get("extracted_data", {})

            monitoring_goal = f"{master_prompt}. Context: {context_prompt}"

            change_result = await self.differ.detect_semantic_change(
                old_data=old_data, new_data=new_data, monitoring_instruction=monitoring_goal
            )

            was_change_detected = change_result.has_changed
            if was_change_detected:
                logger.info(f"Change Detected: {change_result.change_summary}")
                diff_patch = {
                    "change_summary": change_result.change_summary,
                    "risk_level": change_result.risk_level,
                }
            else:
                diff_patch = {
                    "change_summary": "No material changes detected",
                    "risk_level": "NONE",
                }

        try:
            is_baseline = not last_revision

            new_revision = DataRevision(
                source_id=source.id,
                minio_object_key=extraction_result.get("raw_key") or extraction_result["clean_key"],
                content_hash=content_hash,
                extracted_data=ai_result,
                ai_summary=ai_result.get("summary"),
                ai_markdown_summary=ai_result.get("markdown_summary"),
                ai_confidence_score=ai_result.get("confidence_score"),
                was_change_detected=False if is_baseline else was_change_detected,
                is_baseline=is_baseline,
                scraped_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self.db.add(new_revision)
            await self.db.flush()

            if was_change_detected and last_revision:
                new_diff_record = ChangeDiff(
                    new_revision_id=new_revision.id,
                    old_revision_id=last_revision.id,
                    diff_patch=diff_patch,
                    ai_confidence=ai_result.get("confidence_score", 0.0),
                )
                self.db.add(new_diff_record)

            await self.db.commit()
            await self.db.refresh(new_revision)

            if was_change_detected and last_revision:
                logger.info(f"Triggering notifications for revision {new_revision.id}")

                try:
                    send_revision_notifications_task.delay(str(new_revision.id))
                except Exception as celery_err:
                    logger.warning(
                        f"Failed to queue notification task via Celery for revision "
                        f"{new_revision.id}: {celery_err}. Scrape completed successfully."
                    )

            elif was_change_detected and not last_revision:
                logger.info(f"First scrape for source {source.id}. Skipping notification.")

            """Create automatic ticket"""
            if was_change_detected and change_result is not None and last_revision:
                if source.auto_create_tickets:
                    ticket_service = TicketService(self.db)
                    await ticket_service.create_auto_ticket(
                        revision=new_revision,
                        change_result=change_result,
                        source=source,
                        project=project,
                        jurisdiction=jurisdiction,
                    )
                else:
                    logger.info(
                        f"Change detect for source {source.id} but auto_create_ticket is disabled. "
                        f"Skipping ticket creation."
                    )

        except Exception as e:
            await self.db.rollback()
            raise e

        return {
            "status": "success",
            "change_detected": was_change_detected,
            "change_summary": diff_patch.get("change_summary"),
            "data_revision_id": str(new_revision.id),
            "is_baseline": is_baseline,
        }
