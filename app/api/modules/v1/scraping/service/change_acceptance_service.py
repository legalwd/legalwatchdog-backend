"""
Change Acceptance Service

Handles accepting/dismissing jurisdiction changes following SoC principles.
All business logic is contained in this service layer.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import (
    ChangeAlreadyAcceptedError,
    JurisdictionChangeNotFoundError,
    PermissionDeniedError,
    ProcessingError,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.async_jurisdiction_state_service import (
    AsyncJurisdictionStateService,
)
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
)
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class ChangeAcceptanceService:
    """Service for managing jurisdiction change acceptance workflow."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session.

        Args:
            db: Async database session
        """
        self.db = db

    async def accept_change(
        self,
        change_id: UUID,
        user_id: UUID,
        commit: bool = True,
    ) -> JurisdictionChange:
        """Accept a jurisdiction change.

        Marks a specific change as accepted/dismissed and records
        who accepted it and when. Also updates the JurisdictionState (Ledger).

        Args:
            change_id: ID of the jurisdiction change
            user_id: ID of the user accepting the change
            commit: Whether to commit the transaction (default: True)

        Returns:
            Updated JurisdictionChange instance

        Raises:
            JurisdictionChangeNotFoundError: If change doesn't exist
            ChangeAlreadyAcceptedError: If change was already accepted
            PermissionDeniedError: If user lacks permission
            ProcessingError: For unexpected processing errors
        """
        try:
            result = await self.db.execute(
                select(JurisdictionChange).where(JurisdictionChange.id == change_id)
            )
            change = result.scalar_one_or_none()

            if not change:
                raise JurisdictionChangeNotFoundError()

            if change.change_accepted:
                raise ChangeAlreadyAcceptedError()

            job_result = await self.db.execute(
                select(JurisdictionScrapeJob).where(
                    JurisdictionScrapeJob.id == change.jurisdiction_scrape_job_id
                )
            )
            job = job_result.scalar_one_or_none()

            if not job:
                raise ProcessingError(message="Associated scrape job not found")

            jurisdiction_result = await self.db.execute(
                select(Jurisdiction).where(Jurisdiction.id == job.jurisdiction_id)
            )
            jurisdiction = jurisdiction_result.scalar_one_or_none()

            if not jurisdiction:
                raise ProcessingError(message="Associated jurisdiction not found")

            project_result = await self.db.execute(
                select(Project).where(Project.id == jurisdiction.project_id)
            )
            project = project_result.scalar_one_or_none()

            if not project:
                raise ProcessingError(message="Associated project not found")

            organization_id = project.org_id

            has_permission = await check_user_permission(
                self.db, user_id, organization_id, "create_tickets"
            )

            if not has_permission:
                raise PermissionDeniedError(
                    message="You don't have permission to accept changes. "
                    "Only administrators, managers, and owners can accept changes."
                )

            change.change_accepted = True
            change.accepted_at = datetime.now(timezone.utc)
            change.accepted_by_user_id = user_id
            self.db.add(change)

            if change.new_value:
                state_service = AsyncJurisdictionStateService(self.db)
                state_map = await state_service.get_jurisdiction_state(jurisdiction.id)
                existing = state_map.get(change.field_name)
                change_reason = f"Accepted Change: {change.change_description or 'User Accepted'}"
                await state_service.update_or_create_field(
                    jurisdiction_id=jurisdiction.id,
                    field_key=change.field_name,
                    new_value=change.new_value,
                    change_reason=change_reason,
                    user_id=user_id,
                    job_id=job.id,
                    existing_state=existing,
                )

            if commit:
                await self.db.commit()
                await self.db.refresh(change)

            return change

        except (
            JurisdictionChangeNotFoundError,
            ChangeAlreadyAcceptedError,
            PermissionDeniedError,
            ProcessingError,
        ):
            await self.db.rollback()
            raise
        except Exception as e:
            logger.error(
                f"Error accepting jurisdiction change {change_id}: {str(e)}", exc_info=True
            )
            await self.db.rollback()
            raise ProcessingError(message="Failed to accept jurisdiction change. Please try again.")

    async def bulk_accept_changes(
        self,
        change_ids: List[UUID],
        user_id: UUID,
    ) -> Dict[str, Any]:
        """Accept multiple jurisdiction changes at once (Optimized).

        Args:
            change_ids: List of change IDs to accept.
            user_id: ID of the user accepting the changes.

        Returns:
            Dict with accepted_count, failed_changes, and accepted_changes.

        Raises:
            ProcessingError: For unexpected processing errors.
        """
        accepted_changes = []
        failed_changes = []

        try:
            stmt = select(JurisdictionChange).where(JurisdictionChange.id.in_(change_ids))
            result = await self.db.execute(stmt)
            changes = result.scalars().all()

            changes_map = {c.id: c for c in changes}

            for cid in change_ids:
                if cid not in changes_map:
                    failed_changes.append({"change_id": str(cid), "error": "Change not found"})

            if not changes:
                return {
                    "accepted_count": 0,
                    "failed_changes": failed_changes,
                    "accepted_changes": [],
                }

            # 2. Resolve Relationships (Job -> Jurisdiction -> Project) to check permissions
            job_ids = {c.jurisdiction_scrape_job_id for c in changes}

            jobs_stmt = select(JurisdictionScrapeJob).where(JurisdictionScrapeJob.id.in_(job_ids))
            jobs_result = await self.db.execute(jobs_stmt)
            jobs_map = {j.id: j for j in jobs_result.scalars().all()}

            jur_ids = {j.jurisdiction_id for j in jobs_map.values()}
            jur_stmt = select(Jurisdiction).where(Jurisdiction.id.in_(jur_ids))
            jur_result = await self.db.execute(jur_stmt)
            jur_map = {j.id: j for j in jur_result.scalars().all()}

            project_ids = {j.project_id for j in jur_map.values()}
            proj_stmt = select(Project).where(Project.id.in_(project_ids))
            proj_result = await self.db.execute(proj_stmt)
            projects = proj_result.scalars().all()

            # 3. Check Permissions (Grouped by Org)
            # Map Project -> Org
            project_org_map = {p.id: p.org_id for p in projects}

            # Org -> HasPermission
            checked_orgs = {}

            valid_changes_to_process = []

            for change in changes:
                try:
                    if change.change_accepted:
                        failed_changes.append(
                            {"change_id": str(change.id), "error": "Change already accepted"}
                        )
                        continue

                    job = jobs_map.get(change.jurisdiction_scrape_job_id)
                    if not job:
                        failed_changes.append(
                            {"change_id": str(change.id), "error": "Job not found"}
                        )
                        continue

                    jur = jur_map.get(job.jurisdiction_id)
                    if not jur:
                        failed_changes.append(
                            {"change_id": str(change.id), "error": "Jurisdiction not found"}
                        )
                        continue

                    # Get Org ID
                    project_id = jur.project_id
                    org_id = project_org_map.get(project_id)

                    if not org_id:
                        failed_changes.append(
                            {"change_id": str(change.id), "error": "Project/Org not found"}
                        )
                        continue

                    # Check/Cache Permission
                    if org_id not in checked_orgs:
                        checked_orgs[org_id] = await check_user_permission(
                            self.db, user_id, org_id, "create_tickets"
                        )

                    if not checked_orgs[org_id]:
                        failed_changes.append(
                            {"change_id": str(change.id), "error": "Permission denied"}
                        )
                        continue

                    # Valid
                    valid_changes_to_process.append((change, job, jur))

                except Exception as e:
                    logger.error(f"Error checking change {change.id}: {e}")
                    failed_changes.append({"change_id": str(change.id), "error": str(e)})

            # 4. Batch Fetch Existing Jurisdiction States via service
            state_service = AsyncJurisdictionStateService(self.db)

            relevant_jur_ids = {jur.id for _, _, jur in valid_changes_to_process}
            jur_state_maps: Dict[UUID, dict] = {}
            for jur_id in relevant_jur_ids:
                jur_state_maps[jur_id] = await state_service.get_jurisdiction_state(jur_id)

            current_time = datetime.now(timezone.utc)

            # 5. Apply Updates
            for change, job, jur in valid_changes_to_process:
                change.change_accepted = True
                change.accepted_at = current_time
                change.accepted_by_user_id = user_id

                accepted_changes.append(change)

                if change.new_value:
                    desc = change.change_description or "User Accepted"
                    change_reason = f"Accepted Change: {desc}"
                    field_states = jur_state_maps.get(jur.id, {})
                    existing = field_states.get(change.field_name)

                    new_state = await state_service.update_or_create_field(
                        jurisdiction_id=jur.id,
                        field_key=change.field_name,
                        new_value=change.new_value,
                        change_reason=change_reason,
                        user_id=user_id,
                        job_id=job.id,
                        existing_state=existing,
                    )
                    field_states[change.field_name] = new_state

            await self.db.commit()

            for c in accepted_changes:
                await self.db.refresh(c)

            return {
                "accepted_count": len(accepted_changes),
                "failed_changes": failed_changes,
                "accepted_changes": accepted_changes,
            }

        except Exception as e:
            logger.error(
                f"Error in bulk_accept_changes for user {user_id}: {str(e)}", exc_info=True
            )
            await self.db.rollback()
            raise ProcessingError(
                message="Failed to process bulk accept changes. Please try again."
            )
