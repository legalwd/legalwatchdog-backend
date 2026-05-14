"""Stage 4: Change detection, notifications, and auto-ticket creation.

.. deprecated::
    This service implements source-level scrape-to-scrape diffing which
    compares consecutive DataRevision snapshots. The architecture is
    migrating toward the Compliance Ledger (Golden Record) pattern
    implemented in ``ConsolidatedExtractionService`` and
    ``JurisdictionStateService``, where accepted state is persisted in
    ``JurisdictionState`` and changes are only applied when a user
    explicitly accepts them.

    This service remains in use for the Stage 4 Celery pipeline
    (``scraping_stage4_diff_and_notify``) but should not be extended
    with new features. Plan to migrate its callers to the Ledger-based
    jurisdiction pipeline.

Responsibilities:
- Load previous revision for comparison
- Detect semantic changes using DiffAIService
- Create ChangeDiff records
- Trigger revision notifications
- Create auto-tickets if enabled
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import text, update
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.service.revision_notification_task import (
    send_revision_notifications_task,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.diff_service import DiffAIService
from app.api.utils.celery_utils import syncify

logger = logging.getLogger(__name__)


class DiffAndNotificationService:
    """Orchestrates Stage 4: Change detection and notifications."""

    def __init__(self):
        """Initialize service."""
        self.differ = DiffAIService()

    def execute(self, source_id: str, revision_id: str) -> Dict[str, Any]:
        """Execute change detection and notification pipeline.

        Args:
            source_id (str): UUID of the source.
            revision_id (str): UUID of the DataRevision.

        Returns:
            dict: Status with keys:
                - status: 'completed' or 'failed'
                - change_detected: Boolean
                - change_summary: String description

        Raises:
            Exception: Propagated to Celery for retry logic.

        Examples:
            >>> service = DiffAndNotificationService()
            >>> result = service.execute("source-uuid", "revision-uuid")
        """
        with SyncSessionLocal() as db:
            return self._execute_with_db(db, source_id, revision_id)

    def _execute_with_db(self, db: Session, source_id: str, revision_id: str) -> Dict[str, Any]:
        """Execute with database session.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.
            revision_id (str): Revision UUID.

        Returns:
            dict: Execution result.
        """
        revision = self._load_revision(db, revision_id)

        if not revision:
            logger.error(f"DataRevision {revision_id} not found")
            return {"status": "failed", "reason": "revision_not_found"}

        source = self._load_source(db, source_id)

        if not source:
            logger.error(f"Source {source_id} not found")
            return {"status": "failed", "reason": "source_not_found"}

        try:
            last_revision = self._get_previous_revision(db, source_id, revision_id)

            if revision.is_baseline:
                logger.info(f"Baseline scrape for {source_id}, skipping change detection")
                return {
                    "status": "completed",
                    "change_detected": False,
                    "reason": "baseline_scrape",
                }

            if not last_revision:
                logger.warning("Previous revision not found for comparison")
                return {
                    "status": "completed",
                    "change_detected": False,
                    "reason": "no_previous_revision",
                }

            logger.info(
                f"Comparing revisions for source {source_id}: "
                f"last={last_revision.id} (scraped_at={last_revision.scraped_at}), "
                f"current={revision.id} (scraped_at={revision.scraped_at})"
            )

            change_result = self._detect_changes(last_revision, revision, source)

            was_change_detected = change_result.has_changed

            logger.info(
                f"Change detection complete for {source_id}: "
                f"detected={was_change_detected}, "
                f"summary={change_result.change_summary}"
            )

            revision.was_change_detected = was_change_detected
            db.commit()

            if was_change_detected:
                self._create_change_diff(db, revision, last_revision, change_result)

                self._trigger_notifications(revision)

                if source.auto_create_tickets:
                    self._create_auto_ticket(db, revision, source, change_result)
                else:
                    logger.info(
                        f"Change detect for source {source.id} but auto_create_ticket is disabled. "
                        f"Skipping ticket creation."
                    )

            return {
                "status": "completed",
                "change_detected": was_change_detected,
                "change_summary": change_result.change_summary,
            }

        except Exception as e:
            logger.error(f"Diff and notification failed: {e}", exc_info=True)
            raise

    @staticmethod
    def _load_revision(db: Session, revision_id: str) -> Optional[DataRevision]:
        """Load revision with eager relationships.

        Args:
            db (Session): Database session.
            revision_id (str): Revision UUID.

        Returns:
            Optional[DataRevision]: Loaded revision.
        """
        stmt = select(DataRevision).where(DataRevision.id == revision_id)
        return db.exec(stmt).first()

    @staticmethod
    def _load_source(db: Session, source_id: str) -> Optional[Source]:
        """Load source with eager relationships.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.

        Returns:
            Optional[Source]: Loaded source with relations.
        """
        stmt = (
            select(Source)
            .where(Source.id == source_id)
            .options(selectinload(Source.jurisdiction).selectinload(Jurisdiction.project))
        )
        return db.exec(stmt).first()

    @staticmethod
    def _get_previous_revision(
        db: Session, source_id: str, current_revision_id: str
    ) -> Optional[DataRevision]:
        """Get previous revision for comparison.

        Args:
            db (Session): Database session.
            source_id (str): Source UUID.
            current_revision_id (str): Current revision UUID to exclude.

        Returns:
            Optional[DataRevision]: Previous revision or None.
        """
        stmt = (
            select(DataRevision)
            .where(
                DataRevision.source_id == source_id,
                DataRevision.id != current_revision_id,
            )
            .order_by(DataRevision.scraped_at.desc())
            .limit(1)
        )
        return db.exec(stmt).first()

    def _detect_changes(
        self, last_revision: DataRevision, current_revision: DataRevision, source: Source
    ) -> Any:
        """Detect semantic changes between revisions.

        Args:
            last_revision (DataRevision): Previous revision.
            current_revision (DataRevision): Current revision.
            source (Source): Source being analyzed.

        Returns:
            ChangeResult: Change detection results.
        """
        old_data = last_revision.extracted_data.get("key_value_pairs", {})
        new_data = current_revision.extracted_data.get("key_value_pairs", {})

        logger.debug(
            f"Comparing data for source {source.id}: "
            f"old keys={list(old_data.keys()) if old_data else 'None'}, "
            f"new keys={list(new_data.keys()) if new_data else 'None'}"
        )

        monitoring_goal = (
            source.jurisdiction.project.master_prompt
            if source.jurisdiction and source.jurisdiction.project
            else ""
        )
        context = source.jurisdiction.name if source.jurisdiction else ""

        monitoring_instruction = f"{monitoring_goal}. Context: {context}"

        # Extract tracking IDs for LLM usage logging
        project_id = None
        organization_id = None
        if source.jurisdiction and source.jurisdiction.project:
            project_id = str(source.jurisdiction.project.id)
            organization_id = str(source.jurisdiction.project.org_id)
            logger.info(
                f"[STAGE4] Extracted tracking IDs: "
                f"org_id={organization_id}, project_id={project_id}, "
                f"source_id={source.id}"
            )
        else:
            logger.warning(
                f"[STAGE4] Missing jurisdiction or project: "
                f"jurisdiction={source.jurisdiction}, "
                f"project={source.jurisdiction.project if source.jurisdiction else 'N/A'}"
            )

        change_result = syncify(self._detect_changes_async)(
            old_data=old_data,
            new_data=new_data,
            monitoring_instruction=monitoring_instruction,
            source_id=str(source.id),
            project_id=project_id,
            organization_id=organization_id,
        )
        return change_result

    @staticmethod
    def _create_change_diff(
        db: Session,
        revision: DataRevision,
        last_revision: DataRevision,
        change_result: Any,
    ) -> None:
        """Create ChangeDiff record.

        Args:
            db (Session): Database session.
            revision (DataRevision): Current revision.
            last_revision (DataRevision): Previous revision.
            change_result: Change detection results.
        """
        existing_diff = (
            db.query(ChangeDiff)
            .filter(
                ChangeDiff.new_revision_id == revision.id,
                ChangeDiff.old_revision_id == last_revision.id,
            )
            .first()
        )

        if existing_diff:
            logger.info(
                f"ChangeDiff already exists for revision {revision.id} "
                f"(old: {last_revision.id}), skipping creation"
            )
            return

        diff_patch = {
            "change_summary": change_result.change_summary,
            "risk_level": change_result.risk_level,
            "field_changes": [
                {
                    "field_name": fc.field_name,
                    "old_value": fc.old_value,
                    "new_value": fc.new_value,
                    "change_type": fc.change_type,
                }
                for fc in change_result.field_changes
            ],
        }

        diff = ChangeDiff(
            new_revision_id=revision.id,
            old_revision_id=last_revision.id,
            diff_patch=diff_patch,
            ai_confidence=revision.ai_confidence_score or 0.0,
        )
        db.add(diff)
        db.commit()

        logger.info(f"Created ChangeDiff for revision {revision.id}")

    @staticmethod
    async def _detect_changes_async(
        old_data: dict,
        new_data: dict,
        monitoring_instruction: str,
        source_id: str,
        project_id: Optional[str],
        organization_id: Optional[str],
    ) -> Any:
        """Detect changes using DiffAIService with SYNC session for Celery tracking.

        Uses SyncSessionLocal instead of AsyncSessionLocal to avoid event loop conflicts
        when running in Celery context. The LLMManager will detect the sync session and
        use synchronous tracking methods.

        Args:
            old_data: Previous revision data.
            new_data: Current revision data.
            monitoring_instruction: Change detection instruction.
            source_id: Source UUID.
            project_id: Project UUID for tracking.
            organization_id: Organization UUID for tracking.

        Returns:
            ChangeResult: Change detection results.
        """
        from app.api.db.database import SyncSessionLocal

        with SyncSessionLocal() as sync_db:
            differ = DiffAIService(db=sync_db, use_openrouter=True)
            result = await differ.detect_semantic_change(
                old_data=old_data,
                new_data=new_data,
                monitoring_instruction=monitoring_instruction,
                source_id=source_id,
                project_id=project_id,
                user_id=None,  # No user for automated change detection
                organization_id=organization_id,
                endpoint="/celery/scraping/stage4",
                ip_address=None,  # Not applicable for background tasks
            )
        return result

    @staticmethod
    def _trigger_notifications(revision: DataRevision) -> None:
        """Trigger revision notifications.

        Args:
            revision (DataRevision): Revision that changed.
        """
        try:
            send_revision_notifications_task.delay(str(revision.id))
            logger.info(f"Queued notifications for revision {revision.id}")
        except Exception as e:
            logger.warning(f"Failed to queue notification task for revision {revision.id}: {e}")

    def _create_auto_ticket(
        self,
        db: Session,
        revision: DataRevision,
        source: Source,
        change_result: Any,
    ) -> None:
        """Create auto-ticket for change (Sync version).

        Replicates logic from TicketService.create_auto_ticket but for synchronous execution.

        Args:
            db (Session): Database session.
            revision (DataRevision): Current revision.
            source (Source): Source that changed.
            change_result: Change detection results.
        """
        try:
            from app.api.modules.v1.tickets.models.ticket_model import (
                Ticket,
                TicketPriority,
                TicketStatus,
            )
            from app.api.modules.v1.users.models.users_model import User

            query = select(User).where(User.is_active).limit(1)
            any_active_user = db.exec(query).first()
            created_by_user_id = any_active_user.id if any_active_user else None

            jurisdiction = source.jurisdiction
            project = jurisdiction.project if jurisdiction else None
            jurisdiction_name = jurisdiction.name if jurisdiction else "General"
            query_diff = (
                select(ChangeDiff).where(ChangeDiff.new_revision_id == revision.id).limit(1)
            )
            change_diff = db.exec(query_diff).first()
            content = {
                "revision_summary": revision.ai_summary,
                "source_name": source.name,
                "source_url": source.url,
                "jurisdiction": jurisdiction_name,
                "scraped_at": revision.scraped_at.isoformat() if revision.scraped_at else None,
                "content_hash": revision.content_hash,
                "diff_patch": {
                    "risk_level": change_result.risk_level,
                    "change_summary": change_result.change_summary,
                    "field_changes": [
                        {
                            "field_name": fc.field_name,
                            "old_value": fc.old_value,
                            "new_value": fc.new_value,
                            "change_type": fc.change_type,
                        }
                        for fc in change_result.field_changes
                    ],
                },
                "ai_confidence": revision.ai_confidence_score,
                "priority_inferred_from_ai": True,
            }

            if change_diff:
                content["change_diff_id"] = str(change_diff.diff_id)

            risk_map = {
                "CRITICAL": TicketPriority.CRITICAL,
                "HIGH": TicketPriority.HIGH,
                "MEDIUM": TicketPriority.MEDIUM,
                "LOW": TicketPriority.LOW,
            }
            risk_upper = change_result.risk_level.upper() if change_result.risk_level else "LOW"
            priority = risk_map.get(risk_upper, TicketPriority.LOW)

            ticket_number_result = db.execute(text("SELECT nextval('tickets_ticket_number_seq')"))
            next_ticket_number = ticket_number_result.scalar()

            ticket = Ticket(
                ticket_number=next_ticket_number,
                title=f"[{jurisdiction_name}] {source.name} - Change Detected",
                description=revision.ai_summary or "No summary available",
                content=content,
                status=TicketStatus.OPEN.value,
                priority=priority.value,
                is_manual=False,
                data_revision_id=revision.id,
                change_diff_id=change_diff.diff_id if change_diff else None,
                created_by_user_id=created_by_user_id,
                assigned_to_user_id=None,
                organization_id=project.org_id if project else None,
                project_id=project.id if project else None,
                source_id=source.id,
            )

            db.add(ticket)
            db.commit()
            db.refresh(ticket)

            db.execute(
                update(DataRevision)
                .where(DataRevision.id == revision.id)
                .values(ticket_created=True)
            )
            db.commit()

            logger.info(
                f"Created auto-ticket for revision {revision.id}, updated ticket_created=True"
            )

        except Exception as e:
            logger.warning(f"Failed to create auto-ticket for revision {revision.id}: {e}")
