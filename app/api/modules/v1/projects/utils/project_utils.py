import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, select

from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


async def get_project_by_id(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> Optional[Project]:
    """
    Fetch project by ID and verify it belongs to organization.

    Args:
        db: Database session
        project_id: Project UUID to fetch
        organization_id: Organization UUID to verify ownership

    Returns:
        Project object if found and accessible, None otherwise
    """
    statement = select(Project).where(
        and_(
            Project.id == project_id,
            Project.org_id == organization_id,
            Project.is_deleted.is_(False),
        )
    )
    result = await db.execute(statement)
    return result.scalars().first()


async def get_project_by_id_including_deleted(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> Optional[Project]:
    """
    Fetch project by ID including soft deleted ones.
    For admin/restore purposes.
    """
    statement = select(Project).where(
        and_(Project.id == project_id, Project.org_id == organization_id)
    )
    result = await db.execute(statement)
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: UUID, organization_id: UUID) -> Optional[User]:
    """
    Fetch user by ID and verify they belong to organization.

    Args:
        db: Database session
        user_id: User UUID to fetch
        organization_id: Organization UUID to verify membership

    Returns:
        User object if found and belongs to organization, None otherwise
    """
    statement = (
        select(User)
        .join(
            UserOrganization,
            and_(
                UserOrganization.user_id == User.id,
                UserOrganization.organization_id == organization_id,
                UserOrganization.is_active,
            ),
        )
        .where(User.id == user_id)
    )

    result = await db.execute(statement)
    user = result.scalar_one_or_none()

    if user:
        logger.info(f"User {user_id} found and is member of organization {organization_id}")
    else:
        logger.warning(f"User {user_id} not found or not member of organization {organization_id}")

    return user


async def check_project_user_exists(db: AsyncSession, project_id: UUID, user_id: UUID) -> bool:
    """
    Check if user is already a member of the project.

    Args:
        db: Database session
        project_id: Project UUID
        user_id: User UUID

    Returns:
        True if user is already in project, False otherwise
    """
    statement = select(ProjectUser).where(
        and_(ProjectUser.project_id == project_id, ProjectUser.user_id == user_id)
    )
    result = await db.execute(statement)
    return result.one_or_none() is not None


def calculate_pagination(total: int, page: int, limit: int) -> dict:
    """
    Calculate pagination metadata.

    Args:
        total: Total number of items
        page: Current page number
        limit: Items per page

    Returns:
        Dictionary with pagination metadata
    """
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    return {"total": total, "page": page, "limit": limit, "total_pages": total_pages}
