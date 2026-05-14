from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.core.dependencies.auth import get_current_user
from app.api.modules.v1.search.schemas.search_schema import DataRevisionSearchResult, SearchResponse
from main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_data_revision_search_route_unauthorized():
    """Should return 403 for unauthorized access (no token)."""
    client = TestClient(app)
    payload = {
        "query": "test",
        "operator": "AND",
        "page": 1,
        "limit": 10,
        "min_rank": 0.0,
        "extracted_data_filters": {},
    }
    response = client.post("/api/v1/data-revisions/", json=payload)
    assert response.status_code == 403


def test_data_revision_search_success(test_client):
    """Test successful data revision search via the endpoint."""
    user_id = uuid4()

    mock_user = AsyncMock()
    mock_user.id = user_id

    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_result = DataRevisionSearchResult(
        id=uuid4(),
        title="Test Revision",
        summary="Summary",
        content="Content",
        key_fields={},
        revision_date=None,
        relevance_score=1.0,
    )
    mock_response = SearchResponse(
        results=[mock_result],
        total=1,
        page=1,
        limit=10,
        total_pages=1,
        query="test",
        operator="AND",
    )

    with patch(
        "app.api.modules.v1.search.service.search_service.SearchService.search",
        new=AsyncMock(return_value=mock_response),
    ):
        payload = {
            "query": "test",
            "operator": "AND",
            "page": 1,
            "limit": 10,
            "min_rank": 0.0,
            "extracted_data_filters": {},
        }
        response = test_client.post("/api/v1/data-revisions/", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["message"] == "Data revision search successful"
    assert data["data"]["results"][0]["title"] == "Test Revision"

    app.dependency_overrides.clear()
