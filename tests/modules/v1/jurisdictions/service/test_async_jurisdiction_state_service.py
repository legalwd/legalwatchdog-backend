"""Tests for AsyncJurisdictionStateService."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.api.modules.v1.jurisdictions.models.jurisdiction_state import (
    JurisdictionState,
)
from app.api.modules.v1.jurisdictions.service.async_jurisdiction_state_service import (
    AsyncJurisdictionStateService,
)


class MockScalarsResult:
    """Mock for result.scalars().all() chain."""

    def __init__(self, items=None):
        self._items = items or []

    def scalars(self):
        return self

    def all(self):
        return self._items


@pytest.fixture
def mock_db():
    """Provide an async mock database session."""
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    """Provide an AsyncJurisdictionStateService instance."""
    return AsyncJurisdictionStateService(mock_db)


@pytest.mark.asyncio
async def test_get_jurisdiction_state_empty(service, mock_db):
    """Test get_jurisdiction_state returns empty dict when no states exist."""
    mock_db.execute.return_value = MockScalarsResult([])

    result = await service.get_jurisdiction_state(uuid.uuid4())

    assert result == {}
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_jurisdiction_state_with_data(service, mock_db):
    """Test get_jurisdiction_state returns field_key to state mapping."""
    jur_id = uuid.uuid4()
    state1 = JurisdictionState(
        id=uuid.uuid4(),
        jurisdiction_id=jur_id,
        field_key="min_wage",
        value="$15/hr",
    )
    state2 = JurisdictionState(
        id=uuid.uuid4(),
        jurisdiction_id=jur_id,
        field_key="overtime_rate",
        value="1.5x",
    )
    mock_db.execute.return_value = MockScalarsResult([state1, state2])

    result = await service.get_jurisdiction_state(jur_id)

    assert len(result) == 2
    assert result["min_wage"] is state1
    assert result["overtime_rate"] is state2


@pytest.mark.asyncio
async def test_update_or_create_field_creates_new(service, mock_db):
    """Test update_or_create_field creates state and history for new field."""
    jur_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    result = await service.update_or_create_field(
        jurisdiction_id=jur_id,
        field_key="min_wage",
        new_value="$16/hr",
        change_reason="Initial value",
        user_id=user_id,
        job_id=job_id,
    )

    assert result.jurisdiction_id == jur_id
    assert result.field_key == "min_wage"
    assert result.value == "$16/hr"
    assert result.confirmed_by_user_id == user_id
    assert result.originating_job_id == job_id
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_update_or_create_field_updates_existing(service, mock_db):
    """Test update_or_create_field updates existing state and creates history."""
    jur_id = uuid.uuid4()
    state_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    existing = JurisdictionState(
        id=state_id,
        jurisdiction_id=jur_id,
        field_key="min_wage",
        value="$15/hr",
        confirmed_at=datetime.now(timezone.utc),
    )

    result = await service.update_or_create_field(
        jurisdiction_id=jur_id,
        field_key="min_wage",
        new_value="$16/hr",
        change_reason="Rate increase",
        user_id=user_id,
        job_id=job_id,
        existing_state=existing,
    )

    assert result is existing
    assert result.value == "$16/hr"
    assert result.confirmed_by_user_id == user_id
    assert result.originating_job_id == job_id
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_update_or_create_field_skips_same_value(service, mock_db):
    """Test update_or_create_field returns existing when value is unchanged."""
    jur_id = uuid.uuid4()

    existing = JurisdictionState(
        id=uuid.uuid4(),
        jurisdiction_id=jur_id,
        field_key="min_wage",
        value="$15/hr",
        confirmed_at=datetime.now(timezone.utc),
    )

    result = await service.update_or_create_field(
        jurisdiction_id=jur_id,
        field_key="min_wage",
        new_value="$15/hr",
        change_reason="No change",
        existing_state=existing,
    )

    assert result is existing
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_or_create_field_with_source_evidence(service, mock_db):
    """Test update_or_create_field stores source evidence."""
    jur_id = uuid.uuid4()
    sources = ["https://gov.example.com/wages"]

    result = await service.update_or_create_field(
        jurisdiction_id=jur_id,
        field_key="min_wage",
        new_value="$16/hr",
        change_reason="Source update",
        source_evidence=sources,
    )

    assert result.source_evidence == sources
    assert mock_db.add.call_count == 2


@pytest.mark.asyncio
async def test_update_or_create_no_commit(service, mock_db):
    """Test that service never commits the transaction."""
    await service.update_or_create_field(
        jurisdiction_id=uuid.uuid4(),
        field_key="test_field",
        new_value="test_value",
        change_reason="test",
    )

    mock_db.commit.assert_not_called()
    mock_db.rollback.assert_not_called()
