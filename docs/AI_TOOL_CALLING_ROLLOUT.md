# AI Tool-Calling Rollout Guide

## Purpose

This guide defines how to roll out campaign AI planner and tool-calling safely in production.
It focuses on reliability, observability, and quick rollback.

## Current Baseline

Phase 0 baseline is now implemented:

- Campaign orchestration generates a per-run `run_id`
- `run_id` is propagated through campaign Celery tasks
- Progress events include `run_id`
- Pipeline error logs include `run_id`
- Taxonomy LLM tracking uses correlated `request_id` values derived from campaign and run context

This gives end-to-end traceability without DB schema migration.

## Runtime Flow

1. Campaign launch or resume generates a new `run_id`
2. Orchestrator stores `run_id` in `campaign.stats.pipeline_control`
3. Celery chain executes with task signatures carrying `run_id`
4. Progress events publish with `run_id`
5. If pipeline fails, `CampaignExecutionLog.error_log` stores `run_id`
6. Taxonomy generation LLM calls include correlated `request_id`

## Production Configuration

Set these environment variables explicitly in production:

- `CAMPAIGN_PIPELINE_BACKEND=celery`
- `CAMPAIGN_AI_ROLLOUT_ENABLED=true`
- `CAMPAIGN_AI_PLANNER_BACKEND=shadow`
- `CAMPAIGN_AI_TOOL_POLICY_MODE=allowlist`
- `CAMPAIGN_AI_MAX_TOOL_CALLS_PER_JURISDICTION=2`
- `CAMPAIGN_AI_TOOL_CALL_TIMEOUT_SECONDS=20`
- `CAMPAIGN_SOURCE_DISCOVERY_CONCURRENCY=5`
- `CAMPAIGN_FORCE_FAIL_AFTER_RETRIES=60`

Notes:

- Keep `CAMPAIGN_PIPELINE_BACKEND=celery` until LangGraph runner is implemented and validated.
- Start with conservative tool limits to protect latency and cost envelopes.

## Rollout Stages

### Stage 1: Shadow mode

- Keep planner backend as `shadow`
- Keep tool policy as `allowlist`
- Do not allow planner output to change execution decisions yet
- Observe behavior for at least 3-5 days

Exit criteria:

- No increase in pipeline failure rate
- No increase in stuck pipelines
- No LLM usage spikes outside budget envelope

### Stage 2: Active planner with guardrails

- Set `CAMPAIGN_AI_PLANNER_BACKEND=active`
- Keep policy `allowlist`
- Keep max calls low (`1-2`) per jurisdiction
- Ramp traffic gradually (for example 10%, 25%, 50%, 100%)

Exit criteria:

- P95 latency remains within SLO
- Pipeline success rate remains stable
- Cost per campaign stays within expected range

### Stage 3: Strict policy (optional)

- Set `CAMPAIGN_AI_TOOL_POLICY_MODE=strict`
- Use only approved tools and argument schemas

Use this stage only after enough production confidence.

## Observability and SLOs

Track these core signals:

- Campaign pipeline success rate
- Campaign pipeline retries per run
- Time to MONITORING per campaign run
- LLM total tokens and cost per run
- Task-level failure counts by phase

Recommended SLO baselines:

- Pipeline completion success >= 98%
- P95 launch-to-monitoring time <= 60 minutes
- Unexpected force-fail incidents <= 1% of runs

## Operational Queries

Use `run_id` as the primary join key across logs and events.

Examples:

- Find campaign run metadata: `campaign.stats.pipeline_control.run_id`
- Find execution errors: `campaign_execution_logs.error_log.run_id`
- Find LLM usage: `llm_usage_logs.request_id` contains campaign/run correlation pattern

## Rollback Plan

If regressions occur, rollback in this order:

1. Set `CAMPAIGN_AI_PLANNER_BACKEND=shadow`
2. If still unstable, set `CAMPAIGN_AI_ROLLOUT_ENABLED=false`
3. If needed, set `CAMPAIGN_AI_TOOL_POLICY_MODE=off`

No schema rollback is required for Phase 0.

## Incident Checklist

1. Identify affected `campaign_id` and `run_id`
2. Confirm failing phase from `CampaignExecutionLog`
3. Correlate with LLM usage by `request_id`
4. Check progress stream gaps by `run_id`
5. Decide to resume, reset, or cancel campaign
6. Capture root cause and update allowlist/policy or timeout/call limits

## Change Management

Before each rollout step:

- Announce the planned config change window
- Snapshot baseline metrics for comparison
- Define clear rollback trigger thresholds
- Verify on-call coverage for the first 24h after change
