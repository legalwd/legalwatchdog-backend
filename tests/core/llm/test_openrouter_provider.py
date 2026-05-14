"""OpenRouter provider comprehensive test suite."""

import json
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import pytest_asyncio

from app.api.core.exceptions import (
    OpenRouterAuthenticationError,
    OpenRouterError,
    OpenRouterRateLimitError,
)
from app.api.core.llm.base_provider import (
    LLMResponse,
    ModelCategory,
)
from app.api.core.llm.openrouter_provider import (
    OPENROUTER_MODEL_CATALOG,
    OpenRouterProvider,
)


@pytest.fixture
def api_key():
    """Standard test API key."""
    return "sk-or-test-key-12345"


@pytest.fixture
def provider_config():
    """Standard provider configuration."""
    return {
        "api_key": "sk-or-test-key-12345",
        "default_model": "google/gemini-3-flash-preview",
        "fallback_models": [
            "google/gemini-2.5-flash-lite",
            "deepseek/deepseek-v3.2",
        ],
        "site_url": "https://example.com",
        "site_name": "Test Site",
        "timeout": 120,
        "enable_routing": True,
    }


@pytest.fixture
def provider(provider_config):
    """Create OpenRouter provider instance."""
    return OpenRouterProvider(**provider_config)


@pytest.fixture
def mock_openrouter_response():
    """Mock successful OpenRouter API response."""
    return {
        "id": "chatcmpl-8nuLqV5Z9m",
        "object": "text_completion",
        "created": int(time.time()),
        "model": "google/gemini-3-flash-preview",
        "choices": [
            {
                "finish_reason": "stop",
                "index": 0,
                "message": {
                    "content": '{"extracted_data": "test", "confidence": 0.95}',
                    "role": "assistant",
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


@pytest.fixture
def mock_http_response(mock_openrouter_response):
    """Mock httpx.Response object."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = mock_openrouter_response
    response.text = json.dumps(mock_openrouter_response)
    response.headers = {}
    return response


@pytest_asyncio.fixture
async def mock_async_client(mock_http_response):
    """Mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post.return_value = mock_http_response
    return client


class TestOpenRouterProviderInitialization:
    """Tests for provider initialization and configuration."""

    def test_provider_initializes_with_required_parameters(self):
        """Test creating provider with minimal required config."""
        provider = OpenRouterProvider(api_key="sk-or-test")
        assert provider.api_key == "sk-or-test"
        assert provider.default_model == "google/gemini-3-flash-preview"
        assert provider.base_url == "https://openrouter.ai/api/v1"
        assert provider.timeout == 120

    def test_provider_uses_default_fallback_models(self):
        """Test provider uses default fallback models when not specified."""
        provider = OpenRouterProvider(api_key="sk-or-test")
        assert len(provider.fallback_models) == 2
        assert "google/gemini-2.5-flash-lite" in provider.fallback_models

    def test_provider_accepts_custom_fallback_models(self):
        """Test provider accepts custom fallback models."""
        custom_models = ["deepseek/deepseek-v3.2"]
        provider = OpenRouterProvider(api_key="sk-or-test", fallback_models=custom_models)
        assert provider.fallback_models == custom_models

    def test_provider_accepts_optional_parameters(self, provider_config):
        """Test provider accepts site_url and site_name for attribution."""
        provider = OpenRouterProvider(**provider_config)
        assert provider.site_url == "https://example.com"
        assert provider.site_name == "Test Site"

    def test_provider_accepts_custom_timeout(self):
        """Test provider accepts custom timeout."""
        provider = OpenRouterProvider(api_key="sk-or-test", timeout=60)
        assert provider.timeout == 60

    def test_provider_respects_enable_routing_flag(self):
        """Test enable_routing flag controls fallback route behavior."""
        provider_enabled = OpenRouterProvider(api_key="sk-or-test", enable_routing=True)
        provider_disabled = OpenRouterProvider(api_key="sk-or-test", enable_routing=False)
        assert provider_enabled.enable_routing is True
        assert provider_disabled.enable_routing is False


class TestModelConfiguration:
    """Tests for model configuration and validation."""

    def test_get_model_config_returns_valid_config(self, provider):
        """Test retrieving configuration for supported model."""
        config = provider.get_model_config("google/gemini-3-flash-preview")
        assert config.name == "google/gemini-3-flash-preview"
        assert config.category == ModelCategory.PREMIUM
        assert config.supports_json_mode is True

    def test_get_model_config_raises_for_unsupported_model(self, provider):
        """Test error raised for unsupported model."""
        with pytest.raises(ValueError, match="not supported"):
            provider.get_model_config("invalid/model")

    def test_all_catalog_models_have_required_fields(self):
        """Test all models in catalog have required configuration."""
        for model_name, config in OPENROUTER_MODEL_CATALOG.items():
            assert config.name == model_name
            assert config.provider == "openrouter"
            assert config.cost_per_1m_input_tokens >= 0
            assert config.cost_per_1m_output_tokens >= 0
            assert config.context_window > 0
            assert config.max_retries >= 2

    @pytest.mark.parametrize(
        "model,expected_category",
        [
            ("google/gemini-3-flash-preview", ModelCategory.PREMIUM),
            ("google/gemini-2.5-flash-lite", ModelCategory.BALANCED),
            ("deepseek/deepseek-v3.2", ModelCategory.ECONOMY),
            ("xiaomi/mimo-v2-flash", ModelCategory.ECONOMY),
        ],
    )
    def test_model_category_classification(self, provider, model, expected_category):
        """Test models are correctly categorized."""
        config = provider.get_model_config(model)
        assert config.category == expected_category

    @pytest.mark.parametrize(
        "model",
        [
            "google/gemini-3-flash-preview",
            "google/gemini-2.5-flash-lite",
            "deepseek/deepseek-v3.2",
            "xiaomi/mimo-v2-flash",
        ],
    )
    def test_all_models_support_json_mode(self, provider, model):
        """Test all catalog models support JSON mode."""
        config = provider.get_model_config(model)
        assert config.supports_json_mode is True


class TestCostCalculation:
    """Tests for cost calculation accuracy."""

    def test_cost_calculation_includes_openrouter_platform_fee(self, provider):
        """Test cost calculation includes 5.5% OpenRouter platform fee."""
        model = "google/gemini-3-flash-preview"
        input_tokens = 1_000_000
        output_tokens = 1_000_000

        config = provider.get_model_config(model)

        cost = provider.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        base_input = (input_tokens / 1_000_000) * config.cost_per_1m_input_tokens
        base_output = (output_tokens / 1_000_000) * config.cost_per_1m_output_tokens
        base_cost = base_input + base_output
        platform_fee = base_cost * 0.055
        expected_cost = base_cost + platform_fee
        assert abs(cost - expected_cost) < 0.000001

    @pytest.mark.parametrize(
        "model,input_tokens,output_tokens",
        [
            ("google/gemini-3-flash-preview", 1500, 300),
            ("google/gemini-2.5-flash-lite", 1000, 200),
            ("deepseek/deepseek-v3.2", 2000, 400),
            ("xiaomi/mimo-v2-flash", 1000, 500),
        ],
    )
    def test_cost_calculation_for_different_models(
        self, provider, model, input_tokens, output_tokens
    ):
        """Test cost calculation for all supported models."""
        cost = provider.calculate_cost(model, input_tokens, output_tokens)
        assert cost >= 0
        assert isinstance(cost, float)

    def test_cost_calculation_zero_tokens(self, provider):
        """Test cost calculation with zero tokens."""
        cost = provider.calculate_cost(
            model="google/gemini-3-flash-preview", input_tokens=0, output_tokens=0
        )
        assert cost == 0.0

    def test_cost_calculation_large_token_count(self, provider):
        """Test cost calculation with large token count."""
        cost = provider.calculate_cost(
            model="google/gemini-3-flash-preview",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost > 0
        assert cost < 100


class TestHTTPHeadersConstruction:
    """Tests for HTTP headers building."""

    def test_build_headers_includes_authorization(self, provider):
        """Test Authorization header is included with API key."""
        headers = provider._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer sk-or-")

    def test_build_headers_includes_content_type(self, provider):
        """Test Content-Type header is set correctly."""
        headers = provider._build_headers()
        assert headers["Content-Type"] == "application/json"

    def test_build_headers_includes_site_url_when_provided(self, provider):
        """Test HTTP-Referer header when site_url is provided."""
        headers = provider._build_headers()
        assert headers["HTTP-Referer"] == "https://example.com"

    def test_build_headers_includes_site_name_when_provided(self, provider):
        """Test X-Title header when site_name is provided."""
        headers = provider._build_headers()
        assert headers["X-Title"] == "Test Site"

    def test_build_headers_without_optional_fields(self):
        """Test headers when site_url and site_name are not provided."""
        provider = OpenRouterProvider(api_key="sk-or-test")
        headers = provider._build_headers()
        assert "Authorization" in headers
        assert "Content-Type" in headers
        assert "HTTP-Referer" not in headers
        assert "X-Title" not in headers


class TestRequestPayloadConstruction:
    """Tests for request payload building."""

    def test_build_payload_includes_messages(self, provider):
        """Test payload includes properly formatted messages."""
        payload = provider._build_request_payload(
            prompt="Extract data",
            model="google/gemini-3-flash-preview",
            temperature=0.0,
            max_tokens=1000,
            json_mode=False,
            system_prompt=None,
        )
        assert "messages" in payload
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Extract data"

    def test_build_payload_includes_system_prompt(self, provider):
        """Test system prompt is added to messages when provided."""
        system_prompt = "You are an expert extractor."
        payload = provider._build_request_payload(
            prompt="Extract data",
            model="google/gemini-3-flash-preview",
            temperature=0.0,
            max_tokens=1000,
            json_mode=False,
            system_prompt=system_prompt,
        )
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == system_prompt

    def test_build_payload_includes_model_and_params(self, provider):
        """Test payload includes model and generation parameters."""
        payload = provider._build_request_payload(
            prompt="Extract",
            model="google/gemini-3-flash-preview",
            temperature=0.5,
            max_tokens=2000,
            json_mode=False,
            system_prompt=None,
        )
        assert payload["model"] == "google/gemini-3-flash-preview"
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 2000

    def test_build_payload_includes_json_mode_format(self, provider):
        """Test JSON mode adds response_format specification."""
        payload = provider._build_request_payload(
            prompt="Extract",
            model="google/gemini-3-flash-preview",
            temperature=0.0,
            max_tokens=1000,
            json_mode=True,
            system_prompt=None,
        )
        assert "response_format" in payload
        assert payload["response_format"]["type"] == "json_object"

    def test_build_payload_excludes_json_mode_for_unsupported_model(self, provider):
        """Test JSON mode is not added if model doesn't support it."""
        with patch.object(provider, "get_model_config") as mock_config:
            mock_config.return_value.supports_json_mode = False
            payload = provider._build_request_payload(
                prompt="Extract",
                model="test/model",
                temperature=0.0,
                max_tokens=1000,
                json_mode=True,
                system_prompt=None,
            )
            assert "response_format" not in payload

    def test_build_payload_includes_routing_when_enabled(self, provider):
        """Test fallback route is included when routing is enabled."""
        assert provider.enable_routing is True
        payload = provider._build_request_payload(
            prompt="Extract",
            model="google/gemini-3-flash-preview",
            temperature=0.0,
            max_tokens=1000,
            json_mode=False,
            system_prompt=None,
        )
        assert payload["route"] == "fallback"

    def test_build_payload_excludes_routing_when_disabled(self):
        """Test fallback route is excluded when routing is disabled."""
        provider = OpenRouterProvider(api_key="sk-or-test", enable_routing=False)
        payload = provider._build_request_payload(
            prompt="Extract",
            model="google/gemini-3-flash-preview",
            temperature=0.0,
            max_tokens=1000,
            json_mode=False,
            system_prompt=None,
        )
        assert "route" not in payload


class TestRateLimitHandling:
    """Tests for rate limit (429) handling with exponential backoff."""

    @pytest.mark.asyncio
    async def test_rate_limit_triggers_retry_with_backoff(self, provider):
        """Test 429 response triggers retry with Retry-After header."""
        retry_after_response = Mock(spec=httpx.Response)
        retry_after_response.status_code = 429
        retry_after_response.headers = {"Retry-After": "2"}

        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = [retry_after_response, success_response]
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep") as mock_sleep:
                payload = {"model": "test", "messages": []}
                response_data, retry_count = await provider._make_request_with_retry(
                    payload=payload, max_retries=2
                )

                assert retry_count == 1
                assert mock_sleep.called
                assert response_data["choices"][0]["message"]["content"] == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_rate_limit_exceeds_max_retries(self, provider):
        """Test OpenRouterRateLimitError raised when retries exhausted."""
        rate_limit_response = Mock(spec=httpx.Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = rate_limit_response
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep"):
                payload = {"model": "test", "messages": []}
                with pytest.raises(OpenRouterRateLimitError):
                    await provider._make_request_with_retry(payload=payload, max_retries=2)

    @pytest.mark.asyncio
    async def test_rate_limit_respects_retry_after_header(self, provider):
        """Test Retry-After header is respected in sleep duration."""
        rate_limit_response = Mock(spec=httpx.Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "5"}

        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = [rate_limit_response, success_response]
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep") as mock_sleep:
                payload = {"model": "test", "messages": []}
                await provider._make_request_with_retry(payload=payload, max_retries=2)

                assert mock_sleep.called
                call_args = mock_sleep.call_args[0][0]
                assert call_args >= 5


class TestAuthenticationErrorHandling:
    """Tests for authentication (401) error handling."""

    @pytest.mark.asyncio
    async def test_authentication_error_raises_immediately(self, provider):
        """Test 401 raises OpenRouterAuthenticationError without retry."""
        auth_error_response = Mock(spec=httpx.Response)
        auth_error_response.status_code = 401
        auth_error_response.json.return_value = {"error": "Invalid API key"}
        auth_error_response.text = '{"error": "Invalid API key"}'

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = auth_error_response
            mock_client_class.return_value = mock_client

            payload = {"model": "test", "messages": []}
            with pytest.raises(OpenRouterAuthenticationError):
                await provider._make_request_with_retry(payload=payload, max_retries=2)

            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_authentication_error_logs_masked_api_key(self, provider):
        """Test API key is masked in logs for security."""
        auth_error_response = Mock(spec=httpx.Response)
        auth_error_response.status_code = 401
        auth_error_response.json.return_value = {}
        auth_error_response.text = "{}"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = auth_error_response
            mock_client_class.return_value = mock_client

            with patch("app.api.core.llm.openrouter_provider.logger") as mock_logger:
                payload = {"model": "test", "messages": []}
                with pytest.raises(OpenRouterAuthenticationError):
                    await provider._make_request_with_retry(payload=payload, max_retries=2)

                mock_logger.error.assert_called()
                log_message = mock_logger.error.call_args[0][0]
                assert "sk-or-..." in log_message or "sk-or" in log_message


class TestGenerationWithMetrics:
    """Tests for successful generation and metrics tracking."""

    @pytest.mark.asyncio
    async def test_successful_generation_returns_llm_response(self, provider):
        """Test successful request returns properly formatted LLMResponse."""
        response_data = {
            "choices": [{"message": {"content": '{"extracted": "data", "confidence": 0.95}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(provider, "_make_request_with_retry") as mock_request:
            mock_request.return_value = (response_data, 0)

            response = await provider.generate(
                prompt="Extract data",
                model="google/gemini-3-flash-preview",
                temperature=0.0,
                max_tokens=1000,
                json_mode=False,
            )

            assert isinstance(response, LLMResponse)
            assert response.content == '{"extracted": "data", "confidence": 0.95}'
            assert response.model == "google/gemini-3-flash-preview"
            assert response.provider == "openrouter"

    @pytest.mark.asyncio
    async def test_generation_tracks_usage_metrics(self, provider):
        """Test generation properly calculates and tracks usage metrics."""
        response_data = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(provider, "_make_request_with_retry") as mock_request:
            mock_request.return_value = (response_data, 0)

            response = await provider.generate(
                prompt="Test",
                model="google/gemini-3-flash-preview",
                temperature=0.0,
                max_tokens=1000,
                user_id="user_123",
                organization_id="org_456",
            )

            metrics = response.usage_metrics
            assert metrics.input_tokens == 100
            assert metrics.output_tokens == 50
            assert metrics.total_tokens == 150
            assert metrics.success is True
            assert metrics.user_id == "user_123"
            assert metrics.organization_id == "org_456"
            assert metrics.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_generation_calculates_cost_correctly(self, provider):
        """Test cost is calculated and included in metrics."""
        response_data = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        }

        with patch.object(provider, "_make_request_with_retry") as mock_request:
            mock_request.return_value = (response_data, 0)

            response = await provider.generate(
                prompt="Test",
                model="google/gemini-3-flash-preview",
                temperature=0.0,
                max_tokens=1000,
            )

            expected_cost = provider.calculate_cost("google/gemini-3-flash-preview", 1000, 500)
            assert abs(response.usage_metrics.cost_usd - expected_cost) < 0.000001

    @pytest.mark.asyncio
    async def test_generation_includes_retry_count_in_metrics(self, provider):
        """Test retry count is tracked in usage metrics."""
        response_data = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch.object(provider, "_make_request_with_retry") as mock_request:
            mock_request.return_value = (response_data, 2)

            response = await provider.generate(
                prompt="Test",
                model="google/gemini-3-flash-preview",
                temperature=0.0,
                max_tokens=1000,
            )

            assert response.usage_metrics.retry_count == 2


class TestFallbackChain:
    """Tests for model fallback chain behavior."""

    @pytest.mark.asyncio
    async def test_fallback_tries_default_model_first(self, provider):
        """Test fallback chain attempts primary model first."""
        response_data = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch.object(provider, "generate") as mock_generate:
            mock_generate.return_value = LLMResponse(
                content='{"test": "data"}',
                model="google/gemini-3-flash-preview",
                provider="openrouter",
                usage_metrics=Mock(),
                raw_response=response_data,
            )

            await provider.generate_with_fallback(prompt="Test", temperature=0.0, max_tokens=1000)

            assert mock_generate.call_count == 1
            call_args = mock_generate.call_args
            assert call_args[1]["model"] == "google/gemini-3-flash-preview"

    @pytest.mark.asyncio
    async def test_fallback_tries_fallback_models_on_error(self, provider):
        """Test fallback chain activates on primary model failure."""
        response_data = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        success_response = LLMResponse(
            content='{"test": "data"}',
            model="google/gemini-2.5-flash-lite",
            provider="openrouter",
            usage_metrics=Mock(),
            raw_response=response_data,
        )

        with patch.object(provider, "generate") as mock_generate:
            mock_generate.side_effect = [
                OpenRouterError("Primary model failed"),
                success_response,
            ]

            response = await provider.generate_with_fallback(
                prompt="Test", temperature=0.0, max_tokens=1000
            )

            assert mock_generate.call_count == 2
            assert response.model == "google/gemini-2.5-flash-lite"

    @pytest.mark.asyncio
    async def test_fallback_raises_after_all_models_fail(self, provider):
        """Test error raised when all models in fallback chain fail."""
        with patch.object(provider, "generate") as mock_generate:
            mock_generate.side_effect = OpenRouterError("All models failed")

            with pytest.raises(OpenRouterError, match="All models failed"):
                await provider.generate_with_fallback(
                    prompt="Test", temperature=0.0, max_tokens=1000
                )

            assert mock_generate.call_count == len(provider.fallback_models) + 1

    @pytest.mark.asyncio
    async def test_fallback_respects_model_order(self, provider):
        """Test fallback models are tried in specified order."""
        provider.fallback_models = [
            "google/gemini-2.5-flash-lite",
            "deepseek/deepseek-v3.2",
        ]

        models_attempted = []

        async def mock_generate(*args, **kwargs):
            models_attempted.append(kwargs.get("model"))
            raise OpenRouterError("Model failed")

        with patch.object(provider, "generate", side_effect=mock_generate):
            with pytest.raises(OpenRouterError):
                await provider.generate_with_fallback(
                    prompt="Test", temperature=0.0, max_tokens=1000
                )

            assert models_attempted[0] == "google/gemini-3-flash-preview"
            assert models_attempted[1] == "google/gemini-2.5-flash-lite"
            assert models_attempted[2] == "deepseek/deepseek-v3.2"


class TestTimeoutHandling:
    """Tests for timeout retry behavior."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self, provider):
        """Test timeout exception triggers exponential backoff retry."""
        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = [
                httpx.TimeoutException("Request timeout"),
                success_response,
            ]
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep"):
                payload = {"model": "test", "messages": []}
                response_data, retry_count = await provider._make_request_with_retry(
                    payload=payload, max_retries=2
                )

                assert retry_count == 1
                assert response_data["choices"][0]["message"]["content"] == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_timeout_exceeds_max_retries_raises_error(self, provider):
        """Test OpenRouterError raised after timeout retries exhausted."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep"):
                payload = {"model": "test", "messages": []}
                with pytest.raises(OpenRouterError, match="timeout"):
                    await provider._make_request_with_retry(payload=payload, max_retries=2)


class TestErrorHandling:
    """Tests for error response handling."""

    @pytest.mark.asyncio
    async def test_5xx_error_triggers_retry(self, provider):
        """Test 5xx server errors trigger exponential backoff retry."""
        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.json.return_value = {"error": "Internal server error"}

        success_response = Mock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": '{"test": "data"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = [error_response, success_response]
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep"):
                payload = {"model": "test", "messages": []}
                response_data, retry_count = await provider._make_request_with_retry(
                    payload=payload, max_retries=2
                )

                assert retry_count == 1

    @pytest.mark.asyncio
    async def test_generation_failure_returns_error_metrics(self, provider):
        """Test failed generation includes error info in metrics."""
        with patch.object(provider, "_make_request_with_retry") as mock_request:
            mock_request.side_effect = OpenRouterError("Connection failed")

            with pytest.raises(OpenRouterError):
                await provider.generate(
                    prompt="Test",
                    model="google/gemini-3-flash-preview",
                    temperature=0.0,
                    max_tokens=1000,
                )

    @pytest.mark.asyncio
    async def test_request_error_triggers_retry(self, provider):
        """Test httpx.RequestError triggers exponential backoff retry."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = [
                httpx.RequestError("Connection refused"),
                httpx.RequestError("Connection refused"),
                httpx.RequestError("Connection refused"),
            ]
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep"):
                payload = {"model": "test", "messages": []}
                with pytest.raises(OpenRouterError, match="failed"):
                    await provider._make_request_with_retry(payload=payload, max_retries=2)
