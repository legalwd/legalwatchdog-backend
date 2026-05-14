"""
Integration tests for Source API routes.

Tests all endpoints with authentication and database integration.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source, SourceType
from app.api.modules.v1.users.models.users_model import User
from main import app


@pytest.fixture
def sample_user():
    """Fixture for an authenticated user."""
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        name="Test User",
        is_active=True,
        is_approved=True,
    )


@pytest_asyncio.fixture
async def sample_jurisdiction_id(pg_async_session):
    """Fixture for a sample jurisdiction UUID."""
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project

    organization = Organization(name="Test Organization", is_active=True)
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Test Project",
        description="Test description",
        master_prompt="Collect latest regulations",
    )
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test description",
        prompt="Focus on legal updates",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    return jurisdiction.id


@pytest.fixture
def auth_headers(sample_user):
    """Fixture for authentication headers."""

    return {"Authorization": "Bearer mock_valid_token"}


@pytest_asyncio.fixture
async def client():
    """Fixture for FastAPI async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_source_success(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test successful source creation via API."""

    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Test Ministry",
        "url": "https://www.gov.uk/national-minimum-wage-rates",
        "source_type": "web",
        "scrape_frequency": "DAILY",
        "auth_details": {"username": "admin", "password": "secret"},
        "scraping_rules": {"selector": ".content"},
    }

    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["status_code"] == 201
    assert data["message"] == "Source created successfully"
    assert "source" in data["data"]
    assert data["data"]["source"]["name"] == "Test Ministry"
    assert data["data"]["source"]["has_auth"] is True


@pytest.mark.asyncio
async def test_create_source_without_auth_details(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test creating source without authentication details."""

    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Public Website",
        "url": "https://public.example.com",
        "source_type": "web",
        "scrape_frequency": "HOURLY",
    }

    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["data"]["source"]["has_auth"] is False


@pytest.mark.asyncio
async def test_create_source_invalid_url(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test that invalid URLs are rejected."""

    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Invalid Source",
        "url": "not-a-valid-url",
        "source_type": "web",
        "scrape_frequency": "DAILY",
    }

    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.post(
        "/api/v1/sources",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_source_duplicate_url_in_jurisdiction(
    client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
):
    """Test that duplicate URLs in the same jurisdiction are rejected."""

    payload1 = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "First Source",
        "url": "https://duplicate.example.com",
        "source_type": "web",
        "scrape_frequency": "DAILY",
    }

    async def override_get_db():
        yield pg_async_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    response1 = await client.post(
        "/api/v1/sources",
        json=payload1,
        headers=auth_headers,
    )
    assert response1.status_code == status.HTTP_201_CREATED

    payload2 = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Second Source",
        "url": "https://duplicate.example.com",
        "source_type": "web",
        "scrape_frequency": "HOURLY",
    }

    response2 = await client.post(
        "/api/v1/sources",
        json=payload2,
        headers=auth_headers,
    )

    assert response2.status_code == status.HTTP_409_CONFLICT
    data = response2.json()
    assert data["status_code"] == 409
    assert "Source with this URL already exists in the jurisdiction" in data["message"]


@pytest.mark.asyncio
async def test_create_source_unauthorized(client, pg_async_session, sample_jurisdiction_id):
    """Test that unauthenticated requests are rejected."""

    payload = {
        "jurisdiction_id": str(sample_jurisdiction_id),
        "name": "Test Source",
        "url": "https://example.com",
    }

    app.dependency_overrides.clear()

    response = await client.post("/api/v1/sources", json=payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


class TestBulkCreateSourceEndpoint:
    """Tests for POST /sources/bulk"""

    @pytest.mark.asyncio
    async def test_bulk_create_sources_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful bulk creation of sources."""

        payload = {
            "sources": [
                {
                    "jurisdiction_id": str(sample_jurisdiction_id),
                    "name": "Bulk Source 1",
                    "url": "https://bulk1.example.com",
                    "source_type": "web",
                    "scrape_frequency": "DAILY",
                },
                {
                    "jurisdiction_id": str(sample_jurisdiction_id),
                    "name": "Bulk Source 2",
                    "url": "https://bulk2.example.com",
                    "source_type": "web",
                    "scrape_frequency": "HOURLY",
                },
            ]
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/bulk",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["status_code"] == 201
        assert data["message"] == "Sources created successfully"
        assert "sources" in data["data"]
        assert data["data"]["count"] == 2
        assert len(data["data"]["sources"]) == 2
        assert data["data"]["sources"][0]["name"] == "Bulk Source 1"
        assert data["data"]["sources"][1]["name"] == "Bulk Source 2"

    @pytest.mark.asyncio
    async def test_bulk_create_sources_empty_list(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test bulk creation with empty sources list fails validation."""

        payload = {"sources": []}

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/bulk",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_bulk_create_sources_duplicate_url(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test bulk creation fails when duplicate URLs exist."""

        # First create a source with the normalized URL (with trailing slash as Pydantic does)
        from pydantic import HttpUrl

        existing_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Existing Source",
            url=str(HttpUrl("https://duplicate.example.com")),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(existing_source)
        await pg_async_session.commit()

        payload = {
            "sources": [
                {
                    "jurisdiction_id": str(sample_jurisdiction_id),
                    "name": "New Source",
                    "url": "https://duplicate.example.com",  # Duplicate URL
                    "source_type": "web",
                    "scrape_frequency": "DAILY",
                }
            ]
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/bulk",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT, (
            f"Expected 409, got {response.status_code}: {response.json()}"
        )
        data = response.json()
        # Error responses use 'error' key, check for the duplicate URL message
        assert "already exist" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_bulk_create_sources_unauthorized(self, client, pg_async_session):
        """Test that unauthenticated bulk create requests are rejected."""

        payload = {
            "sources": [
                {
                    "jurisdiction_id": str(uuid.uuid4()),
                    "name": "Test Source",
                    "url": "https://example.com",
                    "source_type": "web",
                    "scrape_frequency": "DAILY",
                }
            ]
        }

        app.dependency_overrides.clear()

        response = await client.post("/api/v1/sources/bulk", json=payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetSourcesListEndpoint:
    @pytest.mark.asyncio
    async def test_get_sources_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful retrieval of sources list."""

        source1 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 1",
            url="https://example1.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        source2 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 2",
            url="https://example2.com",
            source_type=SourceType.PDF,
            scrape_frequency="WEEKLY",
        )

        pg_async_session.add(source1)
        pg_async_session.add(source2)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            "/api/v1/sources",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Sources retrieved successfully"
        assert "sources" in data["data"]
        assert data["data"]["count"] >= 2

    @pytest.mark.asyncio
    async def test_get_sources_with_filters(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test get sources with jurisdiction filter."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources?jurisdiction_id={sample_jurisdiction_id}&is_active=true",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sources" in data["data"]

    @pytest.mark.asyncio
    async def test_get_sources_pagination(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test pagination parameters."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            "/api/v1/sources?skip=0&limit=10",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK


class TestGetSourceEndpoint:
    """Tests for GET /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_get_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful retrieval of a single source."""

        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Test Source",
            url="https://test.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            auth_details_encrypted="encrypted_value",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{source.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["source"]["id"] == str(source.id)
        assert data["data"]["source"]["name"] == "Test Source"
        assert data["data"]["source"]["has_auth"] is True

        assert "auth_details_encrypted" not in data["data"]["source"]

    @pytest.mark.asyncio
    async def test_get_source_not_found(self, client, pg_async_session, auth_headers, sample_user):
        """Test 404 when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{non_existent_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateSourceEndpoint:
    """Tests for PUT /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_update_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful source update."""

        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Original Name",
            url="https://original.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        update_payload = {
            "name": "Updated Name",
            "scrape_frequency": "HOURLY",
            "is_active": False,
        }

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.put(
            f"/api/v1/sources/{source.id}",
            json=update_payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["source"]["name"] == "Updated Name"
        assert data["data"]["source"]["scrape_frequency"] == "HOURLY"
        assert data["data"]["source"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_source_partial(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test partial update (only some fields)."""

        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Original",
            url="https://original.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        update_payload = {"is_active": False}

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.put(
            f"/api/v1/sources/{source.id}",
            json=update_payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["data"]["source"]["name"] == "Original"
        assert data["data"]["source"]["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test update of non-existent source."""
        non_existent_id = uuid.uuid4()
        update_payload = {"name": "New Name"}

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.put(
            f"/api/v1/sources/{non_existent_id}",
            json=update_payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteSourceEndpoint:
    """Tests for DELETE /sources/{source_id}"""

    @pytest.mark.asyncio
    async def test_delete_source_success(
        self, client, pg_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful source deletion."""

        source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="To Delete",
            url="https://delete.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )
        pg_async_session.add(source)
        await pg_async_session.commit()

        source_id = source.id

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.delete(
            f"/api/v1/sources/{source_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

        deleted_source = await pg_async_session.get(Source, source_id)
        assert deleted_source is not None
        assert deleted_source.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test deletion of non-existent source."""
        non_existent_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.delete(
            f"/api/v1/sources/{non_existent_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest_asyncio.fixture
async def test_source_for_revisions(pg_async_session):
    """Create a test source for revision tests."""
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project

    # Create organization
    organization = Organization(name="Test Revision Org", is_active=True)
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    project = Project(
        org_id=organization.id,
        title="Test Revision Project",
        description="Project for revision tests",
    )
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Revision Jurisdiction",
        description="Jurisdiction for revision tests",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    source = Source(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction.id,
        name="Test Source for Revisions",
        url="https://example.com/test",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
    )
    pg_async_session.add(source)
    await pg_async_session.commit()
    await pg_async_session.refresh(source)
    return source


@pytest_asyncio.fixture
async def test_revisions(pg_async_session, test_source_for_revisions):
    """Create test revisions for a source."""
    revisions = []
    for i in range(5):
        revision = DataRevision(
            id=uuid.uuid4(),
            source_id=test_source_for_revisions.id,
            minio_object_key=f"scrapes/2025/11/{i:02d}/test.html",
            extracted_data={
                "title": f"Regulation {i}",
                "content": f"Content for regulation {i}",
                "index": i,
            },
            ai_summary=f"Summary for revision {i}",
            was_change_detected=(i % 2 == 0),
        )
        pg_async_session.add(revision)
        revisions.append(revision)

    await pg_async_session.commit()
    for revision in revisions:
        await pg_async_session.refresh(revision)

    return revisions


class TestGetRevisionsEndpoint:
    """Tests for GET /sources/{source_id}/revisions"""

    @pytest.mark.asyncio
    async def test_get_revisions_success(
        self,
        client,
        pg_async_session,
        test_source_for_revisions,
        test_revisions,
        auth_headers,
        sample_user,
    ):
        """Test successful retrieval of revisions."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Revisions retrieved successfully"
        assert len(data["data"]["revisions"]) == 5
        assert data["data"]["pagination"]["total"] == 5
        assert data["data"]["pagination"]["page"] == 1

    @pytest.mark.asyncio
    async def test_get_revisions_ordering(
        self,
        client,
        pg_async_session,
        test_source_for_revisions,
        test_revisions,
        auth_headers,
        sample_user,
    ):
        """Test that revisions are ordered by scraped_at DESC."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        scraped_times = [rev["scraped_at"] for rev in data["data"]["revisions"]]
        assert scraped_times == sorted(scraped_times, reverse=True)

    @pytest.mark.asyncio
    async def test_get_revisions_pagination(
        self,
        client,
        pg_async_session,
        test_source_for_revisions,
        test_revisions,
        auth_headers,
        sample_user,
    ):
        """Test pagination with skip and limit."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?skip=0&limit=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["data"]["revisions"]) == 2

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?skip=2&limit=2",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()["data"]["revisions"]) == 2

    @pytest.mark.asyncio
    async def test_get_revisions_empty(
        self, client, pg_async_session, test_source_for_revisions, auth_headers, sample_user
    ):
        """Test retrieving revisions for source with no revisions."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert len(response.json()["data"]["revisions"]) == 0

    @pytest.mark.asyncio
    async def test_get_revisions_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test 404 when source doesn''t exist."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{uuid.uuid4()}/revisions",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_revisions_unauthorized(
        self, client, pg_async_session, test_source_for_revisions
    ):
        """Test endpoint requires authentication."""
        app.dependency_overrides.clear()
        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions",
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_revisions_data_structure(
        self,
        client,
        pg_async_session,
        test_source_for_revisions,
        test_revisions,
        auth_headers,
        sample_user,
    ):
        """Test revision data structure."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions",
            headers=auth_headers,
        )

        data = response.json()["data"]
        revision = data["revisions"][0]
        assert "id" in revision
        assert "source_id" in revision

        assert "pagination" in data
        assert "total" in data["pagination"]
        assert "page" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "total_pages" in data["pagination"]
        assert "extracted_data" in revision
        assert isinstance(revision["extracted_data"], dict)

    @pytest.mark.asyncio
    async def test_get_revisions_limit_validation(
        self, client, pg_async_session, test_source_for_revisions, auth_headers, sample_user
    ):
        """Test limit parameter validation."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?limit=200",
            headers=auth_headers,
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?limit=300",
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_revisions_skip_validation(
        self, client, pg_async_session, test_source_for_revisions, auth_headers, sample_user
    ):
        """Test skip parameter validation."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?skip=0",
            headers=auth_headers,
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/v1/sources/{test_source_for_revisions.id}/revisions?skip=-1",
            headers=auth_headers,
        )
        assert response.status_code == 422
