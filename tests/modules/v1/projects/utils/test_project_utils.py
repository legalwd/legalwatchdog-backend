from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.utils.project_utils import (
    calculate_pagination,
    get_project_by_id,
)


@pytest.mark.asyncio
async def test_get_project_by_id(pg_async_session: AsyncSession):
    """Test fetching project by id."""
    org_id = uuid4()
    project_id = uuid4()
    project = await get_project_by_id(pg_async_session, project_id, org_id)
    assert project is None or isinstance(project, Project)


def test_calculate_pagination():
    """Test pagination calculation."""
    result = calculate_pagination(total=25, page=2, limit=10)
    assert result["total"] == 25
    assert result["page"] == 2
    assert result["limit"] == 10
    assert result["total_pages"] == 3
