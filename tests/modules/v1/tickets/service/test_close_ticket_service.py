from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import AlreadyExistsError, PermissionDeniedError
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import TicketCloseRequest
from app.api.modules.v1.tickets.service.close_ticket_service import TicketService
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_service_close_ticket_success():
    """Test successful ticket closing."""
    ticket_id = uuid4()
    user_id = uuid4()
    organization_id = uuid4()
    project_id = uuid4()

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1003,
        organization_id=organization_id,
        project_id=project_id,
        status=TicketStatus.OPEN,
        description="Initial description",
    )

    user = User(id=user_id)

    db = AsyncMock()

    db.execute.side_effect = [
        Mock(scalar_one_or_none=Mock(return_value=ticket)),
        Mock(scalar_one_or_none=Mock(return_value=user)),
    ]

    with (
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.TenantGuard.get_membership",
            new=AsyncMock(),
        ),
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.check_user_permission",
            new=AsyncMock(return_value=True),
        ),
    ):
        service = TicketService(db)

        result = await service.close_ticket(
            ticket_id=ticket_id,
            user_id=user_id,
            close_data=TicketCloseRequest(closing_notes="Resolved"),
        )

    assert result.status == TicketStatus.CLOSED
    assert result.closed_at is not None
    assert "Resolved" in result.description
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_close_ticket_already_closed():
    ticket = Ticket(
        id=uuid4(),
        ticket_number=1004,
        status=TicketStatus.CLOSED,
        organization_id=uuid4(),
        project_id=uuid4(),
    )

    user = User(id=uuid4())

    db = AsyncMock()

    db.execute.side_effect = [
        Mock(scalar_one_or_none=Mock(return_value=ticket)),
        Mock(scalar_one_or_none=Mock(return_value=user)),
    ]

    with (
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.TenantGuard.get_membership",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.check_user_permission",
            new=AsyncMock(return_value=True),
        ),
    ):
        service = TicketService(db)

        with pytest.raises(AlreadyExistsError):
            await service.close_ticket(
                ticket_id=ticket.id,
                user_id=user.id,
                close_data=TicketCloseRequest(),
            )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_close_ticket_permission_denied():
    """Test closing a ticket without sufficient permissions."""
    ticket = Ticket(
        id=uuid4(),
        ticket_number=1005,
        status=TicketStatus.OPEN,
        organization_id=uuid4(),
        project_id=uuid4(),
    )

    user = User(id=uuid4())

    db = AsyncMock()
    db.execute.side_effect = [
        Mock(scalar_one_or_none=Mock(return_value=ticket)),
        Mock(scalar_one_or_none=Mock(return_value=user)),
    ]

    with (
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.TenantGuard.get_membership",
            new=AsyncMock(),
        ),
        patch(
            "app.api.modules.v1.tickets.service.close_ticket_service.check_user_permission",
            new=AsyncMock(return_value=False),
        ),
    ):
        service = TicketService(db)

        with pytest.raises(PermissionDeniedError):
            await service.close_ticket(
                ticket_id=ticket.id,
                user_id=user.id,
                close_data=TicketCloseRequest(),
            )

    db.rollback.assert_awaited_once()
