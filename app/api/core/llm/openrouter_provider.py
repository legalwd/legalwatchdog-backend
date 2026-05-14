"""OpenRouter LLM provider implementation with routing and fallback."""

import asyncio
import logging
import random
import time
import uuid
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.api.core.exceptions import (
    OpenRouterAuthenticationError,
    OpenRouterError,
    OpenRouterRateLimitError,
)
from app.api.core.llm.base_provider import (
    BaseLLMProvider,
    LLMResponse,
    LLMUsageMetrics,
    ModelCategory,
    ModelConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

try:
    import instructor
    from openai import OpenAI

    _HAS_INSTRUCTOR = True
except ImportError:
    _HAS_INSTRUCTOR = False
    instructor = None
    OpenAI = None
    logger.warning("Instructor not installed. Structured outputs use JSON mode fallback.")


# Model pricing catalog (verified against OpenRouter official pricing Jan 2026)
# Source: https://openrouter.ai/models
OPENROUTER_MODEL_CATALOG = {
    "google/gemini-3-flash-preview": ModelConfig(
        name="google/gemini-3-flash-preview",
        provider="openrouter",
        category=ModelCategory.PREMIUM,
        cost_per_1m_input_tokens=0.50,
        cost_per_1m_output_tokens=3.00,
        context_window=1000000,
        supports_json_mode=True,
        supports_function_calling=True,
        max_retries=2,
    ),
    "google/gemini-2.5-flash-lite": ModelConfig(
        name="google/gemini-2.5-flash-lite",
        provider="openrouter",
        category=ModelCategory.BALANCED,
        cost_per_1m_input_tokens=0.10,
        cost_per_1m_output_tokens=0.40,
        context_window=1000000,
        supports_json_mode=True,
        supports_function_calling=True,
        max_retries=2,
    ),
    "deepseek/deepseek-v3.2": ModelConfig(
        name="deepseek/deepseek-v3.2",
        provider="openrouter",
        category=ModelCategory.ECONOMY,
        cost_per_1m_input_tokens=0.21,
        cost_per_1m_output_tokens=0.32,
        context_window=163840,
        supports_json_mode=True,
        supports_function_calling=True,
        max_retries=2,
    ),
    "xiaomi/mimo-v2-flash": ModelConfig(
        name="xiaomi/mimo-v2-flash",
        provider="openrouter",
        category=ModelCategory.ECONOMY,
        cost_per_1m_input_tokens=0.09,
        cost_per_1m_output_tokens=0.29,
        context_window=262144,
        supports_json_mode=True,
        supports_function_calling=True,
        max_retries=2,
    ),
}


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider with routing, fallback, and cost tracking.

    Manages multiple model providers through OpenRouter's unified API,
    implementing intelligent routing, automatic fallback, and comprehensive
    usage monitoring for admin dashboard integration.

    Attributes:
        api_key (str): OpenRouter API key.
        base_url (str): OpenRouter API base URL.
        default_model (str): Primary model identifier.
        fallback_models (list[str]): Ordered list of fallback models.
        site_url (Optional[str]): Site URL for OpenRouter rankings.
        site_name (Optional[str]): Site name for OpenRouter rankings.
        timeout (int): HTTP request timeout in seconds.

    Examples:
        >>> provider = OpenRouterProvider(
        ...     api_key="sk-or-...",
        ...     default_model="anthropic/claude-3.5-sonnet",
        ...     fallback_models=[
        ...         "meta-llama/llama-3.1-405b-instruct",
        ...         "mistralai/mistral-large-2407"
        ...     ]
        ... )
        >>> response = await provider.generate(
        ...     prompt="Extract data...",
        ...     model="anthropic/claude-3.5-sonnet",
        ...     json_mode=True
        ... )
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "google/gemini-3-flash-preview",
        fallback_models: Optional[list[str]] = None,
        site_url: Optional[str] = None,
        site_name: Optional[str] = None,
        timeout: int = 120,
        enable_routing: bool = True,
    ):
        """Initialize OpenRouter provider.

        Args:
            api_key (str): OpenRouter API key.
            default_model (str): Primary model identifier.
            fallback_models (Optional[list[str]]): Fallback model list.
            site_url (Optional[str]): Site URL for attribution.
            site_name (Optional[str]): Site name for attribution.
            timeout (int): Request timeout in seconds.
            enable_routing (bool): Enable intelligent model routing.
        """
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.default_model = default_model
        self.fallback_models = fallback_models or [
            "google/gemini-2.5-flash-lite",
            "deepseek/deepseek-v3.2",
        ]
        self.site_url = site_url
        self.site_name = site_name
        self.timeout = timeout
        self.enable_routing = enable_routing

    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a specific model.

        Args:
            model (str): Model identifier.

        Returns:
            ModelConfig: Model configuration details.

        Raises:
            ValueError: If model not supported.

        Examples:
            >>> config = provider.get_model_config("google/gemini-3-flash-preview")
            >>> print(config.category)
            ModelCategory.PREMIUM
        """
        if model not in OPENROUTER_MODEL_CATALOG:
            raise ValueError(
                f"Model {model} not supported. Available: {list(OPENROUTER_MODEL_CATALOG.keys())}"
            )
        return OPENROUTER_MODEL_CATALOG[model]

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate request cost in USD including OpenRouter 5.5% fee.

        Args:
            model (str): Model identifier.
            input_tokens (int): Number of input tokens.
            output_tokens (int): Number of output tokens.

        Returns:
            float: Estimated cost in USD.

        Examples:
            >>> cost = provider.calculate_cost(
            ...     model="google/gemini-3-flash-preview",
            ...     input_tokens=1500,
            ...     output_tokens=300
            ... )
            >>> print(f"${cost:.6f}")
            $0.001739
        """
        config = self.get_model_config(model)
        input_cost = (input_tokens / 1_000_000) * config.cost_per_1m_input_tokens
        output_cost = (output_tokens / 1_000_000) * config.cost_per_1m_output_tokens
        base_cost = input_cost + output_cost
        platform_fee = base_cost * 0.055
        total_cost = base_cost + platform_fee

        return total_cost

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for OpenRouter API requests.

        Returns:
            dict[str, str]: Headers dictionary with authorization and attribution.

        Examples:
            >>> headers = provider._build_headers()
            >>> assert "Authorization" in headers
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name

        return headers

    def _build_request_payload(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        system_prompt: Optional[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build request payload for OpenRouter API.

        Args:
            prompt (str): User prompt.
            model (str): Model identifier.
            temperature (float): Sampling temperature.
            max_tokens (int): Maximum output tokens.
            json_mode (bool): Enable JSON mode.
            system_prompt (Optional[str]): System instructions.
            **kwargs: Additional parameters.

        Returns:
            dict[str, Any]: Request payload.

        Examples:
            >>> payload = provider._build_request_payload(
            ...     prompt="Extract...",
            ...     model="anthropic/claude-3.5-sonnet",
            ...     temperature=0.0,
            ...     max_tokens=1000,
            ...     json_mode=True,
            ...     system_prompt="You are an expert..."
            ... )
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            config = self.get_model_config(model)
            if config.supports_json_mode:
                if "claude" in model.lower():
                    payload["response_format"] = {"type": "json_object"}
                elif "gpt" in model.lower():
                    payload["response_format"] = {"type": "json_object"}
                else:
                    payload["response_format"] = {"type": "json_object"}

        if self.enable_routing:
            payload["route"] = "fallback"

        # Disable reasoning mode for Xiaomi MiMo models (optimized for agentic tools)
        if "xiaomi/mimo" in model.lower():
            payload["reasoning"] = {"enabled": False}

        payload.update(kwargs)
        return payload

    async def _make_request_with_retry(
        self,
        payload: dict[str, Any],
        max_retries: int = 2,
    ) -> tuple[dict[str, Any], int]:
        """Make HTTP request to OpenRouter with exponential backoff retry.

        Args:
            payload (dict[str, Any]): Request payload.
            max_retries (int): Maximum retry attempts.

        Returns:
            tuple[dict[str, Any], int]: Response data and retry count.

        Raises:
            OpenRouterError: If all retries fail.
            OpenRouterRateLimitError: If rate limited.
            OpenRouterAuthenticationError: If authentication fails.

        Examples:
            >>> response, retries = await provider._make_request_with_retry(payload)
            >>> print(f"Success after {retries} retries")
        """
        headers = self._build_headers()
        retry_count = 0

        logger.debug(
            f"Making OpenRouter request with auth header: "
            f"Authorization: {headers.get('Authorization', 'MISSING')[:30]}..."
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 10))
                        logger.warning(
                            f"OpenRouter rate limit hit. "
                            f"Retry after {retry_after}s (attempt {attempt + 1}/{max_retries + 1})"
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(retry_after + random.uniform(0, 2))
                            retry_count += 1
                            continue
                        else:
                            raise OpenRouterRateLimitError(
                                f"Rate limit exceeded after {max_retries} retries"
                            )

                    if response.status_code == 401:
                        error_detail = response.json() if response.text else {}
                        logger.error(
                            f"OpenRouter 401 Authentication Error. "
                            f"Response: {error_detail}. "
                            f"API Key (masked): {self.api_key[:20]}...{self.api_key[-10:]}"
                        )
                        raise OpenRouterAuthenticationError("Invalid OpenRouter API key")

                    if response.status_code >= 400:
                        error_detail = response.json() if response.text else {}
                        logger.error(f"OpenRouter error {response.status_code}: {error_detail}")
                        if attempt < max_retries:
                            backoff = (2**attempt) + random.uniform(0, 1)
                            await asyncio.sleep(backoff)
                            retry_count += 1
                            continue
                        else:
                            raise OpenRouterError(f"HTTP {response.status_code}: {error_detail}")
                    return response.json(), retry_count
                except httpx.TimeoutException as e:
                    logger.warning(
                        f"OpenRouter request timeout (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    if attempt < max_retries:
                        backoff = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(backoff)
                        retry_count += 1
                        continue
                    else:
                        raise OpenRouterError(f"Request timeout after {max_retries} retries") from e

                except httpx.RequestError as e:
                    logger.error(
                        f"OpenRouter request failed (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    if attempt < max_retries:
                        backoff = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(backoff)
                        retry_count += 1
                        continue
                    else:
                        raise OpenRouterError(f"Request failed after {max_retries} retries") from e

        raise OpenRouterError("Unexpected error: no response received")

    async def _validate_with_instructor(
        self,
        content: str,
        response_model: Type[T],
        max_retries: int,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
    ) -> T:
        """Validate LLM response content with Pydantic model via Instructor.

        Attempts to parse and validate the raw content against the response_model.
        If validation fails, uses Instructor to retry with the model and schema.

        Args:
            content: Raw LLM response content (expected JSON).
            response_model: Pydantic model class for validation.
            max_retries: Maximum validation retry attempts.
            prompt: Original prompt (for retry context).
            model: Model identifier (for retry).
            temperature: Temperature setting.
            max_tokens: Max tokens setting.
            system_prompt: System prompt (for retry context).

        Returns:
            Validated Pydantic model instance.

        Raises:
            OpenRouterError: If validation fails after all retries.
        """
        import json

        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            validated = response_model.model_validate(parsed)
            logger.info(f"Direct Pydantic validation successful: {response_model.__name__}")
            return validated
        except Exception as direct_error:
            logger.warning(f"Direct validation failed, attempting Instructor retry: {direct_error}")

        if not _HAS_INSTRUCTOR:
            raise OpenRouterError("Pydantic validation failed and Instructor not available")

        try:
            openai_client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers=self._build_headers(),
            )
            client = instructor.from_openai(openai_client, mode=instructor.Mode.JSON)

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            validated = client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )

            logger.info(f"Instructor validation successful after retry: {response_model.__name__}")
            return validated

        except Exception as instructor_error:
            logger.error(
                f"Instructor validation failed after {max_retries} retries: {instructor_error}"
            )
            raise OpenRouterError(
                f"Structured output validation failed: {instructor_error}"
            ) from instructor_error

    async def generate_with_fallback(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        json_mode: bool = False,
        response_model: Optional[Type[T]] = None,
        max_validation_retries: int = 3,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate with automatic fallback to alternative models.

        Attempts generation with default model first, then falls back to
        alternative models in order if primary fails. Tracks all attempts
        for cost and usage monitoring.

        Args:
            prompt (str): Input prompt text.
            temperature (float): Sampling temperature.
            max_tokens (int): Maximum tokens to generate.
            json_mode (bool): Enable JSON mode.
            system_prompt (Optional[str]): System instructions.
            user_id (Optional[str]): User ID for tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse: Response from successful model.

        Raises:
            OpenRouterError: If all models fail.

        Examples:
            >>> response = await provider.generate_with_fallback(
            ...     prompt="Extract legal data...",
            ...     json_mode=True,
            ...     user_id="user_123"
            ... )
        """
        primary_model = model or self.default_model
        models_to_try = [primary_model]
        if primary_model != self.default_model:
            models_to_try.append(self.default_model)

        for fb_model in self.fallback_models:
            if fb_model not in models_to_try:
                models_to_try.append(fb_model)

        last_error = None

        for idx, model in enumerate(models_to_try):
            try:
                logger.info(
                    f"Attempting generation with model {model} "
                    f"(attempt {idx + 1}/{len(models_to_try)})"
                )

                response = await self.generate(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    response_model=response_model,
                    max_validation_retries=max_validation_retries,
                    system_prompt=system_prompt,
                    user_id=user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    **kwargs,
                )

                if idx > 0:
                    logger.info(
                        f"Fallback successful: model {model} succeeded after {idx} failed attempts"
                    )

                return response

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Model {model} failed (attempt {idx + 1}/{len(models_to_try)}): {e}"
                )
                if idx < len(models_to_try) - 1:
                    await asyncio.sleep(1)
                    continue

        raise OpenRouterError(f"All models failed. Last error: {last_error}") from last_error

    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        json_mode: bool = False,
        response_model: Optional[Type[T]] = None,
        max_validation_retries: int = 3,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text completion from prompt.

        Args:
            prompt (str): Input prompt text.
            model (str): Model identifier to use.
            temperature (float): Sampling temperature.
            max_tokens (int): Maximum tokens to generate.
            json_mode (bool): Enable structured JSON output.
            system_prompt (Optional[str]): System-level instructions.
            user_id (Optional[str]): User ID for tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse: Standardized response with content and metrics.

        Raises:
            OpenRouterError: If generation fails after retries.

        Examples:
            >>> response = await provider.generate(
            ...     prompt="Extract data from: ...",
            ...     model="anthropic/claude-3.5-sonnet",
            ...     temperature=0.0,
            ...     json_mode=True
            ... )
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()

        config = self.get_model_config(model)
        payload = self._build_request_payload(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            system_prompt=system_prompt,
            **kwargs,
        )

        try:
            response_data, retry_count = await self._make_request_with_retry(
                payload=payload,
                max_retries=config.max_retries,
            )

            content = response_data["choices"][0]["message"]["content"]
            usage = response_data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            cost_usd = self.calculate_cost(model, input_tokens, output_tokens)
            latency_ms = (time.time() - start_time) * 1000

            validated_content = content
            if response_model is not None:
                validated_content = await self._validate_with_instructor(
                    content=content,
                    response_model=response_model,
                    max_retries=max_validation_retries,
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )

            usage_metrics = LLMUsageMetrics(
                model=model,
                provider="openrouter",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=True,
                error_message=None,
                retry_count=retry_count,
                timestamp=None,
                request_id=request_id,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
            )

            logger.info(
                f"OpenRouter request successful: model={model}, "
                f"tokens={total_tokens}, cost=${cost_usd:.6f}, "
                f"latency={latency_ms:.1f}ms, retries={retry_count}"
            )

            return LLMResponse(
                content=validated_content,
                model=model,
                provider="openrouter",
                usage_metrics=usage_metrics,
                raw_response=response_data,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            usage_metrics = LLMUsageMetrics(
                model=model,
                provider="openrouter",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error_message=str(e),
                retry_count=config.max_retries,
                timestamp=None,
                request_id=request_id,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
            )

            logger.error(
                f"OpenRouter request failed: model={model}, "
                f"latency={latency_ms:.1f}ms, error={str(e)}"
            )

            raise
