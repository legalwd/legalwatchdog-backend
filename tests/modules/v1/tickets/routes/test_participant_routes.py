import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import NotFoundError, PermissionDeniedError
from app.api.modules.v1.tickets.routes.participant_routes import (
    get_ticket_participants,
    invite_participants,
)
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    ExternalParticipantDetail,
    InternalParticipantDetail,
    InviteParticipantsRequest,
    TicketParticipantsResponse,
)
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_invite_participants_ticket_not_found():
    """Test inviting participants to a non-existent ticket."""
    ticket_id = uuid.uuid4()
    current_user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin",
    )

    payload = InviteParticipantsRequest(emails=["test@example.com"])

    with patch(
        "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.invite_participants = AsyncMock(
            side_effect=NotFoundError(
                message="The ticket you're trying to add participants to doesn't exist."
            )
        )

        with pytest.raises(NotFoundError):
            await invite_participants(
                ticket_id=ticket_id,
                payload=payload,
                current_user=current_user,
                db=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_invite_participants_no_permission():
    """Test inviting participants when user lacks permission."""
    ticket_id = uuid.uuid4()
    current_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        name="User",
    )

    payload = InviteParticipantsRequest(emails=["test@example.com"])

    with patch(
        "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.invite_participants = AsyncMock(
            side_effect=PermissionDeniedError(
                message="You don't have permission to invite participants."
            )
        )

        with pytest.raises(PermissionDeniedError):
            await invite_participants(
                ticket_id=ticket_id,
                payload=payload,
                current_user=current_user,
                db=AsyncMock(),
                client=None,
            )

        mock_service.invite_participants.assert_called_once_with(
            ticket_id=ticket_id,
            emails=payload.emails,
            current_user_id=current_user.id,
            client=None,
        )


@pytest.mark.asyncio
async def test_get_ticket_participants_success():
    """Test retrieving ticket participants successfully."""
    from datetime import datetime, timedelta, timezone

    ticket_id = uuid.uuid4()
    current_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        name="Test User",
    )

    mock_response = TicketParticipantsResponse(
        internal_participants=[
            InternalParticipantDetail(
                user_id=str(uuid.uuid4()),
                name="Internal User",
                email="internal@example.com",
                status="online",
                invited_at=datetime.now(timezone.utc),
            )
        ],
        external_participants=[
            ExternalParticipantDetail(
                participant_id=str(uuid.uuid4()),
                name="Guest",
                email="external@example.com",
                role="Viewer",
                status="offline",
                invited_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
        ],
    )

    with patch(
        "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.get_ticket_participants = AsyncMock(return_value=mock_response)

        await get_ticket_participants(
            ticket_id=ticket_id,
            user_or_guest=current_user,
            db=AsyncMock(),
        )

        mock_service.get_ticket_participants.assert_called_once_with(
            ticket_id=ticket_id,
            user_or_guest=current_user,
        )


@pytest.mark.asyncio
async def test_get_ticket_participants_ticket_not_found():
    """Test retrieving participants for a non-existent ticket."""
    ticket_id = uuid.uuid4()
    current_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        name="Test User",
    )

    with patch(
        "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.get_ticket_participants = AsyncMock(
            side_effect=NotFoundError(message="Ticket not found")
        )

        with pytest.raises(NotFoundError):
            await get_ticket_participants(
                ticket_id=ticket_id,
                user_or_guest=current_user,
                db=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_get_ticket_participants_permission_denied():
    """Test retrieving participants when user lacks permission."""
    ticket_id = uuid.uuid4()
    current_user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        name="Test User",
    )

    with patch(
        "app.api.modules.v1.tickets.routes.participant_routes.ParticipantService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.get_ticket_participants = AsyncMock(
            side_effect=PermissionDeniedError(
                message="You don't have permission to view participants for this ticket"
            )
        )

        with pytest.raises(PermissionDeniedError):
            await get_ticket_participants(
                ticket_id=ticket_id,
                user_or_guest=current_user,
                db=AsyncMock(),
            )
