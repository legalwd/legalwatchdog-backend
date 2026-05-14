"""Base provider interface for LLM clients."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ProviderType(str, Enum):
    """Supported LLM provider types."""

    GEMINI = "gemini"
    OPENROUTER = "openrouter"


class ModelCategory(str, Enum):
    """Model categories for routing decisions."""

    PREMIUM = "premium"
    BALANCED = "balanced"
    ECONOMY = "economy"


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Attributes:
        name (str): Full model identifier (e.g., 'anthropic/claude-3.5-sonnet').
        provider (str): Provider identifier (e.g., 'openrouter', 'gemini').
        category (ModelCategory): Model category for routing.
        cost_per_1m_input_tokens (float): Input token cost per million.
        cost_per_1m_output_tokens (float): Output token cost per million.
        context_window (int): Maximum context window size in tokens.
        supports_json_mode (bool): Whether model supports structured JSON output.
        supports_function_calling (bool): Whether model supports function calling.
        max_retries (int): Maximum retry attempts for this model.

    Examples:
        >>> config = ModelConfig(
        ...     name="anthropic/claude-3.5-sonnet",
        ...     provider="openrouter",
        ...     category=ModelCategory.PREMIUM,
        ...     cost_per_1m_input_tokens=3.00,
        ...     cost_per_1m_output_tokens=15.00,
        ...     context_window=200000,
        ...     supports_json_mode=True
        ... )
    """

    name: str
    provider: str
    category: ModelCategory
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float
    context_window: int
    supports_json_mode: bool = True
    supports_function_calling: bool = False
    max_retries: int = 2
    temperature_range: tuple[float, float] = (0.0, 1.0)


@dataclass
class LLMUsageMetrics:
    """Metrics for a single LLM request.

    Attributes:
        model (str): Model identifier used.
        provider (str): Provider identifier.
        input_tokens (int): Number of input tokens consumed.
        output_tokens (int): Number of output tokens generated.
        total_tokens (int): Total tokens consumed (input + output).
        cost_usd (float): Estimated cost in USD.
        latency_ms (float): Request latency in milliseconds.
        success (bool): Whether request succeeded.
        error_message (Optional[str]): Error message if failed.
        retry_count (int): Number of retries attempted.
        timestamp (datetime): Request timestamp.

    Examples:
        >>> metrics = LLMUsageMetrics(
        ...     model="anthropic/claude-3.5-sonnet",
        ...     provider="openrouter",
        ...     input_tokens=1500,
        ...     output_tokens=300,
        ...     total_tokens=1800,
        ...     cost_usd=0.0084,
        ...     latency_ms=1234.5,
        ...     success=True,
        ...     error_message=None,
        ...     retry_count=0,
        ...     timestamp=datetime.now()
        ... )
    """

    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    jurisdiction_id: Optional[str] = None

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class LLMResponse:
    """Standardized LLM response wrapper.

    Attributes:
        content (str): Generated text content.
        model (str): Model identifier used.
        provider (str): Provider identifier.
        usage_metrics (LLMUsageMetrics): Token usage and cost metrics.
        raw_response (Optional[dict]): Original provider response.

    Examples:
        >>> response = LLMResponse(
        ...     content='{"summary": "Example", "confidence": 0.95}',
        ...     model="anthropic/claude-3.5-sonnet",
        ...     provider="openrouter",
        ...     usage_metrics=metrics
        ... )
    """

    content: str
    model: str
    provider: str
    usage_metrics: LLMUsageMetrics
    raw_response: Optional[dict] = None


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    Defines interface for all LLM provider implementations with built-in
    metrics tracking, retry logic, and cost monitoring.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        json_mode: bool = False,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text completion from prompt.

        Args:
            prompt (str): Input prompt text.
            model (str): Model identifier to use.
            temperature (float, optional): Sampling temperature. Defaults to 0.1.
            max_tokens (int, optional): Maximum tokens to generate. Defaults to 1000.
            json_mode (bool, optional): Enable structured JSON output. Defaults to False.
            system_prompt (Optional[str], optional): System-level instructions.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse: Standardized response with content and metrics.

        Raises:
            LLMProviderError: If generation fails after retries.

        Examples:
            >>> response = await provider.generate(
            ...     prompt="Extract data from: ...",
            ...     model="anthropic/claude-3.5-sonnet",
            ...     temperature=0.0,
            ...     json_mode=True
            ... )
        """
        pass

    @abstractmethod
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate request cost in USD.

        Args:
            model (str): Model identifier.
            input_tokens (int): Number of input tokens.
            output_tokens (int): Number of output tokens.

        Returns:
            float: Estimated cost in USD.

        Examples:
            >>> cost = provider.calculate_cost(
            ...     model="anthropic/claude-3.5-sonnet",
            ...     input_tokens=1500,
            ...     output_tokens=300
            ... )
            >>> print(f"${cost:.4f}")
            $0.0084
        """
        pass

    @abstractmethod
    def get_model_config(self, model: str) -> ModelConfig:
        """Get configuration for a specific model.

        Args:
            model (str): Model identifier.

        Returns:
            ModelConfig: Model configuration details.

        Raises:
            ValueError: If model not supported.

        Examples:
            >>> config = provider.get_model_config("anthropic/claude-3.5-sonnet")
            >>> print(config.cost_per_1m_input_tokens)
            3.0
        """
        pass
