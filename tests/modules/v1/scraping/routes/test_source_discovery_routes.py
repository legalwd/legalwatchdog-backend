"""Integration tests for Source Discovery API routes."""

import uuid
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.users.models.users_model import User
from main import app


@pytest.fixture
def sample_user():
    """Fixture for an authenticated user."""
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_approved=True,
    )


@pytest_asyncio.fixture
async def sample_jurisdiction_id(mocked_async_session):
    """Fixture for a sample jurisdiction UUID."""
    # Return a mock jurisdiction ID since we're using a mocked session
    return uuid.uuid4()


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


class TestAcceptSuggestedSourcesEndpoint:
    """Tests for POST /sources/accept-suggestions"""

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_success(
        self, client, mocked_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test successful acceptance of Parallel.ai-suggested sources."""

        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
        from app.api.modules.v1.projects.models.project_model import Project

        mock_project = Project(
            id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            title="Test Project",
            description="Test description",
            master_prompt="Collect latest regulations",
        )

        mock_jurisdiction = Jurisdiction(
            id=sample_jurisdiction_id,
            project_id=mock_project.id,
            name="Test Jurisdiction",
            description="Test description",
            prompt="Focus on legal updates",
        )

        async def mock_get(model, pk, **kwargs):
            if model == Jurisdiction:
                return mock_jurisdiction
            elif model == Project:
                return mock_project
            return None

        mocked_async_session.get = AsyncMock(side_effect=mock_get)

        mock_all_result = Mock()
        mock_all_result.all.return_value = []

        mock_scalars = Mock()
        mock_scalars.all = mock_all_result.all

        mock_result = Mock()
        mock_result.scalars = Mock(return_value=mock_scalars)

        mocked_async_session.execute = AsyncMock(return_value=mock_result)

        payload = {
            "suggested_sources": [
                {
                    "title": "Supreme Court Opinions",
                    "url": "https://supremecourt.gov/opinions",
                    "snippet": "Official court opinions and decisions",
                    "confidence_reason": "Government domain with official content",
                    "is_official": True,
                },
                {
                    "title": "Federal Register",
                    "url": "https://federalregister.gov",
                    "snippet": "Official publication of federal regulations",
                    "confidence_reason": "Official government publication",
                    "is_official": True,
                },
            ],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
            "scraping_rules": {"selector": ".content"},
        }

        async def override_get_db():
            yield mocked_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["status_code"] == 201
        assert "activated for monitoring" in data["message"].lower()
        assert "sources" in data["data"]
        assert data["data"]["count"] == 2
        assert len(data["data"]["sources"]) == 2
        assert data["data"]["sources"][0]["name"] == "Supreme Court Opinions"
        assert data["data"]["sources"][1]["name"] == "Federal Register"
        assert "powered_by" in data["data"]
        assert "Parallel.ai" in data["data"]["powered_by"]

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_empty_list(
        self, client, mocked_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test acceptance with empty suggested sources list."""
        payload = {
            "suggested_sources": [],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield mocked_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["count"] == 0
        assert data["data"]["sources"] == []

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_duplicate_url(
        self, client, mocked_async_session, auth_headers, sample_jurisdiction_id, sample_user
    ):
        """Test acceptance fails when duplicate URLs exist."""
        from unittest.mock import Mock

        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
        from app.api.modules.v1.projects.models.project_model import Project

        # Create mock jurisdiction and project
        mock_project = Project(
            id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            title="Test Project",
            description="Test description",
            master_prompt="Collect latest regulations",
        )

        mock_jurisdiction = Jurisdiction(
            id=sample_jurisdiction_id,
            project_id=mock_project.id,
            name="Test Jurisdiction",
            description="Test description",
            prompt="Focus on legal updates",
        )

        # Mock the session.get method
        async def mock_get(model, pk, **kwargs):
            if model == Jurisdiction:
                return mock_jurisdiction
            elif model == Project:
                return mock_project
            return None

        mocked_async_session.get = AsyncMock(side_effect=mock_get)

        # Mock execute to return the existing source URL when querying for duplicates
        async def mock_execute(stmt):
            mock_result = Mock()
            mock_scalars = Mock()
            # Note: HttpUrl normalizes URLs with trailing slashes
            mock_scalars.all.return_value = ["https://duplicate.gov/"]
            mock_result.scalars.return_value = mock_scalars
            return mock_result

        mocked_async_session.execute = AsyncMock(side_effect=mock_execute)

        payload = {
            "suggested_sources": [
                {
                    "title": "Duplicate Source",
                    "url": "https://duplicate.gov",
                    "snippet": "This will fail",
                    "confidence_reason": "Test",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(sample_jurisdiction_id),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield mocked_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT, (
            f"Expected 409, got {response.status_code}: {response.json()}"
        )

        data = response.json()
        assert "already exist" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_invalid_data(
        self, client, mocked_async_session, auth_headers, sample_user
    ):
        """Test acceptance with invalid suggested source data."""
        payload = {
            "suggested_sources": [
                {
                    "title": "",
                    "url": "not-a-valid-url",
                    "snippet": "Test",
                    "confidence_reason": "Test",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(uuid.uuid4()),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        async def override_get_db():
            yield mocked_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            "/api/v1/sources/accept-suggestions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_accept_suggested_sources_unauthorized(self, client, mocked_async_session):
        """Test that unauthenticated acceptance requests are rejected."""
        payload = {
            "suggested_sources": [
                {
                    "title": "Test Source",
                    "url": "https://example.com",
                    "snippet": "Test snippet",
                    "confidence_reason": "Test reason",
                    "is_official": True,
                }
            ],
            "jurisdiction_id": str(uuid.uuid4()),
            "source_type": "web",
            "scrape_frequency": "DAILY",
        }

        app.dependency_overrides.clear()

        response = await client.post("/api/v1/sources/accept-suggestions", json=payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
