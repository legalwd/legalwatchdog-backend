"""Taxonomy generation service — LLM-powered taxonomy tree creation.

Uses the instructor library (via LLMManager ``response_model``) to enforce
schema-valid output at generation time, avoiding brittle ``json.loads`` parsing.
"""

import logging
import re
import traceback
from datetime import datetime, timezone
from functools import lru_cache
from math import ceil
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

import pycountry
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ProcessingError,
    ResourceLockedError,
)
from app.api.core.exceptions import OpenRouterError
from app.api.core.llm.base_provider import LLMResponse
from app.api.core.llm.llm_manager import LLMManager
from app.api.core.queues import PROCESSING_QUEUE
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.service.taxonomy_geo_validator import (
    TaxonomyGeoValidator,
)

logger = logging.getLogger("app")


class TaxonomyNodeModel(BaseModel):
    """A single node in the LLM-generated taxonomy tree."""

    name: str = Field(..., max_length=255)
    description: str = Field(..., description="Brief scope description for this jurisdiction")
    suggested_prompt: str = Field(
        ..., description="AI extraction prompt scoped to this jurisdiction"
    )
    suggested_search_queries: List[str] = Field(
        ...,
        min_length=1,
        description="At least one search query for source discovery",
    )
    children: List["TaxonomyNodeModel"] = Field(
        default_factory=list,
        description="Child jurisdiction nodes",
    )
    iso_code: Optional[str] = Field(
        default=None,
        description="ISO 3166 code (populated by geo validator)",
    )


TaxonomyNodeModel.model_rebuild()


class TaxonomyTreeModel(BaseModel):
    """Root schema returned by the LLM for taxonomy generation."""

    nodes: List[TaxonomyNodeModel] = Field(..., description="Top-level taxonomy nodes (countries)")


class TaxonomyValidationResult(BaseModel):
    """Structural validation outcome."""

    valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


SYSTEM_PROMPT = (
    "You are a regulatory taxonomy architect. Return data that strictly conforms "
    "to the provided schema.\n"
    "Do not include markdown, prose, explanations, or keys not in schema."
)

USER_PROMPT_TEMPLATE = """Generate a taxonomy for:
- industry: {industry}
- domain_description: {domain_description}
- target_depth: {target_depth}
- max_jurisdictions: {max_jurisdictions}
{locale_hints}
Rules:
1) depth mapping: COUNTRY=1, STATE=2, CITY=3
2) every node requires: name, description, suggested_prompt,
   suggested_search_queries, children
3) suggested_search_queries must contain at least one query string
4) total generated nodes must not exceed {max_jurisdictions}
5) output must be valid for the TaxonomyTreeModel schema
6) use empty array [] for children of leaf nodes
7) top-level nodes must be sovereign ISO 3166-1 countries only
    (do not output regional blocs like "European Union", "ASEAN", "GCC", etc.)
8) breadth-first strategy is mandatory:
    - include globally distributed countries first
    - only after broad country coverage, add subdivisions for STATE/CITY depth
    - avoid over-indexing on any single country
9) for STATE depth, prioritize broad country coverage before deep state lists
10) if unsure, prefer including more countries with fewer children rather than
     fewer countries with dense children

Example valid node:
{{
  "name": "United States",
  "description": "Federal employment law and EOR regs",
  "suggested_prompt": "Extract federal EOR compliance
    requirements for worker classification",
  "suggested_search_queries": [
    "US federal employment law 2026",
    "FLSA EOR regulations"
  ],
  "children": []
}}

Invalid outputs (do NOT produce):
- Missing "children" key (use empty array [] for leaf nodes)
- Empty "suggested_search_queries" array
- Free-text narrative instead of JSON
- Nodes with null required fields"""


EXPANSION_USER_PROMPT_TEMPLATE = """Expand an existing campaign taxonomy to improve
global country coverage.

Campaign context:
- industry: {industry}
- domain_description: {domain_description}
- target_depth: {target_depth}
- max_jurisdictions: {max_jurisdictions}

Current coverage:
- distinct_countries: {distinct_countries}
- required_countries: {required_countries}

Countries to add in this pass:
{countries_to_add}

Rules:
1) Return only NEW top-level country nodes in schema format: {{"nodes": [...]}}
2) Do not repeat countries already covered
3) If target_depth is COUNTRY, every country node must use children: [] (no subdivisions)
4) For STATE depth, keep subdivisions concise (up to 3 high-signal subdivisions per country)
5) Ensure every node has non-empty suggested_search_queries and explicit children arrays
6) Prefer breadth over depth in this pass
"""


DEPTH_LIMITS: Dict[CampaignTargetDepth, int] = {
    CampaignTargetDepth.COUNTRY: 1,
    CampaignTargetDepth.STATE: 2,
    CampaignTargetDepth.CITY: 3,
}


class TaxonomyGenerationService:
    """Generates a taxonomy tree for a campaign using LLM + instructor.

    Attributes:
        db: Async database session.
    """

    @staticmethod
    def _classify_generation_failure(exc: Exception) -> dict[str, Any]:
        """Classify generation failures into structured frontend-friendly categories."""
        message = str(exc)
        normalized = message.lower()

        failure: dict[str, Any] = {
            "category": "unknown",
            "error_code": "CAMPAIGN_TAXONOMY_FAILED",
            "message": "Taxonomy generation failed. Please try again.",
            "retryable": True,
        }

        if isinstance(exc, OpenRouterError):
            failure.update(
                {
                    "category": "llm_provider",
                    "error_code": "LLM_PROVIDER_ERROR",
                    "message": "Taxonomy generation failed due to LLM provider error.",
                    "provider": "openrouter",
                    "retryable": True,
                }
            )

        if (
            "http 402" in normalized
            or "payment required" in normalized
            or "requires more credits" in normalized
            or "upgrade to a paid account" in normalized
        ):
            affordable_match = re.search(r"can only afford\s+(\d+)", normalized)
            requested_match = re.search(r"requested up to\s+(\d+)", normalized)
            failure.update(
                {
                    "category": "billing",
                    "error_code": "LLM_BILLING_LIMIT",
                    "message": (
                        "Taxonomy generation failed because LLM credits are insufficient. "
                        "Upgrade OpenRouter credits or reduce token limits and retry."
                    ),
                    "provider": "openrouter",
                    "retryable": False,
                }
            )
            if affordable_match:
                failure["affordable_tokens"] = int(affordable_match.group(1))
            if requested_match:
                failure["requested_max_tokens"] = int(requested_match.group(1))

        return failure

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def enqueue_taxonomy_generation(self, campaign_id: UUID) -> "Campaign":
        """Validate campaign state and dispatch taxonomy generation as a background task.

        Used by the HTTP route to return 202 immediately — the actual LLM work
        is executed by ``generate_taxonomy_task`` in the processing queue.

        Steps:
            1. Load campaign, validate status is DRAFT or FAILED
            2. Transition status to GENERATING_TAXONOMY and commit
            3. Dispatch ``generate_taxonomy_task.delay(campaign_id, run_id)``

        Args:
            campaign_id: UUID of the campaign.

        Returns:
            The updated Campaign instance (status=GENERATING_TAXONOMY).

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in DRAFT or FAILED status.
            ProcessingError: Task dispatch failed.
        """
        from app.api.modules.v1.campaigns.tasks.campaign_tasks import generate_taxonomy_task

        campaign = await self._load_campaign(campaign_id)
        allowed_statuses = {CampaignStatus.DRAFT, CampaignStatus.FAILED}
        if campaign.status not in allowed_statuses:
            raise ResourceLockedError(
                f"Taxonomy can only be generated for campaigns in DRAFT or FAILED status. "
                f"Current status: {campaign.status.value}"
            )

        campaign.status = CampaignStatus.GENERATING_TAXONOMY
        campaign.updated_at = datetime.now(timezone.utc)
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        run_id = str(uuid4())

        try:
            async_result = generate_taxonomy_task.apply_async(
                args=[str(campaign_id), run_id],
                queue=PROCESSING_QUEUE,
            )
            snapshot = campaign.generation_config_snapshot or {}
            snapshot["taxonomy_task_id"] = async_result.id
            snapshot["run_id"] = run_id
            campaign.generation_config_snapshot = snapshot

            stats = dict(campaign.stats) if isinstance(campaign.stats, dict) else {}
            pipeline_control = dict(stats.get("pipeline_control") or {})
            pipeline_control["run_id"] = run_id
            pipeline_control["task_ids"] = [async_result.id]
            pipeline_control["last_started_status"] = CampaignStatus.GENERATING_TAXONOMY.value
            pipeline_control["updated_at"] = datetime.now(timezone.utc).isoformat()
            stats["pipeline_control"] = pipeline_control
            campaign.stats = stats

            campaign.updated_at = datetime.now(timezone.utc)
            self.db.add(campaign)
            await self.db.commit()
            await self.db.refresh(campaign)
        except Exception as exc:
            campaign.status = CampaignStatus.FAILED
            campaign.updated_at = datetime.now(timezone.utc)
            snapshot = campaign.generation_config_snapshot or {}
            snapshot["last_error"] = traceback.format_exc()[-2000:]
            campaign.generation_config_snapshot = snapshot
            self.db.add(campaign)
            await self.db.commit()
            raise ProcessingError(
                "Unable to dispatch taxonomy generation task. Please try again."
            ) from exc

        logger.info("Taxonomy generation task dispatched for campaign %s", campaign_id)
        return campaign

    async def generate(self, campaign_id: UUID, run_id: str | None = None) -> Dict[str, Any]:
        """Generate a taxonomy tree for the given campaign.

        Steps:
            1. Load campaign, validate status == DRAFT or FAILED
            2. Transition status to GENERATING_TAXONOMY
            3. Call LLM with instructor enforcement
            4. Run structural validation
            5. Run geo validation (ISO 3166 normalization)
            6. Store result, transition to TAXONOMY_READY

        Args:
            campaign_id: UUID of the campaign.

        Returns:
            The validated taxonomy dict.

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in DRAFT status.
            ProcessingError: LLM generation or validation failed.
        """

        campaign = await self._load_campaign(campaign_id)
        # Added GENERATING_TAXONOMY to allow idempotency when the route/orchestrator
        # pre-transitions the status before dispatching the Celery task.
        allowed_statuses = {
            CampaignStatus.DRAFT,
            CampaignStatus.FAILED,
            CampaignStatus.GENERATING_TAXONOMY,
        }
        if campaign.status not in allowed_statuses:
            raise ResourceLockedError(
                f"Taxonomy can only be generated for campaigns in DRAFT, FAILED, "
                f"or GENERATING_TAXONOMY status. Current status: {campaign.status.value}"
            )

        # Only transition (and bump updated_at) if not already transitioning
        if campaign.status != CampaignStatus.GENERATING_TAXONOMY:
            campaign.status = CampaignStatus.GENERATING_TAXONOMY
            campaign.updated_at = datetime.now(timezone.utc)
            self.db.add(campaign)
            await self.db.commit()
            await self.db.refresh(campaign)

        try:
            user_prompt = self._build_user_prompt(campaign)
            max_tokens = settings.CAMPAIGN_TAXONOMY_MAX_TOKENS
            temperature = settings.CAMPAIGN_TAXONOMY_TEMPERATURE

            llm_manager = LLMManager(db=self.db)
            response = await self._request_taxonomy_tree(
                llm_manager=llm_manager,
                prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint="taxonomy_generation",
                request_id=self._build_tracking_request_id(
                    campaign_id=campaign_id,
                    run_id=run_id,
                    phase="primary",
                ),
            )
            self._handle_truncation(
                response=response,
                max_tokens=max_tokens,
                context="taxonomy_generation",
                campaign_id=campaign_id,
            )
            taxonomy_tree = self._extract_taxonomy_tree(response)
            geo_validator = TaxonomyGeoValidator()
            (
                taxonomy_tree,
                validation,
                geo_result,
                expansion_trace,
            ) = await self._expand_taxonomy_for_coverage(
                taxonomy_tree=taxonomy_tree,
                campaign=campaign,
                llm_manager=llm_manager,
                geo_validator=geo_validator,
                run_id=run_id,
            )
            required_country_coverage = self._required_country_coverage(campaign)
            self._enforce_country_coverage(campaign, geo_result.stats)

            campaign.taxonomy_json = geo_result.normalized_taxonomy
            campaign.generation_model = getattr(response, "model", None)
            campaign.generation_config_snapshot = {
                "run_id": run_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "model_preference": "premium",
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "raw_response": (
                    response.content
                    if isinstance(response.content, str)
                    else str(response.content)[:5000]
                ),
                "validation_warnings": validation.warnings,
                "geo_warnings": [w.to_dict() for w in geo_result.warnings],
                "geo_stats": geo_result.stats,
                "coverage_gate": {
                    "enforced": settings.CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE,
                    "required_countries": required_country_coverage,
                    "distinct_countries": geo_result.stats.get("distinct_countries", 0),
                },
                "expansion": {
                    "enabled": settings.CAMPAIGN_TAXONOMY_EXPANSION_ENABLED,
                    "passes": len(expansion_trace),
                    "trace": expansion_trace,
                },
            }
            campaign.status = CampaignStatus.TAXONOMY_READY
            campaign.updated_at = datetime.now(timezone.utc)
            self.db.add(campaign)
            await self.db.commit()
            await self.db.refresh(campaign)

            logger.info(
                "Taxonomy generated for campaign %s: %d top-level nodes",
                campaign_id,
                len(taxonomy_tree.nodes),
            )
            return geo_result.normalized_taxonomy

        except ResourceLockedError:
            raise
        except OpenRouterError as exc:
            logger.exception(
                "Taxonomy generation failed for campaign %s due to OpenRouter error",
                campaign_id,
            )
            campaign.status = CampaignStatus.FAILED
            campaign.updated_at = datetime.now(timezone.utc)
            snapshot = campaign.generation_config_snapshot or {}
            failure = self._classify_generation_failure(exc)
            snapshot["failure"] = failure
            snapshot["last_error"] = traceback.format_exc()[-2000:]
            campaign.generation_config_snapshot = snapshot
            self.db.add(campaign)
            await self.db.commit()
            raise ProcessingError(message=failure["message"]) from exc
        except ProcessingError:
            campaign.status = CampaignStatus.FAILED
            campaign.updated_at = datetime.now(timezone.utc)
            snapshot = campaign.generation_config_snapshot or {}
            failure = self._classify_generation_failure(ProcessingError())
            existing_failure = snapshot.get("failure")
            snapshot["failure"] = (
                existing_failure if isinstance(existing_failure, dict) else failure
            )
            snapshot["last_error"] = traceback.format_exc()[-2000:]
            campaign.generation_config_snapshot = snapshot
            self.db.add(campaign)
            await self.db.commit()
            raise
        except Exception as exc:
            logger.exception(
                "Taxonomy generation failed for campaign %s — root cause follows",
                campaign_id,
            )
            campaign.status = CampaignStatus.FAILED
            campaign.updated_at = datetime.now(timezone.utc)
            # Persist failure context for debugging via GET /campaigns/{id}
            snapshot = campaign.generation_config_snapshot or {}
            snapshot["failure"] = self._classify_generation_failure(exc)
            snapshot["last_error"] = traceback.format_exc()[-2000:]
            campaign.generation_config_snapshot = snapshot
            self.db.add(campaign)
            await self.db.commit()
            raise ProcessingError("Taxonomy generation failed. Please try again.")

    async def edit_taxonomy(self, campaign_id: UUID, new_taxonomy: Dict[str, Any]) -> tuple:
        """Replace taxonomy nodes, re-run geo validation, and persist.

        Args:
            campaign_id: UUID of the campaign.
            new_taxonomy: Dict with ``nodes`` key containing the new tree.

        Returns:
            Tuple of (campaign, geo_result) after commit.

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in TAXONOMY_READY status.
        """
        campaign = await self._load_campaign(campaign_id)
        if campaign.status != CampaignStatus.TAXONOMY_READY:
            raise ResourceLockedError("Taxonomy can only be edited while in TAXONOMY_READY status.")

        geo_validator = TaxonomyGeoValidator()
        geo_result = geo_validator.validate_and_normalize(new_taxonomy)

        campaign.taxonomy_json = geo_result.normalized_taxonomy
        snapshot = campaign.generation_config_snapshot or {}
        snapshot["geo_warnings"] = [w.to_dict() for w in geo_result.warnings]
        snapshot["geo_stats"] = geo_result.stats
        campaign.generation_config_snapshot = snapshot
        campaign.updated_at = datetime.now(timezone.utc)
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        return campaign, geo_result

    async def approve_taxonomy(self, campaign_id: UUID, approver_id: UUID) -> "Campaign":
        """Approve the taxonomy, recording approver and timestamp.

        Args:
            campaign_id: UUID of the campaign.
            approver_id: UUID of the approving user.

        Returns:
            The updated Campaign instance.

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in TAXONOMY_READY status.
        """
        campaign = await self._load_campaign(campaign_id)
        if campaign.status != CampaignStatus.TAXONOMY_READY:
            raise ResourceLockedError(
                "Taxonomy can only be approved while in TAXONOMY_READY status."
            )

        now = datetime.now(timezone.utc)
        campaign.taxonomy_approved_by = approver_id
        campaign.taxonomy_approved_at = now
        campaign.updated_at = now
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        return campaign

    @staticmethod
    def _build_user_prompt(campaign: Campaign) -> str:
        """Build the user prompt for taxonomy generation.

        Args:
            campaign: The campaign to generate a taxonomy for.

        Returns:
            Formatted user prompt string.
        """
        depth_label = campaign.target_depth.value

        locale_parts: List[str] = []

        # Note: These are future fields not yet defined on the Campaign model.
        # getattr is used because hasattr returns True for SQLModel attribute descriptors
        # even if the field isn't actually present on the instance or model yet.
        locale = getattr(campaign, "locale", None)
        if locale:
            locale_parts.append(f"locale: {locale}")

        region_focus = getattr(campaign, "region_focus", None)
        if region_focus:
            locale_parts.append(f"region_focus: {region_focus}")

        language = getattr(campaign, "language", None)
        if language:
            locale_parts.append(f"language: {language}")

        target_countries = getattr(campaign, "target_countries", None)
        if target_countries:
            countries_str = ", ".join(target_countries)
            locale_parts.append(f"ONLY target these countries (names or codes): {countries_str}")

        target_states = getattr(campaign, "target_states", None)
        if target_states:
            states_str = ", ".join(target_states)
            locale_parts.append(f"ONLY target these states/subdivisions: {states_str}")

        locale_hints = ""
        if locale_parts:
            locale_hints = "- locale_hints: " + ", ".join(locale_parts) + "\n"

        return USER_PROMPT_TEMPLATE.format(
            industry=campaign.industry,
            domain_description=campaign.domain_description or campaign.industry,
            target_depth=depth_label,
            max_jurisdictions=campaign.max_jurisdictions,
            locale_hints=locale_hints,
        )

    async def _expand_taxonomy_for_coverage(
        self,
        taxonomy_tree: TaxonomyTreeModel,
        campaign: Campaign,
        llm_manager: LLMManager,
        geo_validator: TaxonomyGeoValidator,
        run_id: str | None = None,
    ) -> tuple[TaxonomyTreeModel, TaxonomyValidationResult, Any, List[str]]:
        """Iteratively expand taxonomy when country coverage is below threshold."""
        validation, geo_result = self._validate_and_normalize_taxonomy(
            taxonomy_tree=taxonomy_tree,
            campaign=campaign,
            geo_validator=geo_validator,
        )

        expansion_trace: List[str] = []
        required_countries = self._required_country_coverage(campaign)
        if not settings.CAMPAIGN_TAXONOMY_EXPANSION_ENABLED or required_countries <= 0:
            return taxonomy_tree, validation, geo_result, expansion_trace

        max_passes = max(0, settings.CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES)
        batch_size = max(1, settings.CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE)
        current_distinct = int(geo_result.stats.get("distinct_countries", 0))

        remaining_needed = max(required_countries - current_distinct, 0)
        minimum_passes_needed = ceil(remaining_needed / batch_size) if remaining_needed else 0
        if minimum_passes_needed > max_passes:
            expansion_trace.append(
                "auto-escalated expansion passes "
                f"from {max_passes} to {minimum_passes_needed} "
                "to satisfy minimum country coverage"
            )
            max_passes = minimum_passes_needed

        for pass_number in range(1, max_passes + 1):
            if current_distinct >= required_countries:
                break

            missing_countries = self._missing_country_names(
                normalized_taxonomy=geo_result.normalized_taxonomy,
                limit=batch_size,
            )
            if not missing_countries:
                expansion_trace.append(
                    f"pass {pass_number}: no missing ISO countries identified for expansion"
                )
                break

            expansion_prompt = self._build_expansion_prompt(
                campaign=campaign,
                distinct_countries=current_distinct,
                required_countries=required_countries,
                countries_to_add=missing_countries,
            )
            expansion_response = await self._request_taxonomy_tree(
                llm_manager=llm_manager,
                prompt=expansion_prompt,
                temperature=max(settings.CAMPAIGN_TAXONOMY_TEMPERATURE - 0.1, 0.0),
                max_tokens=settings.CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS,
                endpoint="taxonomy_generation_expansion",
                request_id=self._build_tracking_request_id(
                    campaign_id=campaign.id,
                    run_id=run_id,
                    phase="expansion",
                    pass_number=pass_number,
                ),
            )
            self._handle_truncation(
                response=expansion_response,
                max_tokens=settings.CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS,
                context="taxonomy_generation_expansion",
                campaign_id=campaign.id,
            )

            expansion_tree = self._extract_taxonomy_tree(expansion_response)
            merged_nodes = self._merge_taxonomy_nodes(taxonomy_tree.nodes, expansion_tree.nodes)
            taxonomy_tree = TaxonomyTreeModel(nodes=merged_nodes)

            validation, geo_result = self._validate_and_normalize_taxonomy(
                taxonomy_tree=taxonomy_tree,
                campaign=campaign,
                geo_validator=geo_validator,
            )
            current_distinct = int(geo_result.stats.get("distinct_countries", 0))
            expansion_trace.append(
                f"pass {pass_number}: requested={len(missing_countries)} "
                f"distinct_countries={current_distinct}"
            )

        return taxonomy_tree, validation, geo_result, expansion_trace

    def _validate_and_normalize_taxonomy(
        self,
        taxonomy_tree: TaxonomyTreeModel,
        campaign: Campaign,
        geo_validator: TaxonomyGeoValidator,
    ) -> tuple[TaxonomyValidationResult, Any]:
        """Run structural validation and geo normalization for a taxonomy tree."""
        validation = self._validate_taxonomy(taxonomy_tree, campaign)
        if not validation.valid:
            raise ProcessingError(f"Taxonomy validation failed: {'; '.join(validation.errors)}")

        taxonomy_dict = taxonomy_tree.model_dump(mode="json")
        geo_result = geo_validator.validate_and_normalize(taxonomy_dict)

        # Filter by campaign target_countries and target_states if specified
        target_countries = getattr(campaign, "target_countries", None)
        target_states = getattr(campaign, "target_states", None)

        if (target_countries or target_states) and isinstance(geo_result.normalized_taxonomy, dict):
            filtered_nodes = []
            normalized_target_countries = (
                {c.strip().upper() for c in target_countries} if target_countries else set()
            )
            normalized_target_states = (
                {s.strip().upper() for s in target_states} if target_states else set()
            )

            for node in geo_result.normalized_taxonomy.get("nodes", []):
                country_name = node.get("name", "").strip().upper()
                country_iso = node.get("iso_code", "").strip().upper()

                # If target_countries is set, must match either name or ISO code
                if normalized_target_countries:
                    if (
                        country_name not in normalized_target_countries
                        and country_iso not in normalized_target_countries
                    ):
                        continue  # Skip this country

                # If target_states is set, filter subdivisions (children)
                if normalized_target_states:
                    filtered_children = []
                    for child in node.get("children", []):
                        child_name = child.get("name", "").strip().upper()
                        child_iso = child.get("iso_code", "").strip().upper()

                        # Match by name or code
                        if (
                            child_name in normalized_target_states
                            or child_iso in normalized_target_states
                        ):
                            filtered_children.append(child)
                        else:
                            # Also check if child_iso has a country code prefix like "US-CA" vs "CA"
                            short_child_iso = (
                                child_iso.split("-")[-1] if "-" in child_iso else child_iso
                            )
                            if short_child_iso in normalized_target_states:
                                filtered_children.append(child)
                    node["children"] = filtered_children

                filtered_nodes.append(node)
            geo_result.normalized_taxonomy["nodes"] = filtered_nodes

            # Re-calculate distinct countries and top-level matched stats
            seen_countries = {n.get("name").lower() for n in filtered_nodes if n.get("name")}
            geo_result.stats["distinct_countries"] = len(seen_countries)
            geo_result.stats["countries_matched"] = len(filtered_nodes)
            geo_result.stats["subdivisions_matched"] = sum(
                len(n.get("children", [])) for n in filtered_nodes
            )

        return validation, geo_result

    @staticmethod
    @lru_cache(maxsize=1)
    def _all_iso_country_names() -> tuple[str, ...]:
        """Return a stable sorted tuple of canonical ISO 3166-1 country names."""
        return tuple(sorted({country.name for country in pycountry.countries}))

    def _missing_country_names(self, normalized_taxonomy: Dict[str, Any], limit: int) -> List[str]:
        """Find canonical countries not yet represented as top-level nodes."""
        nodes = normalized_taxonomy.get("nodes", [])
        existing = {
            str(node.get("name", "")).strip().lower()
            for node in nodes
            if isinstance(node, dict) and str(node.get("name", "")).strip()
        }
        missing = [
            country_name
            for country_name in self._all_iso_country_names()
            if country_name.lower() not in existing
        ]
        return missing[:limit]

    @staticmethod
    def _build_expansion_prompt(
        campaign: Campaign,
        distinct_countries: int,
        required_countries: int,
        countries_to_add: List[str],
    ) -> str:
        """Build prompt for iterative breadth expansion pass."""
        countries_str = "\n".join(f"- {name}" for name in countries_to_add)
        return EXPANSION_USER_PROMPT_TEMPLATE.format(
            industry=campaign.industry,
            domain_description=campaign.domain_description or campaign.industry,
            target_depth=campaign.target_depth.value,
            max_jurisdictions=campaign.max_jurisdictions,
            distinct_countries=distinct_countries,
            required_countries=required_countries,
            countries_to_add=countries_str,
        )

    @staticmethod
    async def _request_taxonomy_tree(
        llm_manager: LLMManager,
        prompt: str,
        temperature: float,
        max_tokens: int,
        endpoint: str,
        request_id: str | None = None,
    ) -> LLMResponse:
        """Issue taxonomy generation request with schema enforcement."""
        return await llm_manager.generate_with_tracking(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            model_preference="premium",
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            response_model=TaxonomyTreeModel,
            max_validation_retries=2,
            endpoint=endpoint,
            request_id=request_id,
        )

    @staticmethod
    def _build_tracking_request_id(
        campaign_id: UUID,
        run_id: str | None,
        phase: str,
        pass_number: int | None = None,
    ) -> str:
        """Build a stable LLM request correlation id for campaign taxonomy runs."""
        base = f"campaign:{campaign_id}:taxonomy"
        if run_id:
            base = f"{base}:run:{run_id}"
        if pass_number is not None:
            return f"{base}:{phase}:{pass_number}"
        return f"{base}:{phase}"

    @staticmethod
    def _handle_truncation(
        response: LLMResponse,
        max_tokens: int,
        context: str,
        campaign_id: UUID,
    ) -> None:
        """Fail fast or warn on truncated LLM responses based on policy."""
        raw_response = getattr(response, "raw_response", {}) or {}
        choices = raw_response.get("choices", [{}])
        truncated = any(
            isinstance(choice, dict) and choice.get("finish_reason") == "length"
            for choice in choices
        )
        if truncated and settings.CAMPAIGN_TAXONOMY_STRICT_TRUNCATION:
            raise ProcessingError(
                f"{context} response was truncated. "
                f"Increase token budget (current={max_tokens}) and retry."
            )
        if truncated:
            logger.warning(
                "%s response was truncated (finish_reason=length) for campaign %s",
                context,
                campaign_id,
            )

    def _merge_taxonomy_nodes(
        self,
        existing_nodes: List[TaxonomyNodeModel],
        incoming_nodes: List[TaxonomyNodeModel],
    ) -> List[TaxonomyNodeModel]:
        """Merge sibling nodes by case-insensitive name and recursively merge children."""
        merged = [node for node in existing_nodes]
        name_to_index = {
            node.name.strip().lower(): index
            for index, node in enumerate(merged)
            if node.name and node.name.strip()
        }

        for incoming in incoming_nodes:
            key = incoming.name.strip().lower()
            if not key:
                continue
            if key in name_to_index:
                idx = name_to_index[key]
                merged[idx] = self._merge_single_node(merged[idx], incoming)
                continue

            merged.append(incoming)
            name_to_index[key] = len(merged) - 1

        return merged

    def _merge_single_node(
        self,
        base: TaxonomyNodeModel,
        incoming: TaxonomyNodeModel,
    ) -> TaxonomyNodeModel:
        """Merge two nodes representing the same jurisdiction."""
        merged_queries = self._merge_queries(
            base.suggested_search_queries,
            incoming.suggested_search_queries,
        )
        merged_children = self._merge_taxonomy_nodes(base.children, incoming.children)

        return TaxonomyNodeModel(
            name=base.name,
            description=base.description or incoming.description or f"Regulations for {base.name}",
            suggested_prompt=(
                base.suggested_prompt
                or incoming.suggested_prompt
                or f"Extract regulations for {base.name}"
            ),
            suggested_search_queries=merged_queries or [f"{base.name} regulations"],
            children=merged_children,
            iso_code=base.iso_code or incoming.iso_code,
        )

    @staticmethod
    def _merge_queries(existing: Optional[List[str]], incoming: Optional[List[str]]) -> List[str]:
        """Merge query lists preserving order and uniqueness."""
        merged: List[str] = []
        seen: set[str] = set()
        for query in (existing or []) + (incoming or []):
            value = str(query).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(value)
        return merged

    def _validate_taxonomy(
        self, taxonomy: TaxonomyTreeModel, campaign: Campaign
    ) -> TaxonomyValidationResult:
        """Validate taxonomy structure against business rules.

        Args:
            taxonomy: The parsed taxonomy tree.
            campaign: The campaign (for max_jurisdictions / target_depth).

        Returns:
            TaxonomyValidationResult with errors and warnings.
        """
        result = TaxonomyValidationResult()
        max_depth = DEPTH_LIMITS.get(campaign.target_depth, 3)

        self._check_circular_references(taxonomy.nodes, path=set(), result=result)

        taxonomy.nodes = self._deduplicate_nodes(taxonomy.nodes, depth=1, result=result)
        taxonomy.nodes = self._truncate_nodes_beyond_depth(
            taxonomy.nodes,
            depth=1,
            max_depth=max_depth,
            result=result,
        )

        self._validate_nodes(
            nodes=taxonomy.nodes,
            depth=1,
            max_depth=max_depth,
            result=result,
        )

        total_nodes = self._count_nodes(taxonomy.nodes)

        if total_nodes > campaign.max_jurisdictions:
            taxonomy.nodes = self._trim_to_budget(
                taxonomy.nodes,
                campaign.max_jurisdictions,
                result,
            )

        required_country_coverage = self._required_country_coverage(campaign)
        distinct_top_level = self._count_distinct_top_level_countries(taxonomy.nodes)
        if required_country_coverage > 0 and distinct_top_level < required_country_coverage:
            result.warnings.append(
                "Low pre-normalization country breadth detected: "
                f"{distinct_top_level} distinct top-level countries vs required "
                f"{required_country_coverage}."
            )

        return result

    def _truncate_nodes_beyond_depth(
        self,
        nodes: List[TaxonomyNodeModel],
        depth: int,
        max_depth: int,
        result: TaxonomyValidationResult,
    ) -> List[TaxonomyNodeModel]:
        """Trim children beyond campaign depth instead of failing generation."""
        trimmed: List[TaxonomyNodeModel] = []
        for node in nodes:
            if depth >= max_depth and node.children:
                removed_count = self._count_nodes(node.children)
                result.warnings.append(
                    f"Trimmed {removed_count} child nodes from '{node.name}' "
                    f"to honor max depth {max_depth}."
                )
                node.children = []
            elif node.children:
                node.children = self._truncate_nodes_beyond_depth(
                    node.children,
                    depth=depth + 1,
                    max_depth=max_depth,
                    result=result,
                )
            trimmed.append(node)
        return trimmed

    @staticmethod
    def _count_distinct_top_level_countries(nodes: List[TaxonomyNodeModel]) -> int:
        """Count distinct top-level node names (case-insensitive)."""
        distinct = {node.name.strip().lower() for node in nodes if node.name and node.name.strip()}
        return len(distinct)

    @staticmethod
    def _required_country_coverage(campaign: Campaign) -> int:
        """Return required minimum country coverage for coverage gate checks.

        Global coverage enforcement is only meaningful for COUNTRY/STATE depths and
        campaigns with budgets at least as large as the required threshold.

        Geo-targeted campaigns (those with ``target_countries`` or ``target_states``
        explicitly set) are intentionally scoped to a narrow geography, so the global
        country-coverage gate is not applied — requiring 180+ countries for a campaign
        that targets only 6 would always produce a false failure.
        """
        # Geo-targeted campaigns bypass the global coverage gate entirely.
        target_countries = getattr(campaign, "target_countries", None)
        target_states = getattr(campaign, "target_states", None)
        if target_countries or target_states:
            return 0

        if campaign.target_depth == CampaignTargetDepth.COUNTRY:
            required = settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY
        elif campaign.target_depth == CampaignTargetDepth.STATE:
            required = settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE
        else:
            return 0

        if campaign.max_jurisdictions < required:
            return 0
        return required

    def _enforce_country_coverage(self, campaign: Campaign, geo_stats: Dict[str, int]) -> None:
        """Fail taxonomy generation if global country coverage is below threshold.

        This protects downstream hydration and scraping from narrow taxonomies that
        are structurally valid but operationally incomplete for global campaigns.
        """
        if not settings.CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE:
            return

        required = self._required_country_coverage(campaign)
        if required <= 0:
            return

        distinct_countries = int(geo_stats.get("distinct_countries", 0))
        if distinct_countries < required:
            raise ProcessingError(
                "Taxonomy country coverage is below the required threshold for global execution. "
                f"Found {distinct_countries}, required at least {required}."
            )

    def _check_circular_references(
        self,
        nodes: List[TaxonomyNodeModel],
        path: Set[str],
        result: TaxonomyValidationResult,
    ) -> None:
        """Detect circular references by tracking ancestor names.

        Args:
            nodes: List of nodes at the current level.
            path: Set of lower-cased ancestor names in the current branch.
            result: Validation result to populate.
        """
        for node in nodes:
            name_lower = node.name.lower().strip()
            if name_lower in path:
                result.valid = False
                result.errors.append(
                    f"Circular reference detected: '{node.name}' appears in its own ancestry."
                )
                continue
            if node.children:
                self._check_circular_references(node.children, path | {name_lower}, result)

    def _deduplicate_nodes(
        self,
        nodes: List[TaxonomyNodeModel],
        depth: int,
        result: TaxonomyValidationResult,
    ) -> List[TaxonomyNodeModel]:
        """Remove duplicate node names at the same hierarchy level.

        Args:
            nodes: List of sibling nodes.
            depth: Current depth (for warning messages).
            result: Validation result to populate with warnings.

        Returns:
            Deduplicated list of nodes.
        """
        seen: set = set()
        unique_nodes: List[TaxonomyNodeModel] = []
        for node in nodes:
            name_lower = node.name.lower().strip()
            if name_lower in seen:
                result.warnings.append(f"Duplicate node removed at depth {depth}: '{node.name}'")
                continue
            seen.add(name_lower)
            if node.children:
                node.children = self._deduplicate_nodes(node.children, depth + 1, result)
            unique_nodes.append(node)
        return unique_nodes

    def _validate_nodes(
        self,
        nodes: List[TaxonomyNodeModel],
        depth: int,
        max_depth: int,
        result: TaxonomyValidationResult,
    ) -> None:
        """Recursively validate taxonomy nodes.

        Args:
            nodes: List of nodes at the current depth.
            depth: Current depth (1-indexed).
            max_depth: Maximum allowed depth.
            result: Validation result to populate.
        """
        for node in nodes:
            if len(node.name) > 255:
                result.valid = False
                result.errors.append(f"Node name exceeds 255 chars: '{node.name[:50]}...'")
            if not node.suggested_search_queries:
                result.valid = False
                result.errors.append(f"Node '{node.name}' has no suggested_search_queries.")

            if depth > max_depth:
                result.valid = False
                result.errors.append(
                    f"Node '{node.name}' exceeds max depth {max_depth} (at depth {depth})."
                )

            if node.children:
                self._validate_nodes(
                    nodes=node.children,
                    depth=depth + 1,
                    max_depth=max_depth,
                    result=result,
                )

    @staticmethod
    def _extract_taxonomy_tree(response: "LLMResponse") -> TaxonomyTreeModel:
        """Extract TaxonomyTreeModel from LLMResponse regardless of content type.

        The ``LLMResponse.content`` field may be:
        - A ``TaxonomyTreeModel`` instance (when instructor validation succeeds)
        - A JSON string (when json_mode is used without response_model)
        - A dict (in edge cases)

        Args:
            response: The LLM response object.

        Returns:
            Validated TaxonomyTreeModel.

        Raises:
            ProcessingError: If content cannot be parsed into TaxonomyTreeModel.
        """
        content = response.content

        if isinstance(content, TaxonomyTreeModel):
            return content

        if isinstance(content, dict):
            return TaxonomyTreeModel.model_validate(content)

        if isinstance(content, str):
            try:
                return TaxonomyTreeModel.model_validate_json(content)
            except ValidationError as exc:
                raise ProcessingError(
                    message=(
                        "LLM returned invalid taxonomy payload that does not satisfy "
                        "TaxonomyTreeModel"
                    )
                ) from exc

        raise ProcessingError(
            f"Unexpected LLM response type: {type(content).__name__}. Cannot extract taxonomy tree."
        )

    @staticmethod
    def _count_nodes(nodes: List[TaxonomyNodeModel]) -> int:
        """Count total nodes (recursive).

        Args:
            nodes: Root node list.

        Returns:
            Total number of nodes in the tree.
        """
        count = 0
        for node in nodes:
            count += 1
            if node.children:
                count += TaxonomyGenerationService._count_nodes(node.children)
        return count

    @staticmethod
    def _trim_to_budget(
        nodes: List[TaxonomyNodeModel],
        budget: int,
        result: TaxonomyValidationResult,
    ) -> List[TaxonomyNodeModel]:
        """Trim the taxonomy tree so total node count <= budget.

        Strategy:
        1) Preserve breadth by keeping sibling nodes where possible.
        2) Allocate descendant budget proportionally across siblings.
        3) Recursively trim each subtree to allocated descendant budget.
        4) Fall back to dropping trailing siblings only when budget is
           smaller than sibling count.

        A warning is appended to *result* for every dropped node.

        Args:
            nodes: Top-level node list (mutated in place).
            budget: Maximum total nodes allowed.
            result: Validation result to record warnings.

        Returns:
            Trimmed list of nodes.
        """
        original = TaxonomyGenerationService._count_nodes(nodes)
        if original <= budget:
            return nodes

        if budget <= 0:
            if original > 0:
                result.warnings.append(
                    f"Dropped {original} nodes to fit max_jurisdictions={budget}"
                )
            return []

        # If budget cannot even hold one entry per sibling, preserve deterministic
        # order and drop trailing siblings. This is the only breadth-breaking case.
        if budget < len(nodes):
            keep = nodes[:budget]
            for removed in nodes[budget:]:
                dropped = TaxonomyGenerationService._count_nodes([removed])
                result.warnings.append(
                    f"Dropped top-level node '{removed.name}' ({dropped} nodes) "
                    f"to fit max_jurisdictions={budget}"
                )

            # No descendant budget remains once one node-per-sibling is consumed.
            for node in keep:
                if node.children:
                    dropped_children = TaxonomyGenerationService._count_nodes(node.children)
                    if dropped_children > 0:
                        result.warnings.append(
                            f"Trimmed all {dropped_children} children of '{node.name}' "
                            f"to fit max_jurisdictions={budget}"
                        )
                    node.children = []

            logger.info(
                "Taxonomy trimmed from %d to %d nodes (budget=%d)",
                original,
                TaxonomyGenerationService._count_nodes(keep),
                budget,
            )
            return keep

        sibling_budget = budget - len(nodes)
        sibling_weights = [
            TaxonomyGenerationService._count_nodes(node.children) if node.children else 0
            for node in nodes
        ]
        child_allocations = TaxonomyGenerationService._allocate_proportional_budgets(
            weights=sibling_weights,
            budget=sibling_budget,
        )

        for index, node in enumerate(nodes):
            allocated_children_budget = child_allocations[index]
            current_children_count = TaxonomyGenerationService._count_nodes(node.children)
            if current_children_count <= allocated_children_budget:
                continue

            if allocated_children_budget == 0:
                result.warnings.append(
                    f"Trimmed all {current_children_count} children of '{node.name}' "
                    f"to fit max_jurisdictions={budget}"
                )
                node.children = []
                continue

            node.children = TaxonomyGenerationService._trim_to_budget(
                node.children,
                allocated_children_budget,
                result,
            )

        trimmed = TaxonomyGenerationService._count_nodes(nodes)
        while nodes and trimmed > budget:
            removed = nodes.pop()
            dropped = TaxonomyGenerationService._count_nodes([removed])
            trimmed -= dropped
            result.warnings.append(
                f"Dropped top-level node '{removed.name}' ({dropped} nodes) "
                f"to fit max_jurisdictions={budget}"
            )

        logger.info(
            "Taxonomy trimmed from %d to %d nodes (budget=%d)",
            original,
            trimmed,
            budget,
        )
        return nodes

    @staticmethod
    def _allocate_proportional_budgets(weights: List[int], budget: int) -> List[int]:
        """Allocate descendant budgets proportionally using largest remainders."""
        if not weights or budget <= 0:
            return [0] * len(weights)

        normalized_weights = [max(0, int(weight)) for weight in weights]
        total_weight = sum(normalized_weights)
        if total_weight <= 0:
            return [0] * len(weights)

        raw_allocations = [(budget * weight) / total_weight for weight in normalized_weights]
        allocations = [
            min(int(allocation), normalized_weights[index])
            for index, allocation in enumerate(raw_allocations)
        ]

        used_budget = sum(allocations)
        remainders = sorted(
            (
                (raw_allocations[index] - int(raw_allocations[index]), index)
                for index in range(len(raw_allocations))
            ),
            reverse=True,
        )

        while used_budget < budget:
            progressed = False
            for _, index in remainders:
                if allocations[index] >= normalized_weights[index]:
                    continue
                allocations[index] += 1
                used_budget += 1
                progressed = True
                if used_budget >= budget:
                    break
            if not progressed:
                break

        return allocations

    async def _load_campaign(self, campaign_id: UUID) -> Campaign:
        """Load a campaign by ID.

        Args:
            campaign_id: Primary key.

        Returns:
            Campaign instance.

        Raises:
            NotFoundError: If campaign does not exist.
        """
        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise NotFoundError("Campaign not found.")
        return campaign
