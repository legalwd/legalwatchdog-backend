"""Service for retrieving consolidated data page content."""

import json
import logging
from typing import Any, Dict, List
from uuid import UUID

import httpx
from sqlmodel import Session, select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    BadRequestError,
    JurisdictionScrapeJobNotFoundError,
    ProcessingError,
)
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus

logger = logging.getLogger(__name__)


class DataPageService:
    """Service for managing Data Page content retrieval."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_scrape_status(self, jurisdiction_id: UUID) -> Dict[str, Any]:
        """Get lightweight status of the current or most recent scrape job.

        Args:
            jurisdiction_id (UUID): Jurisdiction ID.

        Returns:
            Dict: Job status info (lightweight for polling).
        """
        job = self.db.exec(
            select(JurisdictionScrapeJob)
            .where(JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id)
            .order_by(JurisdictionScrapeJob.started_at.desc())
        ).first()

        if not job:
            return {"status": "no_jobs_run"}

        progress = self._calculate_progress(job)

        return {
            "job_id": str(job.id),
            "status": job.status,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "total_sources": job.total_sources,
            "successful_sources": job.successful_sources,
            "filtered_sources": job.filtered_sources,
            "progress_percentage": progress,
        }

    def get_data_page(self, jurisdiction_id: UUID) -> Dict[str, Any]:
        """Get the latest consolidated data page content with changes.

        Args:
            jurisdiction_id (UUID): Jurisdiction ID.

        Returns:
            Dict: Full data page content with change tracking (heavy payload).
        """
        current_job = self.db.exec(
            select(JurisdictionScrapeJob)
            .where(
                JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
            )
            .order_by(JurisdictionScrapeJob.completed_at.desc())
        ).first()

        if not current_job:
            return {"status": "empty", "message": "No data available yet.", "last_updated": None}

        previous_job = self.db.exec(
            select(JurisdictionScrapeJob)
            .where(
                JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                JurisdictionScrapeJob.id != current_job.id,
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
            )
            .order_by(JurisdictionScrapeJob.completed_at.desc())
        ).first()

        extracted_data = current_job.extracted_data or {}

        # Find the job that has the actual JurisdictionChange records.
        # When content is unchanged, extracted_data is inherited but
        # change records stay on the original job.
        jurisdiction_changes = list(
            self.db.exec(
                select(JurisdictionChange).where(
                    JurisdictionChange.jurisdiction_scrape_job_id == current_job.id
                )
            ).all()
        )

        change_detection = extracted_data.get("change_detection", {})
        if not jurisdiction_changes and change_detection.get("field_changes"):
            subquery = (
                select(JurisdictionChange.jurisdiction_scrape_job_id)
                .where(JurisdictionChange.jurisdiction_scrape_job_id == JurisdictionScrapeJob.id)
                .exists()
            )

            job_with_changes = self.db.exec(
                select(JurisdictionScrapeJob)
                .where(
                    JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                    JurisdictionScrapeJob.id != current_job.id,
                    JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
                    subquery,
                )
                .order_by(JurisdictionScrapeJob.completed_at.desc())
            ).first()

            if job_with_changes:
                jurisdiction_changes = list(
                    self.db.exec(
                        select(JurisdictionChange).where(
                            JurisdictionChange.jurisdiction_scrape_job_id == job_with_changes.id
                        )
                    ).all()
                )
                logger.info(
                    f"Found JurisdictionChange records on job {job_with_changes.id} "
                    f"(inherited by current job {current_job.id})"
                )

        changes_by_index = {jc.change_index: jc for jc in jurisdiction_changes}

        change_detection = extracted_data.get("change_detection", {})
        if change_detection:
            changes = []
            for idx, fc in enumerate(change_detection.get("field_changes", [])):
                field_name = fc.get("field_name", fc.get("field", ""))

                if fc.get("change_description"):
                    change_desc = fc.get("change_description")
                elif idx in changes_by_index and changes_by_index[idx].change_description:
                    change_desc = changes_by_index[idx].change_description
                else:
                    change_desc = (
                        f"{field_name} "
                        f"{fc.get('change_type', 'changed')}: "
                        f"{fc.get('old_value')} → {fc.get('new_value')}"
                    )

                change_obj = {
                    "field": field_name,
                    "old_value": fc.get("old_value"),
                    "new_value": fc.get("new_value"),
                    "change_description": change_desc,
                    "change_index": idx,
                }

                if idx in changes_by_index:
                    jc = changes_by_index[idx]
                    change_obj["change_id"] = str(jc.id)
                    change_obj["ticket_created"] = jc.ticket_created
                    change_obj["change_accepted"] = jc.change_accepted
                else:
                    change_obj["change_id"] = None
                    change_obj["ticket_created"] = False
                    change_obj["change_accepted"] = False

                changes.append(change_obj)

            change_summary = change_detection.get("change_summary", "Changes detected")
        else:
            changes = self._compute_changes(current_job, previous_job) if previous_job else []
            change_summary = extracted_data.get("summary")

        extracted_kv = extracted_data.get("extracted_data", {}).get("key_value_pairs", {})

        changed_fields = {c["field"]: idx for idx, c in enumerate(changes)}
        data_items = []
        for field_name, field_data in extracted_kv.items():
            if isinstance(field_data, dict):
                canonical_value = field_data.get("canonical_value")
                has_discrepancy = field_data.get("has_discrepancy", False)
                discrepancies = field_data.get("discrepancies", [])
                source_count = field_data.get("source_count", 1)
                agreement_count = field_data.get("agreement_count", 1)
            else:
                canonical_value = field_data
                has_discrepancy = False
                discrepancies = []
                source_count = 1
                agreement_count = 1

            has_change = field_name in changed_fields
            item = {
                "field": field_name,
                "value": canonical_value,
                "has_change": has_change,
                "has_discrepancy": has_discrepancy,
                "source_count": source_count,
                "agreement_count": agreement_count,
            }

            if discrepancies:
                item["discrepancies"] = discrepancies

            if has_change:
                change_idx = changed_fields[field_name]
                change_obj = changes[change_idx].copy()
                change_obj["detected_at"] = current_job.completed_at
                item["change"] = change_obj
                item["change_index"] = change_idx

            data_items.append(item)

        return {
            "status": "available",
            "last_updated": current_job.completed_at,
            "job_id": str(current_job.id),
            "summary": change_summary,
            "markdown_content": extracted_data.get("markdown_summary"),
            "extracted_data": extracted_kv,  # Keep for backward compat
            "data_items": data_items,  # Array format for FE with discrepancy info
            "confidence_score": extracted_data.get("confidence_score"),
            "changes": changes,  # Keep for backward compat
            "has_unaccepted_changes": len(changes) > 0,
            "change_detection": change_detection,
        }

    def get_scrape_job_summary(self, job_id: UUID, jurisdiction_id: UUID) -> Dict[str, Any]:
        """Get markdown summary and changes for a specific JurisdictionScrapeJob.

        Args:
            job_id: UUID of the JurisdictionScrapeJob
            jurisdiction_id: UUID of the jurisdiction (for validation)

        Returns:
            Dict containing job summary, markdown content, and changes.

        Raises:
            JurisdictionScrapeJobNotFoundError: If job doesn't exist
            BadRequestError: If job doesn't belong to the jurisdiction
            ProcessingError: If an unexpected error occurs during processing
        """
        try:
            job = self.db.exec(
                select(JurisdictionScrapeJob).where(JurisdictionScrapeJob.id == job_id)
            ).first()

            if not job:
                raise JurisdictionScrapeJobNotFoundError()

            if job.jurisdiction_id != jurisdiction_id:
                raise BadRequestError(
                    message="The scrape job does not belong to this jurisdiction."
                )

            if job.status == JurisdictionScrapeJobStatus.FAILED:
                return {
                    "job_id": str(job.id),
                    "jurisdiction_id": str(job.jurisdiction_id),
                    "status": job.status.value,
                    "markdown_summary": None,
                    "change_summary": None,
                    "changes": [],
                    "error_message": job.error_message,
                    "created_at": job.created_at,
                    "completed_at": job.completed_at,
                }

            extracted_data = job.extracted_data or {}

            change_detection = extracted_data.get("change_detection", {})
            change_summary = change_detection.get("change_summary")

            # Find the job that has the actual JurisdictionChange records.
            # When content is unchanged, extracted_data is inherited but
            # change records stay on the original job.
            jurisdiction_changes = list(
                self.db.exec(
                    select(JurisdictionChange).where(
                        JurisdictionChange.jurisdiction_scrape_job_id == job.id
                    )
                ).all()
            )

            # If no change records but we have change_detection data,
            # trace back to find original job
            if not jurisdiction_changes and change_detection.get("field_changes"):
                # Optimized: Single query with EXISTS subquery
                subquery = (
                    select(JurisdictionChange.jurisdiction_scrape_job_id)
                    .where(
                        JurisdictionChange.jurisdiction_scrape_job_id == JurisdictionScrapeJob.id
                    )
                    .exists()
                )

                job_with_changes = self.db.exec(
                    select(JurisdictionScrapeJob)
                    .where(
                        JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                        JurisdictionScrapeJob.id != job.id,
                        JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
                        subquery,
                    )
                    .order_by(JurisdictionScrapeJob.completed_at.desc())
                ).first()

                if job_with_changes:
                    jurisdiction_changes = list(
                        self.db.exec(
                            select(JurisdictionChange).where(
                                JurisdictionChange.jurisdiction_scrape_job_id == job_with_changes.id
                            )
                        ).all()
                    )
                    logger.info(
                        f"Found JurisdictionChange records on job {job_with_changes.id} "
                        f"(inherited by job {job.id})"
                    )

            changes_by_index = {jc.change_index: jc for jc in jurisdiction_changes}

            changes = []
            for idx, fc in enumerate(change_detection.get("field_changes", [])):
                field_name = fc.get("field_name", fc.get("field", ""))
                if fc.get("change_description"):
                    change_desc = fc.get("change_description")
                elif idx in changes_by_index and changes_by_index[idx].change_description:
                    change_desc = changes_by_index[idx].change_description
                else:
                    change_desc = (
                        f"{field_name} "
                        f"{fc.get('change_type', 'changed')}: "
                        f"{fc.get('old_value')} → {fc.get('new_value')}"
                    )

                change_obj = {
                    "field": field_name,
                    "old_value": fc.get("old_value"),
                    "new_value": fc.get("new_value"),
                    "change_description": change_desc,
                    "change_index": idx,
                }

                if idx in changes_by_index:
                    jc = changes_by_index[idx]
                    change_obj["change_id"] = str(jc.id)
                    change_obj["ticket_created"] = jc.ticket_created
                    change_obj["change_accepted"] = jc.change_accepted
                else:
                    change_obj["change_id"] = None
                    change_obj["ticket_created"] = False
                    change_obj["change_accepted"] = False

                changes.append(change_obj)

            return {
                "job_id": str(job.id),
                "jurisdiction_id": str(job.jurisdiction_id),
                "status": job.status.value,
                "markdown_summary": extracted_data.get("markdown_summary"),
                "change_summary": change_summary,
                "changes": changes,
                "error_message": None,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
            }

        except (JurisdictionScrapeJobNotFoundError, BadRequestError):
            raise
        except Exception as e:
            logger.exception(f"Error retrieving scrape job summary for job {job_id}")
            raise ProcessingError(
                message="An error occurred while retrieving scrape job summary. Please try again."
            ) from e

    def _extract_source_url(self, field_name: str) -> str | None:
        """Extract source URL from field name if present.

        Field names may contain URLs in parentheses, e.g.:
        "fee_schedule_source_1 (https://example.com/fees)"

        Args:
            field_name: Field name potentially containing URL

        Returns:
            Extracted URL or None if not present
        """
        import re

        match = re.search(r"\(https?://[^)]+\)", field_name)
        if match:
            return match.group(0)[1:-1]
        return None

    def _calculate_progress(self, job: JurisdictionScrapeJob) -> int:
        """Calculate progress percentage based on job status and child jobs.

        Progress breakdown:
        - 0-60%: SCRAPING phase (based on completed sources)
        - 60-70%: CONSOLIDATING phase
        - 70-80%: FILTERING phase
        - 80-95%: ANALYZING phase
        - 95-99%: Final processing
        - 100%: COMPLETED
        """
        if job.status == JurisdictionScrapeJobStatus.COMPLETED:
            return 100
        if job.status == JurisdictionScrapeJobStatus.FAILED:
            return 0

        if not job.total_sources or job.total_sources == 0:
            status_progress = {
                JurisdictionScrapeJobStatus.PENDING: 0,
                JurisdictionScrapeJobStatus.SCRAPING: 30,
                JurisdictionScrapeJobStatus.CONSOLIDATING: 65,
                JurisdictionScrapeJobStatus.FILTERING: 75,
                JurisdictionScrapeJobStatus.ANALYZING: 87,
            }
            return status_progress.get(job.status, 0)

        completed_count = self.db.exec(
            select(ScrapeJob).where(
                ScrapeJob.jurisdiction_scrape_job_id == job.id,
                ScrapeJob.status == ScrapeJobStatus.COMPLETED,
            )
        ).all()

        scraping_progress = int((len(completed_count) / job.total_sources) * 60)

        if job.status == JurisdictionScrapeJobStatus.PENDING:
            return 0

        if job.status == JurisdictionScrapeJobStatus.SCRAPING:
            return scraping_progress

        if job.status == JurisdictionScrapeJobStatus.CONSOLIDATING:
            return max(60, min(scraping_progress + 10, 70))

        if job.status == JurisdictionScrapeJobStatus.FILTERING:
            return max(70, min(scraping_progress + 20, 80))

        if job.status == JurisdictionScrapeJobStatus.ANALYZING:
            return max(80, min(scraping_progress + 35, 95))

        return min(scraping_progress + 35, 99)

    def _compute_changes(
        self, current_job: JurisdictionScrapeJob, previous_job: JurisdictionScrapeJob
    ) -> List[Dict[str, Any]]:
        """Compute field-level changes between current and previous jobs.

        Args:
            current_job: Current jurisdiction scrape job.
            previous_job: Previous jurisdiction scrape job.

        Returns:
            List of change objects with old/new values.
        """
        current_data = current_job.extracted_data or {}
        previous_data = previous_job.extracted_data or {}

        current_kv = current_data.get("extracted_data", {}).get("key_value_pairs", {})
        previous_kv = previous_data.get("extracted_data", {}).get("key_value_pairs", {})

        changes = []

        for key, new_value in current_kv.items():
            old_value = previous_kv.get(key)

            if old_value != new_value:
                change_description = self._generate_change_description(key, old_value, new_value)

                changes.append(
                    {
                        "field": key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "change_description": change_description,
                        "detected_at": current_job.completed_at,
                        "status": "pending",
                    }
                )

        for key in previous_kv:
            if key not in current_kv:
                changes.append(
                    {
                        "field": key,
                        "old_value": previous_kv[key],
                        "new_value": None,
                        "change_description": f"{key} was removed",
                        "detected_at": current_job.completed_at,
                        "status": "pending",
                    }
                )

        if changes and settings.OPENROUTER_API_KEY:
            changes = self._filter_semantic_changes(changes)

        return changes

    def _filter_semantic_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out cosmetic changes using LLM semantic analysis.

        Uses LLM to classify each change as:
        - 'significant': Real information change (keep)
        - 'cosmetic': Formatting only change (filter out)

        Args:
            changes: List of raw change objects.

        Returns:
            Filtered list with only significant changes.
        """
        if not changes:
            return []

        try:
            from app.api.modules.v1.scraping.constants.change_detection import (
                COSMETIC_CHANGE_EXAMPLES,
            )

            changes_text = "\n".join(
                [
                    f"- Field: {c['field']}\n  Old: {c['old_value']}\n  New: {c['new_value']}"
                    for c in changes
                ]
            )

            prompt = f"""Analyze these field changes and classify each as either:
- "significant": The information content has actually changed (different dates, amounts, \
requirements, etc.)
- "cosmetic": Only formatting changed (same date different format, same amount different \
currency symbol, punctuation changes, case changes, code/ID additions or removals, etc.)

Changes:
{changes_text}

Return a JSON array with the field name and classification for EACH change:
[{{"field": "field_name", "classification": "significant|cosmetic", "reason": "brief explanation"}}]

{COSMETIC_CHANGE_EXAMPLES}

Return ONLY the JSON array, no other text."""

            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "xiaomi/mimo-v2-flash:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 500,
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.warning(
                    f"LLM filter failed with status {response.status_code}, returning all changes"
                )
                return changes

            content = response.json()["choices"][0]["message"]["content"]

            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            classifications = json.loads(content)
            significant_fields = {
                c["field"] for c in classifications if c.get("classification") == "significant"
            }
            filtered = [c for c in changes if c["field"] in significant_fields]

            cosmetic_count = len(changes) - len(filtered)
            if cosmetic_count > 0:
                logger.info(
                    f"Filtered out {cosmetic_count} cosmetic changes, "
                    f"keeping {len(filtered)} significant changes"
                )

            return filtered

        except Exception as e:
            logger.warning(f"LLM semantic filter failed: {e}, returning all changes")
            return changes

    def _generate_change_description(self, field: str, old_value: Any, new_value: Any) -> str:
        """Generate human-readable change description.

        Args:
            field: Field name.
            old_value: Previous value.
            new_value: New value.

        Returns:
            Human-readable description.
        """
        if old_value is None:
            return f"{field} is now {new_value}"

        if new_value is None:
            return f"{field} was removed (was {old_value})"

        return f"{field} changed from {old_value} to {new_value}"
