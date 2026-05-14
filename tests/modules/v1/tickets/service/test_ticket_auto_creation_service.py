"""
Unit tests for Auto Ticket Service
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.modules.v1.tickets.models.ticket_model import TicketPriority, TicketStatus
from app.api.modules.v1.tickets.service.ticket_auto_creation_service import TicketService


@pytest.mark.asyncio
async def test_map_risk_to_priority():
    """Test risk level mapping to ticket priority."""
    assert TicketService.map_risk_to_priority("CRITICAL") == TicketPriority.CRITICAL
    assert TicketService.map_risk_to_priority("HIGH") == TicketPriority.HIGH
    assert TicketService.map_risk_to_priority("MEDIUM") == TicketPriority.MEDIUM
    assert TicketService.map_risk_to_priority("LOW") == TicketPriority.LOW
    assert TicketService.map_risk_to_priority("low") == TicketPriority.LOW
    assert TicketService.map_risk_to_priority(None) == TicketPriority.LOW
    assert TicketService.map_risk_to_priority("UNKNOWN") == TicketPriority.LOW


@pytest.mark.asyncio
async def test_create_auto_ticket_success():
    """Test successful automatic ticket creation."""
    mock_db = AsyncMock()

    user_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    source_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    change_diff_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_active = True

    user_result = MagicMock()
    user_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_user)))

    mock_change_diff = MagicMock()
    mock_change_diff.diff_id = change_diff_id
    mock_change_diff.new_revision_id = revision_id

    change_diff_result = MagicMock()
    change_diff_result.scalar_one_or_none = MagicMock(return_value=mock_change_diff)

    mock_db.execute = AsyncMock(
        side_effect=[
            user_result,
            change_diff_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    from datetime import datetime

    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.ai_summary = "Test summary"
    mock_revision.scraped_at = datetime(2026, 1, 3, 10, 0, 0)
    mock_revision.content_hash = "abc123"
    mock_revision.ai_confidence_score = 0.85

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.name = "Test Source"
    mock_source.url = "https://test.com"

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.name = "Test Jurisdiction"

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_change_result = MagicMock()
    mock_change_result.risk_level = "HIGH"
    mock_change_result.change_summary = "Significant changes detected"

    service = TicketService(db=mock_db)
    ticket = await service.create_auto_ticket(
        revision=mock_revision,
        source=mock_source,
        jurisdiction=mock_jurisdiction,
        project=mock_project,
        change_result=mock_change_result,
    )

    assert ticket is not None
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    mock_db.refresh.assert_called_once()

    added_ticket = mock_db.add.call_args[0][0]
    assert added_ticket.title == "[Test Jurisdiction] Test Source - Change Detected"
    assert added_ticket.description == "Test summary"
    assert added_ticket.status == TicketStatus.OPEN.value
    assert added_ticket.priority == TicketPriority.HIGH.value
    assert added_ticket.is_manual is False
    assert added_ticket.data_revision_id == revision_id
    assert added_ticket.change_diff_id == change_diff_id
    assert added_ticket.created_by_user_id == user_id
    assert added_ticket.assigned_to_user_id is None
    assert added_ticket.organization_id == org_id
    assert added_ticket.project_id == project_id
    assert added_ticket.source_id == source_id


@pytest.mark.asyncio
async def test_create_auto_ticket_no_active_user():
    """Test automatic ticket creation when no active user exists."""
    mock_db = AsyncMock()

    revision_id = uuid.uuid4()
    source_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()

    user_result = MagicMock()
    user_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))

    change_diff_result = MagicMock()
    change_diff_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_db.execute = AsyncMock(
        side_effect=[
            user_result,
            change_diff_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    from datetime import datetime

    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.ai_summary = "Test summary"
    mock_revision.scraped_at = datetime(2026, 1, 3, 10, 0, 0)
    mock_revision.content_hash = "abc123"
    mock_revision.ai_confidence_score = 0.85

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.name = "Test Source"
    mock_source.url = "https://test.com"

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.name = "Test Jurisdiction"

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_change_result = MagicMock()
    mock_change_result.risk_level = "CRITICAL"
    mock_change_result.change_summary = "Critical changes detected"

    service = TicketService(db=mock_db)
    ticket = await service.create_auto_ticket(
        revision=mock_revision,
        source=mock_source,
        jurisdiction=mock_jurisdiction,
        project=mock_project,
        change_result=mock_change_result,
    )

    assert ticket is not None
    mock_db.add.assert_called_once()

    added_ticket = mock_db.add.call_args[0][0]
    assert added_ticket.created_by_user_id is None
    assert added_ticket.priority == TicketPriority.CRITICAL.value


@pytest.mark.asyncio
async def test_create_auto_ticket_no_change_diff():
    """Test automatic ticket creation when no change diff exists."""
    mock_db = AsyncMock()

    user_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    source_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_active = True

    user_result = MagicMock()
    user_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_user)))

    change_diff_result = MagicMock()
    change_diff_result.scalar_one_or_none = MagicMock(return_value=None)

    mock_db.execute = AsyncMock(
        side_effect=[
            user_result,
            change_diff_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.ai_summary = None
    mock_revision.scraped_at = None
    mock_revision.content_hash = "abc123"
    mock_revision.ai_confidence_score = 0.50

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.name = "Test Source"
    mock_source.url = "https://test.com"

    mock_jurisdiction = None

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_change_result = MagicMock()
    mock_change_result.risk_level = "MEDIUM"
    mock_change_result.change_summary = "Medium risk changes"

    service = TicketService(db=mock_db)
    ticket = await service.create_auto_ticket(
        revision=mock_revision,
        source=mock_source,
        jurisdiction=mock_jurisdiction,
        project=mock_project,
        change_result=mock_change_result,
    )

    assert ticket is not None
    mock_db.add.assert_called_once()

    added_ticket = mock_db.add.call_args[0][0]
    assert added_ticket.title == "[General] Test Source - Change Detected"
    assert added_ticket.description == "No summary available"
    assert added_ticket.change_diff_id is None
    assert added_ticket.priority == TicketPriority.MEDIUM.value
    assert "change_diff_id" not in added_ticket.content


@pytest.mark.asyncio
async def test_create_auto_ticket_with_all_fields():
    """Test automatic ticket creation with all optional fields populated."""
    mock_db = AsyncMock()

    user_id = uuid.uuid4()
    revision_id = uuid.uuid4()
    source_id = uuid.uuid4()
    jurisdiction_id = uuid.uuid4()
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    change_diff_id = uuid.uuid4()

    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.is_active = True

    user_result = MagicMock()
    user_result.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=mock_user)))

    mock_change_diff = MagicMock()
    mock_change_diff.diff_id = change_diff_id
    mock_change_diff.new_revision_id = revision_id

    change_diff_result = MagicMock()
    change_diff_result.scalar_one_or_none = MagicMock(return_value=mock_change_diff)

    mock_db.execute = AsyncMock(
        side_effect=[
            user_result,
            change_diff_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    from datetime import datetime

    scraped_time = datetime(2026, 1, 3, 15, 30, 0)
    mock_revision = MagicMock()
    mock_revision.id = revision_id
    mock_revision.ai_summary = "Comprehensive AI summary of changes"
    mock_revision.scraped_at = scraped_time
    mock_revision.content_hash = "def456"
    mock_revision.ai_confidence_score = 0.95

    mock_source = MagicMock()
    mock_source.id = source_id
    mock_source.name = "Premium Source"
    mock_source.url = "https://premium.source.com/data"

    mock_jurisdiction = MagicMock()
    mock_jurisdiction.id = jurisdiction_id
    mock_jurisdiction.name = "California"

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.org_id = org_id

    mock_change_result = MagicMock()
    mock_change_result.risk_level = "CRITICAL"
    mock_change_result.change_summary = "Critical regulatory changes"

    service = TicketService(db=mock_db)
    await service.create_auto_ticket(
        revision=mock_revision,
        source=mock_source,
        jurisdiction=mock_jurisdiction,
        project=mock_project,
        change_result=mock_change_result,
    )

    added_ticket = mock_db.add.call_args[0][0]

    assert added_ticket.content["revision_summary"] == "Comprehensive AI summary of changes"
    assert added_ticket.content["source_name"] == "Premium Source"
    assert added_ticket.content["source_url"] == "https://premium.source.com/data"
    assert added_ticket.content["jurisdiction"] == "California"
    assert added_ticket.content["scraped_at"] == scraped_time.isoformat()
    assert added_ticket.content["content_hash"] == "def456"
    assert added_ticket.content["diff_patch"]["risk_level"] == "CRITICAL"
    assert added_ticket.content["diff_patch"]["change_summary"] == "Critical regulatory changes"
    assert added_ticket.content["ai_confidence"] == 0.95
    assert added_ticket.content["priority_inferred_from_ai"] is True
    assert added_ticket.content["change_diff_id"] == str(change_diff_id)
