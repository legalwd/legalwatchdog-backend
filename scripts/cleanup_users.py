"""Cleanup orphaned test users."""

import asyncio

from sqlalchemy import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.users.models.users_model import User


async def cleanup():
    """Delete orphaned test users"""

    print("=" * 80)
    print("🧹 Cleaning up orphaned test users...")
    print("=" * 80)
    print()

    async with AsyncSessionLocal() as db:
        # Find test users
        users_result = await db.execute(
            select(User).where(
                User.email.in_(
                    [
                        "admin@testlegalfirm.com",
                        "emaduilzjr1@gmail.com",
                        "internal@testlegalfirm.com",
                    ]
                )
            )
        )
        users = users_result.scalars().all()

        if not users:
            print("✅ No orphaned test users found!")
            return

        print(f"📋 Found {len(users)} test user(s):")
        for user in users:
            print(f"   - {user.email} (ID: {user.id})")

        # Delete their memberships first
        for user in users:
            memberships_result = await db.execute(
                select(UserOrganization).where(UserOrganization.user_id == user.id)
            )
            memberships = memberships_result.scalars().all()

            if memberships:
                print(f"   Deleting {len(memberships)} membership(s) for {user.email}...")
                for membership in memberships:
                    await db.delete(membership)

        # Delete the users
        print(f"\n   Deleting {len(users)} user(s)...")
        for user in users:
            await db.delete(user)

        # Commit
        await db.commit()

        print()
        print("=" * 80)
        print("✅ Cleanup complete!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(cleanup())
