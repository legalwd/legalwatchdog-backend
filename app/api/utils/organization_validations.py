import logging
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.organization.service.user_organization_service import UserOrganizationCRUD
from app.api.modules.v1.users.models.roles_model import Role
from app.api.utils.get_organization_by_email import get_organization_by_email
from app.api.utils.redis import get_user_credentials

logger = logging.getLogger("app")


async def validate_organization_email_available(db: AsyncSession, email: str) -> None:
    """
    Validate that an organization email is not already registered.

    Args:
        db: Database session for querying
        email: Email address to check

    Raises:
        ValueError: If organization with email already exists
    """
    existing_org = await get_organization_by_email(db, email)
    logger.debug("Organization existence check for email=%s: %s", email, bool(existing_org))

    if existing_org:
        logger.warning("Validation failed: Organization already exists with email=%s", email)
        raise ValueError("An organization with this email already exists.")


async def validate_no_pending_registration(redis_client: Redis, email: str) -> None:
    """
    Validate that there is no pending registration for the email.

    Args:
        redis_client: Redis client instance
        email: Email address to check for pending registration

    Raises:
        ValueError: If a pending registration exists for this email
    """
    pending = await get_user_credentials(redis_client, email)

    if pending:
        logger.warning("Validation failed: Pending registration exists for email=%s", email)
        raise ValueError("A registration with this email is already pending OTP verification.")


async def check_user_permission(
    db: AsyncSession,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permission: str,
) -> bool:
    """
    Check if user has a specific permission in an organization.

    Args:
        user_id: User UUID
        organization_id: Organization UUID
        permission: Permission to check (e.g., "organization:write")

    Returns:
        True if user has permission, False otherwise
    """
    membership = await UserOrganizationCRUD.get_user_organization(db, user_id, organization_id)

    if not membership or not membership.is_active:
        return False

    result = await db.execute(select(Role).where(Role.id == membership.role_id))
    role = result.scalar_one_or_none()

    if not role:
        return False

    return role.permissions.get(permission, False) is True
