"""
Unit tests for Ticket routes: /tickets
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus
from main import app


@pytest.fixture
def mock_user():
    """Create a mock user for testing"""
    user = MagicMock()
    user.id = uuid4()
    return user


@pytest.fixture
def client(mock_user):
    """Create test client with overridden dependencies"""
    from app.api.core.dependencies.auth import get_current_user

    def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_guest_support(mock_user):
    """Create test client with get_user_or_guest dependency overridden"""
    from app.api.core.dependencies.auth import get_current_user
    from app.api.core.dependencies.guest_auth import get_user_or_guest

    def override_get_current_user():
        return mock_user

    def override_get_user_or_guest():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_user_or_guest] = override_get_user_or_guest
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_manual_ticket_route_success(client, mock_user):
    """Test POST /tickets successful ticket creation."""
    ticket_id = uuid4()
    source_id = uuid4()
    revision_id = uuid4()

    mock_ticket = MagicMock()
    mock_ticket.id = ticket_id
    mock_ticket.ticket_number = 1001
    mock_ticket.title = "[Test Jurisdiction] Test Source - Change Detected"
    mock_ticket.priority = TicketPriority.HIGH.value
    mock_ticket.status = TicketStatus.OPEN.value
    mock_ticket.is_manual = True
    mock_ticket.source_id = source_id
    mock_ticket.data_revision_id = revision_id
    mock_ticket.created_by_user_id = mock_user.id

    ticket_data = {
        "source_id": str(source_id),
        "revision_id": str(revision_id),
        "priority": TicketPriority.HIGH.value,
    }

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.create_manual_ticket",
        new_callable=AsyncMock,
        return_value=mock_ticket,
    ):
        response = client.post("/api/v1/tickets", json=ticket_data)

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()

        assert "data" in response_data
        assert "ticket" in response_data["data"]
        assert "message" in response_data
        assert response_data["message"] == "Ticket created successfully"


@pytest.mark.asyncio
async def test_create_manual_ticket_route_permission_denied(client, mock_user):
    """Test POST /tickets fails when user not permitted."""
    from app.api.core.custom_exceptions.exceptions import PermissionDeniedError

    ticket_data = {
        "source_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "priority": TicketPriority.LOW.value,
    }

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.create_manual_ticket",
        new_callable=AsyncMock,
        side_effect=PermissionDeniedError(
            message="You don't have permission to create tickets in this project"
        ),
    ):
        response = client.post("/api/v1/tickets", json=ticket_data)
        assert response.status_code == 403
        assert "permission" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_tickets_by_source_route_success(client, mock_user):
    """Test GET /tickets?source_id=<uuid> returns tickets with pagination."""
    source_id = uuid4()
    ticket_id = uuid4()

    mock_tickets = [
        {"id": str(ticket_id), "ticket_number": 1015, "priority": TicketPriority.MEDIUM.value}
    ]

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.get_tickets",
        new_callable=AsyncMock,
        return_value=(mock_tickets, 1),
    ):
        response = client.get(f"/api/v1/tickets?source_id={source_id}&page=1&limit=20")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["tickets"] == mock_tickets
        assert response.json()["data"]["pagination"]["total_pages"] == 1


@pytest.mark.asyncio
async def test_get_tickets_by_source_route_permission_denied(client, mock_user):
    """Test GET /tickets fails when user not permitted."""
    from app.api.core.custom_exceptions.exceptions import PermissionDeniedError

    source_id = uuid4()

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.get_tickets",
        new_callable=AsyncMock,
        side_effect=PermissionDeniedError(message="You don't have permission to view tickets"),
    ):
        response = client.get(f"/api/v1/tickets?source_id={source_id}")
        assert response.status_code == 403
        assert "permission" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_ticket_by_id_route_success(client_with_guest_support, mock_user):
    """Test GET /tickets/{ticket_id} returns ticket."""
    ticket_id = uuid4()

    mock_ticket = {
        "id": str(ticket_id),
        "ticket_number": 1016,
        "priority": TicketPriority.MEDIUM.value,
    }

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.get_ticket_by_id",
        new_callable=AsyncMock,
        return_value=mock_ticket,
    ):
        response = client_with_guest_support.get(f"/api/v1/tickets/{ticket_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["ticket"]["id"] == str(ticket_id)


@pytest.mark.asyncio
async def test_get_ticket_by_id_route_not_found(client_with_guest_support, mock_user):
    """Test GET /tickets/{ticket_id} returns 404 when not found."""
    from app.api.core.custom_exceptions.exceptions import NotFoundError

    ticket_id = uuid4()

    with patch(
        "app.api.modules.v1.tickets.routes.ticket_routes.TicketService.get_ticket_by_id",
        new_callable=AsyncMock,
        side_effect=NotFoundError(message="Ticket not found"),
    ):
        response = client_with_guest_support.get(f"/api/v1/tickets/{ticket_id}")
        assert response.status_code == 404
        assert "ticket" in response.json()["message"].lower()
