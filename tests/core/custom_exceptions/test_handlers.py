"""
Tests for app.api.core.custom_exceptions.handlers
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.core.custom_exceptions.exceptions import NotFoundError
from app.api.core.custom_exceptions.handlers import (
    domain_exception_handler,
    internal_server_error_handler,
    starlette_http_exception_handler,
)


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.url.path = "/api/v1/test"
    request.method = "GET"
    return request


class TestDomainExceptionHandler:
    @pytest.mark.asyncio
    @patch("app.api.core.custom_exceptions.handlers.logger")
    async def test_domain_exception_handler(self, mock_logger, mock_request):
        exc = NotFoundError(message="Resource not found")

        response = await domain_exception_handler(mock_request, exc)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_logger.warning.assert_called_once()


class TestInternalServerErrorHandler:
    @pytest.mark.asyncio
    @patch("app.api.core.custom_exceptions.handlers.logger")
    async def test_internal_server_error_handler(self, mock_logger, mock_request):
        exc = Exception("Server error")

        response = await internal_server_error_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        mock_logger.exception.assert_called_once()


class TestStarletteHTTPExceptionHandler:
    @pytest.mark.asyncio
    @patch("app.api.core.custom_exceptions.handlers.logger")
    async def test_starlette_http_exception_handler(self, mock_logger, mock_request):
        exc = StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        response = await starlette_http_exception_handler(mock_request, exc)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_logger.warning.assert_called_once()
