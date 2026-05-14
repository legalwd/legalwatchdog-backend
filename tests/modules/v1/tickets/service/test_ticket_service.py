import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate
from app.api.modules.v1.tickets.service.ticket_service import TicketService


@pytest.mark.asyncio
async def test_create_manual_ticket_success():
    """Test successful manual ticket creation."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    source_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.jurisdiction_id = jurisdiction_id
    mock_source.jurisdiction = MagicMock()
    mock_source.jurisdiction.id = jurisdiction_id
    mock_source.jurisdiction.project = MagicMock(id=project_id, org_id=org_id)
    mock_source.name = "Test Source"
    mock_source.url = "https://source.test"

    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.source_id = source_id
    mock_revision.ai_summary = "AI Summary"
    mock_revision.content_hash = "abc123"
    from datetime import datetime

    mock_revision.scraped_at = datetime(2026, 1, 3, 10, 0, 0)
    mock_revision.ai_confidence_score = 0.75

    mock_change_diff = MagicMock()
    mock_change_diff.diff_id = uuid.uuid4()
    mock_change_diff.ai_confidence = 0.9
    mock_change_diff.diff_patch = "patch text"

    source_result = MagicMock()
    source_result.scalar_one_or_none = MagicMock(return_value=mock_source)

    revision_result = MagicMock()
    revision_result.scalar_one_or_none = MagicMock(return_value=mock_revision)

    change_diff_result = MagicMock()
    change_diff_result.scalar_one_or_none = MagicMock(return_value=mock_change_diff)

    user_org_result = MagicMock()
    user_org_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=True)))

    sequence_result = MagicMock()
    sequence_result.scalar = MagicMock(return_value=1001)

    update_result = MagicMock()

    mock_db.execute = AsyncMock(
        side_effect=[
            source_result,
            user_org_result,
            revision_result,
            change_diff_result,
            sequence_result,
            update_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with (
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_project_user_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        service = TicketService(db=mock_db)
        ticket_data = TicketCreate(source_id=source_id, revision_id=revision_id, priority=None)
        ticket = await service.create_manual_ticket(data=ticket_data, user_id=user_id)

    assert ticket is not None
    mock_db.add.assert_called()
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_get_tickets_by_source_success():
    """Test fetching tickets by source."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    source_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.jurisdiction_id = jurisdiction_id
    mock_source.jurisdiction = MagicMock()
    mock_source.jurisdiction.project_id = project_id
    mock_source.jurisdiction.project = MagicMock(id=project_id, org_id=org_id)

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.project_id = project_id

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=1)

    mock_ticket = MagicMock()
    mock_ticket.id = uuid.uuid4()
    mock_ticket.ticket_number = 1014
    tickets_result = MagicMock()
    tickets_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[mock_ticket]))
    )

    source_result = MagicMock()
    source_result.scalar_one_or_none = MagicMock(return_value=mock_source)

    jurisdiction_result = MagicMock()
    jurisdiction_result.scalar_one_or_none = MagicMock(return_value=mock_jurisdiction)

    project_result = MagicMock()
    project_result.scalar_one_or_none = MagicMock(return_value=mock_project)

    mock_db.execute = AsyncMock(
        side_effect=[
            source_result,
            jurisdiction_result,
            project_result,
            count_result,
            tickets_result,
        ]
    )

    with (
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_project_user_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        service = TicketService(db=mock_db)
        tickets, total = await service.get_tickets(source_id=source_id, user_id=user_id)

    assert tickets == [mock_ticket]
    assert total == 1
