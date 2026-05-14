import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.service.guest_access_service import (
    GuestAccessService,
)


@pytest.mark.asyncio
async def test_guest_access_service_success():
    """Service correctly maps ticket and participant data"""
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()
    org_id = uuid.uuid4()

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
        ticket_number=1001,
        title="Legal Review Required",
        description="Review contract",
        priority=TicketPriority.HIGH,
        status=TicketStatus.OPEN,
        organization_id=org_id,
        created_at=datetime.now(timezone.utc),
    )

    ticket.project = MagicMock()
    ticket.project.title = "Contract Management"

    guest = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    service = GuestAccessService(db=MagicMock(spec=AsyncSession))

    result = await service.get_guest_ticket_access(guest)

    assert result.ticket_id == str(ticket_id)
    assert result.priority == "HIGH"
    assert result.project_name == "Contract Management"
    assert result.participant_email == "guest@external.com"


@pytest.mark.asyncio
async def test_guest_access_service_without_project():
    """Service handles ticket without project"""
    ticket_id = uuid.uuid4()
    participant_id = uuid.uuid4()

    participant = ExternalParticipant(
        id=participant_id,
        ticket_id=ticket_id,
        email="guest@external.com",
        role="Consultant",
        is_active=True,
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1002,
        title="Standalone Ticket",
        description="No project",
        priority=TicketPriority.MEDIUM,
        status=TicketStatus.OPEN,
        created_at=datetime.now(timezone.utc),
    )
    ticket.project = None

    guest = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": str(participant_id), "ticket_id": str(ticket_id)},
    )

    service = GuestAccessService(db=MagicMock())

    result = await service.get_guest_ticket_access(guest)

    assert result.project_name is None


@pytest.mark.asyncio
async def test_guest_access_service_raises_processing_error():
    """Service wraps unexpected errors in ProcessingError"""
    participant = MagicMock()
    participant.id = uuid.uuid4()
    participant.email = "guest@external.com"

    ticket = MagicMock()
    ticket.id = uuid.uuid4()
    ticket.title = "Bad Ticket"

    type(ticket).priority = property(lambda self: (_ for _ in ()).throw(ValueError("Boom")))

    guest = GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload={"sub": "x", "ticket_id": "y"},
    )

    service = GuestAccessService(db=MagicMock())

    with pytest.raises(ProcessingError) as exc:
        await service.get_guest_ticket_access(guest)

    assert "Failed to load ticket" in str(exc.value)
