import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.routes.guest_access_routes import (
    get_guest_ticket_access,
)
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    GuestTicketAccessResponse,
)


@pytest.mark.asyncio
async def test_get_guest_ticket_access_success():
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()

    participant = ExternalParticipant(
        id=participant_id,
        ticket_id=ticket_id,
        email="guest@external.com",
        role="Legal Counsel",
        is_active=True,
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1013,
        title="Legal Review",
        description="Review contract",
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )

    guest_context = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    service_response = GuestTicketAccessResponse(
        ticket_id=str(ticket_id),
        title="Legal Review",
        description="Review contract",
        priority="HIGH",
        status="OPEN",
        created_at=ticket.created_at,
        project_name=None,
        participant_email="guest@external.com",
        participant_role="Legal Counsel",
        access_expires_at=participant.expires_at,
    )

    db = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.routes.guest_access_routes.GuestAccessService"
        ) as mock_service,
        patch(
            "app.api.modules.v1.tickets.routes.guest_access_routes.success_response"
        ) as mock_success,
    ):
        mock_service.return_value.get_guest_ticket_access = AsyncMock(return_value=service_response)

        mock_success.return_value = {
            "status_code": status.HTTP_200_OK,
            "success": True,
            "message": "Guest access validated successfully",
            "data": service_response.model_dump(),
        }

        response = await get_guest_ticket_access(guest=guest_context, db=db)

        assert response["status_code"] == status.HTTP_200_OK
        assert response["data"]["priority"] == "HIGH"
        assert response["data"]["status"] == "OPEN"
