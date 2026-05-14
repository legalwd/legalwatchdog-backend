import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import (
    require_permission,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.users.models.roles_model import Role
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.permissions import Permission


@pytest.mark.asyncio
async def test_require_permission_grants(pg_async_session: AsyncSession):
    session = pg_async_session

    org = Organization(name="Test Org")
    session.add(org)
    await session.flush()

    permissions = {Permission.CREATE_PROJECTS.value: True}
    role = Role(name="admin", organization_id=org.id, permissions=permissions)
    session.add(role)
    await session.flush()

    user = User(email="perm@example.com", hashed_password="x", name="Test User", is_verified=True)
    session.add(user)
    await session.commit()

    checker = require_permission(Permission.CREATE_PROJECTS)

    result = await checker(user_role=(user, role))
    assert result.email == user.email
