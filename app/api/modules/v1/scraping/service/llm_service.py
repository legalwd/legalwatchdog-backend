import asyncio
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig

    _HAS_GENAI = True
except ImportError:
    genai = None
    _HAS_GENAI = False

from asgiref.sync import async_to_sync
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
    LLMExtractionError,
)
from app.api.core.llm.llm_manager import LLMManager
from app.api.modules.v1.scraping.schemas.ai_analysis import ExtractionResult

logger = logging.getLogger(__name__)

# Constants
_MAX_PROMPT_TEXT_CHARS = 1_000_000

if _HAS_GENAI and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)


class AIExtractionServiceError(Exception):
    """Raised when AI extraction fails after all retries.

    Attributes:
        technical_message (str): Technical error message for logging.
        user_message (str): User-friendly error message for display.
        error_category: ErrorCategory enum value.
        should_retry (bool): Whether this error should trigger retries.
        original_error: The original exception that caused this error.
    """

    def __init__(
        self,
        technical_message: str,
        user_message: str = None,
        error_category=None,
        should_retry: bool = False,
        original_error: Exception = None,
    ):
        """Initialize AI extraction service error.

        Args:
            technical_message: Technical error message for logging.
            user_message: User-friendly message. Auto-generated if None.
            error_category: Error category. Auto-detected if None.
            should_retry: Whether to retry. Auto-determined if None.
            original_error: Original exception.
        """
        super().__init__(technical_message)
        self.technical_message = technical_message
        self.original_error = original_error

        from app.api.modules.v1.scraping.service.error_types import (
            classify_error,
            get_user_friendly_message,
            should_retry_error,
        )

        if error_category is None:
            if original_error:
                error_category = classify_error(original_error)
            else:
                error_category = classify_error(Exception(technical_message))

        self.error_category = error_category

        if user_message is None:
            user_message = get_user_friendly_message(error_category)

        self.user_message = user_message

        if should_retry is False and error_category:
            should_retry = should_retry_error(error_category)

        self.should_retry = should_retry


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "markdown_summary": {"type": "string"},
        "extracted_data": {
            "type": "object",
            "properties": {
                "key_value_pairs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                        "required": ["key", "value"],
                    },
                }
            },
            "required": ["key_value_pairs"],
        },
        "confidence_score": {"type": "number"},
    },
    "required": ["summary", "markdown_summary", "extracted_data", "confidence_score"],
}


def _extract_json_from_response(raw_content: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from response content.

    Handles multiple JSON response formats:
    - Raw JSON: {...}
    - Markdown code block: ```json {...}```
    - Escaped control characters in values

    Args:
        raw_content (str): Raw response content from LLM.

    Returns:
        Dict[str, Any]: Parsed JSON dictionary.

    Raises:
        json.JSONDecodeError: If JSON parsing fails.
        ValueError: If no valid JSON found in content.

    Examples:
        >>> content = '```json\\n{"key": "value"}\\n```'
        >>> result = _extract_json_from_response(content)
        >>> result['key']
        'value'
    """
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise ValueError("Content must be non-empty string")

    content = raw_content.strip()

    try:
        logger.debug("Attempting direct JSON parsing...")
        return json.loads(content)
    except json.JSONDecodeError:
        logger.debug("Direct parsing failed, trying markdown extraction...")

    json_pattern = r"```(?:json)?\s*([\s\S]*?)```"

    matches = re.findall(json_pattern, content)
    for match in matches:
        try:
            logger.debug("Attempting markdown block extraction...")
            parsed = json.loads(match.strip())
            logger.debug("Successfully extracted JSON from markdown block")
            return parsed
        except json.JSONDecodeError:
            continue

    try:
        logger.debug("Attempting JSON object pattern search...")
        json_start = content.find("{")
        if json_start >= 0:
            json_end = content.rfind("}") + 1
            if json_end > json_start:
                candidate = content[json_start:json_end]
                parsed = json.loads(candidate)
                logger.debug("Successfully extracted JSON from pattern search")
                return parsed
    except json.JSONDecodeError:
        pass

    try:
        json_start = content.find("[")
        if json_start >= 0:
            json_end = content.rfind("]") + 1
            if json_end > json_start:
                candidate = content[json_start:json_end]
                parsed = json.loads(candidate)
                logger.debug("Successfully extracted JSON array from pattern search")
                return parsed
    except json.JSONDecodeError:
        pass

    raise ValueError(f"No valid JSON found in response. First 200 chars: {content[:200]}")


class AIExtractionService:
    """
    Service responsible for extracting structured data from raw text using Google's Gemini AI.

    This service utilizes Gemini's Native JSON mode to ensure deterministic and schema-compliant
    output. It handles the extraction of key-value pairs, generation of summaries, and
    creation of markdown-formatted analysis in a single API call.
    """

    def __init__(self, db: Optional[AsyncSession] = None, use_openrouter: bool = True):
        """
        Initialize the AIExtractionService with LLM configuration.

        Args:
            db (Optional[AsyncSession]): Database session for tracking.
            use_openrouter (bool): Use OpenRouter (True) or fallback to Gemini (False).

        Raises:
            ImportError: If the google-generativeai package is not installed (Gemini fallback).
            ValueError: If required API keys are not set.
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
            logger.info("AIExtractionService initialized with OpenRouter + fallback")
        else:
            if not _HAS_GENAI:
                raise LLMConfigurationError(
                    "AI service not configured properly. Contact administrator."
                )

            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is not set.")

            self.model = genai.GenerativeModel(
                model_name=settings.MODEL_NAME,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=EXTRACTION_SCHEMA,
                ),
            )
            logger.info("AIExtractionService initialized with Gemini (legacy mode)")

    async def _get_previous_field_names(self, source_id: str) -> list[str]:
        """Get field names from most recent revision for consistency.

        Args:
            source_id: Source UUID to look up previous revision

        Returns:
            List of field names from the last revision, or empty list if none

        Example:
            >>> service = AIExtractionService()
            >>> fields = await service._get_previous_field_names("source-uuid")
            >>> fields
            ['visa_price', 'audit_deadline', 'enterprise_renewal_fee']
        """
        if not self.db:
            logger.debug("No DB session, cannot retrieve previous field names")
            return []

        try:
            from sqlmodel import select

            from app.api.modules.v1.scraping.models.data_revision import DataRevision

            stmt = (
                select(DataRevision)
                .where(DataRevision.source_id == source_id)
                .order_by(DataRevision.scraped_at.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            last_revision = result.scalar_one_or_none()

            if not last_revision or not last_revision.extracted_data:
                logger.debug(f"No previous revision found for source {source_id}")
                return []

            extracted_data = last_revision.extracted_data
            if isinstance(extracted_data, dict):
                if "key_value_pairs" in extracted_data:
                    kv_pairs = extracted_data["key_value_pairs"]
                    if isinstance(kv_pairs, dict):
                        field_names = list(kv_pairs.keys())
                        logger.info(
                            f"Retrieved {len(field_names)} field names from previous revision: "
                            f"{field_names[:5]}..."
                        )
                        return field_names

            logger.debug(f"No key_value_pairs found in previous revision for source {source_id}")
            return []

        except Exception as e:
            logger.warning(f"Failed to retrieve previous field names: {e}")
            return []

    async def run_llm_analysis_with_openrouter(
        self,
        cleaned_text: str,
        project_prompt: str,
        jurisdiction_prompt: str,
        source_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute LLM analysis using OpenRouter with intelligent routing and fallback.

        This method uses the LLMManager to leverage OpenRouter's model routing,
        automatic fallback to alternative models/providers, and comprehensive
        usage tracking for the admin dashboard.

        Args:
            cleaned_text (str): Pre-processed text content to analyze.
            project_prompt (str): Main monitoring goal/instruction.
            jurisdiction_prompt (str): Jurisdiction-specific context.
            source_id (Optional[str]): Source UUID for field name consistency.
            user_id (Optional[str]): User ID for usage tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.

        Returns:
            Dict[str, Any]: Extracted data with summaries and confidence score.

        Raises:
            AIExtractionServiceError: If extraction fails after all retries/fallbacks.
        """
        previous_fields = []
        if source_id:
            previous_fields = await self._get_previous_field_names(source_id)

        field_guidance = ""
        if previous_fields:
            field_list = ", ".join(f'"{field}"' for field in previous_fields[:10])
            if len(previous_fields) > 10:
                field_list += f", ... ({len(previous_fields) - 10} more)"

            field_guidance = f"""
FIELD NAME CONSISTENCY REQUIREMENT (CRITICAL):
Previous extractions from this source used these field names:
{field_list}

When extracting data:
1. If you encounter the SAME concept as a previous field, use the EXACT same field name
2. Only create NEW field names for truly new information not previously extracted
3. Examples:
   - If previous had "visa_price", use "visa_price" (NOT "price_visa" or "visa_fee")
   - If previous had "audit_deadline", use "audit_deadline" (NOT "audit_submission_deadline")
4. This ensures consistent tracking of changes over time
"""
        else:
            field_guidance = """
FIELD NAME CREATION GUIDANCE:
This is the first extraction for this source. Choose clear, descriptive field names:
- Use snake_case format
- Be specific and unambiguous
- Use consistent naming patterns
- Future extractions will reuse YOUR field names
"""

        prompt = f"""You are an Expert Regulatory Data Analyst.
TASK: Extract structured information from the text below and generate summaries based on that data.

PROJECT GOAL: {project_prompt}
JURISDICTION CONTEXT: {jurisdiction_prompt}

{field_guidance}

OUTPUT REQUIREMENTS (CRITICAL - MUST FOLLOW EXACTLY):

You MUST respond with ONLY a valid JSON object. No markdown, no code blocks, no extra text.
The JSON must be parseable by Python's json.loads() function.

Expected JSON Schema:
{{
  "summary": "2-3 sentence executive summary",
  "markdown_summary": "detailed analysis with ## headers, **bold**, bullet points, tables",
  "extracted_data": {{
    "key_value_pairs": [
      {{"key": "field_name", "value": "field_value"}}
    ]
  }},
  "confidence_score": 0.95
}}

JSON FORMATTING RULES (REQUIRED):
- Return ONLY the JSON object, nothing before or after
- NO markdown code blocks (no triple backticks)
- NO literal newlines in string values (use \\n if needed)
- NO literal tabs in string values (use \\t if needed)
- All control characters MUST be properly escaped
- All double quotes inside strings must be escaped: \"
- Ensure valid JSON that Python json.loads() can parse

DATA EXTRACTION RULES:
- Keys MUST be snake_case format
- Extract ALL relevant fields related to the PROJECT GOAL
- Set value to null if information is missing
- Each key-value pair must have "key" and "value" fields

SUMMARY RULES (FOR UI DISPLAY):
- "summary": Concise 2-3 sentence executive summary
- "markdown_summary": Detailed analysis in Markdown format
    - Use ## for section headers
    - Use ** for bold important items
    - Use - for bullet lists
    - Use tables for comparisons
- "confidence_score": Number between 0.0 and 1.0

--- SOURCE TEXT ---
{cleaned_text[:_MAX_PROMPT_TEXT_CHARS]}
"""

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = await self.llm_manager.generate_with_tracking(
                    prompt=prompt,
                    model_preference="premium",
                    temperature=0.0,
                    max_tokens=2000,
                    json_mode=True,
                    system_prompt=(
                        "You are a regulatory data extraction expert. "
                        "Extract information accurately and provide "
                        "clear summaries."
                    ),
                    user_id=user_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    jurisdiction_id=jurisdiction_id,
                    endpoint=endpoint or "/api/v1/scrape/extract",
                    ip_address=ip_address,
                )

                try:
                    logger.debug(
                        f"Received response from OpenRouter. "
                        f"Content length: {len(response.content)}, "
                        f"First 100 chars: {response.content[:100]}"
                    )

                    result_dict = _extract_json_from_response(response.content)
                    logger.debug("Successfully parsed JSON from response.content")
                except (json.JSONDecodeError, TypeError) as je:
                    logger.warning(
                        f"OpenRouter extraction failed "
                        f"(Attempt {attempt + 1}/{max_retries + 1}): {je}"
                    )
                    if attempt < max_retries:
                        base_delay = 1.0
                        exponential_delay = base_delay * (2**attempt)
                        jitter = random.uniform(0, 0.1) * exponential_delay
                        await asyncio.sleep(exponential_delay + jitter)
                        continue
                    raise ValueError(f"Invalid JSON in LLM response: {je}") from je

                if "extracted_data" in result_dict:
                    if isinstance(result_dict["extracted_data"], list):
                        logger.warning(
                            "LLM returned extracted_data as list, wrapping in key_value_pairs"
                        )
                        kv_list = result_dict["extracted_data"]
                        kv_dict = {
                            item.get("key"): item.get("value")
                            for item in kv_list
                            if isinstance(item, dict) and "key" in item
                        }
                        result_dict["extracted_data"] = {"key_value_pairs": kv_dict}
                    elif "key_value_pairs" in result_dict["extracted_data"] and isinstance(
                        result_dict["extracted_data"]["key_value_pairs"], list
                    ):
                        kv_list = result_dict["extracted_data"]["key_value_pairs"]
                        kv_dict = {
                            item.get("key"): item.get("value")
                            for item in kv_list
                            if isinstance(item, dict) and "key" in item
                        }
                        result_dict["extracted_data"]["key_value_pairs"] = kv_dict

                validated_result = ExtractionResult.model_validate(result_dict)
                result_dump = validated_result.model_dump()

                if (
                    "extracted_data" in result_dump
                    and "key_value_pairs" in result_dump["extracted_data"]
                ):
                    kv_pairs = result_dump["extracted_data"]["key_value_pairs"]
                    result_dump["extracted_data"]["key_value_pairs"] = dict(
                        sorted(kv_pairs.items())
                    )

                logger.info(
                    f"OpenRouter extraction successful "
                    f"(Confidence: {validated_result.confidence_score})"
                )
                return result_dump

            except (json.JSONDecodeError, ValueError, ValidationError) as e:
                logger.warning(
                    f"OpenRouter extraction failed (Attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Response content (first 500 chars): {response.content[:500]}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, 0.1) * exponential_delay
                    await asyncio.sleep(exponential_delay + jitter)
                    continue

                if _HAS_GENAI and settings.GEMINI_API_KEY:
                    logger.warning("OpenRouter failed. Falling back to Gemini for extraction...")
                    try:
                        return await self._run_gemini_analysis(
                            cleaned_text=cleaned_text,
                            project_prompt=project_prompt,
                            jurisdiction_prompt=jurisdiction_prompt,
                        )
                    except Exception as gemini_error:
                        logger.error(
                            f"Gemini fallback also failed: {gemini_error}",
                            exc_info=True,
                        )
                        raise LLMAPIError("AI service error. Please try again later.")

                raise LLMAPIError("AI service error. Please try again later.")

            except Exception as e:
                logger.error(f"OpenRouter extraction failed: {e}", exc_info=True)

                if _HAS_GENAI and settings.GEMINI_API_KEY:
                    logger.warning("OpenRouter failed. Falling back to Gemini for extraction...")
                    try:
                        return await self._run_gemini_analysis(
                            cleaned_text=cleaned_text,
                            project_prompt=project_prompt,
                            jurisdiction_prompt=jurisdiction_prompt,
                        )
                    except Exception as gemini_error:
                        logger.error(
                            f"Gemini fallback also failed: {gemini_error}",
                            exc_info=True,
                        )
                        raise LLMAPIError("AI service error. Please try again later.")

                raise LLMAPIError("AI service error. Please try again later.")

    async def _run_gemini_analysis(
        self,
        cleaned_text: str,
        project_prompt: str,
        jurisdiction_prompt: str,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """
        Internal helper for Gemini-based extraction (used as fallback).

        Args:
            cleaned_text (str): Pre-processed text content to analyze.
            project_prompt (str): Main monitoring goal/instruction.
            jurisdiction_prompt (str): Jurisdiction-specific context.
            max_retries (int, optional): Max retries for failed API calls.

        Returns:
            Dict[str, Any]: Extracted data with summaries and confidence.

        Raises:
            AIExtractionServiceError: If extraction fails after retries.
        """
        if not _HAS_GENAI:
            raise LLMConfigurationError(
                "AI service not configured properly. Contact administrator."
            )

        if not hasattr(self, "model"):
            api_key = (settings.GEMINI_API_KEY or "").strip()
            if not api_key or api_key == "your-gemini-api-key":
                raise LLMConfigurationError(
                    "AI service not configured properly. Contact administrator."
                )
            logger.info(f"Configuring Gemini fallback with key: {api_key[:10]}...")
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name=settings.MODEL_NAME,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=EXTRACTION_SCHEMA,
                ),
            )

        prompt = f"""You are an Expert Regulatory Data Analyst.
TASK: Extract structured information from the text below and generate summaries based on that data.

PROJECT GOAL: {project_prompt}
JURISDICTION CONTEXT: {jurisdiction_prompt}

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON matching the schema.
2. CONSISTENCY RULE: Use EXACT same field names/structure every time.

DATA EXTRACTION RULES:
- "extracted_data": Return a LIST of key-value objects 
  (e.g. {{ "key": "current_price", "value": "600 NGN" }}).
- Keys MUST be snake_case. Use null if information is missing.

SUMMARY RULES (UI RENDER):
- "summary": A concise 2-3 sentence executive summary 
  answering the Project Goal based on extracted data.
- "markdown_summary": A detailed analysis formatted for Frontend Display.
    - Use ## Headers for sections.
    - Use bullet points (-) for lists.
    - Use **bold** for important figures (prices, dates).
    - Use Markdown Tables if comparing data (e.g., Old vs New prices).
    - MUST be based strictly on the 'extracted_data'.

--- SOURCE TEXT ---
{cleaned_text[:_MAX_PROMPT_TEXT_CHARS]} 
"""

        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)
                result_json = json.loads(response.text)

                if (
                    "extracted_data" in result_json
                    and "key_value_pairs" in result_json["extracted_data"]
                ):
                    kv_list = result_json["extracted_data"]["key_value_pairs"]
                    if isinstance(kv_list, list):
                        result_json["extracted_data"]["key_value_pairs"] = {
                            item.get("key"): item.get("value") for item in kv_list if "key" in item
                        }

                validated_result = ExtractionResult.model_validate(result_json)
                result_dump = validated_result.model_dump()
                if (
                    "extracted_data" in result_dump
                    and "key_value_pairs" in result_dump["extracted_data"]
                ):
                    kv_pairs = result_dump["extracted_data"]["key_value_pairs"]
                    result_dump["extracted_data"]["key_value_pairs"] = dict(
                        sorted(kv_pairs.items())
                    )

                logger.info(
                    f"Gemini extraction successful "
                    f"(Confidence: {validated_result.confidence_score})"
                )
                return result_dump

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"Gemini extraction failed (Attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    error_msg = (
                        f"Gemini extraction failed after {max_retries} retries. Error: {str(e)}"
                    )
                    logger.error(error_msg)
                    raise LLMAPIError("AI service error. Please try again later.")

            except Exception as e:
                from app.api.modules.v1.scraping.service.error_types import (
                    classify_error,
                    should_retry_error,
                )

                error_category = classify_error(e)
                should_retry = should_retry_error(error_category)

                logger.error(
                    f"Gemini error (attempt {attempt + 1}/{max_retries + 1}): {e}",
                    extra={"error_category": error_category.value, "should_retry": should_retry},
                    exc_info=True,
                )

                if not should_retry:
                    raise LLMAPIError("AI service error. Please try again later.")

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    raise AIExtractionServiceError(
                        technical_message=f"Gemini error after {max_retries} retries: {str(e)}",
                        original_error=e,
                        error_category=error_category,
                    )

    async def run_llm_analysis(
        self,
        cleaned_text: str,
        project_prompt: str,
        jurisdiction_prompt: str,
        max_retries: int = 2,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the LLM analysis pipeline to extract structured data.

        Routes to OpenRouter if enabled (recommended), otherwise uses Gemini
        (legacy fallback). Constructs a prompt based on the project and
        jurisdiction context, sends it to the configured LLM, and parses
        the JSON response.

        Args:
            cleaned_text (str): The pre-processed text content to analyze.
            project_prompt (str): The main goal or monitoring instruction.
            jurisdiction_prompt (str): Context specific to the jurisdiction.
            max_retries (int, optional): Max retries for failed API calls.
                                         Defaults to 2.
            user_id (Optional[str]): User ID for usage tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.

        Returns:
            Dict[str, Any]: A dictionary with extracted data, summaries,
                            and confidence score, validated and formatted.

        Raises:
            AIExtractionServiceError: If extraction fails after retries.
        """
        if self.use_openrouter:
            return await self.run_llm_analysis_with_openrouter(
                cleaned_text=cleaned_text,
                project_prompt=project_prompt,
                jurisdiction_prompt=jurisdiction_prompt,
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                endpoint=endpoint,
                ip_address=ip_address,
            )

        prompt = f"""You are an Expert Regulatory Data Analyst.
TASK: Extract structured information from the text below and generate summaries based on that data.

PROJECT GOAL: {project_prompt}
JURISDICTION CONTEXT: {jurisdiction_prompt}

OUTPUT RULES (CRITICAL):
1. Return ONLY valid JSON matching the schema.
2. CONSISTENCY RULE: Use EXACT same field names/structure every time.

DATA EXTRACTION RULES:
- "extracted_data": Return a LIST of key-value objects 
  (e.g. {{ "key": "current_price", "value": "600 NGN" }}).
- Keys MUST be snake_case. Use null if information is missing.

SUMMARY RULES (UI RENDER):
- "summary": A concise 2-3 sentence executive summary 
  answering the Project Goal based on extracted data.
- "markdown_summary": A detailed analysis formatted for Frontend Display.
    - Use ## Headers for sections.
    - Use bullet points (-) for lists.
    - Use **bold** for important figures (prices, dates).
    - Use Markdown Tables if comparing data (e.g., Old vs New prices).
    - MUST be based strictly on the 'extracted_data'.

--- SOURCE TEXT ---
{cleaned_text[:_MAX_PROMPT_TEXT_CHARS]} 
"""

        for attempt in range(max_retries + 1):
            try:
                response = await self.model.generate_content_async(prompt)

                result_json = json.loads(response.text)

                if (
                    "extracted_data" in result_json
                    and "key_value_pairs" in result_json["extracted_data"]
                ):
                    kv_list = result_json["extracted_data"]["key_value_pairs"]
                    if isinstance(kv_list, list):
                        result_json["extracted_data"]["key_value_pairs"] = {
                            item.get("key"): item.get("value") for item in kv_list if "key" in item
                        }

                validated_result = ExtractionResult.model_validate(result_json)

                result_dump = validated_result.model_dump()
                if (
                    "extracted_data" in result_dump
                    and "key_value_pairs" in result_dump["extracted_data"]
                ):
                    kv_pairs = result_dump["extracted_data"]["key_value_pairs"]
                    result_dump["extracted_data"]["key_value_pairs"] = dict(
                        sorted(kv_pairs.items())
                    )

                logger.info(
                    f"Extraction successful (Confidence: {validated_result.confidence_score})"
                )
                return result_dump

            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(
                    f"AI Extraction Failed (Attempt {attempt + 1}/{max_retries + 1}): {e}"
                )

                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    error_msg = f"Extraction failed after {max_retries} retries. Error: {str(e)}"
                    logger.error(error_msg)
                    raise LLMAPIError("AI service error. Please try again later.")

            except Exception as e:
                logger.error(f"Unexpected AI Error: {e}")
                if attempt < max_retries:
                    base_delay = 1.0
                    exponential_delay = base_delay * (2**attempt)
                    jitter = random.uniform(0, exponential_delay * 0.5)
                    total_delay = exponential_delay + jitter

                    logger.info(f"Retrying in {total_delay:.2f}s (attempt {attempt + 1})")
                    await asyncio.sleep(total_delay)
                else:
                    raise LLMAPIError("AI service error. Please try again later.")

    def run_llm_analysis_with_openrouter_sync(
        self,
        cleaned_text: str,
        project_prompt: str,
        jurisdiction_prompt: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for run_llm_analysis_with_openrouter for Celery compatibility.

        Allows prefork Celery workers to call LLM extraction without asyncio conflicts.
        Uses async_to_sync for automatic loop detection and bridging.

        Args:
            cleaned_text (str): Pre-processed text content to analyze.
            project_prompt (str): Main monitoring goal/instruction.
            jurisdiction_prompt (str): Jurisdiction-specific context.
            user_id (Optional[str]): User ID for usage tracking.
            organization_id (Optional[str]): Organization ID for tracking.
            project_id (Optional[str]): Project ID for tracking.
            jurisdiction_id (Optional[str]): Jurisdiction ID for tracking.
            endpoint (Optional[str]): API endpoint for tracking.
            ip_address (Optional[str]): Client IP for tracking.

        Returns:
            Dict[str, Any]: Extracted data with summaries and confidence score.

        Raises:
            AIExtractionServiceError: If extraction fails.

        Examples:
            >>> service = AIExtractionService()
            >>> result = service.run_llm_analysis_with_openrouter_sync(
            ...     cleaned_text="Regulatory text...",
            ...     project_prompt="Tax regulations",
            ...     jurisdiction_prompt="Federal tax law",
            ...     jurisdiction_id="fed_tax_law_id"
            ... )
            >>> print(result["summary"])
        """
        return async_to_sync(self.run_llm_analysis_with_openrouter)(
            cleaned_text=cleaned_text,
            project_prompt=project_prompt,
            jurisdiction_prompt=jurisdiction_prompt,
            user_id=user_id,
            organization_id=organization_id,
            project_id=project_id,
            jurisdiction_id=jurisdiction_id,
            endpoint=endpoint,
            ip_address=ip_address,
        )

    def run_consolidated_analysis(
        self,
        consolidated_text: str,
        jurisdiction_prompt: str,
        previous_schema: Optional[List[str]] = None,
        source_url_mapping: Optional[Dict[str, str]] = None,
        current_ledger_state: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        project_id: Optional[str] = None,
        jurisdiction_id: Optional[str] = None,
    ) -> tuple[Dict[str, Any], Any]:
        """Run consolidated analysis for a jurisdiction (sync wrapper).

        Args:
            consolidated_text: Consolidated content from all sources.
            jurisdiction_prompt: Jurisdiction-specific instructions.
            previous_schema: Optional list of field names from previous extraction
                for schema grounding.
            source_url_mapping: Optional mapping of source numbers to URLs
                for stable identification.
            current_ledger_state: Optional dictionary of currently accepted values
                to use as an anchor.
            user_id: User ID for usage tracking.
            organization_id: Organization ID for usage tracking.
            project_id: Project ID for usage tracking.
            jurisdiction_id: Jurisdiction ID for usage tracking.

        Returns:
            tuple: (analysis_result_dict, usage_metrics=None)

        Note:
            Usage metrics are currently None due to sync/async complexity.
            TODO: Implement proper usage tracking for Celery context.
        """

        project_goal = (
            "Analyze the provided consolidated regulatory updates from multiple sources. "
            "Identify key changes, actionable items, and summary of activity."
        )

        enhanced_prompt = jurisdiction_prompt
        if previous_schema:
            schema_instruction = (
                f"\n\nIMPORTANT - SCHEMA CONSISTENCY:\n"
                f"Use the EXACT same field names as the previous extraction:\n"
                f"{', '.join(previous_schema)}\n\n"
                f"Only create NEW fields if there is genuinely new information "
                f"not captured by these existing fields. "
                f"Maintain the same level of granularity (individual fields vs aggregated strings)."
            )
            enhanced_prompt = jurisdiction_prompt + schema_instruction

        if source_url_mapping:
            url_instruction = (
                "\n\nSOURCE IDENTIFICATION:\n"
                "The sources in this consolidation are ALWAYS presented in the same order:\n"
            )
            for source_key, url in sorted(source_url_mapping.items()):
                url_instruction += f"- {source_key}: {url}\n"
            url_instruction += (
                "\nWhen referencing sources in field names (e.g., fee_schedule_source_1), "
                "use this exact numbering based on URL ordering to ensure consistency across runs."
            )
            enhanced_prompt = enhanced_prompt + url_instruction

        ledger_instruction = ""
        if current_ledger_state:
            import json

            serializable_ledger = {
                key: state.value if hasattr(state, "value") else str(state)
                for key, state in current_ledger_state.items()
            }
            ledger_json = json.dumps(serializable_ledger, indent=2)
            ledger_instruction = f"""
LEDGER-ANCHORED CONSOLIDATION (CRITICAL):
When a Compliance Ledger exists with previously confirmed/accepted values,
you MUST follow these rules:
- DEFAULT to the Ledger value as canonical_value unless evidence proves it wrong
- Only override the Ledger value if a source explicitly references a NEW law,
  amendment, or effective date that supersedes the Ledger
- Source disagreement alone is NOT a reason to change from the Ledger value
- If a source has older/static information that conflicts with the Ledger,
  the Ledger wins - record the source as a discrepancy instead

CURRENT LEDGER VALUES:
{ledger_json}
"""

        _MAX_PROMPT_TEXT_CHARS = 100000
        prompt = f"""
{project_goal}

JURISDICTION CONTEXT:
{enhanced_prompt}

Expected JSON Schema:
{{
  "summary": "2-3 sentence executive summary",
  "markdown_summary": "detailed analysis with ## headers, **bold**, bullet points, tables",
  "extracted_data": {{
    "key_value_pairs": {{
      "field_name": {{
        "canonical_value": "primary value (most common or authoritative)",
        "has_discrepancy": true|false,
        "source_count": 2,
        "agreement_count": 1,
        "discrepancies": [
          {{"source_id": "source_N", "value": "different_value"}}
        ]
      }}
    }}
  }},
  "confidence_score": 0.95
}}

JSON FORMATTING RULES (REQUIRED):
- Return ONLY the JSON object, nothing before or after
- NO markdown code blocks (no triple backticks)
- NO literal newlines in string values (use \\n if needed)
- NO literal tabs in string values (use \\t if needed)
- All control characters MUST be properly escaped
- All double quotes inside strings must be escaped: \\"
- Ensure valid JSON that Python json.loads() can parse

DATA EXTRACTION RULES:
- Keys MUST be snake_case format
- Extract ALL relevant fields related to the PROJECT GOAL
- Set canonical_value to null if information is missing

MULTI-SOURCE CONSOLIDATION (CRITICAL):
- CONSOLIDATE by DATA TYPE, NOT by source!
- WRONG: fee_schedule_source_1, fee_schedule_source_2
- CORRECT: standard_license_fee, enterprise_renewal_fee, late_penalty_fee
- Create ONE field per data type, then track which sources agree/disagree
{ledger_instruction}
For each consolidated field:
- canonical_value: The value that most sources agree on (majority wins)
- has_discrepancy: true if ANY source has a DIFFERENT value
- source_count: Total number of sources that have this data type
- agreement_count: Number of sources with the SAME value as canonical_value
- discrepancies: ONLY list sources with DIFFERENT values (empty if all agree)
  - Each discrepancy needs: source_id (e.g., "source_1") and value

EXAMPLE - When two sources have SAME fee:
  "standard_license_fee": {{
    "canonical_value": "$20,000.00",
    "has_discrepancy": false,
    "source_count": 2,
    "agreement_count": 2,
    "discrepancies": []
  }}

EXAMPLE - When two sources have DIFFERENT fees:
  "standard_license_fee": {{
    "canonical_value": "$13,500.00",
    "has_discrepancy": true,
    "source_count": 2,
    "agreement_count": 1,
    "discrepancies": [{{"source_id": "source_2", "value": "$9,500.00"}}]
  }}

SUMMARY RULES (FOR UI DISPLAY):
- "summary": Concise 2-3 sentence executive summary about actual data changes
- "markdown_summary": Detailed analysis in Markdown format
    - Use ## for section headers
    - Use ** for bold important items
    - Use - for bullet lists
    - Use tables for comparisons
- "confidence_score": Number between 0.0 and 1.0

--- SOURCE TEXT ---
{consolidated_text[:_MAX_PROMPT_TEXT_CHARS]}
"""
        try:
            from asgiref.sync import async_to_sync

            llm_response = async_to_sync(self.llm_manager.generate_with_tracking)(
                prompt=prompt,
                model_preference="premium",
                temperature=0.0,
                max_tokens=2000,
                json_mode=True,
                response_model=ExtractionResult,
                max_validation_retries=3,
                system_prompt=(
                    "You are a regulatory data extraction expert. "
                    "Extract information accurately and provide clear summaries."
                ),
                user_id=user_id,
                organization_id=organization_id,
                project_id=project_id,
                jurisdiction_id=jurisdiction_id,
                endpoint="/api/v1/jurisdictions/consolidate",
            )

            if isinstance(llm_response.content, ExtractionResult):
                result_dict = llm_response.content.model_dump()
                logger.info("Structured extraction successful via response_model")
            elif isinstance(llm_response.content, dict):
                result_dict = llm_response.content
                logger.info("Structured extraction returned dict")
            else:
                result_dict = _extract_json_from_response(llm_response.content)

            if "extracted_data" in result_dict:
                extracted = result_dict["extracted_data"]

                if isinstance(extracted, list):
                    kv_dict = {}
                    for item in extracted:
                        if isinstance(item, dict) and "key" in item:
                            key = item.get("key")
                            value = item.get("value")
                            kv_dict[key] = {
                                "canonical_value": value,
                                "has_discrepancy": False,
                                "source_count": 1,
                                "agreement_count": 1,
                                "discrepancies": [],
                            }
                    result_dict["extracted_data"] = {"key_value_pairs": kv_dict}

                elif "key_value_pairs" in extracted:
                    kv_pairs = extracted["key_value_pairs"]

                    if isinstance(kv_pairs, list):
                        kv_dict = {}
                        for item in kv_pairs:
                            if isinstance(item, dict) and "key" in item:
                                key = item.get("key")
                                value = item.get("value")
                                kv_dict[key] = {
                                    "canonical_value": value,
                                    "has_discrepancy": False,
                                    "source_count": 1,
                                    "agreement_count": 1,
                                    "discrepancies": [],
                                }
                        result_dict["extracted_data"]["key_value_pairs"] = kv_dict

                    elif isinstance(kv_pairs, dict):
                        for field_name, field_data in kv_pairs.items():
                            if isinstance(field_data, dict):
                                if "canonical_value" not in field_data:
                                    field_data["canonical_value"] = None
                                if "has_discrepancy" not in field_data:
                                    field_data["has_discrepancy"] = False
                                if "discrepancies" not in field_data:
                                    field_data["discrepancies"] = []
                            else:
                                kv_pairs[field_name] = {
                                    "canonical_value": field_data,
                                    "has_discrepancy": False,
                                    "source_count": 1,
                                    "agreement_count": 1,
                                    "discrepancies": [],
                                }

            validated_result = ExtractionResult.model_validate(result_dict)
            result = validated_result.model_dump()

            if "extracted_data" in result and "key_value_pairs" in result["extracted_data"]:
                kv_pairs = result["extracted_data"]["key_value_pairs"]
                result["extracted_data"]["key_value_pairs"] = dict(sorted(kv_pairs.items()))

            usage_metrics = {
                "model": llm_response.model,
                "provider": llm_response.provider,
                "input_tokens": llm_response.usage_metrics.input_tokens,
                "output_tokens": llm_response.usage_metrics.output_tokens,
                "total_tokens": llm_response.usage_metrics.total_tokens,
                "cost_usd": llm_response.usage_metrics.cost_usd,
                "latency_ms": llm_response.usage_metrics.latency_ms,
                "success": llm_response.usage_metrics.success,
                "user_id": user_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "jurisdiction_id": jurisdiction_id,
            }

            logger.info(
                f"Consolidation LLM usage: model={usage_metrics['model']}, "
                f"tokens={usage_metrics['total_tokens']}, cost=${usage_metrics['cost_usd']:.4f}"
            )

            return result, usage_metrics

        except Exception as e:
            logger.error(f"Consolidation analysis failed: {e}", exc_info=True)
            raise LLMExtractionError("AI extraction failed. Please try again.")

    def check_source_relevance(self, content: str, prompt: str) -> bool:
        """Check if source content is relevant to the jurisdiction prompt using LLM.

        Uses economy model for cost-effective filtering of large source lists.

        Args:
            content (str): Source content to check (truncated to first 2000 chars for speed).
            prompt (str): Jurisdiction monitoring focus/prompt.

        Returns:
            bool: True if content is relevant, False otherwise.
        """
        sample = content[:2000] if len(content) > 2000 else content

        analysis_prompt = f"""You are a relevance checker for regulatory monitoring.

Jurisdiction Focus: {prompt}

Content Sample:
{sample}

Question: Is this content directly relevant to the jurisdiction focus above?

Requirements:
- "Relevant" means it contains information about changes, updates, or details matching the focus
- News/statistics ABOUT the topic without actionable details are NOT relevant
- General announcements without specific requirements are NOT relevant

Respond with ONLY one word: "yes" or "no"
"""

        try:
            response = async_to_sync(self.llm_manager.generate_with_tracking)(
                prompt=analysis_prompt,
                model_preference="economy",
                temperature=0.0,
                max_tokens=10,
                json_mode=False,
                endpoint="/api/v1/jurisdictions/filter",
            )

            answer = response.content.strip().lower()
            is_relevant = answer.startswith("yes")

            logger.debug(
                f"Relevance check: '{prompt[:50]}...' against content sample → {is_relevant}"
            )

            return is_relevant

        except Exception as e:
            logger.error(f"Relevance check failed: {e}. Defaulting to RELEVANT (safe fallback)")
            return True
