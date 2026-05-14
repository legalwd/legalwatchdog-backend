import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest


def _make_session_patch(mock_session):
    """Return a MagicMock that acts as an async context manager yielding mock_session."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


@pytest.mark.asyncio
async def test_send_internal_user_notification_creates_and_sends_email():
    """Test that send_internal_user_notification sends an email to an internal user."""
    ticket_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        mock_ticket = MagicMock()
        mock_ticket.id = UUID(ticket_id)
        mock_ticket.title = "Test Ticket"
        mock_ticket.description = "Test Description"
        mock_ticket.priority = "High"
        mock_ticket.status = "OPEN"

        mock_org = MagicMock()
        mock_org.name = "Test Organization"

        mock_project = MagicMock()
        mock_project.title = "Test Project"

        mock_ticket.organization = mock_org
        mock_ticket.project = mock_project

        mock_user = MagicMock()
        mock_user.id = UUID(user_id)
        mock_user.email = "user@example.com"
        mock_user.name = "Test User"

        mock_invited_by_user = MagicMock()
        mock_invited_by_user.id = UUID(invited_by_user_id)
        mock_invited_by_user.email = "inviter@example.com"
        mock_invited_by_user.name = "Inviter User"

        mock_ticket_result = MagicMock()
        mock_ticket_result.unique.return_value.scalar_one_or_none.return_value = mock_ticket

        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_invited_by_result = MagicMock()
        mock_invited_by_result.scalar_one_or_none.return_value = mock_invited_by_user

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_ticket_result,
                mock_user_result,
                mock_invited_by_result,
            ]
        )

        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_internal_user_notification,
            )

            await send_internal_user_notification(ticket_id, user_id, invited_by_user_id)

            assert mock_send_email.await_count == 1

            call_args = mock_send_email.await_args
            assert call_args[1]["template_name"] == "internal_user_ticket_notification.html"
            assert call_args[1]["recipient"] == "user@example.com"

            context = call_args[1]["context"]
            assert context["ticket_title"] == "Test Ticket"
            assert context["is_internal"] is True


@pytest.mark.asyncio
async def test_send_internal_user_notification_ticket_not_found():
    """Test that send_internal_user_notification handles missing ticket gracefully."""
    ticket_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        mock_ticket_result = MagicMock()
        mock_ticket_result.unique.return_value.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_ticket_result)

        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_internal_user_notification,
            )

            await send_internal_user_notification(ticket_id, user_id, invited_by_user_id)

            assert mock_send_email.await_count == 0


@pytest.mark.asyncio
async def test_send_external_participant_notification_creates_and_sends_email():
    """Test that send_external_participant_notification sends an email to external participant."""
    ticket_id = str(uuid.uuid4())
    participant_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())
    magic_link = "https://example.com/guest/access?token=xyz123"

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        mock_ticket = MagicMock()
        mock_ticket.id = UUID(ticket_id)
        mock_ticket.title = "Test Ticket"
        mock_ticket.description = "Test Description"
        mock_ticket.priority = "High"
        mock_ticket.status = "OPEN"

        mock_org = MagicMock()
        mock_org.name = "Test Organization"

        mock_project = MagicMock()
        mock_project.title = "Test Project"

        mock_ticket.organization = mock_org
        mock_ticket.project = mock_project

        mock_participant = MagicMock()
        mock_participant.id = UUID(participant_id)
        mock_participant.email = "external@example.com"
        mock_participant.role = "Guest"
        mock_participant.expires_at = datetime.now(timezone.utc) + timedelta(days=2)

        mock_invited_by_user = MagicMock()
        mock_invited_by_user.id = UUID(invited_by_user_id)
        mock_invited_by_user.email = "inviter@example.com"
        mock_invited_by_user.name = "Inviter User"

        mock_ticket_result = MagicMock()
        mock_ticket_result.unique.return_value.scalar_one_or_none.return_value = mock_ticket

        mock_participant_result = MagicMock()
        mock_participant_result.scalar_one_or_none.return_value = mock_participant

        mock_invited_by_result = MagicMock()
        mock_invited_by_result.scalar_one_or_none.return_value = mock_invited_by_user

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_ticket_result,
                mock_participant_result,
                mock_invited_by_result,
            ]
        )

        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_external_participant_notification,
            )

            await send_external_participant_notification(
                ticket_id, participant_id, invited_by_user_id, magic_link
            )

            assert mock_send_email.await_count == 1

            call_args = mock_send_email.await_args
            assert call_args[1]["template_name"] == "external_participant_invitation.html"
            assert call_args[1]["recipient"] == "external@example.com"

            context = call_args[1]["context"]
            assert context["ticket_title"] == "Test Ticket"
            assert context["magic_link"] == magic_link
            assert context["is_external"] is True
            assert context["recipient_role"] == "Guest"


@pytest.mark.asyncio
async def test_send_external_participant_notification_participant_not_found():
    """Test that send_external_participant_notification handles missing participant gracefully."""
    ticket_id = str(uuid.uuid4())
    participant_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())
    magic_link = "https://example.com/guest/access?token=xyz123"

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        mock_ticket = MagicMock()
        mock_ticket.id = UUID(ticket_id)

        mock_participant_result = MagicMock()
        mock_participant_result.scalar_one_or_none.return_value = None

        mock_ticket_result = MagicMock()
        mock_ticket_result.unique.return_value.scalar_one_or_none.return_value = mock_ticket

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_ticket_result,
                mock_participant_result,
            ]
        )

        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_external_participant_notification,
            )

            await send_external_participant_notification(
                ticket_id, participant_id, invited_by_user_id, magic_link
            )

            assert mock_send_email.await_count == 0


@pytest.mark.asyncio
async def test_send_internal_user_notification_invalid_uuid():
    """Test that send_internal_user_notification handles invalid UUID format gracefully."""
    ticket_id = "invalid-uuid"
    user_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_internal_user_notification,
            )

            await send_internal_user_notification(ticket_id, user_id, invited_by_user_id)

            assert mock_send_email.await_count == 0

            mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_send_external_participant_notification_with_no_expires_at():
    """Test that send_external_participant_notification handles missing expires_at gracefully."""
    ticket_id = str(uuid.uuid4())
    participant_id = str(uuid.uuid4())
    invited_by_user_id = str(uuid.uuid4())
    magic_link = "https://example.com/guest/access?token=xyz123"

    mock_session = AsyncMock()

    with patch(
        "app.api.modules.v1.notifications.service.participant_notification_task.get_isolated_async_session",
        return_value=_make_session_patch(mock_session),
    ):
        mock_ticket = MagicMock()
        mock_ticket.id = UUID(ticket_id)
        mock_ticket.title = "Test Ticket"
        mock_ticket.description = "Test Description"
        mock_ticket.priority = "High"
        mock_ticket.status = "OPEN"

        mock_org = MagicMock()
        mock_org.name = "Test Organization"

        mock_project = MagicMock()
        mock_project.title = "Test Project"

        mock_ticket.organization = mock_org
        mock_ticket.project = mock_project

        mock_participant = MagicMock()
        mock_participant.id = UUID(participant_id)
        mock_participant.email = "external@example.com"
        mock_participant.role = "Guest"
        mock_participant.expires_at = None

        mock_invited_by_user = MagicMock()
        mock_invited_by_user.id = UUID(invited_by_user_id)
        mock_invited_by_user.email = "inviter@example.com"
        mock_invited_by_user.name = "Inviter User"

        mock_ticket_result = MagicMock()
        mock_ticket_result.unique.return_value.scalar_one_or_none.return_value = mock_ticket

        mock_participant_result = MagicMock()
        mock_participant_result.scalar_one_or_none.return_value = mock_participant

        mock_invited_by_result = MagicMock()
        mock_invited_by_result.scalar_one_or_none.return_value = mock_invited_by_user

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_ticket_result,
                mock_participant_result,
                mock_invited_by_result,
            ]
        )

        with patch(
            "app.api.modules.v1.notifications.service.participant_notification_task.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.participant_notification_task import (
                send_external_participant_notification,
            )

            await send_external_participant_notification(
                ticket_id, participant_id, invited_by_user_id, magic_link
            )

            assert mock_send_email.await_count == 1

            call_args = mock_send_email.await_args
            context = call_args[1]["context"]
            assert context["expires_at"] == ""
