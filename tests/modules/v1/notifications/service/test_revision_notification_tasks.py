import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)


def _make_session_patch(mock_session):
    """Return a MagicMock that acts as an async context manager yielding mock_session."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


@pytest.mark.asyncio
async def test_send_revision_notifications_creates_and_sends_email():
    """Test that send_revision_notifications creates a notification and sends an email
    when no prior notification exists for the user and revision.
    """
    revision_id = str(uuid.uuid4())

    mock_session = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.get_isolated_async_session",
            return_value=_make_session_patch(mock_session),
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.get_event_publisher",
            new_callable=AsyncMock,
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.build_notification_events",
            return_value=[],
        ),
    ):
        mock_revision = MagicMock()
        mock_revision.id = revision_id
        mock_revision.source_id = uuid.uuid4()
        mock_revision.ai_summary = "AI summary text"

        mock_source = MagicMock()
        mock_source.id = uuid.uuid4()
        mock_source.name = "Test Source"
        mock_source.jurisdiction_id = uuid.uuid4()

        mock_jurisdiction = MagicMock()
        mock_jurisdiction.id = uuid.uuid4()
        mock_jurisdiction.project_id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.organization_id = uuid.uuid4()

        mock_project_user = MagicMock()
        mock_project_user.user_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.id = mock_project_user.user_id
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"

        mock_revision.source = mock_source
        mock_source.jurisdiction = mock_jurisdiction
        mock_jurisdiction.project = mock_project
        mock_project_user.user = mock_user

        mock_revision_result = MagicMock()
        mock_revision_result.unique.return_value.scalar_one_or_none.return_value = mock_revision

        mock_project_users_result = MagicMock()
        mock_project_users_result.unique.return_value.scalars.return_value.all.return_value = [
            mock_project_user
        ]

        mock_change_diff = MagicMock()
        mock_change_diff.change_summary = "Change summary text"
        mock_change_diff.risk_level = "High"
        mock_change_diff_result = MagicMock()
        mock_change_diff_result.unique.return_value.scalar_one_or_none.return_value = (
            mock_change_diff
        )

        mock_ticket = MagicMock()
        mock_ticket.id = uuid.uuid4()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalars.return_value.first.return_value = mock_ticket

        mock_existing_result = MagicMock()
        mock_existing_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_revision_result,
                mock_project_users_result,
                mock_change_diff_result,
                mock_ticket_result,
                mock_existing_result,
            ]
        )

        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.add_all = MagicMock()

        with patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.revision_notification_task import (
                send_revision_notifications,
            )

            await send_revision_notifications(revision_id)

            assert mock_send_email.await_count == 1

            mock_session.add_all.assert_called()
            mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_send_revision_notifications_sends():
    """Test that send_revision_notifications sends notifications."""
    revision_id = str(uuid.uuid4())

    mock_session = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.get_isolated_async_session",
            return_value=_make_session_patch(mock_session),
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.get_event_publisher",
            new_callable=AsyncMock,
        ),
        patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.build_notification_events",
            return_value=[],
        ),
    ):
        mock_revision = MagicMock()
        mock_revision.id = revision_id
        mock_revision.source_id = uuid.uuid4()
        mock_revision.ai_summary = "AI summary text"

        mock_source = MagicMock()
        mock_source.id = uuid.uuid4()
        mock_source.name = "Test Source"
        mock_source.jurisdiction_id = uuid.uuid4()

        mock_jurisdiction = MagicMock()
        mock_jurisdiction.id = uuid.uuid4()
        mock_jurisdiction.project_id = uuid.uuid4()

        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.organization_id = uuid.uuid4()

        mock_project_user = MagicMock()
        mock_project_user.user_id = uuid.uuid4()

        mock_user = MagicMock()
        mock_user.id = mock_project_user.user_id
        mock_user.email = "u@test.com"
        mock_user.name = "Test User"

        mock_revision.source = mock_source
        mock_source.jurisdiction = mock_jurisdiction
        mock_jurisdiction.project = mock_project
        mock_project_user.user = mock_user

        mock_existing_notification = Notification(
            revision_id=UUID(revision_id),
            user_id=mock_user.id,
            message="Old msg",
            status=NotificationStatus.SENT,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        mock_revision_result = MagicMock()
        mock_revision_result.unique.return_value.scalar_one_or_none.return_value = mock_revision

        mock_project_users_result = MagicMock()
        mock_project_users_result.unique.return_value.scalars.return_value.all.return_value = [
            mock_project_user
        ]

        mock_change_diff = MagicMock()
        mock_change_diff.change_summary = "Change summary text"
        mock_change_diff.risk_level = "High"
        mock_change_diff_result = MagicMock()
        mock_change_diff_result.unique.return_value.scalar_one_or_none.return_value = (
            mock_change_diff
        )

        mock_ticket = MagicMock()
        mock_ticket.id = uuid.uuid4()
        mock_ticket_result = MagicMock()
        mock_ticket_result.scalars.return_value.first.return_value = mock_ticket

        mock_existing_result = MagicMock()
        mock_existing_result.scalars.return_value.all.return_value = [mock_existing_notification]

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_revision_result,
                mock_project_users_result,
                mock_change_diff_result,
                mock_ticket_result,
                mock_existing_result,
            ]
        )

        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.add_all = MagicMock()

        with patch(
            "app.api.modules.v1.notifications.service.revision_notification_task.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send_email:
            from app.api.modules.v1.notifications.service.revision_notification_task import (
                send_revision_notifications,
            )

            await send_revision_notifications(revision_id)

            mock_send_email.assert_called_once()
            mock_session.add_all.assert_called()
            # Note: commit is still called even when skipping notifications
            # because the code structure commits after the loop
