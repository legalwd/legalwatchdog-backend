from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.tickets.models.ticket_model import TicketStatus
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import TicketResponse
from main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_close_ticket_success(test_client):
    """Test successful ticket closure via the close ticket endpoint."""
    ticket_id = uuid4()
    user_id = uuid4()
    project_id = uuid4()
    organization_id = uuid4()
    now = datetime.now(timezone.utc)

    mock_user = Mock(id=user_id)
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db

    mock_ticket = TicketResponse(
        id=ticket_id,
        ticket_number=1017,
        title="Test Ticket",
        content={"message": "Something happened"},
        priority="LOW",
        is_manual=False,
        data_revision_id=uuid4(),
        source_id=uuid4(),
        created_by_user_id=user_id,
        assigned_by_user_id=None,
        assigned_to_user_id=None,
        project_id=project_id,
        organization_id=organization_id,
        status=TicketStatus.CLOSED.value,
        description="Closing notes: Issue resolved",
        created_at=now,
        updated_at=now,
        closed_at=now,
    )

    with patch(
        "app.api.modules.v1.tickets.routes.close_ticket_routes.TicketService.close_ticket",
        new=AsyncMock(return_value=mock_ticket),
    ):
        response = test_client.patch(
            f"/api/v1/tickets/{ticket_id}/close",
            json={"closing_notes": "Issue resolved"},
        )

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "SUCCESS"
    assert payload["message"] == "Ticket closed successfully"
    assert payload["data"]["id"] == str(ticket_id)
    assert payload["data"]["status"] == "CLOSED"
    assert "Issue resolved" in payload["data"]["description"]

    app.dependency_overrides.clear()
