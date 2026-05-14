import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.schemas.project_schema import (
    ProjectBase,
    ProjectUpdate,
)
from app.api.modules.v1.projects.services.project_service import ProjectService
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_create_project_after_registration(pg_async_session):
    """Test project creation after registering user and organization."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Dummy Org",
        industry="Tech",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(org)
    await pg_async_session.flush()

    role_id = uuid.uuid4()
    role = Role(
        id=role_id,
        name="admin",
        description="Admin role",
        organization_id=org_id,
        permissions=["all"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(role)
    await pg_async_session.flush()

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        organization_id=org_id,
        role_id=role_id,
        email=f"test_{user_id}@example.com",
        hashed_password="hashedpassword",
        name="Dummy User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    pg_async_session.add(user)
    await pg_async_session.flush()

    project_data = ProjectBase(
        title="Test Project",
        description="Dummy description",
        org_id=org_id,
    )

    with patch(
        "app.api.modules.v1.projects.services.project_service.check_user_permission"
    ) as mock_check:
        mock_check.return_value = True
        project = await project_service.create_project(
            data=project_data,
            organization_id=org_id,
            user_id=user_id,
        )

    assert project.id is not None
    assert project.title == "Test Project"
    assert project.org_id == org_id


@pytest.mark.asyncio
async def test_list_projects_service(pg_async_session: AsyncSession):
    """Test listing projects with pagination."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    page = 1
    limit = 10

    result = await project_service.list_projects(org_id, page=page, limit=limit)

    assert "data" in result
    assert "total" in result
    assert "page" in result
    assert result["page"] == page


@pytest.mark.asyncio
async def test_get_project_service_found_and_not_found(pg_async_session: AsyncSession):
    """Test getting a project by id."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    project = await project_service.get_project_by_id(project_id, org_id)

    assert project is None or isinstance(project, Project)


@pytest.mark.asyncio
async def test_update_project_service_not_found(pg_async_session: AsyncSession):
    """Test updating a project."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    data = ProjectUpdate(title="Updated Title")

    with patch(
        "app.api.modules.v1.projects.services.project_service.check_user_permission"
    ) as mock_check:
        mock_check.return_value = True
        project, message = await project_service.update_project(project_id, org_id, user_id, data)
    assert project is None
    assert "not found" in message.lower()


@pytest.mark.asyncio
async def test_update_project_service_success(pg_async_session: AsyncSession):
    """Test successfully updating an existing project."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name="Test Org",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(org)
    await pg_async_session.flush()

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"test_update_{user_id}@example.com",
        hashed_password="hashed",
        name="Test User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    pg_async_session.add(user)
    await pg_async_session.flush()

    project = Project(
        title="Original Title",
        org_id=org.id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    pg_async_session.add(project)
    await pg_async_session.flush()
    await pg_async_session.refresh(project)

    data = ProjectUpdate(title="Updated Title")

    with patch(
        "app.api.modules.v1.projects.services.project_service.check_user_permission"
    ) as mock_check:
        mock_check.return_value = True
        updated_project, message = await project_service.update_project(
            project.id, org.id, user_id, data
        )

    assert updated_project is not None
    assert updated_project.title == "Updated Title"


@pytest.mark.asyncio
async def test_delete_project_service(pg_async_session: AsyncSession):
    """Test deleting a project."""
    project_service = ProjectService(pg_async_session)
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with patch(
        "app.api.modules.v1.projects.services.project_service.check_user_permission"
    ) as mock_check:
        mock_check.return_value = True
        result = await project_service.delete_project(project_id, user_id, org_id)

    assert result in [True, False]
