import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.api_key_auth import get_api_key_from_header
from app.api.db.database import get_db
from main import app

try:
    from sqlmodel import Relationship

    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.users.models.users_model import User

    if not hasattr(Organization, "api_keys"):
        Organization.api_keys = Relationship(
            back_populates="organization",
            sa_relationship_kwargs={"cascade": "all, delete-orphan"},
        )

    if not hasattr(User, "owned_api_keys"):
        User.owned_api_keys = Relationship(
            back_populates="owner_user",
            sa_relationship_kwargs={"foreign_keys": "api_keys.user_id"},
        )

    if not hasattr(User, "generated_api_keys"):
        User.generated_api_keys = Relationship(
            back_populates="generated_by_user",
            sa_relationship_kwargs={"foreign_keys": "api_keys.generated_by"},
        )
except Exception:
    pass

try:
    from app.api.modules.v1.api_access.models.api_key_model import APIKey

    api_tbl = getattr(APIKey, "__table__", None)
    if api_tbl is not None:
        if not hasattr(api_tbl, "user_id"):
            setattr(api_tbl, "user_id", api_tbl.c.user_id)
        if not hasattr(api_tbl, "generated_by"):
            setattr(api_tbl, "generated_by", api_tbl.c.generated_by)
        if not hasattr(api_tbl, "organization_id"):
            setattr(api_tbl, "organization_id", api_tbl.c.organization_id)
except Exception:
    pass


@pytest_asyncio.fixture
async def sample_resource_setup(pg_async_session):
    """Create organization -> project -> jurisdiction -> source -> data_revision chain."""
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.data_revision import DataRevision
    from app.api.modules.v1.scraping.models.source_model import Source

    org = Organization(name="Webhook Org", is_active=True)
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)

    project = Project(org_id=org.id, title="P1", description="d", master_prompt="m")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(project_id=project.id, name="J1", description="d", prompt="p")
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    source = Source(jurisdiction_id=jurisdiction.id, name="S1", url="https://s1", source_type="web")
    pg_async_session.add(source)
    await pg_async_session.commit()
    await pg_async_session.refresh(source)

    rev = DataRevision(source_id=source.id, minio_object_key="k1", extracted_data={"foo": "bar"})
    pg_async_session.add(rev)
    await pg_async_session.commit()
    await pg_async_session.refresh(rev)

    return {
        "organization": org,
        "project": project,
        "jurisdiction": jurisdiction,
        "source": source,
        "revision": rev,
    }


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_source_extracted_data_happy_path(
    client, pg_async_session, sample_resource_setup
):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=resource["organization"].id, scope="read:source")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = f"/api/v1/external/sources/{resource['source'].id}/extracted-data"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "SUCCESS"
    assert "revisions" in body["data"]
    assert body["data"]["revisions"][0]["extracted_data"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_get_source_insufficient_scope(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=resource["organization"].id, scope="read:project")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = f"/api/v1/external/sources/{resource['source'].id}/extracted-data"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_source_org_mismatch(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=uuid.uuid4(), scope="read:source")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = f"/api/v1/external/sources/{resource['source'].id}/extracted-data"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_download_source_extracted_data_happy_path(
    client, pg_async_session, sample_resource_setup
):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(
        organization_id=resource["organization"].id, scope="download:data_revision"
    )

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = f"/api/v1/external/sources/{resource['source'].id}/extracted-data/download"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    # ensure content-disposition header present
    assert "attachment" in resp.headers.get("content-disposition", "")
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["extracted_data"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_download_source_insufficient_scope(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=resource["organization"].id, scope="read:source")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = f"/api/v1/external/sources/{resource['source'].id}/extracted-data/download"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_sources_happy_path(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=resource["organization"].id, scope="read:source")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = "/api/v1/external/sources"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "SUCCESS"
    items = body["data"]["items"]
    assert any(item["id"] == str(resource["source"].id) for item in items)


@pytest.mark.asyncio
async def test_list_jurisdictions_happy_path(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(
        organization_id=resource["organization"].id, scope="read:jurisdiction"
    )

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = "/api/v1/external/jurisdictions"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "SUCCESS"
    items = body["data"]["items"]
    assert any(item["id"] == str(resource["jurisdiction"].id) for item in items)


@pytest.mark.asyncio
async def test_list_projects_happy_path(client, pg_async_session, sample_resource_setup):
    resource = sample_resource_setup

    async def override_get_db():
        yield pg_async_session

    api_key_obj = SimpleNamespace(organization_id=resource["organization"].id, scope="read:project")

    async def override_api_key():
        return api_key_obj

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_api_key_from_header] = override_api_key

    url = "/api/v1/external/projects"
    resp = await client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "SUCCESS"
    items = body["data"]["items"]
    assert any(item["id"] == str(resource["project"].id) for item in items)
