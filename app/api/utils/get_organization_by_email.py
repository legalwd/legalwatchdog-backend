import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger("app")


async def get_organization_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Fetch a user from the database by email.

    Args:
        db: Async SQLAlchemy session
        email: User email to search for

    Returns:
        User instance if found, otherwise None
    """
    try:
        user = await db.scalar(select(User).where(User.email == email))
        return user
    except Exception as e:
        logger.error(f"Failed to fetch organization_by by email {email}: {e}")
        return None
