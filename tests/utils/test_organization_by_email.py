from unittest.mock import AsyncMock

import pytest

from app.api.modules.v1.users.models.users_model import User
from app.api.utils.get_organization_by_email import get_organization_by_email


@pytest.mark.asyncio
async def test_get_organization_by_email_found():
    """Returns User instance when user exists"""
    db_mock = AsyncMock()
    user_instance = User(id=1, email="test@example.com", name="Test User")
    db_mock.scalar.return_value = user_instance

    result = await get_organization_by_email(db_mock, "test@example.com")
    db_mock.scalar.assert_awaited_once()
    assert result == user_instance


@pytest.mark.asyncio
async def test_get_organization_by_email_not_found():
    """Returns None when user does not exist"""
    db_mock = AsyncMock()
    db_mock.scalar.return_value = None

    result = await get_organization_by_email(db_mock, "missing@example.com")
    db_mock.scalar.assert_awaited_once()
    assert result is None


@pytest.mark.asyncio
async def test_get_organization_by_email_exception():
    """Returns None if database raises exception"""
    db_mock = AsyncMock()
    db_mock.scalar.side_effect = Exception("DB error")

    result = await get_organization_by_email(db_mock, "error@example.com")
    db_mock.scalar.assert_awaited_once()
    assert result is None
