"""
Project Services
Business logic for project operations with proper database integration
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, func, select
from starlette import status as http_status

from app.api.core.custom_exceptions.exceptions import ProcessingError, ResourceNotFoundError
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import JurisdictionService
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectUpdate,
)
from app.api.modules.v1.projects.utils.project_utils import (
    calculate_pagination,
    check_project_user_exists,
    get_project_by_id,
    get_project_by_id_including_deleted,
    get_user_by_id,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class ProjectService:
    """
    Service class for project-related business logic operations.

    This class encapsulates all project operations including creation,
    retrieval, updates, deletion, and user management.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the ProjectService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def create_project(
        self,
        data: ProjectBase,
        organization_id: UUID,
        user_id: UUID,
    ) -> Project:
        """
        Create a new project and add creator as member.

        Args:
            db: Database session
            data: Project creation data
            organization_id: Organization UUID
            user_id: User UUID of user

        Returns:
            Created Project object
        """

        has_permission = await check_user_permission(
            self.db, user_id, organization_id, "create_projects"
        )

        if not has_permission:
            logger.warning(
                f"User lacks permission to create project: "
                f"user_id={user_id}, org_id={organization_id}"
            )
            raise ValueError(
                "You don't have permission to create projects. "
                "Please contact your organization administrator."
            )

        logger.info(
            f"Creating '{data.title}' for organization_id={organization_id}, user_id={user_id}"
        )

        project = Project(
            title=data.title,
            description=data.description,
            org_id=organization_id,
        )

        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)

        project_user = ProjectUser(
            project_id=project.id,
            user_id=user_id,
        )

        self.db.add(project_user)

        logger.info(f"Created project with id={project.id}")

        return project

    async def list_projects(
        self,
        organization_id: UUID,
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        List projects with filtering and pagination.

        Args:
            db: Database session
            organization_id: Organization UUID
            q: Search query for title
            owner: Filter by owner user ID
            page: Page number
            limit: Items per page

        Returns:
            Dictionary with projects list and pagination metadata
        """
        logger.info(
            f"Projects for organization_id={organization_id}, q={q}, page={page}, limit={limit}"
        )

        statement = select(Project).where(
            and_(Project.org_id == organization_id, Project.is_deleted.is_(False))
        )
        logger.info(f"Base SQL: {str(statement)}")
        if q:
            statement = statement.where(Project.title.ilike(f"%{q}%"))
            logger.info(f"Applied search filter: q={q}")

        count_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.db.execute(count_statement)
        total = total_result.scalar_one()

        logger.info(f"Found {total} projects matching criteria")

        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit).order_by(Project.created_at.desc())
        result = await self.db.execute(statement)
        projects = result.scalars().all()

        pagination = calculate_pagination(total, page, limit)

        return {"data": projects, **pagination}

    async def get_project_by_id(self, project_id: UUID, organization_id: UUID) -> Optional[Project]:
        """
        Get project by ID with access verification.

        Args:
            db: Database session
            project_id: Project UUID
            organization_id: Organization UUID

        Returns:
            Project object if found and accessible, None otherwise
        """
        logger.info(f"Fetching project_id={project_id} for organization_id={organization_id}")

        project = await get_project_by_id(self.db, project_id, organization_id)

        if project:
            logger.info(f"Project found: {project.title}")
        else:
            logger.warning(f"Project not found or no access: project_id={project_id}")

        return project

    async def update_project(
        self,
        project_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        data: ProjectUpdate,
    ) -> tuple[Optional[Project], str]:
        """
        Update project with provided data,  including soft delete/restore

        Args:
            db: Database session
            project_id: Project UUID
            organization_id: Organization UUID
            data: Update data
        """

        logger.info(f"Updating project_id={project_id}")

        has_permission = await check_user_permission(
            self.db, user_id, organization_id, "edit_projects"
        )

        if not has_permission:
            logger.warning(
                f"User lacks permission to edit project: user_id={user_id}, "
                f"project_id={project_id}, org_id={organization_id}"
            )
            raise ValueError(
                "You don't have permission to edit projects. "
                "Please contact your organization administrator."
            )

        project = await get_project_by_id_including_deleted(self.db, project_id, organization_id)

        if not project:
            logger.warning(f"Project not found for update: project_id={project_id}")
            return None, "Project not found"

        update_data = data.model_dump(exclude_unset=True)
        success_message = "Project updated successfully"
        changes_made = False

        if "is_deleted" in update_data:
            requested_state = update_data["is_deleted"]
            current_state = project.is_deleted

            if requested_state != current_state:
                project.is_deleted = requested_state
                project.deleted_at = datetime.now(timezone.utc) if requested_state else None
                success_message = (
                    "Project archived successfully"
                    if requested_state
                    else "Project restored successfully"
                )
                changes_made = True
            else:
                success_message = f"Project is already {'archived' if current_state else 'active'}"

            del update_data["is_deleted"]

        for field, value in update_data.items():
            setattr(project, field, value)
            changes_made = True
            logger.info(f"Updated field '{field}' for project_id={project_id}")

        if changes_made:
            project.updated_at = datetime.now(timezone.utc)
            self.db.add(project)
            await self.db.commit()
            await self.db.refresh(project)

        logger.info(f"Project updated successfully: project_id={project_id}")

        return project, success_message

    async def delete_project(self, project_id: UUID, user_id: UUID, organization_id: UUID) -> bool:
        """
        Permanently delete project from database (irreversible).

        Args:
            db: Database session
            project_id: Project UUID
            organization_id: Organization UUID

        Returns:
            True if deleted, False if not found
        """
        logger.warning(f"hard deleting project_id={project_id}")

        has_permission = await check_user_permission(
            self.db, user_id, organization_id, "delete_projects"
        )

        if not has_permission:
            logger.warning(
                f"User lacks permission to delete project: user_id={user_id}, "
                f"project_id={project_id}, org_id={organization_id}"
            )
            raise ValueError(
                "You don't have permission to delete projects. "
                "Please contact your organization administrator."
            )

        project = await get_project_by_id_including_deleted(self.db, project_id, organization_id)

        if not project:
            logger.warning(f"Project not found for hard delete: project_id={project_id}")
            return False

        await self.db.delete(project)
        await self.db.commit()

        logger.warning(f"Project deleted permanently: project_id={project_id}")

        return True

    async def get_project_users(
        self,
        project_id: UUID,
        organization_id: UUID,
        page: int = 1,
        limit: int = 20,
    ) -> Optional[dict]:
        """
        Get paginated list of users in project with details.

        Args:
        project_id: Project UUID
        organization_id: Organization UUID
        page: Page number (default: 1)
        limit: Items per page (default: 20)

        urns:
        Dictionary with users list and pagination metadata, None if project not found
        """
        logger.info(f"Fetching users for project_id={project_id}, page={page}, limit={limit}")

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return None

        statement = (
            select(
                ProjectUser.user_id,
                User.email,
                User.name,
                User.avatar_url,
                ProjectUser.created_at.label("added_at"),
            )
            .join(User, ProjectUser.user_id == User.id)
            .where(ProjectUser.project_id == project_id)
            .order_by(ProjectUser.created_at.desc())
        )

        count_statement = select(func.count()).select_from(statement.subquery())
        total_result = await self.db.execute(count_statement)
        total = total_result.scalar_one()

        offset = (page - 1) * limit
        statement = statement.offset(offset).limit(limit)

        result = await self.db.execute(statement)
        user_rows = result.all()

        users = []
        for row in user_rows:
            users.append(
                {
                    "user_id": row.user_id,
                    "email": row.email,
                    "name": row.name,
                    "avatar_url": row.avatar_url,
                    "added_at": row.added_at.isoformat() if row.added_at else None,
                }
            )

        logger.info(f"Found {total} users in project_id={project_id}")

        pagination = calculate_pagination(total, page, limit)

        return {"users": users, **pagination}

    async def add_user(
        self,
        project_id: UUID,
        user_id: UUID,
        organization_id: UUID,
        current_user_id: UUID,
    ) -> tuple[bool, str]:
        """
        Add user to project.

        Args:
            db: Database session
            project_id: Project UUID
            user_id: User UUID to add
            organization_id: Organization UUID

        Returns:
            Tuple of (success: bool, message: str)
        """
        logger.info(f"Adding user_id={user_id} to project_id={project_id}")

        has_permission = await check_user_permission(
            self.db, current_user_id, organization_id, "edit_projects"
        )

        if not has_permission:
            logger.warning(
                f"User lacks permission to add project member: user_id={current_user_id}, "
                f"project_id={project_id}, org_id={organization_id}"
            )
            raise ValueError(
                "You don't have permission to add members to projects. "
                "Please contact your organization administrator."
            )

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return False, "Project not found or you don't have access to it"

        user = await get_user_by_id(self.db, user_id, organization_id)
        if not user:
            logger.warning(f"User not found in organization: user_id={user_id}")
            return False, "User not found in your organization"

        if await check_project_user_exists(self.db, project_id, user_id):
            logger.warning(f"User already in project: user_id={user_id}, project_id={project_id}")
            return False, "User already added to project"

        project_user = ProjectUser(project_id=project_id, user_id=user_id)
        self.db.add(project_user)
        await self.db.commit()

        logger.info(
            f"User added to project successfully: user_id={user_id}, project_id={project_id}"
        )

        return True, "User successfully added to project"

    async def remove_user(
        self, project_id: UUID, user_id: UUID, organization_id: UUID, current_user_id: UUID
    ) -> tuple[bool, str]:
        """
        Remove user from project.

        Args:
            db: Database session
            project_id: Project UUID
            user_id: User UUID to remove
            organization_id: Organization UUID

        Returns:
            Tuple of (success: bool, message: str)
        """
        logger.info(f"Removing user_id={user_id} from project_id={project_id}")

        has_permission = await check_user_permission(
            self.db, current_user_id, organization_id, "edit_projects"
        )

        if not has_permission:
            logger.warning(
                f"User lacks permission to remove project member: user_id={current_user_id}, "
                f"project_id={project_id}, org_id={organization_id}"
            )
            raise ValueError(
                "You don't have permission to remove members from projects. "
                "Please contact your organization administrator."
            )

        project = await get_project_by_id(self.db, project_id, organization_id)
        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            return False, "Project not found or you don't have access to it"

        statement = select(ProjectUser).where(
            and_(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id)
        )
        result = await self.db.execute(statement)
        project_user = result.scalar_one_or_none()

        if not project_user:
            logger.warning(f"User not in project: user_id={user_id}, project_id={project_id}")
            return False, "User is not a member of this project"

        await self.db.delete(project_user)
        await self.db.commit()

        logger.info(f"Removed user_id={user_id} from project project_id={project_id}")

        return True, "User successfully removed from project"

    async def get_project_stats(self, project_id: UUID, organization_id: UUID) -> Dict:
        """
        Get aggregated change statistics for a project (from all jurisdictions).

        Returns:
            {
                "change_count": int,
                "severity": "Major" | "Minor" | None,
                "last_change_at": datetime | None,
                "change_summary": str | None,
                "jurisdictions": [
                    {
                        "id": UUID,
                        "name": str,
                        "change_count": int,
                        "severity": "Major" | "Minor" | None,
                        "last_change_at": datetime | None
                    }
                ],
                "change_items": [
                    {
                        "field": str,
                        "old_value": str,
                        "new_value": str,
                        "change_type": str,
                        "jurisdiction_name": str
                    }
                ]
            }
        """
        project_stmt = select(Project).where(
            Project.id == project_id,
            Project.org_id == organization_id,
            Project.is_deleted.is_(False),
        )
        project_result = await self.db.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {
                "change_count": 0,
                "severity": None,
                "last_change_at": None,
                "change_summary": None,
                "jurisdictions": [],
                "change_items": [],
            }

        jurisdiction_stmt = select(Jurisdiction).where(
            Jurisdiction.project_id == project_id,
            Jurisdiction.is_deleted.is_(False),
        )
        jurisdiction_result = await self.db.execute(jurisdiction_stmt)
        jurisdictions = jurisdiction_result.scalars().all()

        total_changes = 0
        max_severity = None
        last_change_at = None
        change_summary = None
        jurisdiction_stats = []
        all_change_items = []

        jurisdiction_stats_service = JurisdictionService()

        for jurisdiction in jurisdictions:
            jurisdiction_data = await jurisdiction_stats_service.get_jurisdiction_stats(
                self.db, jurisdiction.id, organization_id
            )

            jurisdiction_changes = jurisdiction_data["change_count"]
            jurisdiction_severity = jurisdiction_data["severity"]
            jurisdiction_last_change = jurisdiction_data["last_change_at"]

            if jurisdiction_changes > 0:
                total_changes += jurisdiction_changes

                if jurisdiction_severity == "Major":
                    max_severity = "Major"
                elif jurisdiction_severity == "Minor" and max_severity != "Major":
                    max_severity = "Minor"

                if jurisdiction_last_change:
                    try:
                        if isinstance(jurisdiction_last_change, str):
                            jurisdiction_dt = datetime.fromisoformat(
                                jurisdiction_last_change.replace("Z", "+00:00")
                            )
                        else:
                            jurisdiction_dt = jurisdiction_last_change

                        if not last_change_at or jurisdiction_dt > last_change_at:
                            last_change_at = jurisdiction_dt
                            change_summary = jurisdiction_data["change_summary"]
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Error parsing jurisdiction_last_change: {e}")
                        continue

                for revision in jurisdiction_data.get("revisions", []):
                    for field_change in revision.get("field_changes", []):
                        all_change_items.append(
                            {
                                "field": field_change.get("field_name", ""),
                                "old_value": str(field_change.get("old_value", "")),
                                "new_value": str(field_change.get("new_value", "")),
                                "change_type": field_change.get("change_type", "changed"),
                                "jurisdiction_name": jurisdiction.name,
                            }
                        )

            jurisdiction_stats.append(
                {
                    "id": str(jurisdiction.id),
                    "name": jurisdiction.name,
                    "change_count": jurisdiction_changes,
                    "severity": jurisdiction_severity,
                    "last_change_at": jurisdiction_last_change,
                }
            )

        change_items = all_change_items[:5]

        return {
            "change_count": total_changes,
            "severity": max_severity,
            "last_change_at": last_change_at.isoformat() if last_change_at else None,
            "change_summary": change_summary,
            "jurisdictions": jurisdiction_stats,
            "change_items": change_items,
        }

    async def publish_all_project_blogs(
        db: AsyncSession,
        organization_id: UUID,
        project_id: UUID,
        is_published: bool,
        jurisdiction_ids: Optional[List[UUID]] = None,
    ) -> dict:
        """Publish/unpublish jurisdiction blog posts for all (or selected) jurisdictions in project.

        Reuses ``publish_blog_post`` per jurisdiction. Jurisdictions without a blog post are skipped
        IDs in ``jurisdiction_ids`` that are not in the project are listed in
        ``not_in_project_jurisdiction_ids`` and are not treated as errors.

        Returns dict with status_code, message, data,
        (succeeded, skipped, failed, not_in_project_jurisdiction_ids).
        Raises ResourceNotFoundError if the project is not found in the organization.
        """
        proj_stmt = select(Project).where(
            Project.id == project_id,
            Project.org_id == organization_id,
        )
        proj_res = await db.execute(proj_stmt)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise ResourceNotFoundError("Project not found in this organization")

        stmt = select(Jurisdiction.id).where(
            Jurisdiction.project_id == project_id,
            cast(Any, Jurisdiction.is_deleted).is_(False),
        )
        res_ids = await db.execute(stmt)
        all_ids = set(res_ids.scalars().all())

        if jurisdiction_ids is not None:
            requested = set(jurisdiction_ids)
            target_ids = list(requested & all_ids)
            not_in_project = [str(x) for x in (requested - all_ids)]
        else:
            target_ids = list(all_ids)
            not_in_project = []

        succeeded: List[dict] = []
        skipped: List[dict] = []
        failed: List[dict] = []

        for jur_id in target_ids:
            try:
                one = await BlogGenerationService.publish_blog_post(
                    db, organization_id, jur_id, is_published
                )
                succeeded.append(one["data"])
            except ResourceNotFoundError as e:
                skipped.append({"jurisdiction_id": str(jur_id), "reason": e.message})
            except ProcessingError as e:
                failed.append({"jurisdiction_id": str(jur_id), "reason": e.message})

        verb = "published" if is_published else "unpublished"
        message = (
            f"Batch {verb}:{len(succeeded)} succeeded, {len(skipped)} skipped, {len(failed)} failed"
        )

        return {
            "status_code": http_status.HTTP_200_OK,
            "message": message,
            "data": {
                "project_id": str(project_id),
                "is_published": is_published,
                "not_in_project_jurisdiction_ids": not_in_project,
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
            },
        }
