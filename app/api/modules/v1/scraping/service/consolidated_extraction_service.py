"""Service for consolidated content extraction and analysis.

Handles the core logic of the new scraping architecture:
1. Consolidate: Merges content from multiple sources.
2. Filter: Use AI to filter irrelevant sources based on jurisdiction prompt.
3. Analyze: Analyze the consolidated context for changes.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    LLMExtractionError,
    ProcessingError,
    StorageError,
    StorageNotFoundError,
)
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
    BlogGenerationService,
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_state_service import (
    JurisdictionStateService,
)
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.llm_service import AIExtractionService
from app.api.modules.v1.scraping.storage import minio_storage
from app.api.modules.v1.scraping.utils.hash_utils import should_skip_consolidation
from app.api.utils.celery_utils import syncify
from app.api.utils.template_utils import format_field_name

logger = logging.getLogger(__name__)


class ConsolidatedExtractionService:
    """Service for handling consolidated extraction logic."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.llm_service = AIExtractionService(db=None)

    def execute(self, job_id: UUID) -> Dict[str, Any]:
        """Execute the consolidation and analysis pipeline.

        Args:
            job_id (UUID): The JurisdictionScrapeJob ID.

        Returns:
            Dict[str, Any]: Results with status, count, and analysis.
        """
        job = self.db.get(JurisdictionScrapeJob, job_id)
        if not job:
            raise ValueError(f"JurisdictionScrapeJob {job_id} not found")

        previous_job = self._get_previous_completed_job(job)
        if should_skip_consolidation(
            job.content_hash, previous_job.content_hash if previous_job else None
        ):
            return self._inherit_from_previous(job, previous_job)

        content_items = self._gather_content(job)
        logger.info(f"Gathered {len(content_items)} content items for job {job_id}")

        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction

        jurisdiction = self.db.get(Jurisdiction, job.jurisdiction_id)

        job.status = JurisdictionScrapeJobStatus.FILTERING
        self.db.add(job)
        self.db.commit()

        filtered_items = self._filter_content(
            content_items, jurisdiction.prompt if jurisdiction else ""
        )
        logger.info(f"Filtered down to {len(filtered_items)} relevant items")
        job.filtered_sources = len(content_items) - len(filtered_items)

        job.status = JurisdictionScrapeJobStatus.CONSOLIDATING
        self.db.add(job)
        self.db.commit()

        consolidated_text = self._consolidate_content(filtered_items)

        job.status = JurisdictionScrapeJobStatus.ANALYZING
        self.db.add(job)
        self.db.commit()

        try:
            org_id = None
            project_id = None
            if jurisdiction:
                project_id = str(jurisdiction.project_id)
                try:
                    from app.api.modules.v1.projects.models.project_model import Project

                    project = self.db.get(Project, jurisdiction.project_id)
                    if project and hasattr(project, "org_id"):
                        org_id = str(project.org_id)
                except Exception as e:
                    logger.warning(f"Could not load project for org_id tracking: {e}")

            previous_schema = self._get_previous_schema(job)

            sorted_sources = sorted(filtered_items, key=lambda x: x.get("source_url", ""))
            source_url_mapping = {
                f"source_{idx}": item.get("source_url", "Unknown")
                for idx, item in enumerate(sorted_sources, 1)
            }

            state_service = JurisdictionStateService(self.db)
            current_state_map = state_service.get_jurisdiction_state(job.jurisdiction_id)

            analysis_result, usage_metrics = self.llm_service.run_consolidated_analysis(
                consolidated_text,
                jurisdiction.prompt if jurisdiction else "",
                previous_schema=previous_schema,
                source_url_mapping=source_url_mapping,
                current_ledger_state=current_state_map,
                organization_id=org_id,
                project_id=project_id,
                jurisdiction_id=str(job.jurisdiction_id),
            )

            if source_url_mapping and "extracted_data" in analysis_result:
                extracted_data = analysis_result["extracted_data"]
                if "key_value_pairs" in extracted_data:
                    kv_pairs = extracted_data["key_value_pairs"]

                    for field_name, field_data in kv_pairs.items():
                        if isinstance(field_data, dict):
                            discrepancies = field_data.get("discrepancies", [])
                            for disc in discrepancies:
                                source_id = disc.get("source_id", "")
                                if source_id in source_url_mapping:
                                    disc["source_url"] = source_url_mapping[source_id]

                    logger.info(
                        f"Post-processed {len(kv_pairs)} fields with source URLs in discrepancies"
                    )

            if usage_metrics:
                self._log_llm_usage_sync(
                    usage_metrics, endpoint="/api/v1/jurisdictions/consolidate"
                )

            job.extracted_data = analysis_result
            job.status = JurisdictionScrapeJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()

            if not current_state_map:
                logger.info(
                    f"Day 1 detected for {job.jurisdiction_id} (Ledger Empty). "
                    "Auto-accepting findings as Initial Truth."
                )
                try:
                    # Re-check ledger immediately before writing to guard against
                    # Celery retry double-writes. If a previous attempt already committed
                    # the jurisdiction_states rows, initialize_state would raise an
                    # IntegrityError (duplicate key), causing db.rollback() to wipe the
                    # ledger. Instead: detect this case and only regenerate the blog.
                    fresh_state_map = state_service.get_jurisdiction_state(job.jurisdiction_id)
                    if not fresh_state_map:
                        self._handle_day_one_auto_accept(job, analysis_result, state_service)
                    else:
                        logger.info(
                            f"Day 1 Retry detected for {job.jurisdiction_id}: "
                            "Ledger already populated by a previous attempt. "
                            "Skipping initialize_state, regenerating blog only."
                        )
                        blog_service = BlogGenerationService(self.db)
                        blog_service.generate_blog_post_sync(
                            jurisdiction_id=job.jurisdiction_id,
                            job_id=job.id,
                            skip_placeholder=True,
                        )

                    self.db.commit()

                    return {
                        "status": "completed",
                        "relevant_sources": len(filtered_items),
                        "analysis": analysis_result,
                        "changes_detected": False,
                        "auto_accepted_day_1": True,
                    }
                except Exception as e:
                    logger.error(
                        f"Day 1 Auto-Accept failed: {e}. Falling back to standard detection.",
                        exc_info=True,
                    )
                    self.db.rollback()

            has_changes, ai_change_result = self._detect_changes_with_ai(
                job,
                jurisdiction,
                org_id,
                project_id,
                current_state_map=current_state_map,
            )

            if has_changes and ai_change_result:
                logger.info(
                    f"AI-detected changes for jurisdiction {job.jurisdiction_id}: "
                    f"{ai_change_result.change_summary}"
                )

                extracted_data = job.extracted_data.copy()
                extracted_data["change_detection"] = {
                    "has_changed": ai_change_result.has_changed,
                    "change_summary": ai_change_result.change_summary,
                    "risk_level": ai_change_result.risk_level,
                    "field_changes": [
                        {
                            "field_name": fc.field_name,
                            "old_value": fc.old_value,
                            "new_value": fc.new_value,
                            "change_type": fc.change_type,
                        }
                        for fc in ai_change_result.field_changes
                    ],
                }
                job.extracted_data = extracted_data
                self.db.add(job)
                self.db.commit()

                # Decide: auto-accept (campaign) or manual review
                is_campaign = (
                    jurisdiction
                    and getattr(jurisdiction, "campaign_id", None) is not None
                    and getattr(jurisdiction, "auto_accept_changes", False)
                )

                if is_campaign and self._is_safe_to_auto_accept(job, ai_change_result):
                    self._handle_day_n_auto_accept(
                        job, jurisdiction, ai_change_result, state_service
                    )
                else:
                    self._create_jurisdiction_change_records(job, ai_change_result)
                    self._send_jurisdiction_notifications(job, jurisdiction, ai_change_result)

            return {
                "status": "completed",
                "relevant_sources": len(filtered_items),
                "analysis": analysis_result,
                "changes_detected": has_changes,
            }

        except (LLMExtractionError, StorageError, StorageNotFoundError) as e:
            logger.error(f"Consolidation failed for job {job_id}: {type(e).__name__}: {e.message}")

            job.status = JurisdictionScrapeJobStatus.FAILED
            job.error_message = e.message
            job.completed_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()
            raise

        except Exception as e:
            logger.exception(f"Unexpected consolidation error for job {job_id}: {e}")

            job.status = JurisdictionScrapeJobStatus.FAILED
            job.error_message = "An unexpected error occurred during consolidation."
            job.completed_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()
            raise ProcessingError("Failed to consolidate content. Please try again.")

    def _gather_content(self, job: JurisdictionScrapeJob) -> List[Dict[str, str]]:
        """Gather raw content from all completed scrape jobs with parallel MinIO fetches."""
        stmt = select(ScrapeJob).where(
            ScrapeJob.jurisdiction_scrape_job_id == job.id,
            ScrapeJob.status == ScrapeJobStatus.COMPLETED,
        )
        completed_jobs = self.db.exec(stmt).all()

        eligible_jobs = [
            sj
            for sj in completed_jobs
            if sj.result and isinstance(sj.result, dict) and sj.result.get("minio_key")
        ]

        if not eligible_jobs:
            return []

        source_ids = [sj.source_id for sj in eligible_jobs]
        sources = self.db.exec(select(Source).where(Source.id.in_(source_ids))).all()
        source_map = {source.id: source for source in sources}

        max_workers = min(
            settings.CONSOLIDATION_MINIO_FETCH_CONCURRENCY,
            len(eligible_jobs),
        )
        results: List[Optional[Dict[str, str]]] = [None] * len(eligible_jobs)

        def _fetch_one(index: int, sj: ScrapeJob) -> Optional[Dict[str, str]]:
            minio_key = sj.result["minio_key"]
            try:
                content_bytes = minio_storage.get_content_from_minio(
                    object_name=minio_key,
                    bucket_name=settings.MINIO_BUCKET,
                    raise_on_error=True,
                )
                content = content_bytes.decode("utf-8") if content_bytes else ""
                source = source_map.get(sj.source_id)
                return {
                    "source_id": str(sj.source_id),
                    "content": content,
                    "source_name": source.name if source else "Unknown",
                    "source_url": source.url if source else "Unknown",
                }
            except Exception as e:
                logger.warning(f"Failed to load content for source {sj.source_id}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(_fetch_one, idx, sj): idx for idx, sj in enumerate(eligible_jobs)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    result = future.result()
                    if result is not None:
                        results[idx] = result
                except Exception as e:
                    sj = eligible_jobs[idx]
                    logger.warning(f"Unexpected error loading source {sj.source_id}: {e}")

        return [r for r in results if r is not None]

    def _filter_content(self, items: List[Dict[str, str]], prompt: str) -> List[Dict[str, str]]:
        """Filter content items based on relevance to the prompt using parallel LLM calls."""
        if not items:
            return []

        max_workers = min(
            settings.CONSOLIDATION_LLM_FILTER_CONCURRENCY,
            len(items),
        )
        relevance_results: List[Optional[bool]] = [None] * len(items)

        def _check_one(index: int, item: Dict[str, str]) -> tuple[int, bool]:
            is_relevant = self.llm_service.check_source_relevance(item["content"], prompt)
            return (index, is_relevant)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(_check_one, idx, item): idx for idx, item in enumerate(items)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    result_idx, is_relevant = future.result()
                    relevance_results[result_idx] = is_relevant
                except Exception as e:
                    logger.warning(
                        f"LLM relevance check failed for source {items[idx].get('source_url')}: {e}"
                    )
                    relevance_results[idx] = False

        return [item for item, is_relevant in zip(items, relevance_results) if is_relevant]

    def _consolidate_content(self, items: List[Dict[str, str]]) -> str:
        """Merge content from multiple sources into a single text."""
        from app.api.modules.v1.scraping.utils.token_counter import estimate_tokens

        MAX_TOKENS = 100000
        consolidated = []
        current_tokens = 0

        sorted_items = sorted(
            items,
            key=lambda x: (
                self._source_priority(x),
                x.get("source_url", ""),
            ),
        )

        for idx, item in enumerate(sorted_items, 1):
            source_header = (
                f"\n\n--- Source {idx}: {item.get('source_name', 'Unknown')} ---\n"
                f"URL: {item.get('source_url', 'Unknown')}\n"
            )
            content_block = source_header + item["content"]

            block_tokens = estimate_tokens(content_block)

            if current_tokens + block_tokens > MAX_TOKENS:
                logger.warning(
                    f"Token limit reached ({current_tokens}/{MAX_TOKENS}). "
                    f"Truncating at source {idx}/{len(sorted_items)}"
                )
                break

            consolidated.append(content_block)
            current_tokens += block_tokens

        return "\n".join(consolidated)

    @staticmethod
    def _source_priority(item: Dict[str, str]) -> int:
        """Rank authoritative legal sources before lower-authority domains."""
        url = item.get("source_url", "")
        hostname = urlparse(url).hostname or ""
        hostname = hostname.lower()

        if hostname.endswith(".gov") or ".gov." in hostname:
            return 0
        if hostname.endswith(".edu") or ".edu." in hostname:
            return 1
        if hostname.endswith(".org") or ".org." in hostname:
            return 2
        return 3

    def _handle_day_one_auto_accept(
        self,
        job: JurisdictionScrapeJob,
        analysis_result: Dict[str, Any],
        state_service: JurisdictionStateService,
    ) -> None:
        """Auto-accept all findings as the initial state (Day 1).

        Args:
            job: Current scrape job.
            analysis_result: Result from LLM analysis.
            state_service: Service to manage state.
        """
        extracted_data = analysis_result.get("extracted_data", {})
        kv_pairs = extracted_data.get("key_value_pairs", {})

        if not kv_pairs:
            logger.warning(f"No data to auto-accept for job {job.id}")
            return

        created_states = state_service.initialize_state(
            jurisdiction_id=job.jurisdiction_id,
            data=kv_pairs,
            originating_job_id=job.id,
            user_id=None,
        )

        logger.info(
            f"Day 1 Auto-Accept: Initialized {len(created_states)} fields "
            f"for jurisdiction {job.jurisdiction_id}."
        )

        try:
            blog_service = BlogGenerationService(self.db)
            blog_result = blog_service.generate_blog_post_sync(
                jurisdiction_id=job.jurisdiction_id,
                job_id=job.id,
                skip_placeholder=True,
            )
            logger.info(
                f"Day 1 Auto-Accept: blog generated for {job.jurisdiction_id}: "
                f"{blog_result.get('status')}"
            )
        except Exception as e:
            logger.error(
                f"Day 1 Auto-Accept: blog generation failed for {job.jurisdiction_id}: {e}",
                exc_info=True,
            )

        try:
            from app.api.modules.v1.jurisdictions.service.sitemap_tasks import (
                sitemap_rebuild_debounced,
            )

            sitemap_rebuild_debounced.delay()
            logger.info("Day 1 Auto-Accept: sitemap rebuild triggered")
        except Exception as e:
            logger.error(f"Day 1 Auto-Accept: sitemap rebuild failed: {e}")

    def _is_safe_to_auto_accept(
        self,
        job: JurisdictionScrapeJob,
        ai_change_result,
    ) -> bool:
        """Two-gate safety check for auto-accept eligibility.

        Gate 1: Source Consensus — all sources must agree on all field values.
        Gate 2: Risk Level — AI must classify change as "low" risk.

        Args:
            job: JurisdictionScrapeJob with extracted_data containing discrepancies.
            ai_change_result: AI change detection result with risk_level.

        Returns:
            True only if both gates pass.
        """
        # Gate 1: Source consensus
        kv_pairs = (job.extracted_data or {}).get("extracted_data", {}).get("key_value_pairs", {})
        for field_name, field_data in kv_pairs.items():
            if not isinstance(field_data, dict):
                continue
            discrepancies = field_data.get("discrepancies", [])
            if len(discrepancies) > 1:
                unique_values = {d.get("value") for d in discrepancies}
                if len(unique_values) > 1:
                    logger.warning(
                        f"Auto-accept blocked: source conflict on '{field_name}' "
                        f"({len(unique_values)} different values) "
                        f"for jurisdiction {job.jurisdiction_id}"
                    )
                    return False

        # Gate 2: Risk level
        risk_level = getattr(ai_change_result, "risk_level", "high")
        if risk_level != "low":
            logger.warning(
                f"Auto-accept blocked: risk_level='{risk_level}' "
                f"for jurisdiction {job.jurisdiction_id}"
            )
            return False

        return True

    def _handle_day_n_auto_accept(
        self,
        job: JurisdictionScrapeJob,
        jurisdiction,
        ai_change_result,
        state_service: JurisdictionStateService,
    ) -> None:
        """Auto-accept Day N changes for campaign jurisdictions.

        Pipeline: Update Ledger → Regenerate Blog → Rebuild Sitemap.
        Does NOT create JurisdictionChange records (no human review needed).

        Args:
            job: JurisdictionScrapeJob that triggered the change.
            jurisdiction: Jurisdiction model instance.
            ai_change_result: AI change detection result with field_changes.
            state_service: JurisdictionStateService for Ledger updates.
        """
        # Step 1: Build updates dict from AI field changes
        updates = {}
        for fc in ai_change_result.field_changes:
            if fc.new_value is not None:
                updates[fc.field_name] = fc.new_value

        if not updates:
            logger.info(
                f"Auto-accept: no field updates to apply for jurisdiction {job.jurisdiction_id}"
            )
            return

        # Step 2: Update Ledger (state_service does NOT commit)
        state_service.update_state(
            jurisdiction_id=job.jurisdiction_id,
            updates=updates,
            change_reason=(
                f"Auto-accepted (campaign {jurisdiction.campaign_id}): "
                f"{ai_change_result.change_summary}"
            ),
            user_id=None,
            job_id=job.id,
        )
        self.db.commit()

        logger.info(
            f"Auto-accept: updated {len(updates)} Ledger fields "
            f"for jurisdiction {job.jurisdiction_id} "
            f"(campaign_id={jurisdiction.campaign_id})"
        )

        # Step 3: Regenerate blog post from updated Ledger
        try:
            blog_service = BlogGenerationService(self.db)
            blog_result = blog_service.generate_blog_post_sync(
                jurisdiction_id=job.jurisdiction_id,
                job_id=job.id,
                skip_placeholder=True,
            )
            logger.info(
                f"Auto-accept: blog regenerated for {job.jurisdiction_id}: "
                f"{blog_result.get('status')}"
            )
        except Exception as e:
            logger.error(
                f"Auto-accept: blog regeneration failed for {job.jurisdiction_id}: {e}",
                exc_info=True,
            )

        # Step 4: Trigger sitemap rebuild (debounced Celery task)
        try:
            from app.api.modules.v1.jurisdictions.service.sitemap_tasks import (
                sitemap_rebuild_debounced,
            )

            sitemap_rebuild_debounced.delay()
            logger.info("Auto-accept: sitemap rebuild triggered")
        except Exception as e:
            logger.error(f"Auto-accept: sitemap rebuild failed: {e}")

    def _detect_changes_with_ai(
        self,
        current_job: JurisdictionScrapeJob,
        jurisdiction,
        org_id: Optional[str],
        project_id: Optional[str],
        current_state_map: Optional[Dict[str, Any]] = None,
    ):
        """Detect changes by comparing current extract against the Jurisdiction State (Ledger).

        Args:
            current_job: The current JurisdictionScrapeJob with extracted data.
            jurisdiction: Jurisdiction model.
            org_id: Organization ID.
            project_id: Project ID.
            current_state_map: Pre-loaded Ledger state to avoid redundant query.

        Returns:
            Tuple[bool, Optional[ChangeDetectionResult]]:
        """
        if current_state_map is None:
            state_service = JurisdictionStateService(self.db)
            current_state_map = state_service.get_jurisdiction_state(current_job.jurisdiction_id)

        previous_kv_normalized = {k: v.value for k, v in current_state_map.items()}
        current_data = current_job.extracted_data or {}
        current_extracted = current_data.get("extracted_data", {})
        current_kv = current_extracted.get("key_value_pairs", {})

        def extract_comparable_values(kv_pairs):
            """Extract canonical_value from nested format."""
            normalized = {}
            for field_name, field_data in kv_pairs.items():
                clean_name = field_name.split(" (")[0] if " (" in field_name else field_name
                if isinstance(field_data, dict):
                    value = field_data.get("canonical_value")
                else:
                    value = field_data
                normalized[clean_name] = value
            return normalized

        current_kv_normalized = extract_comparable_values(current_kv)

        current_normalized = self._normalize_values(current_kv_normalized)
        previous_normalized = self._normalize_values(previous_kv_normalized)

        if current_normalized == previous_normalized:
            logger.info(f"No changes vs Ledger for jur {current_job.jurisdiction_id} (fast match)")
            return False, None

        logger.info(
            f"Diff vs Ledger detected (fast check), running semantic analysis for "
            f"jurisdiction {current_job.jurisdiction_id}"
        )

        monitoring_instruction = (
            jurisdiction.prompt
            if jurisdiction and jurisdiction.prompt
            else "Detect any regulatory or compliance changes"
        )

        if not previous_normalized:
            logger.info("Ledger is empty (Day 1). Treating all fields as NEW for calibration.")

        field_name_mapping = {}
        for original_name in current_kv.keys():
            if " (" in original_name:
                clean_name = original_name.split(" (")[0]
                field_name_mapping[clean_name] = original_name

        try:
            from app.api.modules.v1.scraping.service.diff_service import DiffAIService

            differ = DiffAIService(db=self.db, use_openrouter=True)
            ai_result = differ.detect_semantic_change_sync(
                old_data=previous_kv_normalized,
                new_data=current_kv_normalized,
                monitoring_instruction=monitoring_instruction,
                source_id=str(current_job.jurisdiction_id),
                user_id=None,
                organization_id=org_id,
                project_id=project_id,
                endpoint="/api/v1/jurisdictions/consolidate/diff",
                ip_address=None,
                field_name_mapping=field_name_mapping,
            )

            if ai_result and ai_result.has_changed:
                logger.info(
                    f"AI confirmed changes vs Ledger: "
                    f"risk={ai_result.risk_level}, summary={ai_result.change_summary}"
                )
                return True, ai_result
            else:
                logger.info("AI determined diffs vs Ledger are cosmetic/insignificant.")
                return False, None

        except Exception as e:
            logger.error(
                f"AI detection failed for jur {current_job.jurisdiction_id}: {e}",
                exc_info=True,
            )
            return True, None

    def _get_previous_schema(self, current_job: JurisdictionScrapeJob) -> Optional[List[str]]:
        """Get 'Accepted Schema' from Jurisdiction State (Compliance Ledger).

        Returns the list of field names that are currently confirmed/accepted in the Ledger.
        This guides the LLM to use consistent field naming.

        Args:
            current_job: The current jurisdiction scrape job

        Returns:
            List of field names from Ledger, or None if Ledger is empty.
        """
        state_service = JurisdictionStateService(self.db)
        state_map = state_service.get_jurisdiction_state(current_job.jurisdiction_id)

        if not state_map:
            logger.info(f"Ledger is empty for {current_job.jurisdiction_id}. No previous schema.")
            return None

        schema = list(state_map.keys())
        logger.info(
            f"Using schema from Ledger: {len(schema)} fields - "
            f"{', '.join(schema[:5])}{'...' if len(schema) > 5 else ''}"
        )
        return schema

    def _get_previous_completed_job(
        self, current_job: JurisdictionScrapeJob
    ) -> Optional[JurisdictionScrapeJob]:
        """Get the most recent completed job for this jurisdiction.

        Args:
            current_job: The current jurisdiction scrape job

        Returns:
            Previous completed job or None if no previous job exists
        """
        stmt = (
            select(JurisdictionScrapeJob)
            .where(
                JurisdictionScrapeJob.jurisdiction_id == current_job.jurisdiction_id,
                JurisdictionScrapeJob.id != current_job.id,
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
            )
            .order_by(JurisdictionScrapeJob.completed_at.desc())
        )
        return self.db.exec(stmt).first()

    def _inherit_from_previous(
        self, job: JurisdictionScrapeJob, previous_job: JurisdictionScrapeJob
    ) -> Dict[str, Any]:
        """Inherit extraction data when content is unchanged.

        Args:
            job: Current jurisdiction scrape job
            previous_job: Previous completed job to inherit from

        Returns:
            Result dict indicating content was unchanged
        """
        logger.info(
            f"Content unchanged for jurisdiction {job.jurisdiction_id}, "
            f"inheriting from job {previous_job.id}"
        )

        job.extracted_data = previous_job.extracted_data
        job.status = JurisdictionScrapeJobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        self.db.add(job)
        self.db.commit()

        logger.info(
            f"Skipped consolidation for job {job.id} - inherited extraction from {previous_job.id}"
        )

        return {
            "status": "completed",
            "reason": "content_unchanged",
            "inherited_from": str(previous_job.id),
            "changes_detected": False,
        }

    def _normalize_values(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Normalize values to handle semantic equivalences.

        Handles:
        - Date formatting: "December 31st" == "31st of December" == "Dec 31"
        - Number formatting: "$1,000.00" == "$1000" == "1000 USD"
        - Punctuation: "A; B" == "A, B" == "A B"
        - Codes/IDs: "Item (CODE-123)" == "Item"
        - Whitespace: "  text  " == "text"

        Args:
            data: Dictionary of key-value pairs

        Returns:
            Dictionary with normalized string values for comparison
        """
        import re

        from dateutil import parser

        normalized = {}
        for key, value in data.items():
            if value is None:
                normalized[key] = ""
                continue

            str_value = str(value).strip()

            if self._looks_like_date(str_value):
                try:
                    parsed_date = parser.parse(str_value, fuzzy=True)
                    str_value = parsed_date.strftime("%Y-%m-%d")
                except (ValueError, parser.ParserError):
                    pass

            if "$" in str_value or "USD" in str_value.upper():
                amounts = re.findall(r"\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", str_value)
                if amounts:
                    normalized_amounts = [amt.replace(",", "") for amt in amounts]
                    str_value = " ".join(normalized_amounts)

            str_value = re.sub(r"[;:,]+", " ", str_value)
            str_value = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", r"\1", str_value)
            str_value = re.sub(r"\s+", " ", str_value).strip()

            str_value = str_value.lower()

            normalized[key] = str_value

        return normalized

    def _looks_like_date(self, text: str) -> bool:
        """Quick heuristic to identify potential date strings.

        Args:
            text: String to check

        Returns:
            bool: True if text might be a date
        """
        date_indicators = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            "jan",
            "feb",
            "mar",
            "apr",
            "jun",
            "jul",
            "aug",
            "sep",
            "oct",
            "nov",
            "dec",
            "st of",
            "nd of",
            "rd of",
            "th of",
        ]
        text_lower = text.lower()

        has_month = any(month in text_lower for month in date_indicators)
        has_number = bool(re.search(r"\d+", text))

        return has_month and has_number and len(text) < 50

    def _log_llm_usage_sync(self, metrics, endpoint: str) -> None:
        """Manually log LLM usage with synchronous session.

        Args:
            metrics: Dict or LLMUsageMetrics object from LLM response
            endpoint: API endpoint for tracking
        """
        from app.api.db.models.llm_usage import LLMUsageLog

        try:
            if isinstance(metrics, dict):
                model = metrics.get("model", "unknown")
                provider = metrics.get("provider", "unknown")
                request_id = metrics.get("request_id", "unknown")
                user_id = metrics.get("user_id")
                organization_id = metrics.get("organization_id")
                project_id = metrics.get("project_id")
                jurisdiction_id = metrics.get("jurisdiction_id")
                input_tokens = metrics.get("input_tokens", 0)
                output_tokens = metrics.get("output_tokens", 0)
                total_tokens = metrics.get("total_tokens", 0)
                cost_usd = metrics.get("cost_usd", 0.0)
                latency_ms = metrics.get("latency_ms", 0.0)
                success = metrics.get("success", True)
                error_message = metrics.get("error_message")
                retry_count = metrics.get("retry_count", 0)
            else:
                model = metrics.model
                provider = metrics.provider
                request_id = metrics.request_id or "unknown"
                user_id = metrics.user_id
                organization_id = metrics.organization_id
                project_id = metrics.project_id
                jurisdiction_id = metrics.jurisdiction_id
                input_tokens = metrics.input_tokens
                output_tokens = metrics.output_tokens
                total_tokens = metrics.total_tokens
                cost_usd = metrics.cost_usd
                latency_ms = metrics.latency_ms
                success = metrics.success
                error_message = metrics.error_message
                retry_count = metrics.retry_count

            log_entry = LLMUsageLog(
                request_id=request_id,
                model=model,
                provider=provider,
                user_id=UUID(user_id) if user_id else None,
                organization_id=UUID(organization_id) if organization_id else None,
                project_id=UUID(project_id) if project_id else None,
                jurisdiction_id=UUID(jurisdiction_id) if jurisdiction_id else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message,
                retry_count=retry_count,
                endpoint=endpoint,
                ip_address=None,
            )

            self.db.add(log_entry)
            self.db.commit()

            logger.info(
                f"Logged LLM usage (sync): model={model}, "
                f"tokens={total_tokens}, cost=${cost_usd:.6f}"
            )
        except Exception as e:
            logger.error(f"Failed to log LLM usage (sync): {e}", exc_info=True)
            self.db.rollback()

    def _create_jurisdiction_change_records(
        self, job: JurisdictionScrapeJob, ai_change_result
    ) -> None:
        """Create JurisdictionChange records for each detected field change.

        Args:
            job: JurisdictionScrapeJob with detected changes
            ai_change_result: AI change detection result with field_changes list
        """
        try:
            if not ai_change_result or not ai_change_result.field_changes:
                logger.info(f"No field changes to create records for job {job.id}")
                return

            created_count = 0
            for idx, field_change in enumerate(ai_change_result.field_changes):
                if hasattr(field_change, "change_description") and field_change.change_description:
                    change_description = field_change.change_description
                elif len(ai_change_result.field_changes) == 1 and ai_change_result.change_summary:
                    change_description = ai_change_result.change_summary
                    logger.info(
                        f"Using overall change_summary as description for single field change: "
                        f"{field_change.field_name}"
                    )
                else:
                    change_description = (
                        f"{field_change.field_name} {field_change.change_type}: "
                        f"{field_change.old_value} → {field_change.new_value}"
                    )
                    logger.warning(
                        f"LLM did not provide change_description for field "
                        f"{field_change.field_name}, using technical fallback format"
                    )

                jurisdiction_change = JurisdictionChange(
                    jurisdiction_scrape_job_id=job.id,
                    field_name=field_change.field_name,
                    old_value=str(field_change.old_value) if field_change.old_value else None,
                    new_value=str(field_change.new_value) if field_change.new_value else None,
                    change_description=change_description,
                    change_index=idx,
                    ticket_created=False,
                    change_accepted=False,
                    created_at=job.completed_at or datetime.now(timezone.utc),
                )

                self.db.add(jurisdiction_change)
                created_count += 1

            self.db.commit()
            logger.info(f"Created {created_count} JurisdictionChange records for job {job.id}")

        except Exception as e:
            logger.error(
                f"Failed to create JurisdictionChange records for job {job.id}: {e}",
                exc_info=True,
            )
            self.db.rollback()

    def _send_jurisdiction_notifications(
        self, job: JurisdictionScrapeJob, jurisdiction, ai_change_result=None
    ) -> None:
        """Send email notifications to project users about jurisdiction-level changes.

        Sends notifications WHENEVER changes are detected, regardless of whether
        tickets are created. This ensures users are always informed of changes
        even if they have disabled auto-ticket creation.

        All notification rows are created in a single commit, then emails are
        sent sequentially and statuses updated in a second commit.

        Args:
            job: JurisdictionScrapeJob with detected changes
            jurisdiction: Jurisdiction model
            ai_change_result: Optional AI change detection result with summary
        """
        try:
            from app.api.modules.v1.notifications.models.revision_notification import (
                Notification,
                NotificationStatus,
                NotificationType,
            )
            from app.api.modules.v1.projects.models.project_model import Project
            from app.api.modules.v1.projects.models.project_user_model import ProjectUser
            from app.api.modules.v1.users.models.users_model import User

            project = self.db.get(Project, jurisdiction.project_id)
            if not project:
                logger.error(f"Project {jurisdiction.project_id} not found for notifications")
                return

            stmt = select(ProjectUser).where(ProjectUser.project_id == project.id)
            project_users = self.db.exec(stmt).all()

            if not project_users:
                logger.info(f"No users found in project {project.id}, skipping notifications")
                return

            logger.info(
                f"Sending notifications to {len(project_users)} users for "
                f"jurisdiction {jurisdiction.name}"
            )

            extracted_data = job.extracted_data or {}

            if ai_change_result:
                change_summary = ai_change_result.change_summary
                risk_level = ai_change_result.risk_level
                changes = [
                    {
                        "field": format_field_name(fc.field_name),
                        "old_value": fc.old_value,
                        "new_value": fc.new_value,
                        "change_description": (
                            f"{format_field_name(fc.field_name)} {fc.change_type}: "
                            f"{fc.old_value} → {fc.new_value}"
                        ),
                    }
                    for fc in ai_change_result.field_changes
                ]
            else:
                change_detection = extracted_data.get("change_detection", {})
                change_summary = change_detection.get(
                    "change_summary", extracted_data.get("summary", "Changes detected")
                )
                risk_level = change_detection.get("risk_level", "MEDIUM")
                changes = change_detection.get("field_changes", [])

            base_url = settings.FRONTEND_URL or "https://legalwatch.dog"
            action_url = (
                f"{base_url}/app/jurisdictions/{jurisdiction.id}?"
                f"organizationId={project.org_id}&tab=data-page"
            )

            notification_title = f"Jurisdiction Update: {jurisdiction.name}"

            user_ids = [pu.user_id for pu in project_users]
            users = self.db.exec(select(User).where(User.id.in_(user_ids))).all()
            user_map = {u.id: u for u in users}

            notifications_with_email = []
            for project_user in project_users:
                user = user_map.get(project_user.user_id)
                if not user:
                    logger.warning(f"User {project_user.user_id} not found, skipping")
                    continue

                notification = Notification(
                    user_id=user.id,
                    notification_type=NotificationType.CHANGE_DETECTED,
                    title=notification_title,
                    message=change_summary,
                    jurisdiction_id=jurisdiction.id,
                    organization_id=project.org_id,
                    action_url=action_url,
                    status=NotificationStatus.PENDING,
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(notification)
                notifications_with_email.append((notification, user.email, user.name))

            self.db.commit()

            email_context = {
                "ai_summary": change_summary,
                "risk_level": risk_level,
                "source_name": jurisdiction.name,
                "jurisdiction_name": jurisdiction.name,
                "change_count": len(changes),
                "changes": changes,
                "action_url": action_url,
                "subject": notification_title,
            }

            sent_count = 0
            failed_count = 0

            for notification, email, name in notifications_with_email:
                email_context["user_name"] = name or email.split("@")[0]
                try:
                    success = syncify(send_email)(
                        template_name="revision_notification.html",
                        subject=notification_title,
                        recipient=email,
                        context=email_context,
                    )
                    if success:
                        notification.status = NotificationStatus.SENT
                        sent_count += 1
                        logger.info(f"✓ Notification sent to {email}")
                    else:
                        notification.status = NotificationStatus.FAILED
                        failed_count += 1
                        logger.error(f"✗ Failed to send notification to {email}")
                except Exception as e:
                    notification.status = NotificationStatus.FAILED
                    failed_count += 1
                    logger.error(f"✗ Exception sending notification to {email}: {e}")

                notification.sent_at = datetime.now(timezone.utc)
                self.db.add(notification)

            self.db.commit()

            logger.info(
                f"Jurisdiction notification summary for {jurisdiction.name}: "
                f"Sent: {sent_count}, Failed: {failed_count}"
            )

        except Exception as e:
            logger.error(
                f"Failed to send jurisdiction notifications for job {job.id}: {e}", exc_info=True
            )
