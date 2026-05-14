"""
Tests for register_all_errors function
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI

from main import register_all_errors


class TestRegisterAllErrors:
    @patch("app.api.core.custom_exceptions.register.logger")
    def test_register_all_errors(self, mock_logger):
        mock_app = MagicMock(spec=FastAPI)

        register_all_errors(mock_app)

        assert mock_app.add_exception_handler.call_count == 3
        mock_logger.info.assert_called_once_with("All exception handlers registered successfully")
