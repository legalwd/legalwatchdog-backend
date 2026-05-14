# Campaign Taxonomy Phase 2 Implementation

## Summary

Phase 2 has been implemented with three core capabilities:

- Balanced proportional trimming to avoid country skew when enforcing taxonomy node budgets.
- Iterative multi-pass expansion to recover missing global country coverage.
- Proportional sibling budget allocation for country/state distribution fairness.

This phase builds on Phase 1 reliability gates and keeps behavior config-driven for production operations.

## Implemented Features

### 1. Iterative Expansion Workflow

Implemented in [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](../app/api/modules/v1/campaigns/service/taxonomy_generation_service.py).

What it does:

- After initial generation and normalization, checks distinct-country coverage against configured threshold.
- If below threshold, runs controlled expansion passes to add missing ISO countries.
- Merges expansion output into existing taxonomy deterministically (name merge, child merge, deduplicated queries).
- Re-validates and re-normalizes after each pass.
- Writes trace metadata in `generation_config_snapshot["expansion"]`.

Key methods:

- `_expand_taxonomy_for_coverage()`
- `_missing_country_names()`
- `_build_expansion_prompt()`
- `_merge_taxonomy_nodes()`
- `_merge_single_node()`

### 2. Balanced Trimming Redesign

Implemented in [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](../app/api/modules/v1/campaigns/service/taxonomy_generation_service.py).

What changed:

- Replaced greedy child-first trimming with balanced sibling-aware trimming.
- Preserves breadth first (keeps siblings whenever budget allows).
- Allocates descendant budgets proportionally using largest-remainder distribution.
- Drops trailing siblings only when budget is smaller than sibling count.

Key methods:

- `_trim_to_budget()`
- `_allocate_proportional_budgets()`

### 3. Config Controls for Phase 2

Added in [app/api/core/config.py](../app/api/core/config.py):

- `CAMPAIGN_TAXONOMY_EXPANSION_ENABLED`
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_PASSES`
- `CAMPAIGN_TAXONOMY_EXPANSION_BATCH_SIZE`
- `CAMPAIGN_TAXONOMY_EXPANSION_MAX_TOKENS`

These complement existing Phase 1 controls and allow safer production tuning.

### 4. Truncation Handling Reuse for Expansion

Expansion passes use the same strict truncation guard as base generation.

If strict truncation is enabled, truncated LLM responses fail fast to prevent partial-state promotion.

## Tests Added and Updated

Updated [tests/modules/v1/campaigns/test_taxonomy_generation.py](../tests/modules/v1/campaigns/test_taxonomy_generation.py):

- `TestExpansionPasses.test_expansion_pass_increases_coverage_and_succeeds`
- `TestBalancedTrimming.test_balanced_trim_preserves_multiple_top_level_countries`

These validate:

- Expansion pass execution path and successful recovery of coverage.
- Balanced trim behavior preserving multiple top-level countries under constrained budget.

## Validation Results

Targeted campaign taxonomy suite was executed:

- [tests/modules/v1/campaigns/test_taxonomy_generation.py](../tests/modules/v1/campaigns/test_taxonomy_generation.py)
- [tests/modules/v1/campaigns/test_taxonomy_geo_validator.py](../tests/modules/v1/campaigns/test_taxonomy_geo_validator.py)
- [tests/modules/v1/campaigns/test_taxonomy_routes.py](../tests/modules/v1/campaigns/test_taxonomy_routes.py)

Result:

- `31 passed`
- `0 failed`

## Operational Notes

- Expansion is bounded by pass count and batch size to control cost and runtime.
- Coverage enforcement remains the final gate before `TAXONOMY_READY`.
- Trimming now reduces structural skew for global STATE-level campaigns.

## Files Changed in Phase 2

- [app/api/core/config.py](../app/api/core/config.py)
- [app/api/modules/v1/campaigns/service/taxonomy_generation_service.py](../app/api/modules/v1/campaigns/service/taxonomy_generation_service.py)
- [tests/modules/v1/campaigns/test_taxonomy_generation.py](../tests/modules/v1/campaigns/test_taxonomy_generation.py)

No database schema changes were introduced in this phase.
