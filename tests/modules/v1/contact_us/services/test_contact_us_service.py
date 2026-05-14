from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks

from app.api.modules.v1.contact_us.schemas.contact_us import ContactUsRequest
from app.api.modules.v1.contact_us.service.contact_us import ContactUsService


@pytest.mark.asyncio
async def test_submit_contact_form_success():
    mock_db = AsyncMock()

    service = ContactUsService(db=mock_db)
    background = BackgroundTasks()

    payload = ContactUsRequest(
        full_name="John Doe",
        phone_number="+447911123456",
        email="john@gmail.com",
        message="Hello, I need assistance.",
    )

    with patch(
        "app.api.modules.v1.contact_us.service.contact_us.send_email", new_callable=AsyncMock
    ) as mock_send:
        result = await service.submit_contact_form(payload, background)

        for task in background.tasks:
            await task()

        assert result == {"email": "john@gmail.com"}
        assert mock_send.await_count == 2

        mock_db.add.assert_called()
        mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_submit_contact_form_error_handling():
    mock_db = AsyncMock()
    service = ContactUsService(db=mock_db)
    background = BackgroundTasks()

    payload = ContactUsRequest(
        full_name="Jane Doe",
        phone_number="+447911123456",
        email="jane@gmail.com",
        message="Test message",
    )

    async def mock_email_fail(*args, **kwargs):
        raise RuntimeError("Email service down")

    with patch(
        "app.api.modules.v1.contact_us.service.contact_us.send_email", side_effect=mock_email_fail
    ) as mock_send:
        result = await service.submit_contact_form(payload, background)

        for task in background.tasks:
            try:
                await task()
            except RuntimeError:
                pass

        assert result == {"email": "jane@gmail.com"}
        assert mock_send.await_count == 2

        mock_db.add.assert_called()
        mock_db.commit.assert_awaited()
