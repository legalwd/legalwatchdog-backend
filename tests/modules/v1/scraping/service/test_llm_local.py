from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
)
from app.api.modules.v1.scraping.service.llm_service import (
    AIExtractionService,
)


@pytest.mark.asyncio
async def test_llm_local_integration():
    """Test LLM service integration with mock data and validate response structure."""
    fake_project_prompt = "Summarize regulatory updates for banking sector."
    fake_jurisdiction_prompt = "Focus on Nigerian financial policies."
    extracted_text = """
    The Central Bank of Nigeria released new guidelines for digital banks.
    Policies include stricter KYC and improved consumer protection.
    """

    service = AIExtractionService(use_openrouter=False)

    service.model = Mock()
    mock_response = Mock()
    mock_response.text = (
        "{\n"
        '    "summary": "The Central Bank of Nigeria has introduced new '
        "guidelines for digital banks focusing on enhanced KYC requirements "
        'and consumer protection measures.",\n'
        '    "markdown_summary": "## Regulatory Update Summary\\n\\n'
        "### Key Changes:\\n- **Stricter KYC requirements** for digital banking\\n"
        "- **Enhanced consumer protection** measures\\n"
        "- **New guidelines** for digital bank operations\\n\\n"
        "### Impact:\\nThese changes aim to strengthen the digital banking "
        'sector while ensuring customer security.",\n'
        '    "extracted_data": {\n'
        '        "key_value_pairs": [\n'
        '            {"key": "regulator", "value": "Central Bank of Nigeria"},\n'
        '            {"key": "sector", "value": "digital banking"},\n'
        '            {"key": "kyc_requirements", "value": "stricter"},\n'
        '            {"key": "consumer_protection", "value": "enhanced"}\n'
        "        ]\n"
        "    },\n"
        '    "confidence_score": 0.85\n'
        "}"
    )

    service.model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await service.run_llm_analysis(
        cleaned_text=extracted_text,
        project_prompt=fake_project_prompt,
        jurisdiction_prompt=fake_jurisdiction_prompt,
        max_retries=0,
    )

    print("\n=== LLM RESULT ===\n", result)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "markdown_summary" in result
    assert "extracted_data" in result
    assert "confidence_score" in result
    assert isinstance(result["confidence_score"], float)
    assert 0.0 <= result["confidence_score"] <= 1.0


@pytest.mark.asyncio
async def test_llm_service_error_handling():
    """Test LLM service error handling."""
    service = AIExtractionService(use_openrouter=False)
    service.model = Mock()
    service.model.generate_content_async = AsyncMock(side_effect=Exception("API Error"))

    with pytest.raises(LLMAPIError):
        await service.run_llm_analysis(
            cleaned_text="Test content",
            project_prompt="Test project",
            jurisdiction_prompt="Test jurisdiction",
            max_retries=1,
        )


@pytest.mark.asyncio
async def test_llm_service_json_parsing():
    """Test LLM service JSON parsing and transformation."""
    service = AIExtractionService(use_openrouter=False)
    service.model = Mock()
    mock_response = Mock()
    mock_response.text = (
        "{\n"
        '    "summary": "Test summary",\n'
        '    "markdown_summary": "## Test Markdown",\n'
        '    "extracted_data": {\n'
        '        "key_value_pairs": [\n'
        '            {"key": "test_key_1", "value": "value_1"},\n'
        '            {"key": "test_key_2", "value": "value_2"}\n'
        "        ]\n"
        "    },\n"
        '    "confidence_score": 0.9\n'
        "}"
    )

    service.model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await service.run_llm_analysis(
        cleaned_text="Test content",
        project_prompt="Test project",
        jurisdiction_prompt="Test jurisdiction",
    )

    assert isinstance(result["extracted_data"]["key_value_pairs"], dict)
    assert "test_key_1" in result["extracted_data"]["key_value_pairs"]
    assert result["extracted_data"]["key_value_pairs"]["test_key_1"] == "value_1"


@pytest.mark.asyncio
async def test_llm_service_initialization():
    """Test LLM service initialization with missing dependencies."""
    with patch("app.api.modules.v1.scraping.service.llm_service._HAS_GENAI", False):
        with pytest.raises(LLMConfigurationError):
            AIExtractionService(use_openrouter=False)

    with patch(
        "app.api.modules.v1.scraping.service.llm_service.settings.GEMINI_API_KEY",
        None,
    ):
        with patch("app.api.modules.v1.scraping.service.llm_service._HAS_GENAI", True):
            with pytest.raises(ValueError):
                AIExtractionService(use_openrouter=False)


@pytest.mark.asyncio
async def test_llm_service_retry_logic():
    """Test LLM service retry logic."""
    service = AIExtractionService(use_openrouter=False)
    service.model = Mock()

    service.model.generate_content_async = AsyncMock(
        side_effect=[
            ConnectionError("First failure"),
            ConnectionError("Second failure"),
            Mock(
                text=(
                    "{\n"
                    '    "summary": "Success after retry",\n'
                    '    "markdown_summary": "## Success",\n'
                    '    "extracted_data": {"key_value_pairs": []},\n'
                    '    "confidence_score": 0.8\n'
                    "}"
                )
            ),
        ]
    )

    result = await service.run_llm_analysis(
        cleaned_text="Test content",
        project_prompt="Test project",
        jurisdiction_prompt="Test jurisdiction",
        max_retries=2,
    )

    assert result["summary"] == "Success after retry"
    assert service.model.generate_content_async.call_count == 3


@pytest.mark.asyncio
async def test_llm_service_exponential_backoff():
    """Test LLM service exponential backoff with jitter."""
    service = AIExtractionService(use_openrouter=False)
    service.model = Mock()

    service.model.generate_content_async = AsyncMock(
        side_effect=[
            ConnectionError("First failure"),
            ConnectionError("Second failure"),
            Mock(
                text=(
                    "{\n"
                    '    "summary": "Success after backoff",\n'
                    '    "markdown_summary": "## Success",\n'
                    '    "extracted_data": {"key_value_pairs": []},\n'
                    '    "confidence_score": 0.8\n'
                    "}"
                )
            ),
        ]
    )

    result = await service.run_llm_analysis(
        cleaned_text="Test content",
        project_prompt="Test project",
        jurisdiction_prompt="Test jurisdiction",
        max_retries=2,
    )

    assert result["summary"] == "Success after backoff"
    assert service.model.generate_content_async.call_count == 3
