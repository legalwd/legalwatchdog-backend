"""Tests for per-change ticket creation in TicketService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    ChangeAlreadyHasTicketError,
    JurisdictionChangeNotFoundError,
    PermissionDeniedError,
)
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate
from app.api.modules.v1.tickets.service.ticket_service import TicketService


class MockExecuteResult:
    """Mock class to simulate db.execute() behavior."""

    def __init__(self, scalar_one_or_none_value=None, scalar_value=None):
        self.scalar_one_or_none_value = scalar_one_or_none_value
        self.scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self.scalar_one_or_none_value

    def scalar(self):
        return self.scalar_value


def setup_standard_mocks(jurisdiction_id, job_id, change_id=None, org_id=None, project_id=None):
    """Helper to set up standard mock objects for tests."""
    mock_project = MagicMock()
    mock_project.id = project_id if project_id else uuid.uuid4()
    mock_project.org_id = org_id if org_id else uuid.uuid4()

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.name = "Test Jurisdiction"
    mock_jurisdiction.project_id = mock_project.id
    mock_jurisdiction.project = mock_project

    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.jurisdiction_id = jurisdiction_id
    mock_job.status = JurisdictionScrapeJobStatus.COMPLETED
    mock_job.completed_at = datetime.now(timezone.utc)

    return mock_project, mock_jurisdiction, mock_job


@pytest.mark.asyncio
async def test_create_per_change_ticket_success():
    """Test creating a ticket for a specific jurisdiction change."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    change_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, change_id, org_id, project_id
    )

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="applicable_services",
        old_value="accommodation only",
        new_value="accommodation, dining, and events",
        change_description=(
            "applicable_services changed: accommodation only → accommodation, dining, and events"
        ),
        change_index=0,
        ticket_created=False,
        change_accepted=False,
    )

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)
    sequence_result = MockExecuteResult(scalar_value=1001)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
        sequence_result,
    ]

    mock_db.get.side_effect = lambda model, id: {
        (JurisdictionChange, change_id): mock_change,
    }.get((model, id))

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        jurisdiction_change_id=change_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        ticket = await service._create_jurisdiction_ticket(ticket_data, user_id)

    assert ticket.title == f"[{mock_jurisdiction.name}] applicable_services Change"
    assert ticket.jurisdiction_change_id == change_id
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_create_per_change_ticket_change_not_found():
    """Test creating ticket for non-existent change raises JurisdictionChangeNotFoundError."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    change_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, change_id, org_id, project_id
    )

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
    ]

    mock_db.get.side_effect = lambda model, id: {
        (JurisdictionChange, change_id): None,
    }.get((model, id))

    mock_db.rollback = AsyncMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        jurisdiction_change_id=change_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(JurisdictionChangeNotFoundError):
            await service._create_jurisdiction_ticket(ticket_data, user_id)

    mock_db.rollback.assert_called()


@pytest.mark.asyncio
async def test_create_per_change_ticket_already_has_ticket():
    """Test creating ticket for change that already has ticket raises error."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    change_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, change_id, org_id, project_id
    )

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=True,
    )

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
    ]

    mock_db.get.side_effect = lambda model, id: {
        (JurisdictionChange, change_id): mock_change,
    }.get((model, id))

    mock_db.rollback = AsyncMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        jurisdiction_change_id=change_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(ChangeAlreadyHasTicketError):
            await service._create_jurisdiction_ticket(ticket_data, user_id)

    mock_db.rollback.assert_called()


@pytest.mark.asyncio
async def test_create_per_change_ticket_wrong_job():
    """Test creating ticket for change from different job raises PermissionDeniedError."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    different_job_id = uuid.uuid4()
    change_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, change_id, org_id, project_id
    )

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=different_job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=False,
    )

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
    ]

    mock_db.get.side_effect = lambda model, id: {
        (JurisdictionChange, change_id): mock_change,
    }.get((model, id))

    mock_db.rollback = AsyncMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        jurisdiction_change_id=change_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(PermissionDeniedError) as exc_info:
            await service._create_jurisdiction_ticket(ticket_data, user_id)

    assert "doesn't belong to the specified job" in str(exc_info.value.message)
    mock_db.rollback.assert_called()


@pytest.mark.asyncio
async def test_create_per_change_ticket_updates_flag():
    """Test that creating a per-change ticket updates the ticket_created flag."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    change_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, change_id, org_id, project_id
    )

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=False,
    )

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)
    sequence_result = MockExecuteResult(scalar_value=1001)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
        sequence_result,
    ]

    mock_db.get.side_effect = lambda model, id: {
        (JurisdictionChange, change_id): mock_change,
    }.get((model, id))

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        jurisdiction_change_id=change_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        await service._create_jurisdiction_ticket(ticket_data, user_id)

    assert mock_change.ticket_created is True
    assert mock_db.add.call_count >= 2


@pytest.mark.asyncio
async def test_create_all_changes_ticket_backward_compatibility():
    """Test creating ticket for all changes (legacy behavior) still works."""
    mock_db = AsyncMock()
    user_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    job_id = uuid.uuid4()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    mock_project, mock_jurisdiction, mock_job = setup_standard_mocks(
        jurisdiction_id, job_id, None, org_id, project_id
    )

    mock_job.extracted_data = {
        "summary": "Changes detected",
        "changes": [
            {"field": "field1", "old_value": "old1", "new_value": "new1"},
            {"field": "field2", "old_value": "old2", "new_value": "new2"},
        ],
    }

    jurisdiction_result = MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction)
    org_membership_result = MockExecuteResult(scalar_one_or_none_value=True)
    job_result = MockExecuteResult(scalar_one_or_none_value=mock_job)
    sequence_result = MockExecuteResult(scalar_value=1001)

    mock_db.execute.side_effect = [
        jurisdiction_result,
        org_membership_result,
        job_result,
        sequence_result,
    ]

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()

    ticket_data = TicketCreate(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_scrape_job_id=job_id,
        organization_id=org_id,
        project_id=project_id,
    )

    service = TicketService(mock_db)

    with patch(
        "app.api.modules.v1.tickets.service.ticket_service.check_user_permission",
        new_callable=AsyncMock,
        return_value=True,
    ):
        ticket = await service._create_jurisdiction_ticket(ticket_data, user_id)

    assert ticket.title == f"[{mock_jurisdiction.name}] Jurisdiction Update - 2 Changes"
    assert ticket.jurisdiction_change_id is None
    mock_db.commit.assert_called()
