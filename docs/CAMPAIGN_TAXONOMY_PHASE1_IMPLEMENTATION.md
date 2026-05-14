# Campaign Taxonomy Phase 1 Implementation

## Summary

This document records the Phase 1 production hardening delivered for campaign taxonomy generation, with emphasis on reliability, clean structure, safe execution behavior, and operational diagnostics.

Primary outcomes:

- Taxonomy generation enforces higher reliability and broader global coverage.
- Regional aggregate entities (for example, EU) are normalized into sovereign country nodes.
- API preview diagnostics expose richer taxonomy health signals.
- Targeted taxonomy tests pass end-to-end in the local test environment.

## Scope Implemented

The following implementation was applied:

- Config-driven generation controls and thresholds.
- Breadth-first taxonomy prompt strengthening.
- Strict truncation handling (fail-fast for partial LLM responses).
- Global country coverage gate for COUNTRY and STATE depth campaigns.
- Regional entity expansion and top-level country deduplication in geo normalization.
- Expanded preview diagnostics for taxonomy API responses.
- Test coverage updates for new behavior.

## Files Changed

- [app/api/core/config.py](../app/api/core/config.py)
- [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](../app/api/modules/v1/campaigns/service/taxonomy_generation_service.py)
- [app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py](../app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py)
- [app/api/modules/v1/campaigns/schemas/campaign_schema.py](../app/api/modules/v1/campaigns/schemas/campaign_schema.py)
- [app/api/modules/v1/campaigns/routes/taxonomy_routes.py](../app/api/modules/v1/campaigns/routes/taxonomy_routes.py)
- [tests/modules/v1/campaigns/test_taxonomy_generation.py](../tests/modules/v1/campaigns/test_taxonomy_generation.py)
- [tests/modules/v1/campaigns/test_taxonomy_geo_validator.py](../tests/modules/v1/campaigns/test_taxonomy_geo_validator.py)
- [tests/modules/v1/campaigns/test_taxonomy_routes.py](../tests/modules/v1/campaigns/test_taxonomy_routes.py)

Note:

- [.gitignore](../.gitignore) was changed separately and is not part of taxonomy behavior.

## Detailed Implementation

### 1. Configuration and Operational Controls

Added campaign taxonomy runtime settings in [app/api/core/config.py](../app/api/core/config.py):

- `CAMPAIGN_TAXONOMY_MAX_TOKENS` (default `24000`)
- `CAMPAIGN_TAXONOMY_TEMPERATURE` (default `0.3`)
- `CAMPAIGN_TAXONOMY_ENFORCE_GLOBAL_COVERAGE` (default `True`)
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_COUNTRY` (default `180`)
- `CAMPAIGN_TAXONOMY_MIN_COUNTRIES_STATE` (default `180`)
- `CAMPAIGN_TAXONOMY_STRICT_TRUNCATION` (default `True`)
- `CAMPAIGN_TAXONOMY_EXPAND_REGIONAL_ENTITIES` (default `True`)

Why this matters:

- Operators can tune generation behavior without code changes.
- Production and non-production environments can use different safety/performance profiles.

### 2. Taxonomy Generation Reliability Hardening

Implemented in [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](../app/api/modules/v1/campaigns/service/taxonomy_generation_service.py):

- Prompt contract strengthened for breadth-first generation.
- Explicit prohibition of regional blocs as top-level country nodes.
- Generation uses config-driven `max_tokens` and `temperature`.
- Truncated model output (`finish_reason=length`) triggers deterministic failure when strict mode is enabled.
- Country coverage gate added before transitioning campaign to `TAXONOMY_READY`.

Reliability impact:

- Prevents silent acceptance of incomplete taxonomy payloads.
- Reduces risk of narrow country coverage in global campaigns.

### 3. Geo Normalization Expansion and Dedupe

Implemented in [app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py](../app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py):

- Added regional entity expansion mapping for common blocs.
- Top-level regional entries expand into member countries when enabled.
- Added top-level deduplication after normalization.
- Added richer geo stats:
  - `distinct_countries`
  - `regional_entities_expanded`
  - `unrecognized_top_level`

Operational impact:

- Avoids unresolved pseudo-country nodes.
- Reduces duplicate top-level country branches and downstream duplicate work risk.

### 4. API Diagnostics Extension

Implemented in [app/api/modules/v1/campaigns/schemas/campaign_schema.py](../app/api/modules/v1/campaigns/schemas/campaign_schema.py) and [app/api/modules/v1/campaigns/routes/taxonomy_routes.py](../app/api/modules/v1/campaigns/routes/taxonomy_routes.py):

- Extended taxonomy preview stats with:
  - `distinct_countries`
  - `regional_entities_expanded`
  - `unrecognized_top_level`
- Routes map these values from stored geo stats into response payloads.

Outcome:

- Better operator visibility when deciding taxonomy approval.

## Reliability and Race Condition Considerations

### Deterministic Failure Conditions

Generation now fails early and explicitly on:

- Truncated LLM output in strict mode.
- Country coverage below configured minimum for global campaign depth.

This avoids race-prone downstream workflows operating on invalid intermediate data.

### Duplicate Work Risk Reduction

Top-level country deduplication in geo normalization reduces repeated country branches that can produce duplicate hydration/discovery paths.

### Transactional Safety

Taxonomy generation flow updates campaign state and generation snapshot in one controlled service path, preserving traceability on both success and failure (`last_error`, warnings, coverage metadata).

## Database and Performance Considerations

- No schema migration was introduced in this phase.
- Coverage gate prevents costly downstream execution on under-covered taxonomies.
- Config-driven token/temperature control allows balancing cost vs completeness per environment.

## Test Validation

Targeted taxonomy test suite:

- [tests/modules/v1/campaigns/test_taxonomy_generation.py](../tests/modules/v1/campaigns/test_taxonomy_generation.py)
- [tests/modules/v1/campaigns/test_taxonomy_geo_validator.py](../tests/modules/v1/campaigns/test_taxonomy_geo_validator.py)
- [tests/modules/v1/campaigns/test_taxonomy_routes.py](../tests/modules/v1/campaigns/test_taxonomy_routes.py)

Result:

- `29 passed`
- `0 failed`

## Deployment and Rollout Notes

- Defaults are safe and conservative for production hardening.
- If generation cost increases, operators can tune token/temperature values using environment settings.
- If a campaign intentionally targets a limited geography, disable global coverage enforcement or use lower minimum thresholds in environment configuration.

## Deferred Items (Phase 2 Backlog)

This backlog has now been implemented in [docs/CAMPAIGN_TAXONOMY_PHASE2_IMPLEMENTATION.md](CAMPAIGN_TAXONOMY_PHASE2_IMPLEMENTATION.md).

## Change Footprint

Implementation footprint at Phase 1 close:

- 9 files changed
- 451 insertions
- 12 deletions

This reflected service hardening, diagnostics extension, and tests for reliability guarantees.
