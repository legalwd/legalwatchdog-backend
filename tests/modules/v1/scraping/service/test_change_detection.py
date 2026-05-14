import json
from unittest.mock import AsyncMock, patch

import pytest

from app.api.modules.v1.scraping.schemas.ai_analysis import ChangeDetectionResult
from app.api.modules.v1.scraping.service.diff_service import DiffAIService


class MockGeminiResponse:
    """Simulates a Gemini JSON-mode response."""

    def __init__(self, data: dict):
        self.text = json.dumps(data)


@pytest.fixture
def diff_service():
    with patch(
        "app.api.modules.v1.scraping.service.diff_service.genai.GenerativeModel"
    ) as mock_model_class:
        service = DiffAIService(use_openrouter=False)
        service.model = mock_model_class.return_value
        yield service


@pytest.fixture
def test_context():
    return "Monitor product pricing and stock status."


def mock_ai_result(has_changed: bool, summary: str, risk: str) -> dict:
    return {
        "has_changed": has_changed,
        "change_summary": summary,
        "risk_level": risk,
    }


@pytest.mark.asyncio
async def test_exact_match_no_api_call(diff_service, test_context):
    data = {"product": "A", "price": 10}

    with patch.object(diff_service.model, "generate_content_async") as mock_call:
        result: ChangeDetectionResult = await diff_service.detect_semantic_change(
            data, data, test_context
        )

        assert result.has_changed is False
        assert result.change_summary == "No changes (Exact Match)"
        assert result.risk_level == "LOW"
        mock_call.assert_not_called()


@pytest.mark.asyncio
async def test_new_record_no_ai_call(diff_service, test_context):
    old_data = {}
    new_data = {"product": "B", "price": 50}

    with patch.object(diff_service.model, "generate_content_async") as mock_call:
        result: ChangeDetectionResult = await diff_service.detect_semantic_change(
            old_data, new_data, test_context
        )

        assert result.has_changed is True
        assert result.change_summary == "Initial data extraction (New Record)"
        assert result.risk_level == "LOW"
        mock_call.assert_not_called()


@pytest.mark.asyncio
async def test_ai_detects_relevant_change(diff_service, test_context):
    old_data = {"id": 1, "price": 100}
    new_data = {"id": 1, "price": 110}

    mock_response = MockGeminiResponse(
        mock_ai_result(has_changed=True, summary="Price increased from 100 to 110.", risk="MEDIUM")
    )

    with patch.object(
        diff_service.model, "generate_content_async", new=AsyncMock(return_value=mock_response)
    ) as mock_call:
        result: ChangeDetectionResult = await diff_service.detect_semantic_change(
            old_data, new_data, test_context
        )

        assert result.has_changed is True
        assert "Price increased" in result.change_summary
        assert result.risk_level == "MEDIUM"
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_ai_detects_irrelevant_change(diff_service, test_context):
    old_data = {"id": 2, "stock": 50, "last_updated": "2025-11-23T00:00:00"}
    new_data = {"id": 2, "stock": 50, "last_updated": "2025-11-24T12:00:00"}

    mock_response = MockGeminiResponse(
        mock_ai_result(
            has_changed=False, summary="Only timestamp changed. Not relevant.", risk="LOW"
        )
    )

    with patch.object(
        diff_service.model, "generate_content_async", new=AsyncMock(return_value=mock_response)
    ) as mock_call:
        result: ChangeDetectionResult = await diff_service.detect_semantic_change(
            old_data, new_data, test_context
        )

        assert result.has_changed is False
        assert "Not relevant" in result.change_summary
        assert result.risk_level == "LOW"
        mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_ai_returns_invalid_json_trigger_fallback(diff_service, test_context):
    old_data = {"id": 1}
    new_data = {"id": 2}

    mock_bad_response = AsyncMock()
    mock_bad_response.text = "INVALID_JSON"

    with patch.object(
        diff_service.model, "generate_content_async", new=AsyncMock(return_value=mock_bad_response)
    ):
        result: ChangeDetectionResult = await diff_service.detect_semantic_change(
            old_data, new_data, test_context
        )

        assert result.has_changed is True
        assert "AI Analysis Failed" in result.change_summary
        assert result.risk_level == "HIGH"
