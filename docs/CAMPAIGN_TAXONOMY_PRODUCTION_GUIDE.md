# Campaign Taxonomy Production Guide

This guide explains what to set in production for campaign taxonomy generation and how the runtime behaves.

Related implementation docs:

- [docs/CAMPAIGN_TAXONOMY_PHASE1_IMPLEMENTATION.md](docs/CAMPAIGN_TAXONOMY_PHASE1_IMPLEMENTATION.md)
- [docs/CAMPAIGN_TAXONOMY_PHASE2_IMPLEMENTATION.md](docs/CAMPAIGN_TAXONOMY_PHASE2_IMPLEMENTATION.md)

## Goal

Production taxonomy generation should be:

- Globally broad (not biased to a few countries)
- Deterministic under failure (truncation and low coverage fail fast)
- Cost-controlled (bounded token and expansion limits)
- Observable (coverage and normalization stats exposed in responses/snapshots)

## How It Works

At a high level, generation runs in this order:

1. Initial LLM generation produces taxonomy nodes.
2. Structural validation checks schema shape and budget fit.
3. Geo normalization resolves countries/subdivisions to ISO data.
4. Regional/global entities (for example EU, Global) may expand to country nodes.
5. Coverage gate checks minimum distinct-country count for global campaigns.
6. If enabled and coverage is low, expansion passes run to add missing countries.
7. Balanced trimming keeps breadth while respecting `max_jurisdictions`.
8. Final taxonomy and geo stats are persisted.

Key code locations:

- [app/api/core/config.py](app/api/core/config.py)
- [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](app/api/modules/v1/campaigns/service/taxonomy_generation_service.py)
- [app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py](app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py)
- [app/api/modules/v1/campaigns/routes/taxonomy_routes.py](app/api/modules/v1/campaigns/routes/taxonomy_routes.py)

## Production Environment Variables

Set these in production environment configuration.

### Core Reliability

- `CAMPAIGN_TAXONOMY_MAX_TOKENS`: Max tokens for initial generation.
- `CAMPAIGN_TAXONOMY_TEMPERATURE`: Sampling temperature for taxonomy generation.
- `CAMPAIGN_TAXONOMY_STRICT_TRUNCATION`: If `true`, truncated model output fails the run.

Recommended production values:

- `CAMPAIGN_TAXONOMY_MAX_TOKENS=24000`
- `CAMPAIGN_TAXONOMY_TEMPERATURE=0.3`
- `CAMPAIGN_TAXONOMY_STRICT_TRUNCATION=true`

### Global Coverage Gates

- `CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE`: Enforce minimum breadth for COUNTRY/STATE campaigns.
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY`: Required distinct countries for COUNTRY depth.
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE`: Required distinct countries for STATE depth.

Recommended production values:

- `CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE=true`
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY=180`
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE=180`

### Region and Global Entity Expansion

- `CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES`: Expand top-level regional entities to member countries.
- `CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES`: Expand global aliases like `Global`, `World`, `All Countries`.

Recommended production values:

- `CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES=true`
- `CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES=true`

### Iterative Expansion (Coverage Recovery)

- `CAMPAIGN_TAXONOMY_EXPANSION_ENABLED`: Enables follow-up passes when coverage is low.
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES`: Maximum number of recovery passes.
- `CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE`: Countries requested per pass.
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS`: Token budget per expansion pass.

Recommended production values:

- `CAMPAIGN_TAXONOMY_EXPANSION_ENABLED=true`
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES=2`
- `CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE=40`
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS=12000`

### Optional External Enrichment (Recommended for Maximum Breadth)

- `CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH`: Path to countries CSV containing `region`/`subregion`.
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED`: Enables subdivision fallback from external CSV.
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH`: Path to subdivisions/states CSV.
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES`: Comma-separated allowed subdivision types.
- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED`: Enables city-name normalization fallback from external CSV.
- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH`: Path to city CSV used for depth-3 normalization.

Recommended production values:

- `CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH=/opt/data/geo/countries.csv`
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED=true`
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH=/opt/data/geo/states.csv`
- `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES=state,province,region,county,district,governorate,prefecture,municipality,canton,department,territory,union territory`
- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED=true`
- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH=/opt/data/geo/cities.csv`

## Production Starter Template

Use this as a baseline in production:

```env
# Generation reliability
CAMPAIGN_TAXONOMY_MAX_TOKENS=24000
CAMPAIGN_TAXONOMY_TEMPERATURE=0.3
CAMPAIGN_TAXONOMY_STRICT_TRUNCATION=true

# Breadth enforcement
CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE=true
CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY=180
CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE=180

# Region/global expansion
CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES=true
CAMPAIGN_TAXONOMY_EXPAND_GLOBAL_ENTITIES=true

# Coverage recovery passes
CAMPAIGN_TAXONOMY_EXPANSION_ENABLED=true
CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES=2
CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE=40
CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS=12000

# Optional external enrichment
CAMPAIGN_TAXONOMY_REGION_DATASET_COUNTRIES_CSV_PATH=/opt/data/geo/countries.csv
CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ENABLED=true
CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_CSV_PATH=/opt/data/geo/states.csv
CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES=state,province,region,county,district,governorate,prefecture,municipality,canton,department,territory,union territory
CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED=true
CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH=/opt/data/geo/cities.csv
```

## Choosing Safe Values by Campaign Depth

### COUNTRY depth

- Keep global coverage enforcement on.
- Keep country minimum at `>= 180` for global SEO quality.
- Expansion passes should remain enabled.

### STATE depth

- Keep global coverage enforcement on.
- Keep country minimum at `>= 180`.
- Use external subdivision enrichment to improve state/province resolution.

### CITY depth

- Global gate is less applicable than COUNTRY/STATE breadth.
- Keep strict truncation and balanced trimming on.
- Enable city enrichment CSV to improve city canonicalization and typo tolerance.
- Consider lowering expansion aggressiveness if cost spikes.

## Campaign Creation Payloads for Depth Testing

Use the following request bodies to test campaign creation and downstream taxonomy generation across
all supported depths.

Endpoint:

- `POST /api/v1/campaigns`

Requirements:

- Caller must be a superadmin.
- `organization_id` must be a valid UUID that exists.
- Enum values are strict: `target_depth` must be `COUNTRY`, `STATE`, or `CITY`.
- Enum values are strict: `monitor_backend` must be `CELERY_BEAT`.

### COUNTRY depth payload

Purpose: Validate global breadth and country-level SEO page generation.

```json
{
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"name": "Global SEO Compliance - Country Depth",
	"industry": "Human Resources",
	"domain_description": "Generate SEO pages for labor and employment regulations by country.",
	"project_id": null,
	"target_depth": "COUNTRY",
	"monitor_backend": "CELERY_BEAT",
	"monitor_cadence": "0 9 * * 1",
	"sources_per_jurisdiction": 5,
	"max_jurisdictions": 15000
}
```

### STATE depth payload

Purpose: Validate country coverage plus state/province normalization quality.

```json
{
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"name": "Global SEO Compliance - State Depth",
	"industry": "Human Resources",
	"domain_description": "Generate SEO pages for labor and compliance rules by state and province.",
	"project_id": null,
	"target_depth": "STATE",
	"monitor_backend": "CELERY_BEAT",
	"monitor_cadence": "0 10 * * 1",
	"sources_per_jurisdiction": 5,
	"max_jurisdictions": 15000
}
```

### CITY depth payload

Purpose: Validate city-level enrichment and hierarchical country -> state -> city mapping quality.

```json
{
	"organization_id": "11111111-1111-1111-1111-111111111111",
	"name": "Global SEO Compliance - City Depth",
	"industry": "Human Resources",
	"domain_description": "Generate SEO pages for compliance insights at city level under state and country hierarchy.",
	"project_id": null,
	"target_depth": "CITY",
	"monitor_backend": "CELERY_BEAT",
	"monitor_cadence": "0 11 * * 1",
	"sources_per_jurisdiction": 5,
	"max_jurisdictions": 15000
}
```

### How to Evaluate Each Test Run

After campaign creation, run taxonomy generation and verify:

1. Structure quality: nodes are valid for the selected depth.
2. Coverage quality: `distinct_countries` and `countries_matched` are healthy for global campaigns.
3. Subdivision quality: `subdivisions_matched` improves for `STATE` depth.
4. City quality: `cities_matched` is non-trivial for `CITY` depth and warnings remain bounded.
5. Noise control: `unrecognized_count` and `unrecognized_top_level` remain acceptable.

If `CITY` quality is weak, confirm:

- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_ENABLED=true`
- `CAMPAIGN_TAXONOMY_CITY_ENRICHMENT_CSV_PATH` points to the intended city dataset
- city dataset columns and naming conventions match your expected input variants

## Expected Failure Modes (And Why They Are Good)

The pipeline may intentionally fail when:

- LLM output is truncated and strict truncation is enabled.
- Distinct-country coverage is below configured minimum.

These are protective failures that prevent low-quality global taxonomy from being promoted.

## Observability Checklist

Check these signals after generation:

- `distinct_countries`
- `countries_matched`
- `subdivisions_matched`
- `cities_matched`
- `unrecognized_count`
- `unrecognized_top_level`
- `regional_entities_expanded`
- expansion trace (`passes`, per-pass coverage result)

You can inspect these via persisted generation snapshot and taxonomy preview stats.

## Rollout Plan

1. Deploy with recommended values above.
2. Run a small batch of representative campaigns.
3. Verify distinct-country and unrecognized counters.
4. Confirm expansion pass count stays bounded.
5. Tune only one variable group at a time (tokens, coverage, expansion).

## Practical Tuning Rules

- If coverage is too low: increase `CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES` first, then batch size.
- If cost is high: reduce expansion passes before reducing initial max tokens.
- If false subdivision misses occur: enable enrichment and verify CSV path/types.
- If noisy subdivisions appear: tighten `CAMPAIGN_TAXONOMY_SUBDIVISION_ENRICHMENT_ALLOWED_TYPES`.

## Notes

- Keep external CSV files immutable and versioned in your deployment artifact pipeline.
- Avoid changing many settings at once in production; isolate changes for easier incident rollback.
