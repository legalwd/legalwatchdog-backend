"""Script to create initial superadmin user."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.api.core.config import settings
from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_superadmin():
    """
    Create initial superadmin user for dashboard access.

    Reads credentials from environment variables:
    - SUPERADMIN_EMAIL
    - SUPERADMIN_PASSWORD

    Examples:
        >>> python scripts/create_superadmin.py
    """
    # Get credentials from environment
    email = settings.SUPERADMIN_EMAIL if hasattr(settings, "SUPERADMIN_EMAIL") else None
    password = settings.SUPERADMIN_PASSWORD if hasattr(settings, "SUPERADMIN_PASSWORD") else None

    if not email or not password:
        logger.error("SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD must be set in environment")
        logger.info("Add to .env file:")
        logger.info("SUPERADMIN_EMAIL=admin@yourdomain.com")
        logger.info("SUPERADMIN_PASSWORD=YourSecurePassword123!")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        # Check if superadmin already exists
        existing_user = await db.scalar(select(User).where(User.email == email))

        if existing_user:
            if existing_user.is_superadmin:
                logger.info(f"Superadmin {email} already exists")
                return

            # Update existing user to superadmin
            existing_user.is_superadmin = True
            db.add(existing_user)
            await db.commit()
            logger.info(f"Updated {email} to superadmin")
            return

        # Create new superadmin user
        hashed_password = hash_password(password)

        superadmin = User(
            email=email,
            hashed_password=hashed_password,
            name="Superadmin",
            is_active=True,
            is_verified=True,
            is_superadmin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(superadmin)
        await db.commit()
        await db.refresh(superadmin)

        logger.info(f"✓ Created superadmin user: {email}")
        logger.info(f"  User ID: {superadmin.id}")
        logger.info("  Role: Superadmin (global access)")
        logger.info("\nYou can now log in with these credentials to access:")
        logger.info("  - /api/v1/superadmin/app/overview")
        logger.info("  - /api/v1/superadmin/customers")
        logger.info("  - /api/v1/superadmin/metrics/*")
        logger.info("  - /api/v1/admin/llm/*")


if __name__ == "__main__":
    try:
        asyncio.run(create_superadmin())
    except Exception as e:
        logger.error(f"Failed to create superadmin: {e}", exc_info=True)
        sys.exit(1)
