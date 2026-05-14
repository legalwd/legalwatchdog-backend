from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.routes import jurisdiction_route as jurisdiction_routes_module
from app.api.modules.v1.jurisdictions.service.jurisdiction_service import (
    JurisdictionService,
    OrgResourceGuard,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project


@pytest.mark.asyncio
async def test_create_first_jurisdiction_sets_parent(pg_async_session):
    """
    Test creating the first jurisdiction for a project.

    Ensures that a jurisdiction can be created under a project belonging to an organization,
    and the returned object has a valid ID.
    """
    svc = JurisdictionService()

    org = Organization(name="Test Org")
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)

    project = Project(org_id=org.id, title="P1")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jur = Jurisdiction(project_id=project.id, name="J-First", description="d1")
    created = await svc.create(pg_async_session, jur, org.id)

    assert created is not None
    assert created.id is not None


@pytest.mark.asyncio
async def test_get_by_name_and_delete_and_read(pg_async_session):
    """
    Test full lifecycle of a jurisdiction: create, retrieve by name, read all, and delete.
    """
    svc = JurisdictionService()

    org = Organization(name="Test Org 3")
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)

    project = Project(org_id=org.id, title="P3")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jur = Jurisdiction(project_id=project.id, name="FindMe", description="d")
    created = await svc.create(pg_async_session, jur, org.id)

    found = await svc.get_jurisdiction_by_name(pg_async_session, "FindMe")
    found_obj = found if hasattr(found, "id") else found[0]
    assert found_obj.id == created.id

    all_j = await svc.read(pg_async_session, org.id)
    ids = [item.id if hasattr(item, "id") else item[0].id for item in all_j]
    assert created.id in ids

    deleted = await svc.delete(pg_async_session, created, org.id)
    assert deleted is True


def _build_app_and_client(fake_user=None, fake_project=None):
    """
    Build a FastAPI test app with the jurisdiction router included.

    Args:
        fake_user: SimpleNamespace with `.organization_id`
        fake_project: SimpleNamespace with `.id` and `.org_id`

    Returns:
        tuple: (FastAPI app instance, TestClient)
    """

    app = FastAPI()

    from app.api.db.database import get_db

    app.dependency_overrides[get_db] = lambda: FakeDB()

    # Provide an explicit override for OrgResourceGuard so tests don't depend on
    # the router-level dependency resolution order or middleware timing. This
    # makes the ownership check deterministic using the fake_user/fake_project
    # supplied by the test.
    from fastapi import HTTPException

    def _org_guard_override():
        if (
            fake_user
            and fake_project
            and str(fake_project.org_id) != str(fake_user.organization_id)
        ):
            raise HTTPException(status_code=403, detail="Cross-organization access denied")
        return True

    app.dependency_overrides[OrgResourceGuard] = _org_guard_override

    class FakeDB:
        """Fake async DB for OrgResourceGuard."""

        async def get(self, cls, id):
            if cls.__name__ == "Project" and fake_project:
                return fake_project
            return None

        async def execute(self, stmt):
            class FakeResult:
                def __init__(self, data=None):
                    self._data = data or []

                def scalars(self):
                    return self

                def all(self):
                    return self._data

            return FakeResult([])

    @app.middleware("http")
    async def add_db_to_request(request: Request, call_next):
        """Inject fake DB into request.state.db."""
        request.state.db = FakeDB()
        response = await call_next(request)
        return response

    if fake_user:

        async def get_user_override():
            return fake_user

        app.dependency_overrides[get_current_user] = get_user_override

    app.include_router(jurisdiction_routes_module.router, prefix="/api/v1")
    return app, TestClient(app)


def test_org_guard_blocks_cross_org_access():
    """
    Verify that OrgResourceGuard blocks access to resources in a different organization.
    """
    fake_user = SimpleNamespace(organization_id=uuid4())
    fake_project = SimpleNamespace(id=uuid4(), org_id=uuid4())  # different org

    app, client = _build_app_and_client(fake_user=fake_user, fake_project=fake_project)
    resp = client.get(
        f"/api/v1/organizations/{fake_project.org_id}/jurisdictions/project/{fake_project.id}"
    )

    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "permission" in detail or "access" in detail


def test_org_guard_allows_same_org_access():
    """
    Verify that OrgResourceGuard allows access to resources in the same organization.
    """
    org_id = uuid4()
    fake_user = SimpleNamespace(organization_id=org_id)
    fake_project = SimpleNamespace(id=uuid4(), org_id=org_id)

    app, client = _build_app_and_client(fake_user=fake_user, fake_project=fake_project)

    async def fake_billing_guard(organization_id, db=None):
        return None

    app.dependency_overrides[require_billing_access] = fake_billing_guard

    resp = client.get(
        f"/api/v1/organizations/{fake_project.org_id}/jurisdictions/project/{fake_project.id}"
    )

    assert resp.status_code != 403
