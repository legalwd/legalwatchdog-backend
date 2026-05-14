"""Taxonomy geo validator — ISO 3166 normalization for LLM-generated taxonomy trees.

Cross-references every node against canonical ISO 3166-1 (countries) and
ISO 3166-2 (subdivisions) data via the ``pycountry`` package.  Applies alias
resolution, fuzzy matching, and attaches ISO codes to validated nodes.
"""

import csv
import difflib
import logging
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import pycountry

from app.api.core.config import settings

logger = logging.getLogger("app")


COUNTRY_ALIASES: Dict[str, str] = {
    "USA": "United States",
    "US": "United States",
    "UK": "United Kingdom",
    "UAE": "United Arab Emirates",
    "South Korea": "Korea, Republic of",
    "North Korea": "Korea, Democratic People's Republic of",
    "Russia": "Russian Federation",
    "Iran": "Iran, Islamic Republic of",
    "Syria": "Syrian Arab Republic",
    "Taiwan": "Taiwan, Province of China",
    "Bolivia": "Bolivia, Plurinational State of",
    "Venezuela": "Venezuela, Bolivarian Republic of",
    "Tanzania": "Tanzania, United Republic of",
    "Vietnam": "Viet Nam",
    "Laos": "Lao People's Democratic Republic",
    "Czech Republic": "Czechia",
    "Ivory Coast": "Côte d'Ivoire",
    "Congo": "Congo, The Democratic Republic of the",
    "Palestine": "Palestine, State of",
    "Moldova": "Moldova, Republic of",
    "Macedonia": "North Macedonia",
}


def _normalize_geo_text(value: str) -> str:
    """Normalize geo strings for resilient matching across casing and punctuation."""
    if not value:
        return ""
    folded = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in folded if not unicodedata.combining(ch))
    lowered = without_marks.lower()
    cleaned = (
        lowered.replace("&", " and ")
        .replace("/", " ")
        .replace("-", " ")
        .replace("'", "")
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
    )
    return " ".join(cleaned.split())


COUNTRY_ALIAS_LOOKUP: Dict[str, str] = {
    _normalize_geo_text(alias): canonical for alias, canonical in COUNTRY_ALIASES.items()
}

FUZZY_THRESHOLD = 0.90


REGIONAL_ENTITY_MEMBERS: Dict[str, List[str]] = {
    "european union": [
        "Austria",
        "Belgium",
        "Bulgaria",
        "Croatia",
        "Cyprus",
        "Czechia",
        "Denmark",
        "Estonia",
        "Finland",
        "France",
        "Germany",
        "Greece",
        "Hungary",
        "Ireland",
        "Italy",
        "Latvia",
        "Lithuania",
        "Luxembourg",
        "Malta",
        "Netherlands",
        "Poland",
        "Portugal",
        "Romania",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Sweden",
    ],
    "eu": [
        "Austria",
        "Belgium",
        "Bulgaria",
        "Croatia",
        "Cyprus",
        "Czechia",
        "Denmark",
        "Estonia",
        "Finland",
        "France",
        "Germany",
        "Greece",
        "Hungary",
        "Ireland",
        "Italy",
        "Latvia",
        "Lithuania",
        "Luxembourg",
        "Malta",
        "Netherlands",
        "Poland",
        "Portugal",
        "Romania",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Sweden",
    ],
    "asean": [
        "Brunei Darussalam",
        "Cambodia",
        "Indonesia",
        "Lao People's Democratic Republic",
        "Malaysia",
        "Myanmar",
        "Philippines",
        "Singapore",
        "Thailand",
        "Viet Nam",
    ],
    "gcc": [
        "Bahrain",
        "Kuwait",
        "Oman",
        "Qatar",
        "Saudi Arabia",
        "United Arab Emirates",
    ],
    "mercosur": [
        "Argentina",
        "Bolivia, Plurinational State of",
        "Brazil",
        "Paraguay",
        "Uruguay",
    ],
    "african union": [
        "Algeria",
        "Angola",
        "Benin",
        "Botswana",
        "Burkina Faso",
        "Burundi",
        "Cabo Verde",
        "Cameroon",
        "Central African Republic",
        "Chad",
        "Comoros",
        "Congo",
        "Congo, The Democratic Republic of the",
        "Côte d'Ivoire",
        "Djibouti",
        "Egypt",
        "Equatorial Guinea",
        "Eritrea",
        "Eswatini",
        "Ethiopia",
        "Gabon",
        "Gambia",
        "Ghana",
        "Guinea",
        "Guinea-Bissau",
        "Kenya",
        "Lesotho",
        "Liberia",
        "Libya",
        "Madagascar",
        "Malawi",
        "Mali",
        "Mauritania",
        "Mauritius",
        "Morocco",
        "Mozambique",
        "Namibia",
        "Niger",
        "Nigeria",
        "Rwanda",
        "Sao Tome and Principe",
        "Senegal",
        "Seychelles",
        "Sierra Leone",
        "Somalia",
        "South Africa",
        "South Sudan",
        "Sudan",
        "Tanzania, United Republic of",
        "Togo",
        "Tunisia",
        "Uganda",
        "Zambia",
        "Zimbabwe",
    ],
    "au": [
        "Algeria",
        "Angola",
        "Benin",
        "Botswana",
        "Burkina Faso",
        "Burundi",
        "Cabo Verde",
        "Cameroon",
        "Central African Republic",
        "Chad",
        "Comoros",
        "Congo",
        "Congo, The Democratic Republic of the",
        "Côte d'Ivoire",
        "Djibouti",
        "Egypt",
        "Equatorial Guinea",
        "Eritrea",
        "Eswatini",
        "Ethiopia",
        "Gabon",
        "Gambia",
        "Ghana",
        "Guinea",
        "Guinea-Bissau",
        "Kenya",
        "Lesotho",
        "Liberia",
        "Libya",
        "Madagascar",
        "Malawi",
        "Mali",
        "Mauritania",
        "Mauritius",
        "Morocco",
        "Mozambique",
        "Namibia",
        "Niger",
        "Nigeria",
        "Rwanda",
        "Sao Tome and Principe",
        "Senegal",
        "Seychelles",
        "Sierra Leone",
        "Somalia",
        "South Africa",
        "South Sudan",
        "Sudan",
        "Tanzania, United Republic of",
        "Togo",
        "Tunisia",
        "Uganda",
        "Zambia",
        "Zimbabwe",
    ],
    "ecowas": [
        "Benin",
        "Burkina Faso",
        "Cabo Verde",
        "Côte d'Ivoire",
        "Gambia",
        "Ghana",
        "Guinea",
        "Guinea-Bissau",
        "Liberia",
        "Mali",
        "Niger",
        "Nigeria",
        "Senegal",
        "Sierra Leone",
        "Togo",
    ],
    "sadc": [
        "Angola",
        "Botswana",
        "Comoros",
        "Congo, The Democratic Republic of the",
        "Eswatini",
        "Lesotho",
        "Madagascar",
        "Malawi",
        "Mauritius",
        "Mozambique",
        "Namibia",
        "Seychelles",
        "South Africa",
        "Tanzania, United Republic of",
        "Zambia",
        "Zimbabwe",
    ],
    "east african community": [
        "Burundi",
        "Congo, The Democratic Republic of the",
        "Kenya",
        "Rwanda",
        "Somalia",
        "South Sudan",
        "Tanzania, United Republic of",
        "Uganda",
    ],
    "eac": [
        "Burundi",
        "Congo, The Democratic Republic of the",
        "Kenya",
        "Rwanda",
        "Somalia",
        "South Sudan",
        "Tanzania, United Republic of",
        "Uganda",
    ],
    "caricom": [
        "Antigua and Barbuda",
        "Bahamas",
        "Barbados",
        "Belize",
        "Dominica",
        "Grenada",
        "Guyana",
        "Haiti",
        "Jamaica",
        "Saint Kitts and Nevis",
        "Saint Lucia",
        "Saint Vincent and the Grenadines",
        "Suriname",
        "Trinidad and Tobago",
    ],
    "usmca": ["Canada", "Mexico", "United States"],
    "nafta": ["Canada", "Mexico", "United States"],
    "saarc": [
        "Afghanistan",
        "Bangladesh",
        "Bhutan",
        "India",
        "Maldives",
        "Nepal",
        "Pakistan",
        "Sri Lanka",
    ],
    "efta": ["Iceland", "Liechtenstein", "Norway", "Switzerland"],
    "g20": [
        "Argentina",
        "Australia",
        "Brazil",
        "Canada",
        "China",
        "France",
        "Germany",
        "India",
        "Indonesia",
        "Italy",
        "Japan",
        "Korea, Republic of",
        "Mexico",
        "Russian Federation",
        "Saudi Arabia",
        "South Africa",
        "Türkiye",
        "United Kingdom",
        "United States",
    ],
}


GLOBAL_ENTITY_ALIASES: Set[str] = {
    "global",
    "global market",
    "global markets",
    "global coverage",
    "international",
    "international market",
    "international markets",
    "world",
    "worldwide",
    "all countries",
    "all nations",
    "entire world",
    "united nations",
    "un",
}


@dataclass
class GeoWarningEntry:
    """A single geo-validation warning."""

    node_name: str
    depth: int
    issue: str
    original_name: Optional[str] = None
    resolved_name: Optional[str] = None
    iso_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "node_name": self.node_name,
            "depth": self.depth,
            "issue": self.issue,
            "original_name": self.original_name,
            "resolved_name": self.resolved_name,
            "iso_code": self.iso_code,
        }


@dataclass
class GeoValidationResult:
    """Result of geo-validation and normalization.

    Attributes:
        normalized_taxonomy: Taxonomy dict with corrected names and ISO codes.
        warnings: List of warnings (fuzzy matches, unrecognized entities).
        stats: Summary counts of matched and unrecognized entities.
    """

    normalized_taxonomy: Dict[str, Any] = field(default_factory=dict)
    warnings: List[GeoWarningEntry] = field(default_factory=list)
    stats: Dict[str, int] = field(
        default_factory=lambda: {
            "countries_matched": 0,
            "subdivisions_matched": 0,
            "cities_matched": 0,
            "unrecognized_count": 0,
            "unrecognized_top_level": 0,
            "regional_entities_expanded": 0,
            "distinct_countries": 0,
        }
    )


class TaxonomyGeoValidator:
    """Validates and normalizes LLM-generated taxonomy against ISO 3166.

    Resolution chain per node:
        1. Exact match against pycountry
        2. Alias lookup from ``COUNTRY_ALIASES``
        3. Fuzzy match (>90% via ``difflib.SequenceMatcher``)
        4. Top-level regional entities may be expanded to member countries
        5. Unresolved → flagged in warnings, kept as-is
    """

    @staticmethod
    @lru_cache(maxsize=1)
    def _all_iso_country_names() -> List[str]:
        """Return canonical country names from pycountry."""
        return sorted({country.name for country in pycountry.countries})

    @staticmethod
    def _resolve_csv_path(csv_path: str) -> Optional[Path]:
        """Resolve enrichment CSV path across absolute and repo-relative forms."""
        if not csv_path:
            return None

        raw_path = Path(csv_path)
        candidates: List[Path] = [raw_path]

        trimmed = csv_path.lstrip("/\\")
        if trimmed and trimmed != csv_path:
            candidates.append(Path.cwd() / trimmed)

        if not raw_path.is_absolute():
            candidates.append(Path.cwd() / raw_path)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_external_country_region_index(csv_path: str) -> Dict[str, List[str]]:
        """Build region/subregion -> country name index from optional countries CSV."""
        if not csv_path:
            return {}

        path = TaxonomyGeoValidator._resolve_csv_path(csv_path)
        if path is None:
            logger.warning(
                "Countries CSV path not found for geo expansion: %s (cwd=%s)",
                csv_path,
                Path.cwd(),
            )
            return {}

        index: Dict[str, Set[str]] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                country_code = (
                    (row.get("iso2") or "").strip()
                    or (row.get("country_code") or "").strip()
                    or (row.get("countryCode") or "").strip()
                ).upper()
                if len(country_code) != 2:
                    continue

                country_obj = pycountry.countries.get(alpha_2=country_code)
                if not country_obj:
                    continue

                for region_field in ("region", "subregion", "region_name", "sub_region"):
                    key = _normalize_geo_text((row.get(region_field) or "").strip())
                    if not key:
                        continue
                    index.setdefault(key, set()).add(country_obj.name)

        return {key: sorted(values) for key, values in index.items()}

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_external_subdivision_index(
        csv_path: str,
        allowed_types_csv: str,
    ) -> Dict[str, List[Dict[str, str]]]:
        """Build country -> subdivision index from optional states/provinces CSV."""
        if not csv_path:
            return {}

        path = TaxonomyGeoValidator._resolve_csv_path(csv_path)
        if path is None:
            logger.warning(
                "Subdivision CSV path not found for geo enrichment: %s (cwd=%s)",
                csv_path,
                Path.cwd(),
            )
            return {}

        allowed_types = {
            _normalize_geo_text(raw_type)
            for raw_type in allowed_types_csv.split(",")
            if _normalize_geo_text(raw_type)
        }
        index: Dict[str, List[Dict[str, str]]] = {}

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                country_code = (
                    (row.get("country_code") or "").strip()
                    or (row.get("countryCode") or "").strip()
                    or (row.get("iso2_country") or "").strip()
                ).upper()
                subdivision_name = (
                    (row.get("name") or "").strip()
                    or (row.get("state_name") or "").strip()
                    or (row.get("subdivision_name") or "").strip()
                )
                subdivision_iso = (
                    (row.get("iso2") or "").strip()
                    or (row.get("iso_code") or "").strip()
                    or (row.get("code") or "").strip()
                )
                subdivision_type = _normalize_geo_text((row.get("type") or "").strip())

                if len(country_code) != 2 or not subdivision_name or not subdivision_iso:
                    continue

                if allowed_types and subdivision_type and subdivision_type not in allowed_types:
                    continue

                normalized_name = _normalize_geo_text(subdivision_name)
                if not normalized_name:
                    continue

                entry = {
                    "name": subdivision_name,
                    "iso_code": subdivision_iso,
                    "normalized_name": normalized_name,
                }
                existing = index.setdefault(country_code, [])
                if any(
                    e["iso_code"] == entry["iso_code"]
                    and e["normalized_name"] == entry["normalized_name"]
                    for e in existing
                ):
                    continue
                existing.append(entry)

        return index

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_external_city_index(csv_path: str) -> Dict[str, List[Dict[str, str]]]:
        """Build country -> city index from optional city enrichment CSV."""
        if not csv_path:
            return {}

        path = TaxonomyGeoValidator._resolve_csv_path(csv_path)
        if path is None:
            logger.warning(
                "City CSV path not found for geo enrichment: %s (cwd=%s)",
                csv_path,
                Path.cwd(),
            )
            return {}

        index: Dict[str, List[Dict[str, str]]] = {}
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                country_code = (
                    (row.get("country_code") or "").strip()
                    or (row.get("countryCode") or "").strip()
                    or (row.get("iso2_country") or "").strip()
                ).upper()
                city_name = (
                    (row.get("name") or "").strip()
                    or (row.get("city_name") or "").strip()
                    or (row.get("city") or "").strip()
                )
                state_code = (
                    (row.get("state_code") or "").strip()
                    or (row.get("stateCode") or "").strip()
                    or (row.get("iso2") or "").strip()
                ).upper()
                state_name = (
                    (row.get("state_name") or "").strip()
                    or (row.get("state") or "").strip()
                    or (row.get("subdivision_name") or "").strip()
                )

                if len(country_code) != 2 or not city_name:
                    continue

                normalized_name = _normalize_geo_text(city_name)
                if not normalized_name:
                    continue

                entry = {
                    "name": city_name,
                    "normalized_name": normalized_name,
                    "state_code": state_code,
                    "state_name": state_name,
                }
                existing = index.setdefault(country_code, [])
                if any(
                    e["normalized_name"] == entry["normalized_name"]
                    and e["state_code"] == entry["state_code"]
                    for e in existing
                ):
                    continue
                existing.append(entry)

        for country_code, cities in index.items():
            index[country_code] = sorted(cities, key=lambda c: (c["state_code"], c["name"]))

        return index

    def validate_and_normalize(self, taxonomy: Dict[str, Any]) -> GeoValidationResult:
        """Cross-reference taxonomy nodes against ISO 3166 data.

        Args:
            taxonomy: Taxonomy dict with ``nodes`` key containing the tree.

        Returns:
            GeoValidationResult with normalized tree, warnings, and stats.
        """
        result = GeoValidationResult()
        nodes = taxonomy.get("nodes", [])

        normalized_nodes: List[Dict[str, Any]] = []
        seen_top_level: set[str] = set()
        for node in nodes:
            regional_members = self._resolve_regional_entity_members(node.get("name", ""))
            if not regional_members:
                regional_members = self._resolve_external_region_members(node.get("name", ""))
            if regional_members and settings.CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES:
                result.stats["regional_entities_expanded"] += 1
                result.warnings.append(
                    GeoWarningEntry(
                        node_name=node.get("name", ""),
                        depth=1,
                        issue=(
                            f"Regional entity '{node.get('name', '')}' expanded to "
                            f"{len(regional_members)} member countries"
                        ),
                    )
                )
                for member_country in regional_members:
                    expanded_member_node = self._build_regional_member_node(node, member_country)
                    normalized_member = self._normalize_node(
                        node=expanded_member_node,
                        depth=1,
                        parent_country_code=None,
                        parent_subdivision_code=None,
                        result=result,
                    )
                    self._append_unique_top_level(
                        normalized_member,
                        normalized_nodes,
                        seen_top_level,
                        result,
                    )
                continue

            normalized_node = self._normalize_node(
                node=node,
                depth=1,
                parent_country_code=None,
                parent_subdivision_code=None,
                result=result,
            )
            self._append_unique_top_level(
                normalized_node,
                normalized_nodes,
                seen_top_level,
                result,
            )

        result.stats["distinct_countries"] = len(seen_top_level)
        result.normalized_taxonomy = {"nodes": normalized_nodes}
        return result

    @staticmethod
    def _append_unique_top_level(
        node: Dict[str, Any],
        destination: List[Dict[str, Any]],
        seen: set[str],
        result: GeoValidationResult,
    ) -> None:
        """Append top-level country node if not already present."""
        node_name = (node.get("name") or "").strip()
        if not node_name:
            return
        key = node_name.lower()
        if key in seen:
            result.warnings.append(
                GeoWarningEntry(
                    node_name=node_name,
                    depth=1,
                    issue=f"Duplicate top-level country removed after normalization: '{node_name}'",
                )
            )
            return
        seen.add(key)
        destination.append(node)

    def _resolve_regional_entity_members(self, name: str) -> Optional[List[str]]:
        """Resolve a top-level regional entity into member country names."""
        normalized = _normalize_geo_text(name)
        if not normalized:
            return None

        if (
            settings.CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES
            and normalized in GLOBAL_ENTITY_ALIASES
        ):
            return self._all_iso_country_names()

        return REGIONAL_ENTITY_MEMBERS.get(normalized)

    def _resolve_external_region_members(self, name: str) -> Optional[List[str]]:
        """Resolve region-like names (e.g., Africa, Europe) via optional countries CSV."""
        csv_path = settings.CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH
        if not csv_path:
            return None

        region_index = self._load_external_country_region_index(csv_path)
        if not region_index:
            return None

        key = _normalize_geo_text(name)
        if not key:
            return None

        direct = region_index.get(key)
        if direct:
            return direct

        if key.endswith(" countries"):
            narrowed = key[: -len(" countries")].strip()
            if narrowed:
                return region_index.get(narrowed)

        return None

    @staticmethod
    def _build_regional_member_node(
        region_node: Dict[str, Any],
        country_name: str,
    ) -> Dict[str, Any]:
        """Build a synthetic country node from a regional entity template.

        Existing child nodes under the region are reused when they match a
        member country; otherwise a deterministic fallback country node is built.
        """
        region_children = region_node.get("children") or []
        child_by_name = {
            str(child.get("name", "")).strip().lower(): child
            for child in region_children
            if isinstance(child, dict)
        }
        existing = child_by_name.get(country_name.strip().lower())
        if existing:
            return dict(existing)

        template_prompt = str(region_node.get("suggested_prompt") or "").strip()
        template_description = str(region_node.get("description") or "").strip()
        template_queries = region_node.get("suggested_search_queries") or []

        derived_prompt = (
            f"{template_prompt} for {country_name}"
            if template_prompt
            else f"Extract regulations for {country_name}"
        )
        derived_description = (
            f"{country_name}: {template_description}"
            if template_description
            else f"Regulatory coverage for {country_name}"
        )
        derived_queries = [
            f"{country_name} {str(q).strip()}" for q in template_queries[:3] if str(q).strip()
        ]
        if not derived_queries:
            derived_queries = [f"{country_name} regulations"]

        return {
            "name": country_name,
            "description": derived_description,
            "suggested_prompt": derived_prompt,
            "suggested_search_queries": list(dict.fromkeys(derived_queries)),
            "children": [],
        }

    def _normalize_node(
        self,
        node: Dict[str, Any],
        depth: int,
        parent_country_code: Optional[str],
        parent_subdivision_code: Optional[str],
        result: GeoValidationResult,
    ) -> Dict[str, Any]:
        """Normalize a single node and recurse into children.

        Args:
            node: The node dict to normalize.
            depth: Current tree depth (1=country, 2=state, etc.).
            parent_country_code: ISO alpha-2 code of the parent country.
            parent_subdivision_code: ISO 3166-2 style code for parent subdivision.
            result: GeoValidationResult to populate.

        Returns:
            Normalized copy of the node dict.
        """
        normalized = dict(node)
        name = node.get("name", "")
        current_subdivision_code = parent_subdivision_code

        if depth == 1:
            resolved = self._resolve_country(name)
            if resolved:
                normalized["name"] = resolved["name"]
                normalized["iso_code"] = resolved["iso_code"]
                result.stats["countries_matched"] += 1
                current_subdivision_code = None

                if resolved.get("warning"):
                    result.warnings.append(
                        GeoWarningEntry(
                            node_name=name,
                            depth=depth,
                            issue=resolved["warning"],
                            original_name=name,
                            resolved_name=resolved["name"],
                            iso_code=resolved["iso_code"],
                        )
                    )

                country_code = resolved["iso_code"]
            else:
                result.stats["unrecognized_count"] += 1
                result.stats["unrecognized_top_level"] += 1
                result.warnings.append(
                    GeoWarningEntry(
                        node_name=name,
                        depth=depth,
                        issue=f"Unrecognized country: '{name}' — no ISO 3166-1 match found",
                    )
                )
                country_code = parent_country_code
        elif depth == 2:
            country_code = parent_country_code
            if parent_country_code:
                resolved = self._resolve_subdivision(name, parent_country_code)
                if resolved:
                    normalized["name"] = resolved["name"]
                    normalized["iso_code"] = resolved["iso_code"]
                    result.stats["subdivisions_matched"] += 1
                    current_subdivision_code = resolved["iso_code"]

                    if resolved.get("warning"):
                        result.warnings.append(
                            GeoWarningEntry(
                                node_name=name,
                                depth=depth,
                                issue=resolved["warning"],
                                original_name=name,
                                resolved_name=resolved["name"],
                                iso_code=resolved["iso_code"],
                            )
                        )
                else:
                    result.stats["unrecognized_count"] += 1
                    result.warnings.append(
                        GeoWarningEntry(
                            node_name=name,
                            depth=depth,
                            issue=(
                                f"Unrecognized subdivision: '{name}' under "
                                f"country '{parent_country_code}'"
                            ),
                        )
                    )
            else:
                result.stats["unrecognized_count"] += 1
                result.warnings.append(
                    GeoWarningEntry(
                        node_name=name,
                        depth=depth,
                        issue=(
                            f"Cannot validate subdivision '{name}' — "
                            f"parent country was not resolved"
                        ),
                    )
                )
        else:
            country_code = parent_country_code
            if parent_country_code:
                city_resolved = self._resolve_external_city(
                    name=name,
                    country_code=parent_country_code,
                    parent_subdivision_code=parent_subdivision_code,
                )
                if city_resolved:
                    normalized["name"] = city_resolved["name"]
                    result.stats["cities_matched"] += 1

                    if city_resolved.get("warning"):
                        result.warnings.append(
                            GeoWarningEntry(
                                node_name=name,
                                depth=depth,
                                issue=city_resolved["warning"],
                                original_name=name,
                                resolved_name=city_resolved["name"],
                                iso_code=None,
                            )
                        )
                else:
                    resolved = self._resolve_subdivision(name, parent_country_code)
                    if resolved:
                        normalized["name"] = resolved["name"]
                        normalized["iso_code"] = resolved["iso_code"]
                        result.stats["subdivisions_matched"] += 1
                        current_subdivision_code = resolved["iso_code"]

                        if resolved.get("warning"):
                            result.warnings.append(
                                GeoWarningEntry(
                                    node_name=name,
                                    depth=depth,
                                    issue=resolved["warning"],
                                    original_name=name,
                                    resolved_name=resolved["name"],
                                    iso_code=resolved["iso_code"],
                                )
                            )
                    else:
                        result.stats["unrecognized_count"] += 1
                        result.warnings.append(
                            GeoWarningEntry(
                                node_name=name,
                                depth=depth,
                                issue=(
                                    f"Unrecognized city: '{name}' under country "
                                    f"'{parent_country_code}'"
                                ),
                            )
                        )
            else:
                result.stats["unrecognized_count"] += 1
                result.warnings.append(
                    GeoWarningEntry(
                        node_name=name,
                        depth=depth,
                        issue=(f"Cannot validate city '{name}' — parent country was not resolved"),
                    )
                )

        children = node.get("children", [])
        if children:
            normalized["children"] = [
                self._normalize_node(
                    node=child,
                    depth=depth + 1,
                    parent_country_code=country_code,
                    parent_subdivision_code=current_subdivision_code,
                    result=result,
                )
                for child in children
            ]

        return normalized

    def _resolve_country(self, name: str) -> Optional[Dict[str, Any]]:
        """Match a country name against ISO 3166-1.

        Resolution chain: exact → alias → fuzzy (>90%).

        Args:
            name: The country name to resolve.

        Returns:
            Dict with ``name``, ``iso_code``, and optional ``warning``,
            or None if no match found.
        """
        try:
            country = pycountry.countries.lookup(name)
            return {"name": country.name, "iso_code": country.alpha_2}
        except LookupError:
            pass

        alias_target = COUNTRY_ALIAS_LOOKUP.get(_normalize_geo_text(name))
        if alias_target:
            try:
                country = pycountry.countries.lookup(alias_target)
                return {
                    "name": country.name,
                    "iso_code": country.alpha_2,
                    "warning": f"Alias resolved: '{name}' → '{country.name}'",
                }
            except LookupError:
                pass

        all_countries = list(pycountry.countries)
        country_names = [c.name for c in all_countries]
        best_match = difflib.get_close_matches(name, country_names, n=1, cutoff=FUZZY_THRESHOLD)
        if best_match:
            matched_name = best_match[0]
            country = pycountry.countries.lookup(matched_name)
            return {
                "name": country.name,
                "iso_code": country.alpha_2,
                "warning": (
                    f"Fuzzy matched: '{name}' → '{country.name}' "
                    f"(similarity >{FUZZY_THRESHOLD:.0%})"
                ),
            }

        return None

    @staticmethod
    @lru_cache(maxsize=300)
    def _get_subdivisions_for_country(country_code: str) -> List[Any]:
        """Get subdivisions for a specific country, cached for performance.

        Args:
            country_code: ISO alpha-2 of the parent country.

        Returns:
            List of pycountry subdivision objects.
        """
        return [s for s in pycountry.subdivisions if s.country_code == country_code]

    def _resolve_external_subdivision(
        self,
        name: str,
        country_code: str,
    ) -> Optional[Dict[str, Any]]:
        """Resolve subdivisions using optional external enrichment CSV."""
        if not settings.CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED:
            return None

        csv_path = settings.CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH
        if not csv_path:
            return None

        enrichment_index = self._load_external_subdivision_index(
            csv_path,
            settings.CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES,
        )
        country_subdivisions = enrichment_index.get(country_code, [])
        if not country_subdivisions:
            return None

        normalized_name = _normalize_geo_text(name)
        exact_match = next(
            (
                entry
                for entry in country_subdivisions
                if entry["normalized_name"] == normalized_name
            ),
            None,
        )
        if exact_match:
            return {
                "name": exact_match["name"],
                "iso_code": exact_match["iso_code"],
                "warning": (
                    f"Resolved subdivision using external enrichment: '{name}' "
                    f"→ '{exact_match['name']}' ({exact_match['iso_code']})"
                ),
            }

        normalized_candidates = [entry["normalized_name"] for entry in country_subdivisions]
        best_match = difflib.get_close_matches(
            normalized_name,
            normalized_candidates,
            n=1,
            cutoff=FUZZY_THRESHOLD,
        )
        if not best_match:
            return None

        matched = next(
            entry for entry in country_subdivisions if entry["normalized_name"] == best_match[0]
        )
        return {
            "name": matched["name"],
            "iso_code": matched["iso_code"],
            "warning": (
                f"Fuzzy matched subdivision via external enrichment: '{name}' "
                f"→ '{matched['name']}' ({matched['iso_code']})"
            ),
        }

    @staticmethod
    def _extract_state_segment(subdivision_code: Optional[str]) -> str:
        """Extract state-like segment from a subdivision ISO code (e.g., US-CA -> CA)."""
        if not subdivision_code:
            return ""
        if "-" not in subdivision_code:
            return subdivision_code.upper().strip()
        _, state_segment = subdivision_code.split("-", 1)
        return state_segment.upper().strip()

    def _resolve_external_city(
        self,
        name: str,
        country_code: str,
        parent_subdivision_code: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Resolve city names using optional external city enrichment CSV."""
        if not settings.CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED:
            return None

        csv_path = settings.CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH
        if not csv_path:
            return None

        city_index = self._load_external_city_index(csv_path)
        country_cities = city_index.get(country_code, [])
        if not country_cities:
            return None

        normalized_name = _normalize_geo_text(name)
        if not normalized_name:
            return None

        expected_state_code = self._extract_state_segment(parent_subdivision_code)
        scoped_candidates = [
            city
            for city in country_cities
            if expected_state_code and city["state_code"] == expected_state_code
        ]

        candidate_groups = (
            [scoped_candidates, country_cities] if scoped_candidates else [country_cities]
        )
        for candidates in candidate_groups:
            exact_match = next(
                (city for city in candidates if city["normalized_name"] == normalized_name),
                None,
            )
            if exact_match:
                return {
                    "name": exact_match["name"],
                    "warning": (
                        f"Resolved city using external enrichment: '{name}' → "
                        f"'{exact_match['name']}' (country={country_code}, "
                        f"state={exact_match['state_code'] or 'n/a'})"
                    ),
                }

            normalized_candidates = [city["normalized_name"] for city in candidates]
            best_match = difflib.get_close_matches(
                normalized_name,
                normalized_candidates,
                n=1,
                cutoff=FUZZY_THRESHOLD,
            )
            if not best_match:
                continue

            matched = next(city for city in candidates if city["normalized_name"] == best_match[0])
            return {
                "name": matched["name"],
                "warning": (
                    f"Fuzzy matched city via external enrichment: '{name}' → "
                    f"'{matched['name']}' (country={country_code}, "
                    f"state={matched['state_code'] or 'n/a'})"
                ),
            }

        return None

    def _resolve_subdivision(self, name: str, country_code: str) -> Optional[Dict[str, Any]]:
        """Match a subdivision name against ISO 3166-2 for a given country.

        Resolution chain: exact → fuzzy (>90%).

        Args:
            name: The subdivision name to resolve.
            country_code: ISO alpha-2 country code of the parent.

        Returns:
            Dict with ``name``, ``iso_code``, and optional ``warning``,
            or None if no match found.
        """
        subdivisions = self._get_subdivisions_for_country(country_code)
        if not subdivisions:
            return None
        for sub in subdivisions:
            if sub.name.lower() == name.lower():
                return {"name": sub.name, "iso_code": sub.code}

        sub_names = [s.name for s in subdivisions]
        best_match = difflib.get_close_matches(name, sub_names, n=1, cutoff=FUZZY_THRESHOLD)
        if best_match:
            matched_name = best_match[0]
            matched_sub = next(s for s in subdivisions if s.name == matched_name)
            return {
                "name": matched_sub.name,
                "iso_code": matched_sub.code,
                "warning": (
                    f"Fuzzy matched subdivision: '{name}' → '{matched_sub.name}' "
                    f"({matched_sub.code})"
                ),
            }

        external_match = self._resolve_external_subdivision(name, country_code)
        if external_match:
            return external_match

        return None
