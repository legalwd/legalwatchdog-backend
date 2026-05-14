"""LLM manager with intelligent routing and monitoring integration."""

import logging
from typing import Any, Optional, Type, TypeVar, Union
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.core.config import settings
from app.api.core.exceptions import OpenRouterError
from app.api.core.llm.base_provider import (
    BaseLLMProvider,
    LLMResponse,
    ModelCategory,
)
from app.api.core.llm.openrouter_provider import OpenRouterProvider
from app.api.core.llm.usage_tracker import LLMUsageTracker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProviderFactory:
    """Factory for creating LLM provider instances.

    Examples:
        >>> provider = LLMProviderFactory.create_provider("openrouter")
    """

    @staticmethod
    def create_provider(provider_type: str = "openrouter") -> BaseLLMProvider:
        """Create LLM provider instance.

        Args:
            provider_type (str): Provider type ('openrouter', 'gemini').

        Returns:
            BaseLLMProvider: Configured provider instance.

        Raises:
            ValueError: If provider type not supported.

        Examples:
            >>> provider = LLMProviderFactory.create_provider("openrouter")
            >>> assert isinstance(provider, OpenRouterProvider)
        """
        if provider_type == "openrouter":
            api_key = settings.OPENROUTER_API_KEY
            logger.info(
                f"Creating OpenRouter provider with key: "
                f"{api_key[:20]}...{api_key[-10:] if len(api_key) > 30 else ''} "
                f"(length: {len(api_key)})"
            )
            return OpenRouterProvider(
                api_key=api_key,
                default_model=settings.OPENROUTER_DEFAULT_MODEL,
                fallback_models=settings.OPENROUTER_FALLBACK_MODEL_LIST,
                site_url=settings.OPENROUTER_SITE_URL,
                site_name=settings.OPENROUTER_SITE_NAME,
                timeout=settings.OPENROUTER_TIMEOUT,
                enable_routing=settings.OPENROUTER_ENABLE_ROUTING,
            )
        elif provider_type == "gemini":
            raise NotImplementedError("Gemini provider not yet migrated")
        else:
            raise ValueError(
                f"Unsupported provider: {provider_type}. Supported: ['openrouter', 'gemini']"
            )


class LLMManager:
    """High-level LLM manager with routing, fallback, and monitoring.

    Orchestrates LLM requests across multiple providers with intelligent
    routing, automatic fallback, cost optimization, and comprehensive
    usage tracking for admin dashboard integration.

    Attributes:
        provider (BaseLLMProvider): Primary LLM provider.
        tracker (LLMUsageTracker): Usage tracking service.
        enable_fallback (bool): Enable automatic fallback.
        enable_tracking (bool): Enable usage tracking.

    Examples:
        >>> manager = LLMManager(db=db_session)
        >>> response = await manager.generate_with_tracking(
        ...     prompt="Extract data...",
        ...     model_preference="premium",
        ...     user_id="user_123"
        ... )
    """

    def __init__(
        self,
        db: Optional[Union[AsyncSession, Session]] = None,
        provider_type: str = "openrouter",
        enable_fallback: bool = True,
        enable_tracking: bool = True,
    ):
        """Initialize LLM manager.

        Args:
            db (Optional[Union[AsyncSession, Session]]): Database session for tracking.
                Can be AsyncSession (API requests) or Session (Celery tasks).
            provider_type (str): Provider type to use.
            enable_fallback (bool): Enable automatic fallback.
            enable_tracking (bool): Enable usage tracking.
        """
        self.provider = LLMProviderFactory.create_provider(provider_type)
        self.tracker = LLMUsageTracker()
        self.db = db
        self.enable_fallback = enable_fallback
        self.enable_tracking = enable_tracking
        self.is_sync_db = isinstance(db, Session)  # Detect session type

    def select_model_by_category(self, category: ModelCategory = ModelCategory.PREMIUM) -> str:
        """Select model based on category preference and environment.

        In dev environment with auto-free enabled, uses free model by default
        unless explicitly requesting premium. Staging and production use configured models.

        Args:
            category (ModelCategory): Model category (premium, balanced, economy).

        Returns:
            str: Selected model identifier.

        Examples:
            >>> # Dev environment (auto-free enabled)
            >>> model = manager.select_model_by_category(ModelCategory.BALANCED)
            >>> print(model)
            xiaomi/mimo-v2-flash:free

            >>> # Staging/Production (uses configured models)
            >>> model = manager.select_model_by_category(ModelCategory.PREMIUM)
            >>> print(model)
            google/gemini-3-flash-preview
        """
        if (
            settings.ENVIRONMENT in ["dev", "development", "staging"]
            and settings.OPENROUTER_ENABLE_DEV_AUTO_FREE
        ):
            logger.info(
                f"Dev auto-free enabled: using {settings.OPENROUTER_DEV_MODEL} for {category}"
            )
            return settings.OPENROUTER_DEV_MODEL

        category_mapping = {
            ModelCategory.PREMIUM: settings.OPENROUTER_DEFAULT_MODEL,
            ModelCategory.BALANCED: (
                settings.OPENROUTER_FALLBACK_MODEL_LIST[0]
                if settings.OPENROUTER_FALLBACK_MODEL_LIST
                else settings.OPENROUTER_DEFAULT_MODEL
            ),
            ModelCategory.ECONOMY: (
                settings.OPENROUTER_FALLBACK_MODEL_LIST[-1]
                if settings.OPENROUTER_FALLBACK_MODEL_LIST
                else settings.OPENROUTER_DEFAULT_MODEL
            ),
        }

        selected = category_mapping.get(category, settings.OPENROUTER_DEFAULT_MODEL)
        logger.info(f"Selected model {selected} for category {category} in {settings.ENVIRONMENT}")
        return selected

    async def generate_with_tracking(
        self,
        prompt: str,
        model: Optional[str] = None,
        model_preference: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        json_mode: bool = False,
        response_model: Optional[Type[T]] = None,
        max_validation_retries: int = 3,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate with automatic tracking and fallback.

        Args:
            prompt (str): Input prompt text.
            model (Optional[str]): Specific model to use.
            model_preference (Optional[str]): Model category ('premium', 'balanced', 'economy').
            temperature (float): Sampling temperature.
            max_tokens (int): Maximum tokens to generate.
            json_mode (bool): Enable JSON mode.
            system_prompt (Optional[str]): System instructions.
            user_id (Optional[str]): User ID for tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            jurisdiction_id (Optional[str]): Jurisdiction ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse: Response with content and metrics.

        Raises:
            Exception: If all providers fail.

        Examples:
            >>> response = await manager.generate_with_tracking(
            ...     prompt="Extract legal data...",
            ...     model_preference="premium",
            ...     json_mode=True,
            ...     user_id="user_123",
            ...     endpoint="/api/v1/scrape"
            ... )
            >>> print(response.content)
        """
        if not model:
            if model_preference:
                category = {
                    "premium": ModelCategory.PREMIUM,
                    "balanced": ModelCategory.BALANCED,
                    "economy": ModelCategory.ECONOMY,
                }.get(model_preference.lower(), ModelCategory.PREMIUM)
                model = self.select_model_by_category(category)
            else:
                model = settings.OPENROUTER_DEFAULT_MODEL

        # Use fallback if enabled
        if self.enable_fallback and isinstance(self.provider, OpenRouterProvider):
            response = await self.provider.generate_with_fallback(
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
                jurisdiction_id=jurisdiction_id,
                **kwargs,
            )
        else:
            response = await self.provider.generate(
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
                jurisdiction_id=jurisdiction_id,
                **kwargs,
            )

        if request_id:
            response.usage_metrics.request_id = request_id

        # Track usage if enabled and DB session provided
        if self.enable_tracking and self.db:
            try:
                if self.is_sync_db:
                    self.tracker.log_usage_sync(
                        db=self.db,
                        metrics=response.usage_metrics,
                        endpoint=endpoint,
                        ip_address=ip_address,
                    )
                    logger.info(
                        f"Logged LLM usage (sync): model={response.usage_metrics.model}, "
                        f"tokens={response.usage_metrics.total_tokens}, "
                        f"cost=${response.usage_metrics.cost_usd:.6f}"
                    )
                else:
                    await self.tracker.log_usage(
                        db=self.db,
                        metrics=response.usage_metrics,
                        endpoint=endpoint,
                        ip_address=ip_address,
                    )

                    await self.tracker.update_provider_status(
                        db=self.db,
                        provider=response.provider,
                        model=response.model,
                        success=response.usage_metrics.success,
                        latency_ms=response.usage_metrics.latency_ms,
                        error_message=response.usage_metrics.error_message,
                    )
            except Exception as e:
                logger.error(f"Failed to track LLM usage: {e}", exc_info=True)

        return response

    def _build_sync_fallback_chain(self, primary_model: str) -> list[str]:
        """Build ordered list of models to try for sync fallback.

        Starts with the primary model, then adds the default model and
        configured fallback models, deduplicating along the way.

        Args:
            primary_model: The initially selected model identifier.

        Returns:
            list[str]: Ordered model identifiers for fallback attempts.

        Examples:
            >>> chain = manager._build_sync_fallback_chain(
            ...     "meta-llama/llama-3.3-70b-instruct:free"
            ... )
            >>> print(chain)
            ['meta-llama/llama-3.3-70b-instruct:free',
             'google/gemini-3-flash-preview',
             'google/gemini-2.5-flash-lite',
             'deepseek/deepseek-v3.2']
        """
        models = [primary_model]

        if settings.OPENROUTER_DEFAULT_MODEL not in models:
            models.append(settings.OPENROUTER_DEFAULT_MODEL)

        for fb_model in settings.OPENROUTER_FALLBACK_MODEL_LIST:
            if fb_model not in models:
                models.append(fb_model)

        return models

    def _make_sync_request(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        headers: dict[str, str],
    ) -> dict:
        """Make a single synchronous HTTP request to OpenRouter.

        Args:
            model: Model identifier to use.
            messages: Chat messages for the LLM.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            json_mode: Enable JSON response format.
            headers: HTTP headers with authorization.

        Returns:
            dict: Parsed JSON response from OpenRouter.

        Raises:
            httpx.HTTPStatusError: If the request returns a non-2xx status.
            httpx.TimeoutException: If the request times out.
        """
        import httpx

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        with httpx.Client(timeout=settings.OPENROUTER_TIMEOUT) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        return response.json()

    def _log_usage_isolated(
        self,
        metrics: Any,
        endpoint: Optional[str],
        ip_address: Optional[str],
        model_name: str,
    ) -> None:
        """Log LLM usage in an isolated database session.

        Uses a separate SyncSessionLocal so that commit/rollback
        from usage tracking never affects the parent pipeline's
        transaction state. This is critical in Celery tasks where
        the main session manages scrape job state transitions.

        Args:
            metrics: LLMUsageMetrics to persist.
            endpoint: API endpoint identifier for the log entry.
            ip_address: Client IP address for the log entry.
            model_name: Model name for log messages.
        """
        from app.api.db.database import SyncSessionLocal

        try:
            tracking_db = SyncSessionLocal()
            try:
                self.tracker.log_usage_sync(
                    db=tracking_db,
                    metrics=metrics,
                    endpoint=endpoint,
                    ip_address=ip_address,
                )
                logger.info(
                    f"Logged LLM usage (isolated sync): "
                    f"model={model_name}, "
                    f"tokens={metrics.total_tokens}, "
                    f"success={metrics.success}"
                )
            except Exception as e:
                logger.error(f"Failed to track LLM usage (sync): {e}")
            finally:
                tracking_db.close()
        except Exception as e:
            logger.error(f"Failed to create tracking session: {e}")

    def generate_with_tracking_sync(
        self,
        prompt: str,
        model: Optional[str] = None,
        model_preference: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
        json_mode: bool = False,
        system_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Sync generation with automatic model fallback for Celery tasks.

        Uses httpx sync client to avoid event loop issues in Celery workers.
        When the primary model fails (rate limit, timeout, error), automatically
        falls back to alternative models in the configured fallback chain,
        mirroring the async generate_with_tracking behavior.

        Args:
            prompt: Input prompt text.
            model: Specific model to use (overrides model_preference).
            model_preference: Model category ('premium', 'balanced', 'economy').
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            json_mode: Enable JSON response format.
            system_prompt: System-level instructions.
            user_id: User ID for usage tracking.
            organization_id: Organization ID for usage tracking.
            project_id: Project ID for usage tracking.
            jurisdiction_id: Jurisdiction ID for usage tracking.
            endpoint: API endpoint identifier for tracking.
            ip_address: Client IP for tracking.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse: Response from the first successful model.

        Raises:
            OpenRouterError: If all models in the fallback chain fail.

        Examples:
            >>> response = manager.generate_with_tracking_sync(
            ...     prompt="Detect changes...",
            ...     model_preference="premium",
            ...     json_mode=True,
            ... )
            >>> print(response.model)
            'google/gemini-3-flash-preview'
        """
        import time

        from app.api.core.llm.base_provider import LLMUsageMetrics

        if not model:
            if model_preference:
                category = {
                    "premium": ModelCategory.PREMIUM,
                    "balanced": ModelCategory.BALANCED,
                    "economy": ModelCategory.ECONOMY,
                }.get(model_preference.lower(), ModelCategory.PREMIUM)
                model = self.select_model_by_category(category)
            else:
                model = self.select_model_by_category(ModelCategory.PREMIUM)

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": (settings.OPENROUTER_SITE_URL or "https://legalwatchdog.ai"),
            "X-Title": (settings.OPENROUTER_SITE_NAME or "LegalWatchdog"),
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self.enable_fallback:
            models_to_try = self._build_sync_fallback_chain(model)
        else:
            models_to_try = [model]

        last_error = None

        effective_request_id = request_id or str(uuid4())

        for idx, current_model in enumerate(models_to_try):
            start_time = time.time()
            try:
                logger.info(
                    f"Sync generation attempt with model {current_model} "
                    f"(attempt {idx + 1}/{len(models_to_try)})"
                )

                result = self._make_sync_request(
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                    headers=headers,
                )

                latency_ms = (time.time() - start_time) * 1000

                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = result.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                cost_usd = self.provider.calculate_cost(
                    model=current_model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                )

                metrics = LLMUsageMetrics(
                    model=current_model,
                    provider="openrouter",
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    total_tokens=usage.get("total_tokens", 0),
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    success=True,
                    request_id=effective_request_id,
                    user_id=user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    jurisdiction_id=jurisdiction_id,
                )

                llm_response = LLMResponse(
                    content=content,
                    model=current_model,
                    provider="openrouter",
                    usage_metrics=metrics,
                    raw_response=result,
                )

                if self.enable_tracking and self.db and self.is_sync_db:
                    self._log_usage_isolated(
                        metrics=metrics,
                        endpoint=endpoint,
                        ip_address=ip_address,
                        model_name=current_model,
                    )

                if idx > 0:
                    logger.info(
                        f"Sync fallback successful: model "
                        f"{current_model} succeeded after "
                        f"{idx} failed attempt(s)"
                    )

                return llm_response

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                last_error = e
                logger.warning(
                    f"Sync model {current_model} failed "
                    f"(attempt {idx + 1}/{len(models_to_try)}): {e}"
                )

                if self.enable_tracking and self.db and self.is_sync_db:
                    fail_metrics = LLMUsageMetrics(
                        model=current_model,
                        provider="openrouter",
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        cost_usd=0.0,
                        latency_ms=latency_ms,
                        success=False,
                        error_message=str(e),
                        request_id=effective_request_id,
                        user_id=user_id,
                        organization_id=organization_id,
                        project_id=project_id,
                        jurisdiction_id=jurisdiction_id,
                    )
                    self._log_usage_isolated(
                        metrics=fail_metrics,
                        endpoint=endpoint,
                        ip_address=ip_address,
                        model_name=current_model,
                    )

                if idx < len(models_to_try) - 1:
                    backoff = min(2**idx, 4)
                    logger.info(f"Retrying with next model in {backoff}s...")
                    time.sleep(backoff)
                    continue

        raise OpenRouterError(f"All sync models failed. Last error: {last_error}")

    async def get_usage_summary(
        self,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        days: int = 30,
    ) -> dict:
        """Get usage summary for user or organization.

        Args:
            user_id (Optional[str]): User ID filter.
            organization_id (Optional[str]): Organization ID filter.
            days (int): Number of days to query.

        Returns:
            dict: Usage summary statistics.

        Raises:
            ValueError: If no database session available.

        Examples:
            >>> summary = await manager.get_usage_summary(
            ...     organization_id="org_123",
            ...     days=7
            ... )
            >>> print(f"Total cost: ${summary['total_cost_usd']:.2f}")
        """
        if not self.db:
            raise ValueError("Database session required for usage tracking")

        from datetime import datetime, timedelta
        from uuid import UUID

        start_date = datetime.utcnow() - timedelta(days=days)

        return await self.tracker.get_usage_stats(
            db=self.db,
            user_id=UUID(user_id) if user_id else None,
            organization_id=UUID(organization_id) if organization_id else None,
            start_date=start_date,
        )

    async def get_provider_health_status(self) -> list[dict]:
        """Get health status of all LLM providers.

        Returns:
            list[dict]: Provider health statuses.

        Raises:
            ValueError: If no database session available.

        Examples:
            >>> health = await manager.get_provider_health_status()
            >>> for provider in health:
            ...     print(f"{provider['provider']}: {provider['is_available']}")
        """
        if not self.db:
            raise ValueError("Database session required for health tracking")

        return await self.tracker.get_provider_health(self.db)
