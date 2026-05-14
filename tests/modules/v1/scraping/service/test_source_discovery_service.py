"""Unit tests for SourceDiscoveryService helper methods."""

from unittest.mock import MagicMock, patch

import pytest

from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService


@pytest.fixture
def service():
    """Fixture for SourceDiscoveryService with mocked Parallel.ai client."""
    with patch("app.api.core.config.settings") as mock_settings:
        mock_settings.PARALLEL_API_KEY = "test-key"
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        with (
            patch("app.api.modules.v1.scraping.service.source_discovery_service.AsyncParallel"),
            patch("httpx.AsyncClient"),
        ):
            svc = SourceDiscoveryService.__new__(SourceDiscoveryService)
            svc.db_session = None
            svc.parallel = MagicMock()
            svc.http_client = MagicMock()
            return svc


class TestIsOfficialSource:
    """Tests for _is_official_source."""

    def test_nigerian_government_domain(self, service):
        """Identifies .gov.ng as official."""
        assert service._is_official_source("https://labour.gov.ng/policies")

    def test_uk_government_domain(self, service):
        """Identifies .gov.uk as official."""
        assert service._is_official_source("https://www.legislation.gov.uk/ukpga/2023/1")

    def test_us_gov_domain(self, service):
        """Identifies .gov/ as official."""
        assert service._is_official_source("https://www.dol.gov/agencies/whd/flsa")

    def test_eu_law_domain(self, service):
        """Identifies eur-lex.europa.eu as official."""
        assert service._is_official_source("https://eur-lex.europa.eu/legal-content/EN/TXT/")

    def test_french_government_domain(self, service):
        """Identifies .gouv.fr as official."""
        assert service._is_official_source("https://travail-emploi.gouv.fr/droit-du-travail")

    def test_commercial_domain_not_official(self, service):
        """Rejects commercial domains as non-official."""
        assert not service._is_official_source("https://example.com/labour-law")

    def test_pwc_not_official(self, service):
        """Rejects PwC domain as non-official."""
        assert not service._is_official_source("https://taxsummaries.pwc.com/nigeria")


class TestIsTrustedSecondary:
    """Tests for _is_trusted_secondary."""

    def test_pwc_tax_summaries(self, service):
        """Identifies PwC Tax Summaries as trusted secondary."""
        assert service._is_trusted_secondary("https://taxsummaries.pwc.com/nigeria/individual")

    def test_deloitte_itcd(self, service):
        """Identifies Deloitte ITCD as trusted secondary."""
        assert service._is_trusted_secondary("https://dits.deloitte.com/#TaxGuideContent/nigeria")

    def test_ey_tax_guides(self, service):
        """Identifies EY tax guides as trusted secondary."""
        assert service._is_trusted_secondary("https://www.ey.com/en_gl/tax-guides/nigeria")

    def test_lexology(self, service):
        """Identifies Lexology as trusted secondary."""
        assert service._is_trusted_secondary("https://www.lexology.com/library/detail.aspx?g=abc")

    def test_nigerialii(self, service):
        """Identifies NigeriaLII as trusted secondary."""
        assert service._is_trusted_secondary("https://nigerialii.org/ng/legislation/labour-act")

    def test_random_blog_not_trusted(self, service):
        """Rejects an unrecognised domain as non-trusted."""
        assert not service._is_trusted_secondary("https://random-compliance-blog.com/guide")


class TestGetSourceCategory:
    """Tests for _get_source_category."""

    def test_official_gov_category(self, service):
        """Classifies government domain as official_gov."""
        assert service._get_source_category("https://labour.gov.ng") == "official_gov"

    def test_intergovernmental_category(self, service):
        """Classifies ILO as intergovernmental even though .org is not gov TLD."""
        assert service._get_source_category("https://www.ilo.org/employment") == "intergovernmental"

    def test_oecd_intergovernmental(self, service):
        """Classifies OECD as intergovernmental."""
        assert service._get_source_category("https://www.oecd.org/tax") == "intergovernmental"

    def test_trusted_secondary_category(self, service):
        """Classifies PwC Tax Summaries as trusted_secondary."""
        assert (
            service._get_source_category("https://taxsummaries.pwc.com/nigeria")
            == "trusted_secondary"
        )

    def test_news_media_category(self, service):
        """Classifies Reuters as news_media."""
        assert service._get_source_category("https://www.reuters.com/legal/") == "news_media"

    def test_other_category(self, service):
        """Classifies unknown domain as other."""
        assert service._get_source_category("https://some-unknown-blog.io/article") == "other"

    def test_intergovernmental_takes_priority_over_official(self, service):
        """Intergovernmental classification takes priority over .gov-like patterns."""
        assert service._get_source_category("https://www.ilo.org") == "intergovernmental"


class TestAssessContentDepth:
    """Tests for _assess_content_depth."""

    def test_empty_excerpts_returns_zero(self, service):
        """Returns 0 when no excerpts are provided."""
        assert service._assess_content_depth([], "Some Title") == 0

    def test_high_score_for_data_dense_excerpt(self, service):
        """Returns a high score when excerpts contain percentages and legal keywords."""
        excerpts = [
            "Employer must contribute 10% and employee 8% of monthly salary to pension. "
            "Section 9 of the Pension Reform Act 2014 requires all employers with "
            "15 or more employees to comply within 30 days of hire.",
            "Minimum wage is \u20a670,000 per month as at July 2024.",
        ]
        score = service._assess_content_depth(excerpts, "Pension Reform Act")
        assert score >= 50, f"Expected >= 50, got {score}"

    def test_low_score_for_navigation_page(self, service):
        """Returns a low score for navigation-only excerpt text."""
        excerpts = [
            "Read more about our services. Click here to learn more. "
            "Subscribe to our newsletter. Contact us today. Follow us on social media.",
        ]
        score = service._assess_content_depth(excerpts, "Home Page")
        assert score <= 20, f"Expected <= 20, got {score}"

    def test_longer_excerpts_score_higher(self, service):
        """More total excerpt content correlates with a higher score."""
        short_excerpts = ["Tax information is available online."]
        long_excerpts = [
            "The Personal Income Tax Act (PITA) Cap P8 LFN 2011 as amended provides "
            "for a graduated tax scale of 7%, 11%, 15%, 19%, 21%, and 24% on income "
            "bands. All employers are required to deduct and remit PAYE monthly. "
            "Late remittance attracts a penalty of 10% of the unpaid tax plus interest.",
            "The consolidated relief allowance is the higher of \u20a6200,000 or 1% of "
            "gross income plus 20% of gross income. National Housing Fund "
            "contributions are 2.5% of monthly basic salary.",
        ]
        short_score = service._assess_content_depth(short_excerpts, "Tax")
        long_score = service._assess_content_depth(long_excerpts, "PITA")
        assert long_score > short_score

    def test_score_capped_at_100(self, service):
        """Score never exceeds 100 regardless of excerpt richness."""
        very_rich = [
            "Regulation 5(2)(b) shall require minimum 15% rate within 30 days. "
            "Section 12 must comply with \u20a650,000 threshold pursuant to Act 2024. "
            "Article 7 clause 3: employer liable subject to 25% penalty. "
            "Maximum 20% rate; minimum \u20a630,000 monthly; entitled 21 days leave. "
            "Deadline: 31 March; subsection 4 requires 100% compliance."
        ] * 5
        score = service._assess_content_depth(very_rich, "Dense Regulation")
        assert score <= 100
        assert score >= 80


class TestGetExtractionSuitability:
    """Tests for _get_extraction_suitability."""

    def test_official_gov_high_depth_is_high(self, service):
        """Official gov source with sufficient depth is rated high."""
        assert service._get_extraction_suitability("official_gov", 40) == "high"

    def test_official_gov_low_depth_is_medium(self, service):
        """Official gov source with low depth is still rated medium (not low)."""
        assert service._get_extraction_suitability("official_gov", 10) == "medium"

    def test_trusted_secondary_high_depth(self, service):
        """Trusted secondary source with sufficient depth is rated high."""
        assert service._get_extraction_suitability("trusted_secondary", 35) == "high"

    def test_trusted_secondary_low_depth_is_medium(self, service):
        """Trusted secondary with low depth is rated medium."""
        assert service._get_extraction_suitability("trusted_secondary", 5) == "medium"

    def test_other_high_depth_is_high(self, service):
        """Unknown category with very high depth is still rated high."""
        assert service._get_extraction_suitability("other", 55) == "high"

    def test_other_mid_depth_is_medium(self, service):
        """Unknown category with medium depth is rated medium."""
        assert service._get_extraction_suitability("other", 30) == "medium"

    def test_other_low_depth_is_low(self, service):
        """Unknown category with very low depth is rated low."""
        assert service._get_extraction_suitability("other", 5) == "low"

    def test_news_media_low_depth_is_low(self, service):
        """News media with minimal depth is rated low."""
        assert service._get_extraction_suitability("news_media", 15) == "low"


class TestConvertToSuggestedSources:
    """Tests for _convert_to_suggested_sources."""

    def test_populates_all_new_fields(self, service):
        """All enriched fields are populated for each result."""
        results = {
            "results": [
                {
                    "url": "https://labour.gov.ng/policies-and-regulations/",
                    "title": "Labour Policies",
                    "excerpts": ["Employer must pay minimum wage of \u20a670,000 monthly."],
                }
            ]
        }
        sources = service._convert_to_suggested_sources(results)
        assert len(sources) == 1
        s = sources[0]
        assert s.source_category == "official_gov"
        assert isinstance(s.content_depth_score, int)
        assert s.extraction_suitability in ("high", "medium", "low")
        assert s.is_official is True

    def test_results_sorted_high_suitability_first(self, service):
        """High-suitability sources appear before low-suitability ones."""
        results = {
            "results": [
                {
                    "url": "https://some-random-blog.com/",
                    "title": "Blog",
                    "excerpts": ["Read more. Subscribe now. Contact us."],
                },
                {
                    "url": "https://labour.gov.ng/policies/",
                    "title": "Policies",
                    "excerpts": [
                        "Minimum wage shall be \u20a670,000. Section 3 requires "
                        "employers to comply within 30 days pursuant to Act 2024."
                    ],
                },
            ]
        }
        sources = service._convert_to_suggested_sources(results)
        suitability_order = {"high": 0, "medium": 1, "low": 2}
        assert (
            suitability_order[sources[0].extraction_suitability]
            <= suitability_order[sources[1].extraction_suitability]
        )

    def test_snippet_truncated_at_500_chars(self, service):
        """Snippets longer than 500 chars are truncated with ellipsis."""
        long_text = "a" * 600
        results = {
            "results": [
                {
                    "url": "https://example.gov/page",
                    "title": "Title",
                    "excerpts": [long_text],
                }
            ]
        }
        sources = service._convert_to_suggested_sources(results)
        assert len(sources[0].snippet) <= 503  # 500 + "..."
        assert sources[0].snippet.endswith("...")

    def test_empty_results_returns_empty_list(self, service):
        """Empty Parallel.ai results return an empty list."""
        assert service._convert_to_suggested_sources({"results": []}) == []


class TestBuildObjective:
    """Tests for _build_objective."""

    def test_jurisdiction_scoped_objective(self, service):
        """Objective includes jurisdiction name when provided."""
        obj = service._build_objective("minimum wage", "Nigeria")
        assert "Nigeria" in obj
        assert "minimum wage" in obj

    def test_global_objective_without_jurisdiction(self, service):
        """Objective works without jurisdiction context."""
        obj = service._build_objective("pension contribution rates", None)
        assert "pension contribution rates" in obj
        assert "Nigeria" not in obj

    def test_objective_requests_data_depth(self, service):
        """Objective explicitly asks for specific data pages over homepages."""
        obj = service._build_objective("employment rules", "Kenya")
        obj_lower = obj.lower()
        assert "homepage" in obj_lower or "navigation" in obj_lower or "homepage" in obj_lower
        assert any(
            kw in obj_lower for kw in ["rates", "thresholds", "tables", "data", "requirements"]
        )

    def test_objective_requests_authoritative_sources(self, service):
        """Objective mentions preferred authoritative source types."""
        obj = service._build_objective("corporate tax", None)
        obj_lower = obj.lower()
        assert any(kw in obj_lower for kw in ["government", "oecd", "pwc", "deloitte", "ey"])
