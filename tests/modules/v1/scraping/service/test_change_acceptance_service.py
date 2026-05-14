"""Tests for ChangeAcceptanceService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    ChangeAlreadyAcceptedError,
    JurisdictionChangeNotFoundError,
    ProcessingError,
)
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.service.change_acceptance_service import (
    ChangeAcceptanceService,
)


class MockExecuteResult:
    """Mock class to simulate db.execute() behavior."""

    def __init__(self, scalar_one_or_none_value=None):
        self.scalar_one_or_none_value = scalar_one_or_none_value

    def scalar_one_or_none(self):
        return self.scalar_one_or_none_value


@pytest.mark.asyncio
@patch(
    "app.api.modules.v1.scraping.service.change_acceptance_service.AsyncJurisdictionStateService"
)
@patch("app.api.modules.v1.scraping.service.change_acceptance_service.check_user_permission")
async def test_accept_change_success(mock_check_permission, MockStateServiceCls):
    """Test successfully accepting a jurisdiction change."""
    mock_check_permission.return_value = True

    mock_state_svc = AsyncMock()
    mock_state_svc.get_jurisdiction_state.return_value = {}
    mock_state_svc.update_or_create_field.return_value = AsyncMock()
    MockStateServiceCls.return_value = mock_state_svc

    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="applicable_services",
        old_value="accommodation only",
        new_value="accommodation, dining, and events",
        change_description="applicable_services changed",
        change_index=0,
        ticket_created=False,
        change_accepted=False,
    )

    mock_job = AsyncMock()
    mock_job.id = job_id
    mock_job.jurisdiction_id = jurisdiction_id

    mock_jurisdiction = AsyncMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.project_id = project_id

    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_db.execute.side_effect = [
        MockExecuteResult(scalar_one_or_none_value=mock_change),
        MockExecuteResult(scalar_one_or_none_value=mock_job),
        MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction),
        MockExecuteResult(scalar_one_or_none_value=mock_project),
    ]

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    service = ChangeAcceptanceService(mock_db)
    result = await service.accept_change(change_id=change_id, user_id=user_id)

    assert result.change_accepted is True
    assert result.accepted_by_user_id == user_id
    assert result.accepted_at is not None
    assert isinstance(result.accepted_at, datetime)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()
    mock_state_svc.get_jurisdiction_state.assert_called_once_with(jurisdiction_id)
    mock_state_svc.update_or_create_field.assert_called_once()


@pytest.mark.asyncio
async def test_accept_change_not_found():
    """Test accepting a non-existent change raises JurisdictionChangeNotFoundError."""
    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_db.execute.return_value = MockExecuteResult(scalar_one_or_none_value=None)
    mock_db.rollback = AsyncMock()

    service = ChangeAcceptanceService(mock_db)

    with pytest.raises(JurisdictionChangeNotFoundError):
        await service.accept_change(change_id=change_id, user_id=user_id)

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_accept_change_already_accepted():
    """Test accepting an already-accepted change raises ChangeAlreadyAcceptedError."""
    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=False,
        change_accepted=True,
        accepted_at=datetime.now(timezone.utc),
        accepted_by_user_id=uuid.uuid4(),
    )

    mock_db.execute.return_value = MockExecuteResult(scalar_one_or_none_value=mock_change)
    mock_db.rollback = AsyncMock()

    service = ChangeAcceptanceService(mock_db)

    with pytest.raises(ChangeAlreadyAcceptedError):
        await service.accept_change(change_id=change_id, user_id=user_id)

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_accept_change_database_error():
    """Test database error during accept_change raises ProcessingError."""
    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_db.execute.side_effect = Exception("Database connection error")
    mock_db.rollback = AsyncMock()

    service = ChangeAcceptanceService(mock_db)

    with pytest.raises(ProcessingError) as exc_info:
        await service.accept_change(change_id=change_id, user_id=user_id)

    assert "Failed to accept jurisdiction change" in str(exc_info.value.message)
    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.modules.v1.scraping.service.change_acceptance_service.check_user_permission")
async def test_accept_change_commit_error(mock_check_permission):
    """Test commit error during accept_change raises ProcessingError."""
    mock_check_permission.return_value = True
    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=False,
        change_accepted=False,
    )

    mock_job = AsyncMock()
    mock_job.id = job_id
    mock_job.jurisdiction_id = jurisdiction_id

    mock_jurisdiction = AsyncMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.project_id = project_id

    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_db.execute.side_effect = [
        MockExecuteResult(scalar_one_or_none_value=mock_change),
        MockExecuteResult(scalar_one_or_none_value=mock_job),
        MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction),
        MockExecuteResult(scalar_one_or_none_value=mock_project),
    ]

    mock_db.commit.side_effect = Exception("Commit failed")
    mock_db.rollback = AsyncMock()

    service = ChangeAcceptanceService(mock_db)

    with pytest.raises(ProcessingError):
        await service.accept_change(change_id=change_id, user_id=user_id)

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.modules.v1.scraping.service.change_acceptance_service.check_user_permission")
async def test_accept_change_updates_timestamp(mock_check_permission):
    """Test that accept_change sets accepted_at timestamp correctly."""
    mock_check_permission.return_value = True
    mock_db = AsyncMock()
    change_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()

    before_time = datetime.now(timezone.utc)

    mock_change = JurisdictionChange(
        id=change_id,
        jurisdiction_scrape_job_id=job_id,
        field_name="test_field",
        change_description="test change",
        change_index=0,
        ticket_created=False,
        change_accepted=False,
    )

    mock_job = AsyncMock()
    mock_job.id = job_id
    mock_job.jurisdiction_id = jurisdiction_id

    mock_jurisdiction = AsyncMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.project_id = project_id

    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_db.execute.side_effect = [
        MockExecuteResult(scalar_one_or_none_value=mock_change),
        MockExecuteResult(scalar_one_or_none_value=mock_job),
        MockExecuteResult(scalar_one_or_none_value=mock_jurisdiction),
        MockExecuteResult(scalar_one_or_none_value=mock_project),
    ]

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    service = ChangeAcceptanceService(mock_db)
    result = await service.accept_change(change_id=change_id, user_id=user_id)

    after_time = datetime.now(timezone.utc)

    assert result.accepted_at is not None
    assert before_time <= result.accepted_at <= after_time
