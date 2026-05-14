"""
Test Ticket Endpoint Script
This script helps you test the manual ticket creation endpoint.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.users.models.users_model import User


async def get_test_data():
    """Get existing test data from database."""
    from app.api.db.database import DATABASE_URL

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("\n🔍 Checking for existing test data...\n")

        user_result = await session.execute(select(User).where(User.is_active).limit(1))
        user = user_result.scalar_one_or_none()

        if not user:
            print(" No active users found. Please create a user first.")
            return None

        print(" User found:")
        print(f" ID: {user.id}")
        print(f" Email: {user.email}")
        print(f" Name: {user.name}\n")

        org_result = await session.execute(
            select(Organization)
            .join(UserOrganization)
            .where(UserOrganization.user_id == user.id)
            .where(UserOrganization.is_active)
            .limit(1)
        )
        org = org_result.scalar_one_or_none()

        if not org:
            print("User has no active organization. Please add user to an organization.")
            return None

        print("Organization found:")
        print(f"ID: {org.id}")
        print(f"Name: {org.organization_name}\n")

        project_result = await session.execute(
            select(Project)
            .join(ProjectUser)
            .where(Project.org_id == org.id)
            .where(~Project.is_deleted)
            .where(ProjectUser.user_id == user.id)
            .limit(1)
        )
        project = project_result.scalar_one_or_none()

        if not project:
            print("User has no projects. Please create a project and add user as member.")
            return None

        print("Project found:")
        print(f"ID: {project.id}")
        print(f"Name: {project.name}")
        print(f"Description: {project.description}\n")

        return {
            "user": {"id": str(user.id), "email": user.email, "name": user.name},
            "organization": {"id": str(org.id), "name": org.organization_name},
            "project": {"id": str(project.id), "name": project.name},
        }


async def main():
    data = await get_test_data()
    if data:
        print("\nTest data fetched successfully:")
        print(data)
    else:
        print("\nFailed to fetch test data.")


if __name__ == "__main__":
    asyncio.run(main())
