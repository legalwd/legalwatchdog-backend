"""Tests for TaxonomyGenerationService — mocked LLM, no real API calls."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignMonitorBackend,
    CampaignStatus,
    CampaignTargetDepth,
)
from app.api.modules.v1.campaigns.service.taxonomy_generation_service import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    TaxonomyGenerationService,
    TaxonomyNodeModel,
    TaxonomyTreeModel,
    TaxonomyValidationResult,
)

CAMPAIGN_ID = uuid.uuid4()
ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _make_campaign(
    status: CampaignStatus = CampaignStatus.DRAFT,
    max_jurisdictions: int = 100,
) -> Campaign:
    """Build a Campaign fixture."""
    now = datetime.now(timezone.utc)
    campaign = Campaign(
        id=CAMPAIGN_ID,
        organization_id=ORG_ID,
        name="EOR Compliance",
        industry="EOR",
        domain_description="Employer of Record regulatory tracking",
        target_depth=CampaignTargetDepth.STATE,
        monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
        sources_per_jurisdiction=5,
        max_jurisdictions=max_jurisdictions,
        status=status,
        created_by=USER_ID,
        created_at=now,
        updated_at=now,
    )
    campaign.execution_logs = []
    return campaign


def _valid_taxonomy_tree() -> TaxonomyTreeModel:
    """Build a minimal valid TaxonomyTreeModel."""
    return TaxonomyTreeModel(
        nodes=[
            TaxonomyNodeModel(
                name="United States",
                description="Federal EOR regulations",
                suggested_prompt="Extract US federal EOR compliance data",
                suggested_search_queries=["US federal employment law 2026"],
                children=[
                    TaxonomyNodeModel(
                        name="California",
                        description="California state employment overlays",
                        suggested_prompt="Extract California-specific EOR fields",
                        suggested_search_queries=["California labor code 2026"],
                        children=[],
                    ),
                ],
            ),
            TaxonomyNodeModel(
                name="Nigeria",
                description="Nigerian employment regulations",
                suggested_prompt="Extract Nigerian EOR compliance data",
                suggested_search_queries=["Nigeria employment law 2026"],
                children=[],
            ),
        ]
    )


def _wide_taxonomy_tree(children_per_country: int = 4) -> TaxonomyTreeModel:
    """Build a wide taxonomy with balanced child counts for trim tests."""
    us_children = [
        TaxonomyNodeModel(
            name=f"US-State-{idx}",
            description="US state-level regulations",
            suggested_prompt="Extract US state regulations",
            suggested_search_queries=["US state regulations"],
            children=[],
        )
        for idx in range(children_per_country)
    ]
    ng_children = [
        TaxonomyNodeModel(
            name=f"NG-State-{idx}",
            description="NG state-level regulations",
            suggested_prompt="Extract NG state regulations",
            suggested_search_queries=["NG state regulations"],
            children=[],
        )
        for idx in range(children_per_country)
    ]

    return TaxonomyTreeModel(
        nodes=[
            TaxonomyNodeModel(
                name="United States",
                description="US regulations",
                suggested_prompt="Extract US regulations",
                suggested_search_queries=["US regulations"],
                children=us_children,
            ),
            TaxonomyNodeModel(
                name="Nigeria",
                description="NG regulations",
                suggested_prompt="Extract NG regulations",
                suggested_search_queries=["NG regulations"],
                children=ng_children,
            ),
        ]
    )


def _make_llm_response(taxonomy_tree: TaxonomyTreeModel, finish_reason: str = "stop"):
    """Build a mock LLMResponse."""
    mock_response = MagicMock()
    mock_response.parsed = taxonomy_tree
    mock_response.content = taxonomy_tree.model_dump_json()
    mock_response.model = "google/gemini-2.5-flash"
    mock_response.raw_response = {"choices": [{"finish_reason": finish_reason}]}
    mock_response.usage_metrics = MagicMock()
    return mock_response


class TestGenerateTaxonomySuccess:
    """test_generate_taxonomy_success — happy path with mocked LLM."""

    @pytest.mark.asyncio
    async def test_stores_taxonomy_and_sets_status(self):
        campaign = _make_campaign()
        taxonomy_tree = _valid_taxonomy_tree()
        llm_response = _make_llm_response(taxonomy_tree)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        # Prepare a mock geo validation result
        mock_geo_result = MagicMock()
        mock_geo_result.normalized_taxonomy = {"nodes": [{"name": "US-Normalized"}]}
        mock_geo_result.warnings = []
        mock_geo_result.stats = {
            "countries_matched": 2,
            "subdivisions_matched": 1,
            "unrecognized_count": 0,
            "distinct_countries": 2,
        }

        service = TaxonomyGenerationService(db)

        with (
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
            ) as MockLLM,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.TaxonomyGeoValidator"
            ) as MockGeo,
        ):
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(return_value=llm_response)
            MockGeo.return_value.validate_and_normalize.return_value = mock_geo_result

            result = await service.generate(CAMPAIGN_ID)

        # Result should be the geo-normalized taxonomy
        assert result == {"nodes": [{"name": "US-Normalized"}]}

        assert campaign.status == CampaignStatus.TAXONOMY_READY
        assert campaign.generation_model == "google/gemini-2.5-flash"

        # Geo data should be stored in the snapshot atomically
        snapshot = campaign.generation_config_snapshot
        assert "geo_warnings" in snapshot
        assert "geo_stats" in snapshot
        assert snapshot["geo_stats"]["countries_matched"] == 2


class TestGenerateTaxonomyNotInDraftRejected:
    """test_generate_taxonomy_not_in_draft_rejected."""

    @pytest.mark.asyncio
    async def test_rejects_non_draft_campaign(self):
        campaign = _make_campaign(status=CampaignStatus.TAXONOMY_READY)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )

        service = TaxonomyGenerationService(db)

        from app.api.core.custom_exceptions.exceptions import ResourceLockedError

        with pytest.raises(ResourceLockedError):
            await service.generate(CAMPAIGN_ID)


class TestGenerateTaxonomyExceedsMaxJurisdictions:
    """test_generate_taxonomy_exceeds_max_jurisdictions — validation trims oversized tree."""

    @pytest.mark.asyncio
    async def test_trims_when_exceeds_max(self):
        """When LLM produces more nodes than max_jurisdictions, the tree is
        trimmed to fit and a warning is recorded — not a hard error."""
        campaign = _make_campaign(max_jurisdictions=2)
        taxonomy_tree = _valid_taxonomy_tree()  # 3 nodes: US, California, Nigeria
        llm_response = _make_llm_response(taxonomy_tree)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        mock_geo_result = MagicMock()
        mock_geo_result.normalized_taxonomy = {"nodes": [{"name": "US-Trimmed"}]}
        mock_geo_result.warnings = []
        mock_geo_result.stats = {
            "countries_matched": 1,
            "subdivisions_matched": 0,
            "unrecognized_count": 0,
            "distinct_countries": 1,
        }

        service = TaxonomyGenerationService(db)

        with (
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
            ) as MockLLM,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.TaxonomyGeoValidator"
            ) as MockGeo,
        ):
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(return_value=llm_response)
            MockGeo.return_value.validate_and_normalize.return_value = mock_geo_result

            result = await service.generate(CAMPAIGN_ID)

        # Should succeed (not raise), status should be TAXONOMY_READY
        assert result is not None
        assert campaign.status == CampaignStatus.TAXONOMY_READY

        # The config snapshot should contain trim warnings
        snapshot = campaign.generation_config_snapshot
        warnings = snapshot.get("validation_warnings", [])
        assert any("Trimmed" in w or "Dropped" in w for w in warnings)


class TestGenerateTaxonomyInvalidJsonFromLlm:
    """test_generate_taxonomy_invalid_json_from_llm — LLM returns garbage."""

    @pytest.mark.asyncio
    async def test_sets_failed_on_exception(self):
        campaign = _make_campaign()

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        service = TaxonomyGenerationService(db)

        from app.api.core.custom_exceptions.exceptions import ProcessingError

        with patch(
            "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(
                side_effect=Exception("LLM returned invalid output")
            )

            with pytest.raises(ProcessingError, match="Taxonomy generation failed"):
                await service.generate(CAMPAIGN_ID)

        assert campaign.status == CampaignStatus.FAILED


class TestInstructorSchemaValidationRetriesThenSucceeds:
    """test_instructor_schema_validation_retries_then_succeeds."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_eventually(self):
        """Simulate instructor retry: first call raises, second succeeds.

        Since instructor retries are handled internally by LLMManager via
        max_validation_retries, we test that when the final response is valid
        the service processes it correctly.
        """
        campaign = _make_campaign()
        taxonomy_tree = _valid_taxonomy_tree()
        llm_response = _make_llm_response(taxonomy_tree)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        mock_geo_result = MagicMock()
        mock_geo_result.normalized_taxonomy = taxonomy_tree.model_dump(mode="json")
        mock_geo_result.warnings = []
        mock_geo_result.stats = {
            "countries_matched": 0,
            "subdivisions_matched": 0,
            "unrecognized_count": 0,
            "distinct_countries": 2,
        }

        service = TaxonomyGenerationService(db)

        with (
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
            ) as MockLLM,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.TaxonomyGeoValidator"
            ) as MockGeo,
        ):
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(return_value=llm_response)
            MockGeo.return_value.validate_and_normalize.return_value = mock_geo_result

            result = await service.generate(CAMPAIGN_ID)

        assert "nodes" in result
        assert campaign.status == CampaignStatus.TAXONOMY_READY

        instance.generate_with_tracking.assert_called_once()
        call_kwargs = instance.generate_with_tracking.call_args.kwargs
        assert call_kwargs.get("max_validation_retries") == 2


class TestInstructorSchemaValidationFailsAfterRetries:
    """test_instructor_schema_validation_fails_after_retries."""

    @pytest.mark.asyncio
    async def test_fails_and_sets_campaign_failed(self):
        campaign = _make_campaign()

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        service = TaxonomyGenerationService(db)

        from app.api.core.custom_exceptions.exceptions import ProcessingError

        with patch(
            "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(
                side_effect=Exception("Validation failed after 3 retries")
            )

            with pytest.raises(ProcessingError):
                await service.generate(CAMPAIGN_ID)

        assert campaign.status == CampaignStatus.FAILED


class TestPromptContainsRequiredContractFields:
    """test_prompt_contains_required_contract_fields — verify prompt templates."""

    def test_user_prompt_contains_all_fields(self):
        """The user prompt template must include all required contract fields."""
        assert "{industry}" in USER_PROMPT_TEMPLATE
        assert "{domain_description}" in USER_PROMPT_TEMPLATE
        assert "{target_depth}" in USER_PROMPT_TEMPLATE
        assert "{max_jurisdictions}" in USER_PROMPT_TEMPLATE

    def test_system_prompt_contains_persona(self):
        """System prompt must include the architect persona."""
        assert "regulatory taxonomy architect" in SYSTEM_PROMPT

    def test_system_prompt_forbids_markdown(self):
        """System prompt must forbid markdown/prose."""
        assert "markdown" in SYSTEM_PROMPT.lower()
        assert "prose" in SYSTEM_PROMPT.lower()

    def test_build_user_prompt_substitutes_fields(self):
        """_build_user_prompt correctly substitutes campaign fields."""
        campaign = _make_campaign()
        prompt = TaxonomyGenerationService._build_user_prompt(campaign)
        assert "EOR" in prompt
        assert "Employer of Record" in prompt
        assert "STATE" in prompt


class TestTruncationHandling:
    """Strict truncation should fail fast to avoid persisting partial taxonomies."""

    @pytest.mark.asyncio
    async def test_truncated_response_raises_processing_error(self):
        campaign = _make_campaign()
        taxonomy_tree = _valid_taxonomy_tree()
        llm_response = _make_llm_response(taxonomy_tree, finish_reason="length")

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        service = TaxonomyGenerationService(db)

        from app.api.core.custom_exceptions.exceptions import ProcessingError

        with patch(
            "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(return_value=llm_response)

            with pytest.raises(ProcessingError, match="truncated"):
                await service.generate(CAMPAIGN_ID)

        assert campaign.status == CampaignStatus.FAILED


class TestCountryCoverageGate:
    """Global campaigns should fail when country breadth is too low."""

    @pytest.mark.asyncio
    async def test_low_country_coverage_fails_global_gate(self):
        campaign = _make_campaign(max_jurisdictions=1000)
        taxonomy_tree = _valid_taxonomy_tree()
        llm_response = _make_llm_response(taxonomy_tree)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        mock_geo_result = MagicMock()
        mock_geo_result.normalized_taxonomy = taxonomy_tree.model_dump(mode="json")
        mock_geo_result.warnings = []
        mock_geo_result.stats = {
            "countries_matched": 2,
            "subdivisions_matched": 1,
            "unrecognized_count": 0,
            "distinct_countries": 2,
        }

        service = TaxonomyGenerationService(db)

        from app.api.core.custom_exceptions.exceptions import ProcessingError

        with (
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
            ) as MockLLM,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.TaxonomyGeoValidator"
            ) as MockGeo,
        ):
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(return_value=llm_response)
            MockGeo.return_value.validate_and_normalize.return_value = mock_geo_result

            with pytest.raises(ProcessingError, match="coverage"):
                await service.generate(CAMPAIGN_ID)

        assert campaign.status == CampaignStatus.FAILED


class TestExpansionPasses:
    """Phase 2 iterative expansion should recover low-breadth taxonomies."""

    @pytest.mark.asyncio
    async def test_expansion_pass_increases_coverage_and_succeeds(self):
        campaign = _make_campaign(max_jurisdictions=1000)
        initial_tree = _valid_taxonomy_tree()
        expansion_tree = TaxonomyTreeModel(
            nodes=[
                TaxonomyNodeModel(
                    name="Germany",
                    description="German regulations",
                    suggested_prompt="Extract German regulations",
                    suggested_search_queries=["Germany regulations"],
                    children=[],
                )
            ]
        )
        initial_response = _make_llm_response(initial_tree)
        expansion_response = _make_llm_response(expansion_tree)

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=campaign))
        )
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()

        low_geo = MagicMock()
        low_geo.normalized_taxonomy = initial_tree.model_dump(mode="json")
        low_geo.warnings = []
        low_geo.stats = {
            "countries_matched": 2,
            "subdivisions_matched": 1,
            "unrecognized_count": 0,
            "distinct_countries": 2,
        }

        recovered_geo = MagicMock()
        recovered_geo.normalized_taxonomy = {
            "nodes": initial_tree.model_dump(mode="json")["nodes"]
            + expansion_tree.model_dump(mode="json")["nodes"]
        }
        recovered_geo.warnings = []
        recovered_geo.stats = {
            "countries_matched": 200,
            "subdivisions_matched": 5,
            "unrecognized_count": 0,
            "distinct_countries": 200,
        }

        service = TaxonomyGenerationService(db)

        with (
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.LLMManager"
            ) as MockLLM,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.TaxonomyGeoValidator"
            ) as MockGeo,
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.settings.CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES",
                1,
            ),
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.settings.CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE",
                5,
            ),
            patch(
                "app.api.modules.v1.campaigns.service.taxonomy_generation_service.settings.CAMPAIGN_TAXONOMY_EXPANSION_ENABLED",
                True,
            ),
        ):
            instance = MockLLM.return_value
            instance.generate_with_tracking = AsyncMock(
                side_effect=[initial_response, expansion_response]
            )
            MockGeo.return_value.validate_and_normalize = MagicMock(
                side_effect=[low_geo, recovered_geo]
            )

            result = await service.generate(CAMPAIGN_ID)

        assert result == recovered_geo.normalized_taxonomy
        assert campaign.status == CampaignStatus.TAXONOMY_READY
        assert instance.generate_with_tracking.await_count == 2
        assert campaign.generation_config_snapshot["expansion"]["passes"] == 2


class TestBalancedTrimming:
    """Phase 2 trimming should preserve breadth when budget allows."""

    def test_balanced_trim_preserves_multiple_top_level_countries(self):
        taxonomy_tree = _wide_taxonomy_tree(children_per_country=4)
        validation_result = TaxonomyValidationResult()

        trimmed = TaxonomyGenerationService._trim_to_budget(
            nodes=taxonomy_tree.nodes,
            budget=6,
            result=validation_result,
        )

        assert len(trimmed) == 2
        assert len(trimmed[0].children) >= 1
        assert len(trimmed[1].children) >= 1
        assert TaxonomyGenerationService._count_nodes(trimmed) <= 6


class TestGeoTargetedCoverageBypass:
    """Geo-targeted campaigns must bypass the global country-coverage gate.

    When a campaign has target_countries or target_states set, the taxonomy is
    intentionally filtered to a small geography.  Requiring 180+ countries for
    those campaigns would always produce a spurious ProcessingError.
    """

    def _make_global_campaign(self, max_jurisdictions: int = 15000) -> Campaign:
        """Build an unrestricted global campaign."""
        now = datetime.now(timezone.utc)
        campaign = Campaign(
            id=uuid.uuid4(),
            organization_id=ORG_ID,
            name="Global EOR",
            industry="EOR",
            domain_description="Global employer of record",
            target_depth=CampaignTargetDepth.COUNTRY,
            monitor_backend=CampaignMonitorBackend.CELERY_BEAT,
            sources_per_jurisdiction=5,
            max_jurisdictions=max_jurisdictions,
            status=CampaignStatus.DRAFT,
            created_by=USER_ID,
            created_at=now,
            updated_at=now,
        )
        campaign.execution_logs = []
        return campaign

    def _with_target_countries(
        self, campaign: Campaign, countries: list[str]
    ) -> Campaign:
        campaign.target_countries = countries
        return campaign

    def _with_target_states(self, campaign: Campaign, states: list[str]) -> Campaign:
        campaign.target_states = states
        return campaign

    # ------------------------------------------------------------------
    # _required_country_coverage
    # ------------------------------------------------------------------

    def test_required_coverage_zero_when_target_countries_set(self):
        """target_countries → required coverage must be 0."""
        campaign = self._with_target_countries(
            self._make_global_campaign(), ["US", "CA", "GB", "DE", "FR", "AU"]
        )
        assert TaxonomyGenerationService._required_country_coverage(campaign) == 0

    def test_required_coverage_zero_when_target_states_set(self):
        """target_states → required coverage must be 0."""
        campaign = self._with_target_states(
            self._make_global_campaign(), ["CA", "NY", "TX"]
        )
        assert TaxonomyGenerationService._required_country_coverage(campaign) == 0

    def test_required_coverage_zero_when_both_targets_set(self):
        """target_countries + target_states together → required coverage must be 0."""
        campaign = self._make_global_campaign()
        campaign.target_countries = ["US"]
        campaign.target_states = ["CA", "NY"]
        assert TaxonomyGenerationService._required_country_coverage(campaign) == 0

    def test_required_coverage_nonzero_for_global_campaign(self):
        """Unrestricted global campaign with sufficient budget → coverage is 180."""
        campaign = self._make_global_campaign(max_jurisdictions=15000)
        # No target_countries / target_states set
        required = TaxonomyGenerationService._required_country_coverage(campaign)
        assert required > 0

    def test_required_coverage_zero_for_small_budget_global(self):
        """Global campaign whose budget < threshold → coverage gate is skipped."""
        campaign = self._make_global_campaign(max_jurisdictions=10)
        required = TaxonomyGenerationService._required_country_coverage(campaign)
        assert required == 0

    # ------------------------------------------------------------------
    # _enforce_country_coverage
    # ------------------------------------------------------------------

    def test_enforce_does_not_raise_for_geo_targeted_campaign(self):
        """Geo-targeted campaign with only 6 countries must NOT raise."""
        campaign = self._with_target_countries(
            self._make_global_campaign(), ["US", "CA", "GB", "DE", "FR", "AU"]
        )
        service = TaxonomyGenerationService.__new__(TaxonomyGenerationService)
        # Should not raise regardless of distinct_countries count
        service._enforce_country_coverage(campaign, {"distinct_countries": 6})

    def test_enforce_raises_for_global_campaign_below_threshold(self):
        """Global campaign with < 180 countries must raise ProcessingError."""

        campaign = self._make_global_campaign(max_jurisdictions=15000)
        service = TaxonomyGenerationService.__new__(TaxonomyGenerationService)

        with patch(
            "app.api.modules.v1.campaigns.service.taxonomy_generation_service.settings"
        ) as mock_settings:
            mock_settings.CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE = True
            mock_settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY = 180
            mock_settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE = 180

            with pytest.raises(ProcessingError, match="below the required threshold"):
                service._enforce_country_coverage(campaign, {"distinct_countries": 6})

    def test_enforce_passes_for_global_campaign_at_threshold(self):
        """Global campaign that meets the threshold must NOT raise."""

        campaign = self._make_global_campaign(max_jurisdictions=15000)
        service = TaxonomyGenerationService.__new__(TaxonomyGenerationService)

        with patch(
            "app.api.modules.v1.campaigns.service.taxonomy_generation_service.settings"
        ) as mock_settings:
            mock_settings.CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE = True
            mock_settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY = 180
            mock_settings.CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE = 180

            # Exactly at threshold — should not raise
            service._enforce_country_coverage(campaign, {"distinct_countries": 180})

