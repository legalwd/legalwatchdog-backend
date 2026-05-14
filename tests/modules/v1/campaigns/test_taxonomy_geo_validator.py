"""Tests for the TaxonomyGeoValidator — pure unit tests (no DB, no mocking)."""

import pytest

from app.api.core.config import settings
from app.api.modules.v1.campaigns.service.taxonomy_geo_validator import (
    TaxonomyGeoValidator,
)


@pytest.fixture
def validator():
    """Construct a TaxonomyGeoValidator instance."""
    return TaxonomyGeoValidator()


def _make_taxonomy(*country_nodes):
    """Build a minimal taxonomy dict from country node dicts."""
    return {"nodes": list(country_nodes)}


def _country_node(name, children=None):
    """Build a country-level node dict."""
    return {
        "name": name,
        "description": f"{name} regulations",
        "suggested_prompt": f"Extract {name} data",
        "suggested_search_queries": [f"{name} law"],
        "children": children or [],
    }


def _subdivision_node(name, children=None):
    """Build a subdivision-level node dict."""
    return {
        "name": name,
        "description": f"{name} regulations",
        "suggested_prompt": f"Extract {name} data",
        "suggested_search_queries": [f"{name} law"],
        "children": children or [],
    }


def _city_node(name):
    """Build a city-level node dict."""
    return {
        "name": name,
        "description": f"{name} regulations",
        "suggested_prompt": f"Extract {name} data",
        "suggested_search_queries": [f"{name} law"],
        "children": [],
    }


class TestValidateKnownCountries:
    """test_validate_known_countries — well-known countries resolve correctly."""

    def test_united_states_resolved(self, validator):
        taxonomy = _make_taxonomy(_country_node("United States"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["iso_code"] == "US"
        assert result.stats["countries_matched"] == 1
        assert result.stats["distinct_countries"] == 1

    def test_nigeria_resolved(self, validator):
        taxonomy = _make_taxonomy(_country_node("Nigeria"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["iso_code"] == "NG"

    def test_germany_resolved(self, validator):
        taxonomy = _make_taxonomy(_country_node("Germany"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["iso_code"] == "DE"


class TestNormalizeAliases:
    """test_normalize_aliases — common aliases resolve to official names."""

    def test_usa_alias(self, validator):
        taxonomy = _make_taxonomy(_country_node("USA"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["name"] == "United States"
        assert node["iso_code"] == "US"

    def test_uk_alias(self, validator):
        taxonomy = _make_taxonomy(_country_node("UK"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["name"] == "United Kingdom"
        assert node["iso_code"] == "GB"

    def test_uae_alias(self, validator):
        taxonomy = _make_taxonomy(_country_node("UAE"))
        result = validator.validate_and_normalize(taxonomy)
        node = result.normalized_taxonomy["nodes"][0]
        assert node["name"] == "United Arab Emirates"
        assert node["iso_code"] == "AE"


class TestFuzzyMatchTypo:
    """test_fuzzy_match_typo — close misspellings fuzzily resolve with a warning."""

    def test_californnia_typo(self, validator):
        taxonomy = _make_taxonomy(
            _country_node("United States", children=[_subdivision_node("Californnia")])
        )
        result = validator.validate_and_normalize(taxonomy)
        child = result.normalized_taxonomy["nodes"][0]["children"][0]
        assert child["name"] == "California"
        assert child["iso_code"] == "US-CA"
        assert any("Fuzzy" in w.issue or "fuzzy" in w.issue.lower() for w in result.warnings)


class TestFlagUnknownEntity:
    """test_flag_unknown_entity — fabricated names appear in warnings, NOT removed."""

    def test_north_zambonia_flagged(self, validator):
        taxonomy = _make_taxonomy(_country_node("North Zambonia"))
        result = validator.validate_and_normalize(taxonomy)
        assert result.normalized_taxonomy["nodes"][0]["name"] == "North Zambonia"
        assert any("North Zambonia" in w.node_name for w in result.warnings)
        assert result.stats["unrecognized_count"] >= 1


class TestIsoCodesAttached:
    """test_iso_codes_attached — ISO codes are correctly attached to nodes."""

    def test_us_code(self, validator):
        taxonomy = _make_taxonomy(_country_node("United States"))
        result = validator.validate_and_normalize(taxonomy)
        assert result.normalized_taxonomy["nodes"][0]["iso_code"] == "US"

    def test_nigeria_lagos_code(self, validator):
        taxonomy = _make_taxonomy(_country_node("Nigeria", children=[_subdivision_node("Lagos")]))
        result = validator.validate_and_normalize(taxonomy)
        child = result.normalized_taxonomy["nodes"][0]["children"][0]
        assert child["iso_code"] == "NG-LA"


class TestSubdivisionValidation:
    """test_subdivision_validation — subdivisions resolve under their parent country."""

    def test_lagos_under_nigeria(self, validator):
        taxonomy = _make_taxonomy(_country_node("Nigeria", children=[_subdivision_node("Lagos")]))
        result = validator.validate_and_normalize(taxonomy)
        child = result.normalized_taxonomy["nodes"][0]["children"][0]
        assert child["iso_code"] == "NG-LA"
        assert child["name"] == "Lagos"
        assert result.stats["subdivisions_matched"] >= 1

    def test_california_under_us(self, validator):
        taxonomy = _make_taxonomy(
            _country_node("United States", children=[_subdivision_node("California")])
        )
        result = validator.validate_and_normalize(taxonomy)
        child = result.normalized_taxonomy["nodes"][0]["children"][0]
        assert child["iso_code"] == "US-CA"
        assert child["name"] == "California"


class TestRegionalEntityExpansion:
    """Regional entities should expand into sovereign country nodes."""

    def test_european_union_expands_to_member_countries(self, validator):
        taxonomy = _make_taxonomy(
            _country_node(
                "European Union",
                children=[_country_node("Germany"), _country_node("France")],
            )
        )

        result = validator.validate_and_normalize(taxonomy)
        top_level_nodes = result.normalized_taxonomy["nodes"]
        top_level_names = {n["name"] for n in top_level_nodes}

        assert "European Union" not in top_level_names
        assert "Germany" in top_level_names
        assert "France" in top_level_names
        assert result.stats["regional_entities_expanded"] >= 1
        assert result.stats["distinct_countries"] >= 27
        assert any("expanded" in w.issue.lower() for w in result.warnings)

    def test_global_alias_expands_to_all_available_iso_countries(self, validator):
        taxonomy = _make_taxonomy(_country_node("Global"))

        result = validator.validate_and_normalize(taxonomy)
        top_level_names = {n["name"] for n in result.normalized_taxonomy["nodes"]}

        assert "Global" not in top_level_names
        assert "Nigeria" in top_level_names
        assert "United States" in top_level_names
        assert "Japan" in top_level_names
        assert result.stats["regional_entities_expanded"] >= 1
        assert result.stats["distinct_countries"] >= 200

    def test_african_union_expands_with_broad_coverage(self, validator):
        taxonomy = _make_taxonomy(_country_node("African Union"))

        result = validator.validate_and_normalize(taxonomy)
        top_level_names = {n["name"] for n in result.normalized_taxonomy["nodes"]}

        assert "African Union" not in top_level_names
        assert "Nigeria" in top_level_names
        assert "Kenya" in top_level_names
        assert "South Africa" in top_level_names
        assert result.stats["regional_entities_expanded"] >= 1


class TestExternalGeoEnrichment:
    """Optional external CSV enrichment should improve regional and subdivision matching."""

    def test_external_region_dataset_expands_continent_entity(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        countries_csv = tmp_path / "countries.csv"
        countries_csv.write_text(
            "iso2,name,region,subregion\n"
            "NG,Nigeria,Africa,Western Africa\n"
            "KE,Kenya,Africa,Eastern Africa\n"
            "ZA,South Africa,Africa,Southern Africa\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH",
            str(countries_csv),
        )
        TaxonomyGeoValidator._load_external_country_region_index.cache_clear()

        taxonomy = _make_taxonomy(_country_node("Africa"))
        result = validator.validate_and_normalize(taxonomy)
        top_level_names = {n["name"] for n in result.normalized_taxonomy["nodes"]}

        assert "Africa" not in top_level_names
        assert {"Nigeria", "Kenya", "South Africa"}.issubset(top_level_names)

    def test_external_subdivision_dataset_resolves_non_iso_variant(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        states_csv = tmp_path / "states.csv"
        states_csv.write_text(
            "name,country_code,iso2,type\nKaduna State Government,NG,NG-KD,state\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(settings, "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED", True)
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH",
            str(states_csv),
        )
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES",
            "state,province",
        )
        TaxonomyGeoValidator._load_external_subdivision_index.cache_clear()

        taxonomy = _make_taxonomy(
            _country_node("Nigeria", children=[_subdivision_node("Kaduna State Government")])
        )
        result = validator.validate_and_normalize(taxonomy)
        child = result.normalized_taxonomy["nodes"][0]["children"][0]

        assert child["name"] == "Kaduna State Government"
        assert child["iso_code"] == "NG-KD"
        assert any("external enrichment" in warning.issue for warning in result.warnings)


class TestExternalCityEnrichment:
    """Optional external CSV enrichment should improve city-level normalization."""

    def test_external_city_dataset_resolves_city_exact_match(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        cities_csv = tmp_path / "cities.csv"
        cities_csv.write_text(
            "name,state_code,country_code,state_name\nZaria,KD,NG,Kaduna\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(settings, "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED", True)
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH",
            str(cities_csv),
        )
        TaxonomyGeoValidator._load_external_city_index.cache_clear()

        taxonomy = _make_taxonomy(
            _country_node(
                "Nigeria",
                children=[_subdivision_node("Kaduna", children=[_city_node("Zaria")])],
            )
        )
        result = validator.validate_and_normalize(taxonomy)
        city = result.normalized_taxonomy["nodes"][0]["children"][0]["children"][0]

        assert city["name"] == "Zaria"
        assert city.get("iso_code") is None
        assert result.stats["cities_matched"] == 1
        assert any(
            "Resolved city using external enrichment" in warning.issue
            for warning in result.warnings
        )

    def test_external_city_dataset_resolves_city_with_state_constraint(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        cities_csv = tmp_path / "cities.csv"
        cities_csv.write_text(
            "name,state_code,country_code,state_name\n"
            "Springfield,MO,US,Missouri\n"
            "Springfield,IL,US,Illinois\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(settings, "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED", True)
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH",
            str(cities_csv),
        )
        TaxonomyGeoValidator._load_external_city_index.cache_clear()

        taxonomy = _make_taxonomy(
            _country_node(
                "United States",
                children=[_subdivision_node("Illinois", children=[_city_node("Springfield")])],
            )
        )
        result = validator.validate_and_normalize(taxonomy)
        city = result.normalized_taxonomy["nodes"][0]["children"][0]["children"][0]

        assert city["name"] == "Springfield"
        assert result.stats["cities_matched"] == 1
        assert any("state=IL" in warning.issue for warning in result.warnings)

    def test_external_city_dataset_fuzzy_match(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        cities_csv = tmp_path / "cities.csv"
        cities_csv.write_text(
            "name,state_code,country_code,state_name\nLagos,LA,NG,Lagos\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(settings, "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED", True)
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH",
            str(cities_csv),
        )
        TaxonomyGeoValidator._load_external_city_index.cache_clear()

        taxonomy = _make_taxonomy(
            _country_node(
                "Nigeria",
                children=[_subdivision_node("Lagos", children=[_city_node("Lagoss")])],
            )
        )
        result = validator.validate_and_normalize(taxonomy)
        city = result.normalized_taxonomy["nodes"][0]["children"][0]["children"][0]

        assert city["name"] == "Lagos"
        assert result.stats["cities_matched"] == 1
        assert any(
            "Fuzzy matched city via external enrichment" in warning.issue
            for warning in result.warnings
        )

    def test_city_enrichment_disabled_no_external_city_resolution(
        self,
        validator,
        tmp_path,
        monkeypatch,
    ):
        cities_csv = tmp_path / "cities.csv"
        cities_csv.write_text(
            "name,state_code,country_code,state_name\nEko Mega City,LA,NG,Lagos\n",
            encoding="utf-8",
        )

        monkeypatch.setattr(settings, "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED", False)
        monkeypatch.setattr(
            settings,
            "CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH",
            str(cities_csv),
        )
        TaxonomyGeoValidator._load_external_city_index.cache_clear()

        taxonomy = _make_taxonomy(
            _country_node(
                "Nigeria",
                children=[_subdivision_node("Lagos", children=[_city_node("Eko Mega City")])],
            )
        )
        result = validator.validate_and_normalize(taxonomy)
        city = result.normalized_taxonomy["nodes"][0]["children"][0]["children"][0]

        assert city["name"] == "Eko Mega City"
        assert result.stats["cities_matched"] == 0
        assert result.stats["unrecognized_count"] >= 1
