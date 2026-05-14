"""
Jurisdiction Service Module.

This module provides the JurisdictionService class, which handles the business logic for
managing Jurisdiction entities. It includes methods for creating, retrieving, updating,
and deleting (soft and hard) jurisdictions. It also includes the OrgResourceGuard class
for enforcing organization-level access control on resources.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, inspect, literal, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload, with_loader_criteria
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
)
from app.api.core.dependencies.auth import get_current_user
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.source_model import Source

logger = logging.getLogger("app")


async def filter_archived_recursive(jurisdiction: Jurisdiction, db: AsyncSession):
    stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id)
    result = await db.execute(stmt)
    active_children = [c for c in result.scalars().all() if not c.is_deleted]

    jurisdiction.__dict__["children"] = active_children

    for child in active_children:
        await filter_archived_recursive(child, db)

    return jurisdiction


async def _soft_delete_jurisdiction(root_id: UUID, db: AsyncSession):
    j = Jurisdiction.__table__  # type: ignore[attr-defined]
    cte = select(j.c.id).where(j.c.id == root_id).cte(name="descendants", recursive=True)

    j_alias = aliased(j)
    cte = cte.union_all(select(j_alias.c.id).where(j_alias.c.parent_id == cte.c.id))

    descendant_ids = (await db.execute(select(cte.c.id))).scalars().all()
    if not descendant_ids:
        return

    stmt = (
        update(Jurisdiction)
        .where(Jurisdiction.id.in_(descendant_ids))  # type: ignore
        .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
    )

    try:
        if getattr(db, "in_transaction", None) and db.in_transaction():
            async with db.begin_nested():
                await db.execute(stmt)
        else:
            async with db.begin():
                await db.execute(stmt)
    except Exception:
        raise


async def _restore_jurisdiction_recursive(jurisdiction: "Jurisdiction", db: AsyncSession):
    """
    Recursively restore a jurisdiction and its children.
    """
    jurisdiction.is_deleted = False
    jurisdiction.deleted_at = None
    db.add(jurisdiction)

    children = getattr(jurisdiction, "children", None)

    if children is None:
        stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id)
        result = await db.execute(stmt)
        children = result.scalars().all()

    for child in children:
        await _restore_jurisdiction_recursive(child, db)


async def get_descendant_ids(root_id: UUID, db: AsyncSession) -> list[UUID]:
    """Return all descendant IDs (including root) using a recursive CTE."""
    table = inspect(Jurisdiction).local_table

    cte = select(table.c.id).where(table.c.id == root_id).cte(name="descendants", recursive=True)

    t_alias = table.alias("t_alias")
    cte = cte.union_all(select(t_alias.c.id).where(t_alias.c.parent_id == cte.c.id))

    result = await db.execute(select(cte.c.id))
    return [UUID(str(i)) for i in result.scalars().all()]


class JurisdictionService:
    def _serialize_jurisdiction(self, jurisdiction: Jurisdiction) -> dict:
        """Convert a Jurisdiction ORM object into a plain dict including nested children.

        This ensures the returned structure is JSON-serializable and contains the
        nested `children` produced by `filter_archived_recursive`.
        """
        data = {
            "id": getattr(jurisdiction, "id", None),
            "project_id": getattr(jurisdiction, "project_id", None),
            "parent_id": getattr(jurisdiction, "parent_id", None),
            "name": getattr(jurisdiction, "name", None),
            "description": getattr(jurisdiction, "description", None),
            "prompt": getattr(jurisdiction, "prompt", None),
            "scrape_output": getattr(jurisdiction, "scrape_output", None),
            "created_at": getattr(jurisdiction, "created_at", None),
            "updated_at": getattr(jurisdiction, "updated_at", None),
            "deleted_at": getattr(jurisdiction, "deleted_at", None),
            "is_deleted": getattr(jurisdiction, "is_deleted", False),
        }

        children = getattr(jurisdiction, "children", None)
        if children is None:
            children = jurisdiction.__dict__.get("children", [])

        data["children"] = [self._serialize_jurisdiction(c) for c in children] if children else []

        return data

    async def get_jurisdiction_by_id(
        self, db: AsyncSession, jurisdiction_id: UUID, organization_id: UUID
    ):
        """
        Retrieve a single Jurisdiction by its unique identifier.

        This method queries the database for a Jurisdiction with the given `jurisdiction_id`.
        If no matching record is found, it raises a NotFoundError.
        Any database errors during the query will raise a ProcessingError.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            jurisdiction_id (UUID): The unique identifier of the Jurisdiction to retrieve.
            organization_id (UUID): The organization ID to verify ownership.

        Returns:
            Jurisdiction: The matching Jurisdiction instance from the database.

        Raises:
            NotFoundError: If the Jurisdiction does not exist or is archived.
            ProcessingError: If a database error occurs.
        """
        try:
            query = (
                select(Jurisdiction)
                .join(Project)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: cls.is_deleted == cls.is_deleted,
                        include_aliases=True,
                    )
                )
                .where(
                    Jurisdiction.id == jurisdiction_id,
                    Project.org_id == organization_id,
                )
            )

            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()
            if not jurisdiction:
                raise NotFoundError("The jurisdiction doesn't exist.")

            if getattr(jurisdiction, "is_deleted", False):
                try:
                    await db.refresh(jurisdiction)
                except Exception:
                    pass

            if getattr(jurisdiction, "is_deleted", False):
                raise NotFoundError(
                    "This jurisdiction has been archived and is no longer accessible."
                )

            await filter_archived_recursive(jurisdiction, db)

            return self._serialize_jurisdiction(jurisdiction)

        except SQLAlchemyError:
            raise ProcessingError(
                "An error occurred while retrieving the jurisdiction. Please try again."
            )

    async def get_jurisdiction_by_name(self, db: AsyncSession, name: str):
        """
        Retrieve a single Jurisdiction by its name.

        This method queries the database for a Jurisdiction with the specified `name`
        that has not been soft-deleted (`is_deleted=False`). If multiple jurisdictions
        match the name, only the first one is returned.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            name (str): The name of the Jurisdiction to retrieve.

        Returns:
            Optional[Jurisdiction]: The first matching Jurisdiction instance if found,
            otherwise None.

        Raises:
            SQLAlchemyError: If a database error occurs during the query.
        """
        stmt = select(Jurisdiction).where(
            cast(Any, Jurisdiction.name) == name,
            cast(Any, Jurisdiction.is_deleted).is_(False),
        )
        result = await db.execute(stmt)
        return result.first()

    async def create(self, db: AsyncSession, jurisdiction: Jurisdiction, organization_id: UUID):
        """Create a Jurisdiction. If first in project, set parent_id to itself."""
        try:
            project = await db.get(Project, jurisdiction.project_id)

            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project you're trying to add a jurisdiction to doesn't exist.",
                )

            if str(project.org_id) != str(organization_id):
                raise PermissionDeniedError(
                    "You don't have permission to create jurisdictions in this project. "
                    "Please contact your administrator."
                )

            db.add(jurisdiction)
            await db.commit()
            await db.refresh(jurisdiction)

            return jurisdiction
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A jurisdiction with this name already exists in the project.",
            )
        except Exception:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create jurisdiction. Please try again.",
            )

    async def get_jurisdictions_by_project(
        self, db: AsyncSession, project_id: UUID, organization_id: UUID
    ):
        """
        Retrieve all active jurisdictions associated with a specific project
        including nested children.

        This method queries the database for all Jurisdiction records where
        `project_id` matches the given value and `is_deleted` is False (i.e., not soft-deleted).
        If no jurisdictions are found, an empty list is returned.
        Any database errors during the query will raise a ProcessingError.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            project_id (UUID): The unique identifier of the project
            whose jurisdictions are being retrieved.
            organization_id (UUID): The organization ID to verify ownership.

        Returns:
            List[Jurisdiction]: A list of Jurisdiction instances associated with the project,
            or empty list if none exist.

        Raises:
            NotFoundError: If the project doesn't exist or user lacks permission.
            ProcessingError: If a database error occurs.
        """
        try:
            project = await db.get(Project, project_id)
            if not project:
                raise NotFoundError("The project you're looking for doesn't exist.")

            if str(project.org_id) != str(organization_id):
                raise PermissionDeniedError(
                    "You don't have permission to view jurisdictions in this project."
                )

            stmt = select(Jurisdiction).where(
                cast(Any, Jurisdiction.project_id) == project_id,
                cast(Any, Jurisdiction.is_deleted).is_(False),
                Jurisdiction.parent_id.is_(None),  # type: ignore
            )
            result = await db.execute(stmt)
            active_jurisdictions = result.scalars().all()

            for jurisdiction in active_jurisdictions:
                await filter_archived_recursive(jurisdiction, db)

            return [self._serialize_jurisdiction(j) for j in active_jurisdictions]

        except SQLAlchemyError:
            raise ProcessingError(
                "An error occurred while retrieving jurisdictions. Please try again."
            )

    async def get_all_jurisdictions(self, db: AsyncSession, organization_id: UUID):
        """
        Retrieve all active jurisdictions in the system.
        Flat Structure (non-nested)

        This method queries the database for all Jurisdiction records where `is_deleted` is False
        (i.e., not soft-deleted). If no jurisdictions are found, an empty list is returned.
        Any database errors during the query will raise a ProcessingError.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.
            organization_id (UUID): The organization ID to filter jurisdictions.

        Returns:
            List[Jurisdiction]: A list of all active Jurisdiction instances, or empty list
            if none exist.

        Raises:
            ProcessingError: If a database error occurs.
        """
        try:
            stmt = (
                select(Jurisdiction)
                .join(Project)
                .where(
                    Project.org_id == organization_id,
                    cast(Any, Jurisdiction.is_deleted).is_(False),
                    cast(Any, Jurisdiction.parent_id).is_(None),
                )
            )
            result = await db.execute(stmt)
            active_jurisdictions = result.scalars().all()

            for jurisdiction in active_jurisdictions:
                await filter_archived_recursive(jurisdiction, db)

            return [self._serialize_jurisdiction(j) for j in active_jurisdictions]

        except SQLAlchemyError:
            raise ProcessingError(
                "An error occurred while retrieving jurisdictions. Please try again."
            )

    async def update(self, db: AsyncSession, jurisdiction: Jurisdiction, organization_id: UUID):
        """
        Persist updates to an existing Jurisdiction in the database.

        This method commits any changes made to the given `jurisdiction` instance and refreshes it
        from the database to ensure the latest state is returned. It handles database errors and
        integrity constraints by rolling back the transaction and raising an HTTPException.

        Args:
            db (AsyncSession): The asynchronous database session used to commit changes.
            jurisdiction (Jurisdiction): The Jurisdiction instance with updated fields.

        Returns:
            Jurisdiction: The updated Jurisdiction instance reflecting persisted changes.

        Raises:
            HTTPException:
                - 400 if an integrity constraint is violated
                (e.g., unique or foreign key constraints).
                - 500 if a general database error occurs during commit or refresh.
        """
        try:
            project = await db.get(Project, jurisdiction.project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project for this jurisdiction doesn't exist.",
                )

            if str(project.org_id) != str(organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You don't have permission to update jurisdictions in this project. "
                        "Please contact your administrator."
                    ),
                )

            await db.commit()
            await db.refresh(jurisdiction)

            try:
                if getattr(jurisdiction, "is_deleted", False):
                    await _soft_delete_jurisdiction(jurisdiction.id, db)
                    await db.commit()
                    await db.refresh(jurisdiction)
                else:
                    try:
                        await self.restore_jurisdiction_and_children(
                            db, jurisdiction.id, organization_id
                        )
                    except Exception:
                        await _restore_jurisdiction_recursive(jurisdiction, db)
                        await db.commit()
                        await db.refresh(jurisdiction)
            except Exception:
                pass

            return jurisdiction
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A jurisdiction with this name already exists in the project.",
            )
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update jurisdiction. Please try again.",
            )

    async def read(self, db: AsyncSession, organization_id: UUID):
        """
        Retrieve all jurisdictions from the database, including soft-deleted ones.

        This method queries the database for all Jurisdiction records without filtering
        by `is_deleted`. It handles database errors by raising an HTTPException with
        a 500 status code if any issues occur during the query execution.

        Args:
            db (AsyncSession): The asynchronous database session used to execute queries.

        Returns:
            List[Jurisdiction]: A list of all Jurisdiction instances in the database.

        Raises:
            HTTPException:
                - 500 if a database error occurs while retrieving jurisdictions.
        """
        try:
            stmt = select(Jurisdiction).join(Project).where(Project.org_id == organization_id)
            result = await db.execute(stmt)
            return result.all()
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving jurisdictions. Please try again.",
            )

    async def soft_delete(
        self,
        organization_id: UUID,
        db: AsyncSession,
        jurisdiction_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> Union[Jurisdiction, list[Jurisdiction], None]:
        """
        Soft delete a Jurisdiction by marking it as deleted without removing it from the database.

        This method sets the `is_deleted` flag to True and updates the `deleted_at` timestamp
        to the current time for the jurisdiction identified by `jurisdiction_id`. The record
        remains in the database for historical reference or potential restoration.

        Args:
            db (AsyncSession): The asynchronous database session used to persist changes.
            jurisdiction_id (UUID): The unique identifier of the Jurisdiction to be soft-deleted.

        Returns:
            Optional[Jurisdiction]: The soft-deleted Jurisdiction instance if found,
            otherwise None if no matching jurisdiction exists.

        Raises:
            HTTPException:
                - 400 if the soft delete violates integrity constraints
                (e.g., foreign key dependencies).
                - 500 if a database error occurs during the update.
        """
        try:
            if jurisdiction_id:
                jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
                if not jurisdiction:
                    return None

                project = await db.get(Project, jurisdiction.project_id)
                if project is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="The project for this jurisdiction doesn't exist.",
                    )
                if str(project.org_id) != str(organization_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "You don't have permission to delete jurisdictions in this project. "
                            "Please contact your administrator."
                        ),
                    )
                jurisdiction.is_deleted = True
                jurisdiction.deleted_at = datetime.now(timezone.utc)
                await _soft_delete_jurisdiction(jurisdiction.id, db)
                await db.commit()
                await db.refresh(jurisdiction)

                return jurisdiction

            elif project_id:
                stmt = (
                    select(Jurisdiction)
                    .where(Jurisdiction.project_id == project_id, Jurisdiction.parent_id.is_(None))  # type: ignore
                    .options(selectinload(Jurisdiction.children))
                )

                result = await db.execute(stmt)
                await db.commit()
                updated_jurisdictions = list(result.scalars().all())
                if not updated_jurisdictions:
                    return []

                for jurisdiction in updated_jurisdictions:
                    await _soft_delete_jurisdiction(jurisdiction.id, db)

                return updated_jurisdictions

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please provide either a jurisdiction ID or project ID to delete.",
                )

        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This jurisdiction can't be deleted because other items depend on it. "
                    "Please remove those dependencies first."
                ),
            )
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete jurisdiction. Please try again.",
            )

    async def delete(
        self, db: AsyncSession, jurisdiction: Jurisdiction, organization_id: UUID
    ) -> bool:
        """
        Permanently delete a Jurisdiction record from the database.

        This method removes the given `jurisdiction` instance from the database and commits
        the transaction. Unlike `soft_delete`, this operation irreversibly deletes the record.

        Args:
            db (AsyncSession): The asynchronous database session used to execute the deletion.
            jurisdiction (Jurisdiction): The Jurisdiction instance to be permanently removed.

        Returns:
            bool: True if the deletion was successful.

        Raises:
            HTTPException:
                - 400 if the deletion violates integrity constraints (e.g., related records exist).
                - 500 if a database error occurs during the deletion.
        """
        try:
            project = await db.get(Project, jurisdiction.project_id)
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project for this jurisdiction doesn't exist.",
                )

            if str(project.org_id) != str(organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You don't have permission to delete jurisdictions in this project. "
                        "Please contact your administrator."
                    ),
                )

            await db.delete(jurisdiction)
            await db.commit()
            return True
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This jurisdiction can't be deleted because other items depend on it. "
                    "Please remove those dependencies first."
                ),
            )
        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete jurisdiction permanently. Please try again.",
            )

    async def get_jurisdiction_for_restoration(
        self,
        db: AsyncSession,
        organization_id: UUID,
        jurisdiction_id: UUID,
        restore_nested: bool = False,
    ) -> Jurisdiction:
        """
        Retrieve a single Jurisdiction by ID for restoration purposes.

        This method will return the Jurisdiction even if it is currently archived (is_deleted=True),
        so it can be restored. If the jurisdiction does not exist at all, it raises a 404.
        Any database errors raise a 500.

        Args:
            db (AsyncSession): Database session.
            jurisdiction_id (UUID): ID of the jurisdiction.

        Returns:
            Jurisdiction: The jurisdiction record (archived or active).

        Raises:
            HTTPException: 404 if not found, 500 on DB error.
        """
        try:
            query = (
                select(Jurisdiction)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: cls.is_deleted == cls.is_deleted,
                        include_aliases=True,
                    )
                )
                .where(Jurisdiction.id == jurisdiction_id)
            )
            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()

            if not jurisdiction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The jurisdiction you're trying to restore doesn't exist.",
                )

            project = await db.get(Project, jurisdiction.project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project for this jurisdiction doesn't exist.",
                )
            if str(project.org_id) != str(organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You don't have permission to restore jurisdictions in this project. "
                        "Please contact your administrator."
                    ),
                )

            if restore_nested:
                await _restore_jurisdiction_recursive(jurisdiction, db)
                await db.commit()
                await db.refresh(jurisdiction)

            return jurisdiction
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving the jurisdiction. Please try again.",
            )

    async def restore_jurisdiction_and_children(
        self, db: AsyncSession, jurisdiction_id: UUID, organization_id: UUID
    ):
        """
        Restore a jurisdiction and all its descendant jurisdictions using a
        bulk UPDATE. This avoids ORM lifecycle event DB I/O that can trigger
        "greenlet_spawn" errors when running under an async engine.

        Returns a serialized nested jurisdiction (dict) for predictable JSON output.
        """
        try:
            query = select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            result = await db.execute(query)
            jurisdiction = result.scalar_one_or_none()
            if not jurisdiction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The jurisdiction you're trying to restore doesn't exist.",
                )

            project = await db.get(Project, jurisdiction.project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project for this jurisdiction doesn't exist.",
                )
            if str(project.org_id) != str(organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You don't have permission to restore jurisdictions in this project. "
                        "Please contact your administrator."
                    ),
                )

            cte_sql = text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id, parent_id FROM jurisdictions WHERE id = :start_id
                    UNION ALL
                    SELECT j.id, j.parent_id FROM jurisdictions j
                    JOIN descendants d ON j.parent_id = d.id
                )
                SELECT id FROM descendants
                """
            )
            res = await db.execute(cte_sql, {"start_id": str(jurisdiction_id)})
            ids = [row[0] for row in res.fetchall()]

            try:
                ids = [UUID(str(i)) for i in ids]
            except Exception:
                pass

            if not ids:
                return None

            update_stmt = (
                update(Jurisdiction)
                .where(Jurisdiction.id.in_(ids))  # type: ignore
                .values(is_deleted=False, deleted_at=None)
            )
            await db.execute(update_stmt)
            await db.commit()

            result = await db.execute(
                select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            )
            root = result.scalar_one_or_none()
            if not root:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "The jurisdiction couldn't be found after restoration. Please try again."
                    ),
                )

            await filter_archived_recursive(root, db)
            return self._serialize_jurisdiction(root)

        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore jurisdiction. Please try again.",
            )

    async def restore_all_archived_jurisdictions(
        self, db: AsyncSession, organization_id: UUID, project_id: UUID | None = None
    ) -> list[Jurisdiction]:
        """
        Restore all archived jurisdictions and return the restored objects.
        Args:
            db (AsyncSession): Database session.
            project_id (UUID): ID of the Project,
            the jurisdictions are under
            .

        Returns:
            Jurisdictions: The jurisdiction records (archived or active).

        Raises:
            HTTPException: 404 if not found, 500 on DB error.
        """
        try:
            stmt = (
                select(Jurisdiction)
                .options(
                    with_loader_criteria(
                        Jurisdiction,
                        lambda cls: literal(True),
                        include_aliases=True,
                    )
                )
                .where(cast(Any, Jurisdiction.is_deleted).is_(True))
            )

            if project_id is not None:
                stmt = stmt.where(cast(Any, Jurisdiction.project_id) == project_id)

            result = await db.execute(stmt)
            archived_jurisdictions = list(result.scalars().all())

            filtered_jurisdictions = []
            for j in archived_jurisdictions:
                project = await db.get(Project, j.project_id)
                if project and str(project.org_id) == str(organization_id):
                    filtered_jurisdictions.append(j)

            if not filtered_jurisdictions:
                return []

            archived_jurisdictions = filtered_jurisdictions

            ids = [j.id for j in archived_jurisdictions]

            update_stmt = (
                update(Jurisdiction)
                .where(Jurisdiction.id.in_(ids))  # type: ignore
                .values(is_deleted=False, deleted_at=None)
            )

            await db.execute(update_stmt)
            await db.commit()

            for j in archived_jurisdictions:
                try:
                    j.is_deleted = False
                    j.deleted_at = None
                except Exception:
                    pass

            if not isinstance(db, AsyncSession):
                top_level = [
                    j for j in archived_jurisdictions if getattr(j, "parent_id", None) is None
                ]
                nested = []
                for t in top_level:
                    nested.append(self._serialize_jurisdiction(t))
                return nested

            if project_id is not None:
                top_stmt = select(Jurisdiction).where(
                    cast(Any, Jurisdiction.project_id) == project_id,
                    Jurisdiction.parent_id.is_(None),  # type: ignore
                    cast(Any, Jurisdiction.is_deleted).is_(False),
                )
            else:
                top_stmt = select(Jurisdiction).where(
                    Jurisdiction.parent_id.is_(None),  # type: ignore
                    Jurisdiction.id.in_(ids),  # type: ignore
                )

            top_res = await db.execute(top_stmt)
            top_level = top_res.scalars().all()

            nested = []
            for t in top_level:
                await filter_archived_recursive(t, db)
                nested.append(self._serialize_jurisdiction(t))

            return nested

        except SQLAlchemyError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore jurisdictions. Please try again.",
            )

    async def get_jurisdiction_stats(
        self, db: AsyncSession, jurisdiction_id: UUID, organization_id: UUID
    ) -> Dict:
        """
        Get change statistics for a single jurisdiction.

        Returns:
            {
                "change_count": int,
                "severity": "Major" | "Minor" | None,
                "last_change_at": datetime | None,
                "change_summary": str | None,
                "revisions": [
                    {
                        "id": UUID,
                        "title": str,
                        "summary": str,
                        "severity": "Major" | "Minor",
                        "created_at": datetime,
                        "field_changes": list
                    }
                ]
            }
        """
        try:
            job_stmt = (
                select(JurisdictionScrapeJob)
                .where(
                    JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                    JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
                    JurisdictionScrapeJob.extracted_data.isnot(None),
                )
                .order_by(JurisdictionScrapeJob.completed_at.desc())
            )
            job_result = await db.execute(job_stmt)
            jobs = job_result.scalars().all()

            revisions = []
            total_changes = 0
            max_severity = None
            last_change_at = None
            change_summary = None

            for job in jobs:
                extracted_data = job.extracted_data or {}
                change_detection = extracted_data.get("change_detection", {})

                if not change_detection.get("has_changed", False):
                    continue

                field_changes = change_detection.get("field_changes", [])
                risk_level = change_detection.get("risk_level", "LOW")

                change_count = len(field_changes)
                total_changes += change_count

                severity = "Major" if risk_level in ("HIGH", "CRITICAL") else "Minor"

                if severity == "Major":
                    max_severity = "Major"
                elif severity == "Minor" and max_severity != "Major":
                    max_severity = "Minor"

                if not last_change_at or job.completed_at > last_change_at:
                    last_change_at = job.completed_at
                    change_summary = change_detection.get("change_summary")

                if len(revisions) < 5:
                    revisions.append(
                        {
                            "id": str(job.id),
                            "title": f"Jurisdiction Scrape - {len(field_changes)} changes",
                            "summary": change_detection.get("change_summary", "Changes detected"),
                            "severity": severity,
                            "created_at": job.completed_at.isoformat()
                            if job.completed_at
                            else None,
                            "field_changes": field_changes[:5],
                        }
                    )

            return {
                "change_count": total_changes,
                "severity": max_severity,
                "last_change_at": last_change_at.isoformat() if last_change_at else None,
                "change_summary": change_summary,
                "revisions": revisions,
            }

        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve jurisdiction statistics. Please try again.",
            )

    async def get_scrape_history(
        self,
        db: AsyncSession,
        jurisdiction_id: UUID,
        organization_id: UUID,
        page: int = 1,
        page_size: int = 10,
        status_filter: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """
        Retrieve paginated scrape history for a jurisdiction.

        Args:
            db: Database session.
            jurisdiction_id: ID of the jurisdiction.
            organization_id: Organization ID to verify ownership.
            page: Page number (1-based).
            page_size: Number of items per page.
            status_filter: Optional filter by job status.

        Returns:
            Tuple of (list of job dictionaries, total count).

        Raises:
            NotFoundError: If jurisdiction doesn't exist.
            ProcessingError: If a database error occurs.
        """
        try:
            await self.get_jurisdiction_by_id(db, jurisdiction_id, organization_id)

            query = (
                select(
                    JurisdictionScrapeJob,
                    func.count(JurisdictionChange.id).label("changes_count"),
                )
                .outerjoin(
                    JurisdictionChange,
                    JurisdictionChange.jurisdiction_scrape_job_id == JurisdictionScrapeJob.id,
                )
                .where(JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id)
                .group_by(JurisdictionScrapeJob.id)
            )

            if status_filter:
                try:
                    status_enum = JurisdictionScrapeJobStatus(status_filter)
                    query = query.where(JurisdictionScrapeJob.status == status_enum)
                except ValueError:
                    pass

            count_query = (
                select(func.count())
                .select_from(JurisdictionScrapeJob)
                .where(JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id)
            )
            if status_filter:
                try:
                    status_enum = JurisdictionScrapeJobStatus(status_filter)
                    count_query = count_query.where(JurisdictionScrapeJob.status == status_enum)
                except ValueError:
                    pass

            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0

            offset = (page - 1) * page_size
            query = query.order_by(JurisdictionScrapeJob.created_at.desc())
            query = query.offset(offset).limit(page_size)

            result = await db.execute(query)
            rows = result.all()

            jobs = []
            for row in rows:
                job = row[0]
                changes_count = row[1]

                jobs.append(
                    {
                        "id": job.id,
                        "status": job.status.value
                        if hasattr(job.status, "value")
                        else str(job.status),
                        "total_sources": job.total_sources,
                        "successful_sources": job.successful_sources,
                        "filtered_sources": job.filtered_sources,
                        "created_at": job.created_at,
                        "started_at": job.started_at,
                        "completed_at": job.completed_at,
                        "error_message": job.error_message,
                        "changes_count": changes_count,
                    }
                )

            return jobs, total

        except (NotFoundError, PermissionDeniedError) as e:
            logger.error(
                "Error retrieving scrape history for jurisdiction %s: %s", jurisdiction_id, str(e)
            )
            raise
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while retrieving scrape history for jurisdiction %s: %s",
                jurisdiction_id,
                str(e),
            )
            raise ProcessingError(
                "An error occurred while retrieving scrape history. Please try again."
            )
        except Exception as e:
            logger.exception(
                "Unexpected error while retrieving scrape history for jurisdiction %s: %s",
                jurisdiction_id,
                str(e),
            )
            raise


class OrgResourceGuard:
    """
    Automatically enforces that resources belong to the current user's organization.

    This guard checks resource ownership based on path parameters such as
    `project_id`, `jurisdiction_id`, or `source_id`. If a resource belongs to a different
    organization than the current user, it raises an HTTP 403 Forbidden error.

    Router-Level Use Case:
        Apply this guard to an APIRouter to enforce multi-tenant isolation
        across all routes automatically, without calling `verify()` in each route.

    Example:
        from fastapi import APIRouter, Depends

        router = APIRouter(
            prefix="/jurisdictions",
            tags=["Jurisdictions"],
            dependencies=[
                Depends(TenantGuard),
                Depends(OrgResourceGuard)
            ]
        )

        @router.get("/{jurisdiction_id}")
        async def get_jurisdiction(jurisdiction_id: UUID, db: AsyncSession = Depends(get_db)):
            # No manual verification required
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            return jurisdiction

    Key Points:
        - Works at the router level: all routes inherit the guard.
        - Automatically resolves project from jurisdiction or source if needed.
        - Raises 404 if the resource is not found.
        - Raises 403 if a cross-organization access attempt is detected.
    """

    def __init__(
        self, request: Request, current_user: UserOrganization = Depends(get_current_user)
    ):
        self.request = request
        self.user = current_user

    async def __call__(self):
        path_params = self.request.path_params

        project_id = path_params.get("project_id")
        jurisdiction_id = path_params.get("jurisdiction_id")
        source_id = path_params.get("source_id")

        db: AsyncSession = self.request.state.db

        if source_id:
            source = await db.get(Source, source_id)
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The source you're looking for doesn't exist.",
                )
            jurisdiction_id = source.jurisdiction_id

        if jurisdiction_id:
            jurisdiction = await db.get(Jurisdiction, jurisdiction_id)
            if not jurisdiction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The jurisdiction you're looking for doesn't exist.",
                )
            project_id = jurisdiction.project_id

        if project_id:
            project = await db.get(Project, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The project you're looking for doesn't exist.",
                )

            if str(project.org_id) != str(self.user.organization_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "You don't have permission to access resources in this project. "
                        "Please contact your administrator."
                    ),
                )
