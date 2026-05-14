from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Depends, HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.api.core.config import settings
from app.api.core.dependencies import plan_limits as plan_limits_mod
from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.billing.models.billing_account import BillingStatus
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.routes import jurisdiction_route as routes
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User
from main import app

_TEST_SAMPLE_USER = None


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user():
    return User(
        id=uuid4(),
        email="plan-limit-user@example.com",
        first_name="Plan",
        last_name="Limit",
        is_active=True,
        is_approved=True,
    )


@pytest.mark.asyncio
async def test_create_jurisdiction_handler_monkeypatched(monkeypatch):
    """Ensure create_jurisdiction returns the value from a monkeypatched service.create.

    Patch routes.service.create with an async fake that returns a Jurisdiction with a
    fixed id, call routes.create_jurisdiction(payload, db=None), and assert status 201
    and that the returned jurisdiction id matches the fixed id.
    """
    """Call the route handler with a monkeypatched service.create to ensure
    the handler returns what the service returns."""

    fake_id = uuid4()

    async def fake_create(db, jurisdiction, organization_id):
        return SimpleNamespace(
            id=fake_id,
            project_id=jurisdiction.project_id,
            name=jurisdiction.name,
            description=jurisdiction.description,
        )

    monkeypatch.setattr(routes.service, "create", fake_create)

    class _StubJurisdiction:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    monkeypatch.setattr(routes, "Jurisdiction", _StubJurisdiction)

    payload = JurisdictionCreateSchema(project_id=uuid4(), name="R-1", description="d")

    res = await routes.create_jurisdiction(
        organization_id=uuid4(), payload=payload, db=cast(Any, None)
    )

    assert hasattr(res, "status_code")
    assert res.status_code == 201
    body = res.body
    import json

    content = json.loads(body)
    assert "data" in content and "jurisdiction" in content["data"]
    jur = content["data"]["jurisdiction"]
    assert jur["id"] == str(fake_id)


@pytest.mark.asyncio
async def test_get_jurisdiction_not_found_raises(monkeypatch):
    """Test that requesting a non-existent jurisdiction is handled as a 404.
    This async test patches the service layer to simulate that no jurisdiction
    exists for the requested ID (service.get_jurisdiction_by_id returns None).
    It then calls the route handler with a generated UUID and a placeholder db,
    and asserts that the route returns a response-like object with a status_code
    attribute set to 404, ensuring the route maps a missing resource to an HTTP 404
    failure JSONResponse.
    """

    async def fake_get(*args, **kwargs):
        """Asynchronous test stub that simulates retrieving a jurisdiction by its identifier.
        Parameters
        ----------
        db
            Database connection, session, or mock object (may be unused by the stub).
        jurisdiction_id
            Identifier of the jurisdiction to retrieve.
        Returns
        -------
        None
            Indicates that no matching jurisdiction was found.
            Used in tests to emulate a missing record.
        Notes
        -----
        This function is intended for use in test suites to
        simulate the "not found" path of a database lookup.
        """

        return None

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)

    res = await routes.get_jurisdiction(
        organization_id=uuid4(), jurisdiction_id=uuid4(), db=cast(Any, None)
    )
    assert hasattr(res, "status_code")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_jurisdictions_empty_raises(monkeypatch):
    """
    Test that the jurisdictions route returns a 404 when no jurisdictions are found.
    This asynchronous test patches the service helper exposed by the route
    (routes.service.get_all_jurisdictions) with a fake coroutine that returns an
    empty list (accepting the defensive `(db)` or `(db, project_id)` signature).
    It then calls the route handler `routes.get_all_jurisdictions` with a None
    database argument and asserts that the returned response object has a
    `status_code` attribute equal to 404.
    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to replace the service function with the fake implementation.
    Notes
    -----
    - The fake service is implemented as `async def fake_all(db): return []`.
    - The test verifies route-level behavior (404 on empty result), not service logic.
    """

    async def fake_all(db, organization_id):
        """
        Asynchronous test helper that simulates fetching all records from a datastore.
        Parameters
        ----------
        db : Any
            A database/session fixture or connection object. Accepted for signature
            compatibility but not used by this fake implementation.
        Returns
        -------
        list
            An empty list, representing no records found. Intended for use as a stub
            in unit tests to avoid hitting a real database.
        """

        return []

    monkeypatch.setattr(routes.service, "get_all_jurisdictions", fake_all)

    class _FakeResult:
        def scalar(self):
            return 0

        def scalars(self):
            class _S:
                def all(self):
                    return []

                def first(self):
                    return None

            return _S()

    async def _fake_execute(stmt):
        return _FakeResult()

    fake_db = SimpleNamespace(execute=_fake_execute)

    res = await routes.get_all_jurisdictions(organization_id=uuid4(), db=cast(Any, fake_db))
    assert hasattr(res, "status_code")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_jurisdiction_returns_id(monkeypatch):
    """
    Test that delete_jurisdiction returns the ID of the deleted jurisdiction.
    This test creates a fake UUID and monkeypatches routes.service.soft_delete to
    simulate a successful soft-delete by returning a Jurisdiction instance with
    that ID.
    """

    fake_id = uuid4()

    async def fake_soft_delete(organization_id, db, jurisdiction_id=None, project_id=None):
        return SimpleNamespace(id=fake_id, project_id=uuid4(), name="x", description="d")

    monkeypatch.setattr(routes.service, "soft_delete", fake_soft_delete)

    res = await routes.soft_delete_jurisdiction(
        organization_id=uuid4(), jurisdiction_id=fake_id, db=cast(Any, None)
    )
    assert hasattr(res, "status_code")
    assert res.status_code == 204
    import json

    if not res.body:
        assert res.body in (b"", "")
    else:
        content = json.loads(res.body)
        expected = {
            "status": "SUCCESS",
            "status_code": 204,
            "message": "Jurisdiction archived successfully",
            "data": {},
        }

        assert content == expected


@pytest.mark.asyncio
async def test_delete_jurisdictions_by_project_returns_ids(monkeypatch):
    """
    Test that delete_jurisdictions_by_project returns a 200 response and the expected
    list of jurisdiction IDs when the service soft_delete operation successfully
    soft-deletes jurisdictions for a project.
    """

    fake_id = uuid4()

    async def fake_soft_delete(organization_id, db, jurisdiction_id=None, project_id=None):
        """
        Simulate a soft-delete operation for jurisdictions in tests.
        This asynchronous test helper returns a list containing a single fake
        Jurisdiction object. It does not perform any real database operations;
        its purpose is to emulate the shape and behavior of a soft-delete
        function for use in unit tests.
        """

        return [
            SimpleNamespace(id=fake_id, project_id=project_id or uuid4(), name="x", description="d")
        ]

    monkeypatch.setattr(routes.service, "soft_delete", fake_soft_delete)

    proj_id = uuid4()
    res = await routes.soft_delete_jurisdictions_by_project(
        organization_id=uuid4(), project_id=proj_id, db=cast(Any, None)
    )
    assert hasattr(res, "status_code")
    assert res.status_code == 204
    import json

    if not res.body:
        assert res.body in (b"", "")
    else:
        content = json.loads(res.body)
        expected = {
            "status": "SUCCESS",
            "status_code": 204,
            "message": "1 Jurisdiction(s) archived successfully",
            "data": {},
        }

        assert content == expected


@pytest.mark.asyncio
async def test_restore_jurisdiction_success(monkeypatch):
    """
    Test that the restore_jurisdiction route successfully restores a soft-deleted jurisdiction.
    This asynchronous unit test constructs a fake Jurisdiction model instance marked as deleted
    (is_deleted=True) and uses monkeypatch to replace the service-layer helpers used by the
    route
    """

    fake_id = uuid4()

    jur = SimpleNamespace(
        id=fake_id,
        project_id=uuid4(),
        name="ToRestore",
        description="d",
        is_deleted=True,
        deleted_at=None,
    )

    async def fake_get(*args, **kwargs):
        return jur

    async def fake_update(db, jurisdiction, organization_id=None):
        return jurisdiction

    monkeypatch.setattr(routes.service, "get_jurisdiction_for_restoration", fake_get)
    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get)
    monkeypatch.setattr(routes.service, "update", fake_update)

    res = await routes.restore_jurisdiction(
        organization_id=uuid4(), jurisdiction_id=fake_id, db=cast(Any, None)
    )

    assert hasattr(res, "status_code")
    assert res.status_code == 200
    import json

    content = json.loads(res.body)
    assert "data" in content and "jurisdiction" in content["data"]
    jur = content["data"]["jurisdiction"]

    assert jur.get("is_deleted") is False


@pytest.mark.asyncio
async def test_get_sources_for_jurisdiction_success(monkeypatch):
    """Test successful retrieval of sources for a jurisdiction."""
    from app.api.modules.v1.scraping.schemas.source_service import SourceRead

    fake_jurisdiction = SimpleNamespace(id=uuid4(), name="Test Jurisdiction")

    async def fake_get_jurisdiction(*args, **kwargs):
        return fake_jurisdiction

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get_jurisdiction)

    fake_sources = [
        SourceRead(
            id=uuid4(),
            jurisdiction_id=fake_jurisdiction.id,
            name="Source 1",
            url="https://example.com",
            source_type="web",
            scrape_frequency="DAILY",
            is_active=True,
            is_deleted=False,
            auto_create_tickets=False,
            has_auth=False,
            created_at="2025-01-01T00:00:00Z",
        )
    ]

    async def fake_get_sources(*args, **kwargs):
        return fake_sources

    monkeypatch.setattr(routes.SourceService, "get_sources", fake_get_sources)

    res = await routes.get_sources_for_jurisdiction(
        organization_id=uuid4(), jurisdiction_id=fake_jurisdiction.id, db=cast(Any, None)
    )

    assert hasattr(res, "status_code")
    assert res.status_code == 200
    import json

    content = json.loads(res.body)
    assert "data" in content and "sources" in content["data"]
    sources = content["data"]["sources"]
    assert len(sources) == 1
    assert sources[0]["name"] == "Source 1"


@pytest.mark.asyncio
async def test_get_sources_for_jurisdiction_not_found(monkeypatch):
    """Test that requesting sources for a non-existent jurisdiction returns 404."""

    async def fake_get_jurisdiction(*args, **kwargs):
        return None

    monkeypatch.setattr(routes.service, "get_jurisdiction_by_id", fake_get_jurisdiction)

    res = await routes.get_sources_for_jurisdiction(
        organization_id=uuid4(), jurisdiction_id=uuid4(), db=cast(Any, None)
    )

    assert hasattr(res, "status_code")
    assert res.status_code == 404


def test_jurisdictions_router_has_billing_guard():
    """Ensure the jurisdictions router is configured with require_billing_access."""
    deps = routes.router.dependencies

    assert any(getattr(dep, "dependency", None) == require_billing_access for dep in deps), (
        "Jurisdictions router should include require_billing_access as a dependency"
    )


@pytest.mark.asyncio
async def test_jurisdictions_require_billing_access_allows_active_org(monkeypatch):
    """Billing guard should allow jurisdictions routes when billing is active (on non-dev envs)."""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")

    mock_db = AsyncMock()
    org_id = uuid4()

    mock_account = MagicMock()
    mock_account.status = BillingStatus.ACTIVE

    with patch(
        "app.api.core.dependencies.billing_guard.get_billing_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=mock_account)
        mock_service.is_org_allowed_usage = AsyncMock(return_value=(True, BillingStatus.ACTIVE))
        mock_get_service.return_value = mock_service

        result = await require_billing_access(organization_id=org_id, db=mock_db)

        assert result is mock_account
        mock_service.get_billing_account_by_org.assert_awaited_once_with(org_id)
        mock_service.is_org_allowed_usage.assert_awaited_once_with(org_id)


@pytest.mark.asyncio
async def test_jurisdictions_require_billing_access_blocked_org_raises(monkeypatch):
    """Billing guard should block jurisdictions routes when billing is BLOCKED (on non-dev envs)"""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")

    mock_db = AsyncMock()
    org_id = uuid4()

    mock_account = MagicMock()
    mock_account.status = BillingStatus.BLOCKED

    with patch(
        "app.api.core.dependencies.billing_guard.get_billing_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=mock_account)
        mock_service.is_org_allowed_usage = AsyncMock(return_value=(False, BillingStatus.BLOCKED))
        mock_get_service.return_value = mock_service

        with pytest.raises(HTTPException) as excinfo:
            await require_billing_access(organization_id=org_id, db=mock_db)

        err = excinfo.value
        assert err.status_code == status.HTTP_403_FORBIDDEN
        assert "blocked" in err.detail.lower()


async def override_get_current_user_for_tests():
    """Return the sample user set in the test via _TEST_SAMPLE_USER."""
    return _TEST_SAMPLE_USER


async def fake_require_billing_access_for_tests(
    organization_id,
    db=Depends(get_db),
):
    """Skip real billing checks in this test."""
    return None


async def fake_require_jurisdiction_creation_not_allowed(
    organization_id,
    db=Depends(get_db),
):
    """
    Simulate the 'plan limit reached' guard for jurisdictions.

    This mimics the real error message shape used by plan_limits,
    so our test can assert on the 402 and message substring.
    """
    from fastapi import HTTPException, status

    raise HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Your current plan allows up to 2 jurisdictions. \
Please upgrade your plan to add more jurisdictions.",
    )


@pytest.mark.asyncio
async def test_jurisdiction_creation_blocked_when_plan_limit_reached(
    client, pg_async_session, auth_headers, sample_user, monkeypatch
):
    """
    When max_jurisdictions is reached for an org, POST /organizations/{org_id}/jurisdictions
    should return 402 PAYMENT_REQUIRED.
    """

    monkeypatch.setattr(settings, "ENVIRONMENT", "test")

    organization = Organization(name="Juris Plan Limit Org", is_active=True)
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Juris Project",
        description="For jurisdiction tests",
    )
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    for i in range(2):
        j = Jurisdiction(
            project_id=project.id,
            name=f"Existing J{i}",
            description="Already used slot",
        )
        pg_async_session.add(j)
    await pg_async_session.commit()

    global _TEST_SAMPLE_USER
    _TEST_SAMPLE_USER = sample_user

    app.dependency_overrides[get_current_user] = override_get_current_user_for_tests
    app.dependency_overrides[require_billing_access] = fake_require_billing_access_for_tests

    app.dependency_overrides[plan_limits_mod.require_jurisdiction_creation_allowed] = (
        fake_require_jurisdiction_creation_not_allowed
    )

    payload = {
        "project_id": str(project.id),
        "name": "Should Be Blocked",
        "description": "Over the limit",
    }

    response = await client.post(
        f"/api/v1/organizations/{organization.id}/jurisdictions/",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED, response.text
    body = response.json()
    assert body["status_code"] == status.HTTP_402_PAYMENT_REQUIRED
    assert "plan allows up to 2 jurisdictions" in body["message"]


@pytest.mark.asyncio
async def test_billing_guard_bypasses_in_dev(monkeypatch):
    """In dev ENVIRONMENT, billing guard should *not* block or call is_org_allowed_usage."""

    return  # disabling billing
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")

    mock_db = AsyncMock()
    org_id = uuid4()

    mock_account = MagicMock()
    mock_account.status = BillingStatus.BLOCKED

    with patch("app.api.core.dependencies.billing_guard.get_billing_service") as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_billing_account_by_org = AsyncMock(return_value=mock_account)
        mock_service.is_org_allowed_usage = AsyncMock(return_value=(False, BillingStatus.BLOCKED))
        mock_get_service.return_value = mock_service

        result = await require_billing_access(organization_id=org_id, db=mock_db)

        assert result is mock_account
        mock_service.get_billing_account_by_org.assert_awaited_once_with(org_id)
        mock_service.is_org_allowed_usage.assert_not_awaited()
