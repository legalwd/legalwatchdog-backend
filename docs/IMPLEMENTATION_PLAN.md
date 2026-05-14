# Campaign Module — Implementation Plan

> **Reference:** [docs/CAMPAIGN_ARCHITECTURE.md](CAMPAIGN_ARCHITECTURE.md)  
> **Date:** February 28, 2026  
> **Branch Strategy:**  
> - `feature/campaign-celery` — Approach A (Celery orchestration)  
> - `feature/campaign-langgraph` — Approach B (LangGraph orchestration)  
> - Both branch from `dev`, both implement the same Campaign module + SEO infra + both monitoring backends

---

## Table of Contents

1. [Branch Strategy & Shared Work](#1-branch-strategy--shared-work)
2. [Phase 0 — Shared Foundation (Both Branches)](#2-phase-0--shared-foundation-both-branches)
3. [Phase 1 — Campaign Module Core (Both Branches)](#3-phase-1--campaign-module-core-both-branches)
4. [Phase 2 — Taxonomy + Geo Validation (Both Branches)](#4-phase-2--taxonomy--geo-validation-both-branches)
5. [Phase 3 — Hydration Service (Both Branches)](#5-phase-3--hydration-service-both-branches)
6. [Phase 4 — Source Discovery Automation (Both Branches)](#6-phase-4--source-discovery-automation-both-branches)
7. [Phase 5A — Pipeline Orchestration (Celery Branch)](#7-phase-5a--pipeline-orchestration-celery-branch)
8. [Phase 5B — Pipeline Orchestration (LangGraph Branch)](#8-phase-5b--pipeline-orchestration-langgraph-branch)
9. [Phase 6 — SEO Infrastructure (Both Branches)](#9-phase-6--seo-infrastructure-both-branches)
10. [Phase 7 — Monitoring: Celery Beat (Both Branches)](#10-phase-7--monitoring-celery-beat-both-branches)
11. [~~Phase 8 — Monitoring: Parallel.ai Monitor API~~ (Removed)](#11-phase-8--monitoring-parallelai-monitor-api-removed)
12. [Phase 9 — Testing + Scale Validation](#12-phase-9--testing--scale-validation)
13. [Phase 10 — Production Launch](#13-phase-10--production-launch)
14. [Task Checklist Summary](#14-task-checklist-summary)
15. [Timeline](#15-timeline)

---

## 1. Branch Strategy & Shared Work

### Git Workflow

```
dev (stable)
 ├── feature/campaign-shared       ← Phases 0-4, 6-7 (shared foundation)
 │    ├── feature/campaign-celery   ← Phase 5A (Celery orchestration)
 │    └── feature/campaign-langgraph ← Phase 5B (LangGraph orchestration)
 │
 └── (existing feature branches)
```

**Flow:**
1. Create `feature/campaign-shared` from `dev`
2. Build Phases 0–4 (Campaign module, taxonomy, hydration, source discovery) on `feature/campaign-shared`
3. Build Phase 6 (SEO infra) on `feature/campaign-shared`
4. Build Phase 7 (Celery Beat monitoring) on `feature/campaign-shared`
5. Branch `feature/campaign-celery` from `feature/campaign-shared` → build Phase 5A
6. Branch `feature/campaign-langgraph` from `feature/campaign-shared` → build Phase 5B
7. Each orchestration branch gets its own Phase 9 (testing)
8. Merge the chosen winner into `dev`

### What's Shared vs Branch-Specific

| Component | Shared | Celery Branch | LangGraph Branch |
|-----------|--------|---------------|-----------------|
| Campaign model + migration | ✅ | | |
| Campaign schemas | ✅ | | |
| Campaign routes (CRUD) | ✅ | | |
| TaxonomyGenerationService | ✅ | | |
| TaxonomyGeoValidator | ✅ | | |
| CampaignHydrationService | ✅ | | |
| CampaignSourceDiscoveryService | ✅ | | |
| SitemapService + robots.txt | ✅ | | |
| Enhanced BlogArtifactService | ✅ | | |
| Celery Beat monitoring re-enable | ✅ | | |
| Campaign Celery tasks + chaining | | ✅ | |
| LangGraph StateGraph + nodes | | | ✅ |
| LangGraph checkpoint config | | | ✅ |
| Change Processing Subgraph | | | ✅ |
| `POST /launch` handler | | ✅ (Celery dispatch) | ✅ (graph.ainvoke) |
| `GET /status` handler | | ✅ (DB query) | ✅ (graph.aget_state) |

---

## 2. Phase 0 — Shared Foundation (Both Branches) [2/3 ✅]

> **Goal:** Validate the existing pipeline works end-to-end for the Campaign use case. No new code — just manual verification.
> **Duration:** 3–5 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 0.1 — Verify Day 1 Auto-Accept Pipeline ✅

- [x] Using existing Swagger endpoints, create:
  - 1 Organization (industry: "EOR")
  - 1 Project (title: "EOR Pilot", master_prompt: EOR-focused)
  - 3 Jurisdictions: "United States" (parent), "California" (child), "Texas" (child)
- [x] For each jurisdiction, discover sources via `POST /jurisdictions/{id}/discover-sources`
- [x] Accept top 5 sources per jurisdiction via `POST /jurisdictions/{id}/accept-sources`
- [x] Trigger scrape via `POST /jurisdictions/{id}/trigger-scrape`
- [x] Verify Day 1 auto-accept fires → JurisdictionState populated
- [x] Verify blog generation triggers → JurisdictionBlogPost created
- [x] Verify artifact published → static HTML at `BLOG_STATIC_DIR`

**Acceptance criteria:** 3 published blog pages with correct parent-child URL hierarchy.

> ✅ **Completed March 1, 2026** — `scripts/phase_0_1_pipeline_verify.py` passed **42/42 checks** against `test-user@example.com`. All bugs found during verification were fixed on `fix/general-bugs` (PR #533):
> - `_get_jurisdiction` rewritten with `.join(Project, ...)` (removed invalid `.has()`)
> - `_build_public_resource_path` uses `await db.get(Project, ...)` (fixed async lazy-load)
> - Batch-accept duplicate URL check scoped to `jurisdiction_id` (was globally scoped)
> - `BlogLLMOutput.meta_description` truncates at 157 chars instead of hard-rejecting
> - Migration `654a54ebe9da` stripped to only `project_bulk_blog_jobs` ops (removed bundled unrelated changes)
>
> **IDs from verified run:** org `0b2527c7-5509-48dd-922d-d21ffc84e582` · project `62b7a18d-01e7-4b0d-bc7c-907fecc0ddcb` · US `1730d17b-9456-4ddd-be87-f816862b98c2` · CA `18988f24-c082-4fe4-92c1-e718e8df81ed` · TX `be9d82df-30f0-481d-88b7-57e98b524bdf`

#### 0.2 — Document Current Pipeline Gaps ✅

- [x] Note any failures, timeouts, or unexpected behaviors
- [x] Identify any services that need minor patches for Campaign use
- [x] Confirm `BlogArtifactService.write_artifact()` handles nested paths (`/eor/united-states/california/`)

> ✅ **Completed March 1, 2026** — Gaps documented from Phase 0.1 run. Key findings:
> - **Nested path generation confirmed:** `blog-artifacts/resources/eor-pilot/united-states/california/eor-guide-california/index.html` and `united-states/texas/eor-guide-texas/index.html` were generated correctly — `BlogArtifactService.write_artifact()` handles arbitrary depth without changes.
> - **Bugs patched (all merged via PR #533):** `_get_jurisdiction` `.has()` error, `_build_public_resource_path` async lazy-load, batch-accept global URL uniqueness scope, `meta_description` hard max_length rejection, migration bundling unrelated ops.
> - **No schema changes needed** for Campaign use: `Jurisdiction.prompt`, `parent_id`, `project_id` fields are sufficient for hydration; only `campaign_id` and `auto_accept_changes` additions needed (Phase 1.2).
> - **Celery Beat scraping dispatch remains disabled** (manual trigger via API); re-enabling is tracked in Phase 7.
> - **`content_hash` per-source** already populated after scrape — skip-if-unchanged gate is available at no extra cost.

#### 0.3 — Set Up Branch

```bash
git checkout dev
git pull origin dev
git checkout -b feature/campaign-shared
```

---

## 3. Phase 1 — Campaign Module Core (Both Branches)

> **Goal:** Campaign model, schemas, CRUD routes, Alembic migration.  
> **Duration:** 5–7 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 1.1 — Campaign Model

**File:** `app/api/modules/v1/campaigns/models/campaign_model.py`

- [ ] Create `CampaignStatus` enum (12 values: DRAFT → ACTIVE)
- [ ] Create `CampaignTargetDepth` enum (COUNTRY, STATE, CITY)
- [ ] Create `CampaignMonitorBackend` enum (CELERY_BEAT only — Parallel.ai Monitor removed)
- [ ] Create `Campaign` SQLModel with all fields:
  - Core: `id`, `organization_id`, `project_id`, `name`, `industry`, `domain_description`
  - Config: `target_depth`, `monitor_backend`, `monitor_cadence`, `sources_per_jurisdiction`, `max_jurisdictions`
  - State: `status`, `taxonomy_json`, `stats`
  - Audit: `created_by`, `taxonomy_approved_by`, `taxonomy_approved_at`, `launched_by`, `generation_model`, `generation_config_snapshot`
  - Timestamps: `created_at`, `updated_at`
- [ ] Create `CampaignExecutionLog` SQLModel:
  - `id`, `campaign_id`, `phase`, `started_at`, `completed_at`, `total_items`, `completed_items`, `failed_items`, `error_log`

**Validation:**
- `max_jurisdictions` default 15000, min 1
- `sources_per_jurisdiction` default 5, range 1–20
- `monitor_cadence` must be one of: "hourly", "daily", "weekly", "every_two_weeks"

#### 1.2 — Jurisdiction Model Update

**File:** `app/api/modules/v1/jurisdictions/models/jurisdiction_model.py`

- [ ] Add `campaign_id: Optional[UUID] = Field(default=None, foreign_key="campaigns.id", index=True)`
- [ ] Add `auto_accept_changes: bool = Field(default=False)`

#### 1.3 — Alembic Migration

```bash
alembic revision --autogenerate -m "add campaigns module and jurisdiction campaign fields"
```

- [ ] Run migration generation
- [ ] Review `upgrade()` — verify it contains ONLY:
  - `CREATE TABLE campaigns (...)` with all columns
  - `CREATE TABLE campaign_execution_logs (...)`
  - `ALTER TABLE jurisdictions ADD COLUMN campaign_id ...`
  - `ALTER TABLE jurisdictions ADD COLUMN auto_accept_changes ...`
  - Correct indexes and foreign keys
- [ ] Verify `downgrade()` reverses cleanly
- [ ] Apply: `alembic upgrade head`
- [ ] Test rollback: `alembic downgrade -1` then re-apply

#### 1.4 — Campaign Schemas

**File:** `app/api/modules/v1/campaigns/schemas/campaign_schema.py`

- [ ] `CampaignCreateRequest`: name, industry, domain_description, target_depth, monitor_backend, monitor_cadence, sources_per_jurisdiction, max_jurisdictions
- [ ] `CampaignUpdateRequest`: optional fields for name, domain_description, monitor_backend, monitor_cadence
- [ ] `CampaignResponse`: all fields + computed stats
- [ ] `CampaignListResponse`: paginated list with summary stats
- [ ] `CampaignStatusResponse`: phase, progress percentages, execution logs
- [ ] `TaxonomyNodeSchema`: name, description, suggested_prompt, suggested_search_queries, children[], iso_code (optional)
- [ ] `TaxonomyResponse`: root nodes[], total_count, geo_validation_warnings[]
- [ ] `TaxonomyEditRequest`: nodes[] (partial tree updates)

#### 1.5 — Campaign CRUD Routes

**File:** `app/api/modules/v1/campaigns/routes/campaign_routes.py`

- [ ] `POST /api/v1/campaigns` — create campaign (superadmin only)
- [ ] `GET /api/v1/campaigns` — list campaigns with pagination
- [ ] `GET /api/v1/campaigns/{id}` — get campaign details + execution logs
- [ ] `PATCH /api/v1/campaigns/{id}` — update campaign (only in DRAFT status)
- [ ] `DELETE /api/v1/campaigns/{id}` — delete campaign (only in DRAFT status)
- [ ] All routes use `Depends(get_current_superadmin)` for auth
- [ ] All responses use `success_response()` / `error_response()`

#### 1.6 — Campaign Service (CRUD Only)

**File:** `app/api/modules/v1/campaigns/service/campaign_service.py`

- [ ] `create_campaign()` — validates org exists, sets status=DRAFT, records created_by
- [ ] `get_campaign()` — loads with execution logs
- [ ] `list_campaigns()` — paginated, filterable by status/industry
- [ ] `update_campaign()` — only if status=DRAFT
- [ ] `delete_campaign()` — only if status=DRAFT, cascade delete logs

#### 1.7 — Register Router

**File:** `app/api/modules/v1/__init__.py`

- [ ] Import and include campaign router with prefix `/api/v1/campaigns`

#### 1.8 — OpenAPI Docs

**File:** `app/api/modules/v1/campaigns/routes/docs/campaign_routes_docs.py`

- [ ] Response examples for all endpoints (success + error cases)
- [ ] `_custom_errors` and `_custom_success` markers

#### 1.9 — Tests (Phase 1)

**File:** `tests/modules/v1/campaigns/test_campaign_crud.py`

- [ ] `test_create_campaign_success` — valid payload, verify status=DRAFT
- [ ] `test_create_campaign_missing_required_fields` — 422 validation
- [ ] `test_create_campaign_non_superadmin_forbidden` — 403
- [ ] `test_get_campaign_success`
- [ ] `test_get_campaign_not_found` — 404
- [ ] `test_list_campaigns_paginated`
- [ ] `test_list_campaigns_filter_by_status`
- [ ] `test_update_campaign_in_draft`
- [ ] `test_update_campaign_not_in_draft_rejected`
- [ ] `test_delete_campaign_in_draft`
- [ ] `test_delete_campaign_not_in_draft_rejected`

---

## 4. Phase 2 — Taxonomy + Geo Validation (Both Branches)

> **Goal:** LLM-powered taxonomy generation + ISO geo normalization.  
> **Duration:** 7–10 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 2.1 — Taxonomy Generation Service

**File:** `app/api/modules/v1/campaigns/service/taxonomy_generation_service.py`

- [ ] `TaxonomyGenerationService` class:
  - Constructor: accepts `db: AsyncSession`
  - `generate(campaign_id: UUID) -> dict`: main entry point
- [ ] Build system prompt for taxonomy generation (regulatory domain expert persona)
- [ ] Build user prompt with: `{industry}`, `{domain_description}`, `{target_depth}`
- [ ] Require JSON output with structure: `{"nodes": [{"name", "description", "suggested_prompt", "suggested_search_queries", "children"}]}`
- [ ] Call `LLMManager.generate_with_tracking()`:
  - `temperature=0.4` (slightly creative for diverse coverage)
  - `max_tokens=8000` (large taxonomy trees)
  - `model_preference="premium"` (accuracy matters here)
  - `json_mode=True`
- [ ] Parse LLM output → validate JSON structure
- [ ] Store raw output in `Campaign.taxonomy_json`
- [ ] Record `Campaign.generation_model` from LLM response
- [ ] Snapshot config into `Campaign.generation_config_snapshot`
- [ ] Update `Campaign.status` → `GENERATING_TAXONOMY` → `TAXONOMY_READY`

#### 2.2 — Taxonomy Validation Rules

**In same file or separate validator:**

- [ ] Deduplicate node names at each hierarchy level
- [ ] Enforce max name length (255 chars)
- [ ] Validate no circular references (parent→child→parent)
- [ ] Cap depth: COUNTRY=1, STATE=2, CITY=3
- [ ] Ensure every node has at least one `suggested_search_query`
- [ ] Enforce `max_jurisdictions` cap — count all nodes, reject if exceeds limit
- [ ] Return structured validation result with errors[] and warnings[]

#### 2.3 — Taxonomy Geo Validator

**File:** `app/api/modules/v1/campaigns/service/taxonomy_geo_validator.py`

- [ ] Add `pycountry` to `pyproject.toml` dependencies
- [ ] `TaxonomyGeoValidator` class:
  - `validate_and_normalize(taxonomy: dict) -> GeoValidationResult`
  - `_resolve_country(name: str) -> Optional[GeoEntity]`
  - `_resolve_subdivision(name: str, country_code: str) -> Optional[GeoEntity]`
- [ ] Country validation: match against ISO 3166-1 (exact → alias → fuzzy >90%)
- [ ] Subdivision validation: match against ISO 3166-2 for parent country
- [ ] Alias resolution map: "USA" → "United States", "UK" → "United Kingdom", etc.
- [ ] Fuzzy matching via `difflib.SequenceMatcher` or `rapidfuzz` (optional dep)
- [ ] Attach `iso_code` to each validated node
- [ ] Return `GeoValidationResult`:
  - `normalized_taxonomy: dict` — tree with normalized names + iso_codes
  - `warnings: list[dict]` — fuzzy matches, unrecognized entities
  - `stats: dict` — `{countries_matched, subdivisions_matched, unrecognized_count}`

#### 2.4 — Taxonomy Routes

**Add to:** `app/api/modules/v1/campaigns/routes/campaign_routes.py`

- [ ] `POST /api/v1/campaigns/{id}/generate-taxonomy` (202 Accepted)
  - Validates campaign is in DRAFT status
  - Dispatches generation (sync for now; async in Phase 5)
  - Returns immediately with generation status
- [ ] `GET /api/v1/campaigns/{id}/taxonomy`
  - Returns taxonomy tree + geo validation warnings
  - Shows preview stats: "This will create X countries, Y states, Z total jurisdictions"
- [ ] `PATCH /api/v1/campaigns/{id}/taxonomy`
  - Accepts partial node edits (add/remove/rename nodes)
  - Re-runs geo validation on edited nodes
  - Only allowed when status is TAXONOMY_READY
- [ ] `POST /api/v1/campaigns/{id}/approve-taxonomy`
  - Records `taxonomy_approved_by` + `taxonomy_approved_at`
  - Required before launch

#### 2.5 — Tests (Phase 2)

**File:** `tests/modules/v1/campaigns/test_taxonomy_generation.py`

- [ ] `test_generate_taxonomy_success` — mock LLM, verify JSON structure stored
- [ ] `test_generate_taxonomy_invalid_json_from_llm` — retry/error handling
- [ ] `test_generate_taxonomy_exceeds_max_jurisdictions` — rejected
- [ ] `test_generate_taxonomy_not_in_draft_rejected`

**File:** `tests/modules/v1/campaigns/test_taxonomy_geo_validator.py`

- [ ] `test_validate_known_countries` — "United States", "Nigeria", "Germany" resolved
- [ ] `test_normalize_aliases` — "USA" → "United States", "UK" → "United Kingdom"
- [ ] `test_fuzzy_match_typo` — "Californnia" → "California" with warning
- [ ] `test_flag_unknown_entity` — "North Zambonia" flagged in warnings
- [ ] `test_iso_codes_attached` — US, NG-LA, GB-ENG codes on nodes
- [ ] `test_subdivision_validation` — "Lagos" under "Nigeria" resolves to NG-LA

**File:** `tests/modules/v1/campaigns/test_taxonomy_routes.py`

- [ ] `test_get_taxonomy_shows_preview_stats`
- [ ] `test_edit_taxonomy_reruns_validation`
- [ ] `test_approve_taxonomy_records_audit_fields`
- [ ] `test_approve_taxonomy_not_in_taxonomy_ready_rejected`

---

## 5. Phase 3 — Hydration Service (Both Branches)

> **Goal:** Convert taxonomy tree into real Project + Jurisdiction database records.  
> **Duration:** 5–7 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 3.1 — Campaign Hydration Service

**File:** `app/api/modules/v1/campaigns/service/campaign_hydration_service.py`

- [ ] `CampaignHydrationService` class:
  - Constructor: `db: AsyncSession`
  - `hydrate(campaign_id: UUID) -> list[UUID]`: returns jurisdiction IDs created
- [ ] Create Project for campaign:
  - `title = f"{campaign.industry} - {campaign.name}"`
  - `master_prompt = campaign.domain_description`
  - `organization_id = campaign.organization_id`
  - Store `Project.id` in `Campaign.project_id`
- [ ] Walk taxonomy tree (depth-first):
  - For each node → `Jurisdiction.create()`:
    - `name = node.name`
    - `parent_id = parent jurisdiction's ID` (None for top-level)
    - `prompt = node.suggested_prompt`
    - `description = node.description`
    - `project_id = campaign.project_id`
    - `campaign_id = campaign.id`
    - `auto_accept_changes = True` (campaign jurisdictions auto-accept)
    - `enable_auto_scrape = True`
    - `scrape_frequency = campaign.monitor_cadence`
  - Maintain mapping: `{taxonomy_node_path → jurisdiction_id}` for parent resolution
- [ ] Batch commit: flush every 100 jurisdictions to avoid memory pressure
- [ ] **Idempotency:** `UniqueConstraint("project_id", "parent_id", "name")` means re-running hydration skips existing jurisdictions — catch `IntegrityError` and skip
- [ ] Update `CampaignExecutionLog` with progress (total_items, completed_items)
- [ ] Update `Campaign.stats` with `{total_jurisdictions: N}`
- [ ] Update `Campaign.status` → `HYDRATING` → next phase

#### 3.2 — Tests (Phase 3)

**File:** `tests/modules/v1/campaigns/test_hydration_service.py`

- [ ] `test_hydrate_creates_project` — verify Project created with correct fields
- [ ] `test_hydrate_creates_jurisdiction_hierarchy` — parent-child links correct
- [ ] `test_hydrate_sets_campaign_id_on_jurisdictions`
- [ ] `test_hydrate_sets_auto_accept_true`
- [ ] `test_hydrate_idempotent_rerun` — second run skips existing, no duplicates
- [ ] `test_hydrate_batch_commit_every_100` — verify batch behavior
- [ ] `test_hydrate_updates_execution_log_progress`
- [ ] `test_hydrate_respects_max_jurisdictions_cap`

---

## 6. Phase 4 — Source Discovery Automation (Both Branches)

> **Goal:** Automatically discover and accept sources for all campaign jurisdictions.  
> **Duration:** 5–7 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 4.1 — Campaign Source Discovery Service

**File:** `app/api/modules/v1/campaigns/service/campaign_source_discovery_service.py`

- [ ] `CampaignSourceDiscoveryService` class:
  - Constructor: `db: AsyncSession, redis_client: Redis`
  - `discover_all(campaign_id: UUID) -> dict`: batch discovery for all jurisdictions
  - `discover_for_jurisdiction(jurisdiction_id: UUID, campaign_id: UUID) -> list[UUID]`: single jurisdiction
- [ ] For each jurisdiction:
  1. Build search query from `jurisdiction.prompt` + `jurisdiction.name`
  2. Call existing `SourceDiscoveryService.suggest_sources(search_query, jurisdiction_name, max_results=N)`
  3. Auto-accept top N sources → call `SourceService.create_source()` for each
  4. Rate limit: `asyncio.sleep(2)` between Parallel.ai Search calls (avoid 429)
- [ ] Track progress in `CampaignExecutionLog`
- [ ] Handle failures gracefully: log failed jurisdictions, continue with next
- [ ] Return summary: `{total, discovered, failed, sources_created}`

#### 4.2 — Rate Limiting Strategy

- [ ] Use Redis-based sliding window rate limiter for Parallel.ai Search calls
- [ ] Default: 25 requests/minute (conservative, adjust based on Parallel.ai limits)
- [ ] Configurable via `settings.CAMPAIGN_SEARCH_RATE_LIMIT`
- [ ] If rate limited (429): exponential backoff with max 5 retries

#### 4.3 — Tests (Phase 4)

**File:** `tests/modules/v1/campaigns/test_source_discovery_service.py`

- [ ] `test_discover_for_jurisdiction_success` — mock Parallel.ai, verify sources created
- [ ] `test_discover_all_processes_all_jurisdictions` — verify all campaign jurisdictions hit
- [ ] `test_discover_rate_limited` — verify 2s delay between calls
- [ ] `test_discover_failure_continues_with_next` — one failure doesn't stop batch
- [ ] `test_discover_updates_execution_log`
- [ ] `test_discover_idempotent` — re-run doesn't create duplicate sources (URL dedup)

---

## 7. Phase 5A — Pipeline Orchestration (Celery Branch)

> **Goal:** Chain all campaign phases together using Celery tasks.  
> **Duration:** 10–14 days  
> **Branch:** `feature/campaign-celery` (branched from `feature/campaign-shared`)

### Branch Setup

```bash
git checkout feature/campaign-shared
git checkout -b feature/campaign-celery
```

### Tasks

#### 5A.1 — Campaign Celery Tasks

**File:** `app/api/modules/v1/campaigns/tasks/campaign_tasks.py`

- [ ] `campaign_generate_taxonomy(campaign_id: str)`:
  - Calls `TaxonomyGenerationService.generate()`
  - Calls `TaxonomyGeoValidator.validate_and_normalize()`
  - Updates Campaign status to TAXONOMY_READY
  - Does NOT auto-chain to next step (requires admin approval)

- [ ] `campaign_hydrate(campaign_id: str)`:
  - Calls `CampaignHydrationService.hydrate()`
  - On success → chains to `campaign_discover_sources_batch`
  - `max_retries=3`, `default_retry_delay=120`

- [ ] `campaign_discover_sources_batch(campaign_id: str)`:
  - Loads all jurisdiction IDs for campaign
  - Splits into batches of 50
  - Creates Celery `group` of `campaign_discover_sources_single` per jurisdiction
  - Uses `chord(group, campaign_trigger_scrape_batch.si(campaign_id))` to wait for all

- [ ] `campaign_discover_sources_single(jurisdiction_id: str, campaign_id: str)`:
  - Calls `CampaignSourceDiscoveryService.discover_for_jurisdiction()`
  - `max_retries=3`, `rate_limit="25/m"` (Celery built-in rate limit)

- [ ] `campaign_trigger_scrape_batch(campaign_id: str)`:
  - Loads all campaign jurisdictions
  - For each: calls `JurisdictionScrapingService.trigger_jurisdiction_scrape()`
  - Batches of 100 with 1s delay between batches
  - Existing pipeline takes over from here (Stage 1 → consolidate → Day 1 auto-accept → blog)

- [ ] `campaign_poll_scrape_completion(campaign_id: str)`:
  - Checks: all campaign JurisdictionScrapeJobs in terminal state?
  - If not complete: `self.retry(countdown=60)` (poll every 60s)
  - If complete: chains to `campaign_publish_batch`
  - `max_retries=1440` (up to 24 hours of polling)

- [ ] `campaign_publish_batch(campaign_id: str)`:
  - For each jurisdiction with a JurisdictionBlogPost:
    - Ensure `is_published = True`
    - Call `BlogArtifactService.write_artifact()`
  - Chains to `campaign_setup_monitors`

- [ ] `campaign_setup_monitors(campaign_id: str)`:
  - No-op (Celery Beat schedule handles re-scraping; Parallel.ai Monitor removed)
  - Chains to `campaign_finalize`

- [ ] `campaign_finalize(campaign_id: str)`:
  - Sets `Campaign.status = ACTIVE`
  - Triggers `sitemap_rebuild_debounced`
  - Logs final stats to `CampaignExecutionLog`

#### 5A.2 — Task Routing

**Update:** `app/celery_app.py`

- [ ] Add task routes:
  ```python
  "app.api.modules.v1.campaigns.tasks.*": {"queue": "processing"}
  ```
- [ ] Add all campaign tasks to `task_modules` list

#### 5A.3 — Launch Route (Celery Version)

**Update:** `app/api/modules/v1/campaigns/routes/campaign_routes.py`

- [ ] `POST /api/v1/campaigns/{id}/launch`:
  - Validates `status == TAXONOMY_READY` and `taxonomy_approved_by IS NOT NULL`
  - Records `launched_by = current_user.id`
  - Updates status to `HYDRATING`
  - Dispatches Celery chain:
    ```python
    chain(
        # Phase 1 — Hydration
        campaign_mark_phase.si(str(campaign_id), "hydrating"),
        campaign_hydrate.si(str(campaign_id)),

        # Phase 2 — Source Discovery
        campaign_mark_phase.si(str(campaign_id), "discovering_sources"),
        campaign_discover_sources_batch.si(str(campaign_id)),

        # Phase 3 — Scraping
        campaign_mark_phase.si(str(campaign_id), "scraping"),
        campaign_trigger_scrape_batch.si(str(campaign_id)),
        campaign_poll_scrape_completion.si(str(campaign_id)),

        # Phase 4 — Publishing
        campaign_mark_phase.si(str(campaign_id), "publishing"),
        campaign_publish_batch.si(str(campaign_id)),

        # Phase 5 — Monitoring Setup
        campaign_mark_phase.si(str(campaign_id), "monitoring"),
        campaign_setup_monitors.si(str(campaign_id)),

        # Finalization
        campaign_mark_phase.si(str(campaign_id), "completed"),
        campaign_finalize.si(str(campaign_id)),
    ).apply_async(
        link_error=campaign_pipeline_failed.si(str(campaign_id)),
    )
    ```
  - Returns 202 Accepted

#### 5A.4 — Status Route (Celery Version)

**Update:** `app/api/modules/v1/campaigns/routes/campaign_routes.py`

- [ ] `GET /api/v1/campaigns/{id}/status`:
  - Queries `Campaign.status` + latest `CampaignExecutionLog` entries
  - Returns:
    ```json
    {
        "phase": "discovering_sources",
        "progress": {
            "hydration": {"status": "completed", "total": 5000, "completed": 5000},
            "source_discovery": {"status": "in_progress", "total": 5000, "completed": 3200, "failed": 12},
            "scraping": {"status": "pending"},
            "publishing": {"status": "pending"},
  # Use a configurable TTL so long-running campaigns don't lose their lock.
  # Example: settings.CAMPAIGN_EXECUTION_LOCK_TTL can be derived from
  # max_jurisdictions * estimated_time_per_jurisdiction.
  lock_ttl = settings.CAMPAIGN_EXECUTION_LOCK_TTL
  if not redis_client.set(lock_key, "1", nx=True, ex=lock_ttl):
        }
    }
    ```

#### 5A.5 — Error Handling + Resume

- [ ] Each task: on terminal failure → set `Campaign.status = FAILED`
- [ ] Each task: log error to `CampaignExecutionLog.error_log`
- [ ] Resume logic in `POST /launch`:
  - If `status == FAILED`, check which phase failed
  - Re-dispatch chain starting from the failed phase (skip completed phases)
  - Idempotency of each phase ensures no duplicates

#### 5A.6 — Redis Distributed Lock

- [ ] Prevent duplicate campaign executions:
  ```python
  lock_key = f"campaign_execution:{campaign_id}"
  if not redis_client.set(lock_key, "1", nx=True, ex=3600):
      raise ResourceLockedError("Campaign is already executing")
  ```
- [ ] Release lock in `campaign_finalize` and error handlers

#### 5A.7 — Tests (Phase 5A)

**File:** `tests/modules/v1/campaigns/test_campaign_celery_tasks.py`

- [ ] `test_campaign_hydrate_task_creates_jurisdictions`
- [ ] `test_campaign_discover_sources_batch_splits_into_groups`
- [ ] `test_campaign_discover_sources_single_rate_limited`
- [ ] `test_campaign_trigger_scrape_batch_dispatches_scrapes`
- [ ] `test_campaign_poll_scrape_completion_retries_when_not_done`
- [ ] `test_campaign_poll_scrape_completion_chains_when_done`
- [ ] `test_campaign_publish_batch_writes_artifacts`
- [ ] `test_campaign_finalize_sets_active`
- [ ] `test_campaign_task_failure_sets_campaign_failed`
- [ ] `test_campaign_launch_resume_from_failed_phase`
- [ ] `test_campaign_execution_lock_prevents_duplicate`

**File:** `tests/modules/v1/campaigns/test_campaign_celery_routes.py`

- [ ] `test_launch_campaign_returns_202`
- [ ] `test_launch_campaign_requires_approved_taxonomy`
- [ ] `test_launch_campaign_requires_superadmin`
- [ ] `test_status_endpoint_returns_progress`

---

## 8. Phase 5B — Pipeline Orchestration (LangGraph Branch)

> **Goal:** Build LangGraph StateGraph for campaign pipeline orchestration.  
> **Duration:** 14–21 days  
> **Branch:** `feature/campaign-langgraph` (branched from `feature/campaign-shared`)

### Branch Setup

```bash
git checkout feature/campaign-shared
git checkout -b feature/campaign-langgraph
```

### Tasks

#### 5B.1 — Add Dependencies

**Update:** `pyproject.toml`

- [ ] Add to `[project.dependencies]`:
  ```toml
  langgraph = ">=0.4"
  langgraph-checkpoint-postgres = ">=2.0"
  langchain-core = ">=0.3"
  ```
- [ ] Optional (observability): `langsmith = ">=0.2"`
- [ ] Run `uv sync`

#### 5B.2 — LangGraph Configuration

**File:** `app/api/core/langgraph_config.py`

- [ ] Configure `AsyncPostgresSaver` checkpointer:
  - Shares PostgreSQL with app (separate `langgraph` schema)
  - Connection pool config (separate from SQLAlchemy pool to avoid contention)
- [ ] Startup hook: `await checkpointer.setup()` (creates checkpoint tables)
- [ ] Register startup hook in `main.py` lifespan

#### 5B.3 — Campaign Graph State

**File:** `app/api/modules/v1/campaigns/graphs/campaign_state.py`

- [ ] `CampaignGraphState(TypedDict)`:
  ```python
  campaign_id: str
  taxonomy: dict
  jurisdiction_ids: Annotated[list[str], add]  # append-merge
  source_discovery_results: dict  # {jid: source_count}
  scrape_results: dict  # {jid: status}
  blog_results: dict  # {jid: slug}
  monitor_ids: dict  # {jid: monitor_id}
  phase: str
  errors: Annotated[list[dict], add]
  ```

#### 5B.4 — Campaign Graph Nodes

**File:** `app/api/modules/v1/campaigns/graphs/campaign_nodes.py`

- [ ] `generate_taxonomy(state) -> dict`:
  - Calls `TaxonomyGenerationService.generate()`
  - Calls `TaxonomyGeoValidator.validate_and_normalize()`
  - Returns `{"taxonomy": result, "phase": "taxonomy_ready"}`

- [ ] `hydrate_jurisdictions(state) -> dict`:
  - Calls `CampaignHydrationService.hydrate()`
  - Returns `{"jurisdiction_ids": [ids], "phase": "hydrating"}`

- [ ] `discover_sources_single(state) -> dict`:
  - Receives single jurisdiction context from Send API
  - Calls `CampaignSourceDiscoveryService.discover_for_jurisdiction()`
  - Rate limited with `asyncio.sleep(2)`
  - Returns `{"source_discovery_results": {jid: count}}`

- [ ] `scrape_jurisdiction(state) -> dict`:
  - Calls `JurisdictionScrapingService.trigger_jurisdiction_scrape()`
  - Polls for completion (or uses callback pattern)
  - Returns `{"scrape_results": {jid: "completed"}}`

- [ ] `generate_blog(state) -> dict`:
  - Calls `BlogGenerationService.generate_blog_post_async()`
  - Returns `{"blog_results": {jid: slug}}`

- [ ] `publish_artifact(state) -> dict`:
  - Calls `BlogArtifactService.write_artifact()`
  - Injects cross-linking HTML

- [ ] `setup_monitors(state) -> dict`:
  - No-op for Celery Beat (Parallel.ai Monitor removed)
  - Returns `{"monitor_ids": {}}`

- [ ] `generate_seo(state) -> dict`:
  - Calls `SitemapService.write_all()`
  - Writes `robots.txt`

- [ ] `finalize(state) -> dict`:
  - Sets `Campaign.status = ACTIVE`
  - Returns `{"phase": "active"}`

#### 5B.5 — Fan-Out Functions

- [ ] `fan_out_discovery(state) -> list[Send]`:
  - Returns `[Send("discover_sources_single", {jid, campaign_id}) for jid in state["jurisdiction_ids"]]`
  - Batched: max 200 concurrent Sends

- [ ] `fan_out_scraping(state) -> list[Send]`:
  - Same pattern for scrape triggering

- [ ] `fan_out_blog_generation(state) -> list[Send]`:
  - Same pattern for blog generation

- [ ] `fan_out_publishing(state) -> list[Send]`:
  - Same pattern for artifact publishing

#### 5B.6 — Build Campaign Graph

**File:** `app/api/modules/v1/campaigns/graphs/campaign_graph.py`

- [ ] `build_campaign_graph() -> CompiledGraph`:
  ```python
  builder = StateGraph(CampaignGraphState)
  
  # Add nodes
  builder.add_node("generate_taxonomy", generate_taxonomy)
  builder.add_node("hydrate_jurisdictions", hydrate_jurisdictions)
  builder.add_node("discover_sources_single", discover_sources_single)
  builder.add_node("scrape_jurisdiction", scrape_jurisdiction)
  builder.add_node("generate_blog", generate_blog)
  builder.add_node("publish_artifact", publish_artifact)
  builder.add_node("setup_monitors", setup_monitors)
  builder.add_node("generate_seo", generate_seo)
  builder.add_node("finalize", finalize)
  
  # Set entry + edges
  builder.set_entry_point("generate_taxonomy")
  builder.add_edge("generate_taxonomy", "hydrate_jurisdictions")
  builder.add_conditional_edges("hydrate_jurisdictions", fan_out_discovery)
  builder.add_conditional_edges("discover_sources_single", fan_out_scraping)
  # ... remaining edges
  builder.add_edge("generate_seo", "finalize")
  builder.add_edge("finalize", END)
  
  return builder.compile(checkpointer=checkpointer)
  ```

- [ ] Add `RetryPolicy` per node:
  - LLM nodes: `max_attempts=3, initial_interval=2.0, backoff_factor=2.0`
  - Scraping nodes: `max_attempts=5, initial_interval=5.0, backoff_factor=2.0`
  - API nodes: `max_attempts=3, initial_interval=1.0`

#### 5B.7 — Change Processing Subgraph

**File:** `app/api/modules/v1/campaigns/graphs/change_processing_graph.py`

- [ ] `ChangeProcessingState(TypedDict)`:
  - `jurisdiction_id`, `event_data`, `current_state`, `changes_detected`, `risk_level`, `blog_regenerated`

- [ ] Nodes:
  - `parse_event` — extract structured data from trigger
  - `load_golden_record` — `JurisdictionStateService.get_state_map()`
  - `detect_changes` — AI diff: new data vs Golden Record
  - `auto_accept` — update Golden Record (LOW/MED risk)
  - `interrupt_for_review` — `interrupt()` call for HIGH risk
  - `regenerate_blog` — `BlogGenerationService`
  - `republish` — `BlogArtifactService.write_artifact()`
  - `update_seo` — trigger debounced sitemap rebuild

- [ ] Conditional edge after `detect_changes`:
  - `risk == "HIGH"` → `interrupt_for_review`
  - `risk == "LOW"` or `risk == "MED"` → `auto_accept`

- [ ] Compile with same checkpointer

#### 5B.8 — Launch Route (LangGraph Version)

**Update:** `app/api/modules/v1/campaigns/routes/campaign_routes.py`

- [ ] `POST /api/v1/campaigns/{id}/launch`:
  - Validates approval
  - Records `launched_by`
  - Compiles graph if not cached
  - `asyncio.create_task(campaign_graph.ainvoke(initial_state, config={"configurable": {"thread_id": str(campaign_id)}}))`
  - Returns 202 Accepted

#### 5B.9 — Status Route (LangGraph Version)

- [ ] `GET /api/v1/campaigns/{id}/status`:
  - `state = await campaign_graph.aget_state(config)`
  - Returns `state.values` (phase, jurisdiction_ids count, errors, next node)
  - Also returns `state.next` — what runs next

#### 5B.10 — State History Route

- [ ] `GET /api/v1/campaigns/{id}/history`:
  - `async for state in campaign_graph.aget_state_history(config):`
  - Returns chronological list of all state snapshots (time-travel debugging)
  - Paginated (last N checkpoints)

#### 5B.11 — Tests (Phase 5B)

**File:** `tests/modules/v1/campaigns/test_campaign_graph.py`

- [ ] `test_campaign_graph_compiles` — no errors on build
- [ ] `test_campaign_graph_full_flow` — mock all services, run graph end-to-end
- [ ] `test_campaign_graph_checkpoint_resume` — kill mid-execution, resume from checkpoint
- [ ] `test_campaign_graph_fan_out_discovery` — verify Send API creates N parallel tasks
- [ ] `test_campaign_graph_status_endpoint` — verify aget_state returns current phase
- [ ] `test_campaign_graph_history_endpoint` — verify state history returns checkpoints

**File:** `tests/modules/v1/campaigns/test_change_processing_graph.py`

- [ ] `test_change_low_risk_auto_accepts`
- [ ] `test_change_high_risk_interrupts`
- [ ] `test_change_regenerates_blog_after_accept`
- [ ] `test_change_triggers_seo_rebuild`

---

## 9. Phase 6 — SEO Infrastructure (Both Branches)

> **Goal:** Sitemaps, robots.txt, enhanced blog artifacts.  
> **Duration:** 5–7 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 6.1 — Sitemap Service

**File:** `app/api/utils/sitemap_service.py`

- [ ] `SitemapService` class:
  - `MAX_URLS_PER_SITEMAP = 50_000`
  - `generate_sitemap_index() -> str` — XML sitemap index pointing to children
  - `generate_sitemap(offset, limit) -> str` — single sitemap XML
  - `write_all() -> None` — query all published blogs, write to `BLOG_STATIC_DIR`
  - `write_robots_txt() -> None` — generate `robots.txt`
- [ ] Query `JurisdictionBlogPost` where `is_published=True`
- [ ] Group by industry/campaign for child sitemaps:
  - `sitemap.xml` (index)
  - `sitemap-eor.xml`
  - `sitemap-gdpr.xml`
  - etc.
- [ ] Each entry: `<url><loc>{canonical}</loc><lastmod>{updated_at}</lastmod><changefreq>weekly</changefreq></url>`
- [ ] `robots.txt`:
  ```
  User-agent: *
  Allow: /
  Sitemap: {BLOG_SITE_URL}/sitemap.xml
  ```

#### 6.2 — Sitemap Rebuild Task (Debounced)

**Add to existing Celery tasks:**

- [ ] `sitemap_rebuild_debounced` task:
  - Redis lock: `sitemap_rebuild_lock`, TTL 300s
  - If lock acquired: rebuild all sitemaps
  - If lock exists: skip (recent rebuild is sufficient)
- [ ] Wire into blog publish flow: after any `write_artifact()`, dispatch `sitemap_rebuild_debounced.delay()`

#### 6.3 — Enhanced Blog Artifacts

**Update:** `app/api/modules/v1/jurisdictions/service/blog_artifact_service.py`

- [ ] Add **Breadcrumb JSON-LD** (`BreadcrumbList` schema):
  - Walk jurisdiction hierarchy (child → parent → root)
  - Build `itemListElement` array with position, name, item URL
  - Inject into `<script type="application/ld+json">` tag

- [ ] Add **Internal Cross-Linking**:
  - Query parent jurisdiction (if exists) → link to parent blog
  - Query sibling jurisdictions → link to siblings
  - Query child jurisdictions → link to children
  - Render as `<nav class="related-jurisdictions">` at bottom of blog

- [ ] Add **`dateModified`** to Article JSON-LD:
  - Currently only has `datePublished`
  - Add `"dateModified": "{updated_at_iso}"` to existing Article schema

- [ ] Add **hreflang** tag (future i18n readiness):
  - `<link rel="alternate" hreflang="en" href="{canonical_url}">`

#### 6.4 — Tests (Phase 6)

**File:** `tests/utils/test_sitemap_service.py`

- [ ] `test_generate_sitemap_xml_structure` — valid XML with correct URL entries
- [ ] `test_generate_sitemap_index` — points to child sitemaps
- [ ] `test_sitemap_respects_50k_limit` — splits into multiple files
- [ ] `test_write_robots_txt` — correct content with sitemap URL
- [ ] `test_sitemap_rebuild_debounced` — second call within 5min skipped

**File:** `tests/modules/v1/jurisdictions/test_blog_artifact_enhanced.py`

- [ ] `test_artifact_has_breadcrumb_jsonld` — BreadcrumbList schema present
- [ ] `test_artifact_has_cross_links` — parent/sibling/child links rendered
- [ ] `test_artifact_has_date_modified` — dateModified in Article JSON-LD
- [ ] `test_artifact_has_hreflang` — hreflang tag present

---

## 10. Phase 7 — Monitoring: Celery Beat (Both Branches)

> **Goal:** Re-enable Celery Beat schedule for campaign jurisdictions with auto-accept.  
> **Duration:** 3–5 days  
> **Branch:** `feature/campaign-shared`

### Tasks

#### 7.1 — Re-enable Celery Beat Schedule

**Update:** `app/celery_app.py`

- [ ] Un-comment `dispatch_due_jurisdictions` beat entry:
  ```python
  "dispatch-due-jurisdictions-every-15-minutes": {
      "task": "...",
      "schedule": crontab(minute="*/15"),
  },
  ```
- [ ] Un-comment `monitor_stalled_jobs` beat entry:
  ```python
  "monitor-stalled-jobs": {
      "task": "...",
      "schedule": crontab(minute="*/5"),
  },
  ```

#### 7.2 — Auto-Accept Logic for Campaign Jurisdictions

**Update:** `app/api/modules/v1/scraping/service/consolidated_extraction_service.py`

- [ ] In the Day N change detection path:
  - After changes are detected, check `jurisdiction.auto_accept_changes`
  - If `True` AND `jurisdiction.campaign_id IS NOT NULL`:
    - Auto-accept all detected changes → `JurisdictionStateService.update_state()`
    - Trigger blog regeneration → `BlogGenerationService.generate_blog_post_async()`
    - Trigger artifact republish → `BlogArtifactService.write_artifact()`
    - Trigger `sitemap_rebuild_debounced.delay()`
  - If `False` (manual jurisdictions):
    - Existing behavior: create `JurisdictionChange` records, wait for human

#### 7.3 — Tests (Phase 7)

**File:** `tests/modules/v1/scraping/test_auto_accept_changes.py`

- [ ] `test_day_n_auto_accept_for_campaign_jurisdiction` — changes auto-accepted
- [ ] `test_day_n_manual_jurisdiction_unchanged` — changes require human acceptance
- [ ] `test_auto_accept_triggers_blog_regeneration`
- [ ] `test_auto_accept_triggers_artifact_republish`
- [ ] `test_auto_accept_triggers_sitemap_rebuild`

---

## 11. ~~Phase 8 — Monitoring: Parallel.ai Monitor API~~ (Removed)

> **Decision (March 1, 2026):** Phase 8 is removed. After architectural evaluation the team decided to **stick with Celery Beat** as the sole monitoring backend. Parallel.ai Monitor introduces cross-source consolidation problems (per-source webhooks break the Golden Record aggregation model), the API is alpha-unstable, and `content_hash` per-source already provides skip-if-unchanged at no extra cost. `scrape_frequency` tuning per jurisdiction is the correct cost lever — not a second monitoring stack.

---

## 12. Phase 9 — Testing + Scale Validation

> **Goal:** Validate end-to-end at increasing scale.  
> **Duration:** 7–14 days  
> **Branch:** Each approach in its own branch

### Tasks

#### 9.1 — Pilot Test (5 Countries, ~25 Jurisdictions)

- [ ] Create test campaign: industry="EOR", target_depth=STATE
- [ ] Hardcode taxonomy: US (5 states), UK (4 nations), Nigeria (6 states), Germany (3 states), India (5 states)
- [ ] Run full pipeline end-to-end
- [ ] Verify:
  - All 25+ jurisdictions created with correct hierarchy
  - Sources discovered and accepted for each
  - Day 1 scrape + auto-accept fires
  - Blog posts generated with correct content
  - Static artifacts published with breadcrumbs + cross-links
  - Sitemap generated with all URLs
  - Monitoring active (Beat or Monitor API depending on config)

#### 9.2 — Medium Scale Test (500 Jurisdictions)

- [ ] Create campaign: industry="EOR", target_depth=STATE, all major economies
- [ ] Let taxonomy generation create the full tree
- [ ] Time each phase:
  - Taxonomy generation: expected ~30s
  - Hydration: expected ~2 min
  - Source discovery: expected ~30 min (rate limited)
  - Initial scrape: expected ~2 hours
  - Blog generation: expected ~1 hour
  - Publishing: expected ~10 min
- [ ] Monitor resource usage: CPU, memory, DB connections, Redis memory
- [ ] Verify no failures in pipeline (check CampaignExecutionLog / graph checkpoints)

#### 9.3 — Large Scale Test (5,000 Jurisdictions)

- [ ] Stress test the orchestration:
  - **Celery branch:** verify chord doesn't lose track of tasks at 5K scale
  - **LangGraph branch:** verify Postgres checkpointer handles 5K concurrent nodes
- [ ] Verify DB performance: batch inserts, query times for large jurisdiction trees
- [ ] Verify Parallel.ai API handling: rate limits, error recovery
- [ ] Run cost calculator: compare actual spend vs projected

#### 9.4 — Monitoring Validation (Both Backends)

- [ ] **Celery Beat test:**
  - Set `scrape_frequency = "daily"` for test jurisdictions
  - Wait 24+ hours → verify re-scrape fires
  - Manually modify a source page → verify change detection + auto-accept + blog regen

- [ ] **Parallel.ai Monitor test (if API stable):**
  - Create 10 test monitors
  - Wait for webhook events (or trigger change manually)
  - Verify HMAC validation works
  - Verify change processing pipeline fires

#### 9.5 — Error Recovery Test

- [ ] Kill a worker mid-hydration → verify resume works
- [ ] Simulate LLM rate limit during blog generation → verify retries
- [ ] Simulate Parallel.ai API timeout during source discovery → verify skip + continue
- [ ] Simulate DB connection failure → verify task retries

---

## 13. Phase 10 — Production Launch

> **Goal:** Deploy chosen approach to production.  
> **Duration:** 5–7 days

### Tasks

#### 10.1 — Production Preparation

- [ ] Merge chosen branch into `dev`
- [ ] Create editorial Organization (one-time setup script)
- [ ] Set environment variables:
  - `PARALLEL_WEBHOOK_SECRET`
  - `PARALLEL_MONITOR_WEBHOOK_URL`
  - `CAMPAIGN_SEARCH_RATE_LIMIT`
  - `CAMPAIGN_MONITOR_BATCH_SIZE`
- [ ] Configure Nginx for sitemaps + robots.txt (see architecture doc 10.3)
- [ ] If LangGraph branch: run `await checkpointer.setup()` on production DB

#### 10.2 — Celery Worker Configuration

- [ ] Ensure all 3 worker queues are running:
  - `scraping` (gevent, 200 concurrency)
  - `processing` (prefork, 4 concurrency)
  - `persistence` (prefork, 2 concurrency)
- [ ] Enable Celery Beat with un-commented schedule entries
- [ ] Verify Beat is running: `celery -A app.celery_app beat --loglevel=info`

#### 10.3 — First Production Campaign

- [ ] Create pilot campaign: 1 industry, 3–5 countries, STATE depth
- [ ] Monitor execution in real-time via `GET /campaigns/{id}/status`
- [ ] Verify all pages publish to correct URLs
- [ ] Submit sitemap to Google Search Console
- [ ] Verify pages are indexed within 48 hours

#### 10.4 — Monitoring & Alerting

- [ ] Set up alerts for:
  - Campaign execution failures (status=FAILED)
  - Webhook delivery failures (Parallel.ai Monitor)
  - Celery task queue depth > threshold
  - Blog generation LLM errors
- [ ] Dashboard showing:
  - Total pages published
  - Changes detected this week
  - Pages regenerated this week
  - API costs (Parallel.ai + OpenRouter)

#### 10.5 — Scale Up

- [ ] After pilot success: create full-scale campaign (200+ countries, STATE depth)
- [ ] Monitor closely for first 7 days
- [ ] Tune rate limits and batch sizes based on actual performance
- [ ] Tune `scrape_frequency` per campaign jurisdiction based on content change velocity

---

## 14. Task Checklist Summary

### Shared Work (`feature/campaign-shared`)

| Phase | Task Count | Duration |
|-------|-----------|----------|
| Phase 0: Foundation Verification | 3 tasks (2/3 ✅) | ~~3–5 days~~ — 0.1 + 0.2 done |
| Phase 1: Campaign Module Core | 9 tasks (+ 11 tests) | 5–7 days |
| Phase 2: Taxonomy + Geo Validation | 5 tasks (+ 10 tests) | 7–10 days |
| Phase 3: Hydration Service | 1 task (+ 8 tests) | 5–7 days |
| Phase 4: Source Discovery | 3 tasks (+ 6 tests) | 5–7 days |
| Phase 6: SEO Infrastructure | 4 tasks (+ 9 tests) | 5–7 days |
| Phase 7: Celery Beat Monitoring | 2 tasks (+ 5 tests) | 3–5 days |
| ~~Phase 8: Monitor API~~ | ~~removed~~ | ~~7–10 days~~ |
| **Shared Total** | **27 tasks + 49 tests** | **33–48 days** |

### Celery Branch (`feature/campaign-celery`)

| Phase | Task Count | Duration |
|-------|-----------|----------|
| Phase 5A: Celery Pipeline | 7 tasks (+ 15 tests) | 10–14 days |
| Phase 9: Scale Testing | 5 tasks | 7–14 days |
| Phase 10: Production Launch | 5 tasks | 5–7 days |
| **Celery Total** | **17 tasks + 15 tests** | **22–35 days** |

### LangGraph Branch (`feature/campaign-langgraph`)

| Phase | Task Count | Duration |
|-------|-----------|----------|
| Phase 5B: LangGraph Pipeline | 11 tasks (+ 10 tests) | 14–21 days |
| Phase 9: Scale Testing | 5 tasks | 7–14 days |
| Phase 10: Production Launch | 5 tasks | 5–7 days |
| **LangGraph Total** | **21 tasks + 10 tests** | **26–42 days** |

### Grand Total

| Path | Tasks | Tests | Duration (Calendar) |
|------|-------|-------|-------------------|
| **Shared + Celery** | 44 | 64 | **~7–11 weeks** |
| **Shared + LangGraph** | 48 | 59 | **~8–12 weeks** |
| **Both approaches** (parallel dev) | 65 | 74 | **~8–12 weeks** (shared work done once) |

---

## 15. Timeline

### Sequential (One Developer)

```
Week  1-2:  Phase 0 (verification) + Phase 1 (campaign CRUD)
Week  3-4:  Phase 2 (taxonomy + geo validator)
Week  5:    Phase 3 (hydration)
Week  6:    Phase 4 (source discovery)
Week  7:    Phase 6 (SEO) + Phase 7 (Celery Beat monitoring)
Week  8-9:  Phase 5A (Celery tasks) OR Phase 5B (LangGraph)
Week 10-11: Phase 9 (scale testing)
Week 12:    Phase 10 (production launch)
```

### Parallel (2+ Developers)

```
Dev A (shared infra):                    Dev B (orchestration):
─────────────────────                    ──────────────────────
Week 1-2: Phase 0 + Phase 1             Week 1-2: (waiting for shared)
Week 3-4: Phase 2 (taxonomy)            Week 3-4: Phase 6 (SEO infra)
Week 5:   Phase 3 (hydration)           Week 5:   Phase 7 (Beat monitoring)
Week 6:   Phase 4 (source discovery)    Week 6-7: Phase 5B (LangGraph)
Week 7-8: Phase 5A (Celery tasks)       Week 7-8: Phase 9 (testing both)
Week 9-10: Phase 9 (testing both)       Week 9-10: Phase 9 (testing both)
Week 11:   Phase 10 (launch)            Week 11:   Phase 10 (launch)
```

### Critical Path

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5A/B → Phase 9 → Phase 10
                                                  ↗ (parallel)
                              Phase 6 → Phase 7
```

Phases 6–8 (SEO + monitoring) can run in parallel with Phases 3–4 (hydration + discovery) once the Campaign model exists (Phase 1 complete).

---

*Reference: [docs/CAMPAIGN_ARCHITECTURE.md](CAMPAIGN_ARCHITECTURE.md) for full technical specifications.*