import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    ForbiddenError,
    NotFoundError,
    PermissionDeniedError,
)
from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket, TicketStatus
from app.api.modules.v1.tickets.service.participant_service import ParticipantService
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_service_invite_participants_ticket_not_found():
    """Test inviting participants to a non-existent ticket."""
    db = MagicMock()
    db.rollback = AsyncMock()

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=ticket_result)

    service = ParticipantService(db)

    with pytest.raises(
        NotFoundError,
        match="ticket you're trying to add participants to doesn't exist",
    ):
        await service.invite_participants(
            ticket_id=uuid.uuid4(),
            emails=["test@example.com"],
            current_user_id=uuid.uuid4(),
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_invite_participants_no_permission():
    """Test inviting participants when user lacks permission."""
    db = MagicMock()
    db.rollback = AsyncMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1006,
        organization_id=org_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.organization = Organization(id=org_id, name="Test Org")
    ticket.external_participants = []
    ticket.internal_participants = []

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    user = User(id=user_id, email="user@example.com", name="User")
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    empty_users_result = MagicMock()
    empty_users_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[ticket_result, user_result, empty_users_result])

    with (
        patch("app.api.modules.v1.tickets.service.participant_service.TenantGuard") as mock_tenant,
        patch(
            "app.api.modules.v1.tickets.service.participant_service.check_user_permission"
        ) as mock_permission,
        patch(
            "app.api.modules.v1.tickets.service.participant_service.require_billing_access"
        ) as mock_billing,
    ):
        mock_billing.return_value = None

        tenant_instance = MagicMock()
        tenant_instance.get_membership = AsyncMock(return_value=True)
        mock_tenant.return_value = tenant_instance

        mock_permission.return_value = False

        service = ParticipantService(db)

        with pytest.raises(
            PermissionDeniedError,
            match="don't have permission",
        ):
            await service.invite_participants(
                ticket_id=ticket_id,
                emails=["test@example.com"],
                current_user_id=user_id,
            )

        db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_invite_participants_internal_user_not_in_project():
    """Test that internal users not in the project are added to not_in_project list."""
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    current_user_id = uuid.uuid4()
    internal_user_id = uuid.uuid4()

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1007,
        organization_id=org_id,
        project_id=project_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.organization = Organization(id=org_id, name="Test Org")
    ticket.external_participants = []
    ticket.internal_participants = []

    internal_user = User(
        id=internal_user_id,
        email="internal@example.com",
        name="Internal User",
        is_active=True,
        is_verified=True,
    )

    current_user = User(
        id=current_user_id,
        email="admin@example.com",
        name="Admin",
    )

    call_count = {"count": 0}

    async def mock_execute(stmt):
        call_count["count"] += 1
        result = MagicMock()

        if call_count["count"] == 1:
            result.scalar_one_or_none.return_value = ticket
        elif call_count["count"] == 2:
            result.scalar_one_or_none.return_value = current_user
        elif call_count["count"] == 3:
            result.scalars.return_value.all.return_value = [internal_user]
        elif call_count["count"] == 4:
            result.scalar_one_or_none.return_value = None

        return result

    db.execute = mock_execute

    with (
        patch("app.api.modules.v1.tickets.service.participant_service.TenantGuard") as mock_tenant,
        patch(
            "app.api.modules.v1.tickets.service.participant_service.check_user_permission"
        ) as mock_permission,
        patch(
            "app.api.modules.v1.tickets.service.participant_service.require_billing_access"
        ) as mock_billing,
    ):
        mock_billing.return_value = None

        tenant_instance = MagicMock()
        tenant_instance.get_membership = AsyncMock(return_value=True)
        mock_tenant.return_value = tenant_instance

        mock_permission.return_value = True

        service = ParticipantService(db)

        result = await service.invite_participants(
            ticket_id=ticket_id,
            emails=["internal@example.com"],
            current_user_id=current_user_id,
        )

    assert len(result.internal_users) == 0
    assert len(result.external_participants) == 0
    assert len(result.already_invited) == 0

    assert len(result.not_in_project) == 1
    assert "internal@example.com" in result.not_in_project

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_get_ticket_participants_success_with_view_tickets_permission():
    """Test getting ticket participants with VIEW_TICKETS permission."""
    db = MagicMock()
    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    internal_user_id = uuid.uuid4()
    external_participant_id = uuid.uuid4()

    current_user = User(id=user_id, email="admin@example.com", name="Admin")
    current_user.last_active = datetime.now(timezone.utc) - timedelta(minutes=2)

    internal_user = User(
        id=internal_user_id,
        email="internal@example.com",
        name="Internal User",
    )
    internal_user.last_active = datetime.now(timezone.utc) - timedelta(minutes=1)

    external_participant = ExternalParticipant(
        id=external_participant_id,
        email="external@example.com",
        ticket_id=ticket_id,
        role="viewer",
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    external_participant.last_accessed_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    # Create internal participant relationship
    internal_participant = MagicMock()
    internal_participant.user = internal_user
    internal_participant.invited_at = datetime.now(timezone.utc)

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1008,
        organization_id=org_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.internal_participants = [internal_participant]
    ticket.external_participants = [external_participant]

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    db.execute = AsyncMock(return_value=ticket_result)

    with patch(
        "app.api.modules.v1.tickets.service.participant_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        service = ParticipantService(db)
        result = await service.get_ticket_participants(
            ticket_id=ticket_id,
            user_or_guest=current_user,
        )

    assert len(result.internal_participants) == 1
    assert result.internal_participants[0].name == "Internal User"
    assert result.internal_participants[0].status == "online"

    assert len(result.external_participants) == 1
    assert result.external_participants[0].name == "Guest"
    assert result.external_participants[0].status == "offline"


@pytest.mark.asyncio
async def test_service_get_ticket_participants_success_as_project_member():
    """Test getting ticket participants as a project member."""
    db = MagicMock()
    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    current_user = User(id=user_id, email="member@example.com", name="Member")
    current_user.last_active = datetime.now(timezone.utc)

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1009,
        organization_id=org_id,
        project_id=project_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.internal_participants = []
    ticket.external_participants = []

    async def mock_execute(stmt):
        result = MagicMock()
        if not hasattr(mock_execute, "call_count"):
            mock_execute.call_count = 0
        mock_execute.call_count += 1

        if mock_execute.call_count == 1:
            result.scalar_one_or_none.return_value = ticket
        else:
            result.scalar_one_or_none.return_value = MagicMock()
        return result

    db.execute = mock_execute

    with patch(
        "app.api.modules.v1.tickets.service.participant_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=False,
    ):
        service = ParticipantService(db)
        result = await service.get_ticket_participants(
            ticket_id=ticket_id,
            user_or_guest=current_user,
        )

    assert len(result.internal_participants) == 0
    assert len(result.external_participants) == 0


@pytest.mark.asyncio
async def test_service_get_ticket_participants_success_as_guest():
    """Test getting ticket participants as an external guest."""
    db = MagicMock()
    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    external_participant_id = uuid.uuid4()

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1010,
        organization_id=org_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.internal_participants = []
    ticket.external_participants = []

    external_participant = ExternalParticipant(
        id=external_participant_id,
        email="guest@example.com",
        ticket_id=ticket_id,
        role="viewer",
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    guest_context = GuestContext(
        participant=external_participant,
        ticket=ticket,
        token_payload={},
    )

    ticket_result = MagicMock()
    ticket_result.scalar_one_or_none.return_value = ticket

    db.execute = AsyncMock(return_value=ticket_result)

    service = ParticipantService(db)
    result = await service.get_ticket_participants(
        ticket_id=ticket_id,
        user_or_guest=guest_context,
    )

    assert len(result.internal_participants) == 0
    assert len(result.external_participants) == 0


@pytest.mark.asyncio
async def test_service_get_ticket_participants_ticket_not_found():
    """Test getting participants for a non-existent ticket."""
    db = MagicMock()
    user_id = uuid.uuid4()

    current_user = User(id=user_id, email="user@example.com", name="User")

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    db.execute = mock_execute

    service = ParticipantService(db)

    with pytest.raises(NotFoundError, match="ticket you're trying to view doesn't exist"):
        await service.get_ticket_participants(
            ticket_id=uuid.uuid4(),
            user_or_guest=current_user,
        )


@pytest.mark.asyncio
async def test_service_get_ticket_participants_permission_denied():
    """Test getting participants when user lacks permission."""
    db = MagicMock()
    ticket_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    current_user = User(id=user_id, email="user@example.com", name="User")

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1011,
        organization_id=org_id,
        project_id=project_id,
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )
    ticket.internal_participants = []
    ticket.external_participants = []

    async def mock_execute(stmt):
        result = MagicMock()
        if not hasattr(mock_execute, "call_count"):
            mock_execute.call_count = 0
        mock_execute.call_count += 1

        if mock_execute.call_count == 1:
            result.scalar_one_or_none.return_value = ticket
        else:
            result.scalar_one_or_none.return_value = None
        return result

    db.execute = mock_execute

    with patch(
        "app.api.modules.v1.tickets.service.participant_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=False,
    ):
        service = ParticipantService(db)

        with pytest.raises((PermissionDeniedError, ForbiddenError)):
            await service.get_ticket_participants(
                ticket_id=ticket_id,
                user_or_guest=current_user,
            )


@pytest.mark.asyncio
async def test_service_get_ticket_participants_guest_wrong_ticket():
    """Test getting participants as a guest with wrong ticket_id."""
    db = MagicMock()
    ticket_id = uuid.uuid4()
    wrong_ticket_id = uuid.uuid4()
    external_participant_id = uuid.uuid4()

    ticket = Ticket(
        id=ticket_id,
        ticket_number=1012,
        organization_id=uuid.uuid4(),
        status=TicketStatus.OPEN,
        title="Test Ticket",
    )

    external_participant = ExternalParticipant(
        id=external_participant_id,
        email="guest@example.com",
        ticket_id=ticket_id,
        role="viewer",
        invited_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    guest_context = GuestContext(
        participant=external_participant,
        ticket=ticket,
        token_payload={},
    )

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = ticket
        return result

    db.execute = mock_execute

    service = ParticipantService(db)

    with pytest.raises(
        PermissionDeniedError,
        match="don't have permission to view these participants",
    ):
        await service.get_ticket_participants(
            ticket_id=wrong_ticket_id,
            user_or_guest=guest_context,
        )
