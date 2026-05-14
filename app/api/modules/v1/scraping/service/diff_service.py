import asyncio
import json
import logging
import random
from typing import Any, Dict, Optional, Union

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig

    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.core.config import settings
from app.api.core.exceptions import DiffAIServiceError
from app.api.core.llm.llm_manager import LLMManager
from app.api.modules.v1.scraping.constants.change_detection import (
    build_change_detection_prompt,
)
from app.api.modules.v1.scraping.schemas.ai_analysis import ChangeDetectionResult

logger = logging.getLogger(__name__)

if _HAS_GENAI and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)


CHANGE_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "has_changed": {"type": "boolean"},
        "change_summary": {"type": "string"},
        "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "field_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_name": {"type": "string"},
                    "old_value": {"type": ["string", "null"]},
                    "new_value": {"type": ["string", "null"]},
                    "change_type": {"type": "string"},
                    "change_description": {"type": "string"},
                },
                "required": ["field_name", "change_type", "change_description"],
            },
        },
    },
    "required": ["has_changed", "change_summary", "risk_level", "field_changes"],
}


class DiffAIService:
    """Provides semantic change detection using OpenRouter with Gemini fallback.

    Detects meaningful changes between old and new data structures using LLMs
    with schema-enforced JSON output. Routes to OpenRouter (recommended) or
    Gemini (legacy fallback) based on configuration.
    """

    def __init__(
        self,
        db: Optional[Union[AsyncSession, Session]] = None,
        use_openrouter: bool = True,
    ):
        """Initialize the DiffAIService with LLM configuration.

        Args:
            db (Optional[Union[AsyncSession, Session]]): Database session for tracking.
                Can be AsyncSession (API requests) or Session (Celery tasks).
            use_openrouter (bool): Use OpenRouter (True) or fallback to Gemini
                                   (False).

        Raises:
            ImportError: If google-generativeai is not installed (Gemini).
            ValueError: If required API keys are not configured.
        """
        self.db = db
        self.use_openrouter = use_openrouter

        if use_openrouter:
            self.llm_manager = LLMManager(
                db=db,
                provider_type="openrouter",
                enable_fallback=True,
                enable_tracking=True,
            )
            logger.info("DiffAIService initialized with OpenRouter + fallback")
        else:
            if not _HAS_GENAI:
                raise ImportError("`google-generativeai` package missing.")
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set.")

            self.model = genai.GenerativeModel(
                model_name=settings.MODEL_NAME,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=CHANGE_DETECTION_SCHEMA,
                ),
            )
            logger.info("DiffAIService initialized with Gemini (legacy mode)")

    async def detect_semantic_change(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        monitoring_instruction: str,
        source_id: Optional[str] = None,
        max_retries: int = 2,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        field_name_mapping: Optional[Dict[str, str]] = None,
    ) -> ChangeDetectionResult:
        """Detects meaningful changes between old and new data structures.

        Routes to OpenRouter if enabled (recommended), otherwise uses Gemini
        (legacy fallback). Performs deterministic AI analysis with JSON schema
        enforcement and safe fallbacks.

        Normalizes field names before comparison to focus on factual changes
        rather than structural differences.

        Args:
            old_data (Dict[str, Any]): Previously stored structured data.
            new_data (Dict[str, Any]): Newly scraped or updated data.
            monitoring_instruction (str): Human-readable rule describing what
                                          changes matter.
            source_id (Optional[str]): Source UUID for field normalization.
            max_retries (int, optional): Max retries if AI produces invalid
                                         JSON. Defaults to 2.
            user_id (Optional[str]): User ID for usage tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.
            field_name_mapping (Optional[Dict[str, str]]): Mapping of clean keys to
                                                           formatted display names.

        Returns:
            ChangeDetectionResult: Validated result with has_changed (bool),
                                   change_summary (str), risk_level
                                   ("LOW" | "MEDIUM" | "HIGH"), and detailed
                                   field_changes list.

        Raises:
            DiffAIServiceError: If all retries and fallbacks fail.
        """
        if source_id:
            from app.api.modules.v1.scraping.service.data_normalization_service import (
                DataNormalizationService,
            )

            normalizer = DataNormalizationService(db=self.db)
            old_data_normalized = normalizer.normalize_extracted_data(old_data, source_id)
            new_data_normalized = normalizer.normalize_extracted_data(new_data, source_id)
            logger.info(f"Data normalized for source {source_id}")
        else:
            old_data_normalized = old_data
            new_data_normalized = new_data
            logger.warning("No source_id provided, skipping field normalization")

        old_json = json.dumps(old_data_normalized, sort_keys=True, default=str)
        new_json = json.dumps(new_data_normalized, sort_keys=True, default=str)

        if old_json == new_json:
            return ChangeDetectionResult(
                has_changed=False,
                change_summary="No changes (Exact Match)",
                risk_level="LOW",
                field_changes=[],
            )

        if not old_data_normalized and new_data_normalized:
            return ChangeDetectionResult(
                has_changed=True,
                change_summary="Initial data extraction (New Record)",
                risk_level="LOW",
                field_changes=[],
            )

        if self.use_openrouter:
            return await self.run_change_detection_with_openrouter(
                old_json=old_json,
                new_json=new_json,
                monitoring_instruction=monitoring_instruction,
                source_id=source_id,
                max_retries=max_retries,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                endpoint=endpoint,
                ip_address=ip_address,
                field_name_mapping=field_name_mapping,
            )

        return await self._run_gemini_change_detection(
            old_json=old_json,
            new_json=new_json,
            monitoring_instruction=monitoring_instruction,
            source_id=source_id,
            max_retries=max_retries,
        )

    async def run_change_detection_with_openrouter(
        self,
        old_json: str,
        new_json: str,
        monitoring_instruction: str,
        source_id: Optional[str] = None,
        max_retries: int = 2,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        field_name_mapping: Optional[Dict[str, str]] = None,
    ) -> ChangeDetectionResult:
        """Execute change detection using OpenRouter with intelligent routing.

        Args:
            old_json (str): Old data as JSON string (normalized).
            new_json (str): New data as JSON string (normalized).
            monitoring_instruction (str): Change detection goal.
            source_id (Optional[str]): Source UUID (for logging).
            max_retries (int, optional): Max retries. Defaults to 2.
            user_id (Optional[str]): User ID for tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.

        Returns:
            ChangeDetectionResult: Detection result validated and formatted.

        Raises:
            DiffAIServiceError: If extraction fails after all retries/fallbacks.
        """
        prompt = build_change_detection_prompt(
            monitoring_instruction=monitoring_instruction,
            old_json=old_json,
            new_json=new_json,
            field_name_mapping=field_name_mapping,
        )

        for attempt in range(max_retries + 1):
            try:
                response = await self.llm_manager.generate_with_tracking(
                    prompt=prompt,
                    model_preference="premium",
                    temperature=0.0,
                    max_tokens=1000,
                    json_mode=True,
                    response_model=ChangeDetectionResult,
                    max_validation_retries=3,
                    system_prompt=(
                        "You are a regulatory compliance auditor. "
                        "Detect meaningful changes accurately."
                    ),
                    user_id=user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    endpoint=endpoint or "/api/v1/diff/detect",
                    ip_address=ip_address,
                )

                content = response.content
                if isinstance(content, ChangeDetectionResult):
                    validated_result = content
                    logger.info("Structured change detection successful via response_model")
                elif isinstance(content, dict):
                    validated_result = ChangeDetectionResult.model_validate(content)
                    logger.info("Change detection returned dict, validated successfully")
                elif isinstance(content, str):
                    validated_result = ChangeDetectionResult.model_validate_json(content)
                    logger.info("Change detection returned JSON string, validated successfully")
                else:
                    logger.error(f"LLM returned unexpected type: {type(content)}")
                    raise ValidationError.from_exception_data("LLM Content", [])

                logger.info(
                    f"OpenRouter change detection successful: "
                    f"has_changed={validated_result.has_changed}, "
                    f"risk_level={validated_result.risk_level}"
                )
                return validated_result

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"Change detection failed (Attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, 0.1) * exponential_delay
                    await asyncio.sleep(exponential_delay + jitter)
                    continue

                if _HAS_GENAI and settings.GEMINI_API_KEY:
                    logger.warning(
                        "OpenRouter failed. Falling back to Gemini for change detection..."
                    )
                    try:
                        return await self._run_gemini_change_detection(
                            old_json=old_json,
                            new_json=new_json,
                            monitoring_instruction=monitoring_instruction,
                        )
                    except Exception as gemini_error:
                        logger.error(
                            f"Gemini fallback also failed: {gemini_error}",
                            exc_info=True,
                        )
                        raise DiffAIServiceError(
                            f"Both OpenRouter and Gemini failed. "
                            f"OpenRouter: {e}. Gemini: {gemini_error}"
                        )

                raise DiffAIServiceError(f"Failed to detect changes using OpenRouter: {e}")

            except Exception as e:
                logger.error(f"Change detection failed: {e}", exc_info=True)

                if _HAS_GENAI and settings.GEMINI_API_KEY:
                    logger.warning(
                        "OpenRouter failed. Falling back to Gemini for change detection..."
                    )
                    try:
                        return await self._run_gemini_change_detection(
                            old_json=old_json,
                            new_json=new_json,
                            monitoring_instruction=monitoring_instruction,
                        )
                    except Exception as gemini_error:
                        logger.error(
                            f"Gemini fallback also failed: {gemini_error}",
                            exc_info=True,
                        )
                        raise DiffAIServiceError(
                            f"Both OpenRouter and Gemini failed. "
                            f"OpenRouter: {e}. Gemini: {gemini_error}"
                        )

                raise DiffAIServiceError(f"Failed to detect changes using OpenRouter: {e}")

    def detect_semantic_change_sync(
        self,
        old_data: Dict[str, Any],
        new_data: Dict[str, Any],
        monitoring_instruction: str,
        source_id: Optional[str] = None,
        max_retries: int = 2,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        field_name_mapping: Optional[Dict[str, str]] = None,
    ) -> ChangeDetectionResult:
        """Sync version of detect_semantic_change for Celery tasks.

        Uses httpx sync client and sync DB tracking to avoid event loop issues.
        """
        import time

        old_json = json.dumps(old_data, sort_keys=True, default=str)
        new_json = json.dumps(new_data, sort_keys=True, default=str)

        if old_json == new_json:
            return ChangeDetectionResult(
                has_changed=False,
                change_summary="No changes (Exact Match)",
                risk_level="LOW",
                field_changes=[],
            )

        if not old_data and new_data:
            return ChangeDetectionResult(
                has_changed=True,
                change_summary="Initial data extraction (New Record)",
                risk_level="LOW",
                field_changes=[],
            )

        prompt = build_change_detection_prompt(
            monitoring_instruction=monitoring_instruction,
            old_json=old_json,
            new_json=new_json,
            field_name_mapping=field_name_mapping,
        )

        for attempt in range(max_retries + 1):
            try:
                response = self.llm_manager.generate_with_tracking_sync(
                    prompt=prompt,
                    model_preference="premium",
                    temperature=0.0,
                    max_tokens=1000,
                    json_mode=True,
                    system_prompt=(
                        "You are a regulatory compliance auditor. "
                        "Detect meaningful changes accurately. "
                        "Return valid JSON only."
                    ),
                    user_id=user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    endpoint=endpoint or "/api/v1/diff/detect-sync",
                    ip_address=ip_address,
                )

                content = response.content
                if isinstance(content, ChangeDetectionResult):
                    validated_result = content
                elif isinstance(content, dict):
                    validated_result = ChangeDetectionResult.model_validate(content)
                elif isinstance(content, str):
                    validated_result = ChangeDetectionResult.model_validate_json(content)
                else:
                    logger.error(f"LLM returned unexpected type: {type(content)}")
                    raise ValidationError.from_exception_data("LLM Content", [])

                logger.info(
                    f"Sync change detection: "
                    f"has_changed={validated_result.has_changed}, "
                    f"risk={validated_result.risk_level}, "
                    f"model={response.model}"
                )
                return validated_result

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"Sync change detection validation failed (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries:
                    import time

                    time.sleep(1.0 * (2**attempt))
                    continue
                raise DiffAIServiceError(f"Sync change detection failed: {e}") from e

            except Exception as e:
                logger.error(
                    f"Sync change detection failed after "
                    f"model fallback (attempt {attempt + 1}): {e}"
                )
                raise DiffAIServiceError(f"Sync change detection failed: {e}") from e

        return ChangeDetectionResult(
            has_changed=True,
            change_summary="Unable to analyze changes - assuming changed for safety",
            risk_level="MEDIUM",
            field_changes=[],
        )

    async def _run_gemini_change_detection(
        self,
        old_json: str,
        new_json: str,
        monitoring_instruction: str,
        source_id: Optional[str] = None,
        max_retries: int = 2,
    ) -> ChangeDetectionResult:
        """Internal helper for Gemini-based change detection (fallback).

        Args:
            old_json (str): Old data as JSON string.
            new_json (str): New data as JSON string.
            monitoring_instruction (str): Change detection goal.
            max_retries (int, optional): Max retries. Defaults to 2.

        Returns:
            ChangeDetectionResult: Detection result validated.

        Raises:
            DiffAIServiceError: If detection fails after retries.
        """
        if not _HAS_GENAI:
            raise DiffAIServiceError("google-generativeai package not installed")

        if not hasattr(self, "model"):
            if not settings.GEMINI_API_KEY:
                raise DiffAIServiceError("GEMINI_API_KEY not configured")
            self.model = genai.GenerativeModel(
                model_name=settings.MODEL_NAME,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=CHANGE_DETECTION_SCHEMA,
                ),
            )

        prompt = f"""You are a Regulatory Compliance Auditor.
TASK: Compare OLD vs NEW data.
USER GOAL: "{monitoring_instruction}"

INSTRUCTIONS:
1. Ignore formatting, whitespace, or metadata.
2. Only report changes that affect the USER GOAL.
3. Missing or null fields in both versions are not changes.
4. risk_level must be LOW, MEDIUM, or HIGH.

--- OLD DATA ---
{old_json}

--- NEW DATA ---
{new_json}
"""

        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)
                result_dict = json.loads(response.text)
                validated_result = ChangeDetectionResult.model_validate(result_dict)

                logger.info(
                    f"Gemini change detection successful: "
                    f"has_changed={validated_result.has_changed}, "
                    f"risk_level={validated_result.risk_level}"
                )
                return validated_result

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"Gemini detection failed (Attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    logger.error(
                        f"Gemini detection failed after {max_retries} retries. "
                        f"Returning error result."
                    )
                    return ChangeDetectionResult(
                        has_changed=True,
                        change_summary="AI Analysis Failed",
                        risk_level="HIGH",
                    )

            except Exception as e:
                logger.error(f"Unexpected Gemini error: {e}")
                return ChangeDetectionResult(
                    has_changed=True,
                    change_summary="AI Analysis Failed",
                    risk_level="HIGH",
                )
                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    raise DiffAIServiceError(f"System Error: {str(e)}")
