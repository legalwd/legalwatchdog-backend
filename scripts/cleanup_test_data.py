"""Cleanup script for ticket invitation test data."""

import asyncio

from sqlalchemy import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket
from app.api.modules.v1.users.models.users_model import User


async def cleanup():
    """Delete all test data created by test_ticket_invitations.py"""

    print("=" * 80)
    print("🧹 Cleaning up test data...")
    print("=" * 80)
    print()

    async with AsyncSessionLocal() as db:
        # Find test organization
        org_result = await db.execute(
            select(Organization).where(Organization.name == "Test Legal Firm")
        )
        org = org_result.scalar_one_or_none()

        if not org:
            print("✅ No test data found. Already clean!")
            return

        print(f"📋 Found test organization: {org.name} (ID: {org.id})")

        # 1. Delete external participants
        ext_participants_result = await db.execute(
            select(ExternalParticipant).join(Ticket).where(Ticket.organization_id == org.id)
        )
        ext_participants = ext_participants_result.scalars().all()

        if ext_participants:
            print(f"   Deleting {len(ext_participants)} external participant(s)...")
            for participant in ext_participants:
                await db.delete(participant)

        # 2. Delete tickets
        tickets_result = await db.execute(select(Ticket).where(Ticket.organization_id == org.id))
        tickets = tickets_result.scalars().all()

        if tickets:
            print(f"   Deleting {len(tickets)} ticket(s)...")
            for ticket in tickets:
                await db.delete(ticket)

        # 3. Delete projects
        projects_result = await db.execute(select(Project).where(Project.org_id == org.id))
        projects = projects_result.scalars().all()

        if projects:
            print(f"   Deleting {len(projects)} project(s)...")
            for project in projects:
                await db.delete(project)

        # 4. Delete user memberships
        memberships_result = await db.execute(
            select(UserOrganization).where(UserOrganization.organization_id == org.id)
        )
        memberships = memberships_result.scalars().all()

        if memberships:
            print(f"   Deleting {len(memberships)} user membership(s)...")
            for membership in memberships:
                await db.delete(membership)

        # 5. Delete users
        users_result = await db.execute(
            select(User).where(User.email.in_(["admin@testlegalfirm.com", "emaduilzjr1@gmail.com"]))
        )
        users = users_result.scalars().all()

        if users:
            print(f"   Deleting {len(users)} test user(s)...")
            for user in users:
                await db.delete(user)

        # 6. Delete organization
        print(f"   Deleting organization: {org.name}")
        await db.delete(org)

        # Commit all deletions
        await db.commit()

        print()
        print("=" * 80)
        print("✅ Cleanup complete!")
        print("=" * 80)
        print()

        # Verify cleanup
        verify_org = await db.execute(
            select(Organization).where(Organization.name == "Test Legal Firm")
        )
        if verify_org.scalar_one_or_none():
            print("⚠️  Warning: Some data may still exist")
        else:
            print("✅ Verified: All test data removed")


if __name__ == "__main__":
    asyncio.run(cleanup())
