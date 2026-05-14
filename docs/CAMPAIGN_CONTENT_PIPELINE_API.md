# Campaign Content Pipeline API

This document describes the campaign-level content pipeline added to separate blog generation
from scraping and make production recovery safer.

## What changed

The campaign workflow now has two distinct concerns:

1. Scraping and extraction, which discovers sources and builds jurisdiction state.
2. Content generation, which turns jurisdiction state into blog posts.

The campaign status endpoint now exposes both scrape and content health so operators can see
whether a campaign is truly ready, degraded, or still missing blog output.

## Status endpoint

`GET /api/v1/campaigns/{campaign_id}/status`

### Response fields

- `status`: Campaign lifecycle state, for example `MONITORING`.
- `campaign_id`: Campaign UUID.
- `taxonomy_task_id`: Original taxonomy task identifier when available.
- `run_id`: Current orchestration run identifier.
- `health`: Operational view of the campaign, one of:
  - `HEALTHY`
  - `DEGRADED`
  - `FAILED`
- `scrape_summary`: Aggregate scrape-job counts.
- `content_pipeline_status`: Latest campaign content pipeline state.
- `content_summary`: Blog-generation readiness and result summary.
- `failure`: Structured failure details when the pipeline encountered a known issue.

### Example

```json
{
  "status": "MONITORING",
  "campaign_id": "0ed17188-abb3-4459-8047-8c898d10674c",
  "taxonomy_task_id": "",
  "run_id": "f1fef7ac-e960-4452-8b84-8d056b61db74",
  "health": "DEGRADED",
  "scrape_summary": {
    "total_jobs": 88,
    "completed_jobs": 68,
    "failed_jobs": 20,
    "active_jobs": 0
  },
  "content_pipeline_status": "NOT_STARTED",
  "content_summary": {
    "total_jurisdictions": 215,
    "jurisdictions_with_state": 46,
    "blog_count": 0,
    "missing_blog_count": 46,
    "last_run_mode": "",
    "last_run_generated": 0,
    "last_run_skipped": 0,
    "last_run_failed": 0,
    "last_run_missing_state": 0,
    "eligible_jurisdictions": 46,
    "content_pipeline_status": "NOT_STARTED",
    "last_run_id": "",
    "last_error_summary": ""
  },
  "failure": {
    "category": "partial_failure",
    "error_code": "CAMPAIGN_PIPELINE_PARTIAL_FAILURE",
    "message": "Some jurisdiction tasks failed during extraction.",
    "retryable": true,
    "failed_jurisdiction_count": 20
  }
}
```

## Campaign content endpoints

### Queue a full campaign content run

`POST /api/v1/campaigns/{campaign_id}/content/run`

Queues campaign-wide blog generation for jurisdictions that have state data.

### Retry failed content jobs

`POST /api/v1/campaigns/{campaign_id}/content/retry-failed`

Retries only jurisdictions that failed in the latest campaign content run.

### Backfill missing blogs

`POST /api/v1/campaigns/{campaign_id}/content/backfill-missing`

Generates blogs for jurisdictions that already have state but do not yet have a blog row.

## Content progress UX contract

### Real-time stream (SSE)

Use the existing stream endpoint:

`GET /api/v1/campaigns/{campaign_id}/progress-stream`

Content generation now emits `phase = "content_generation"` events on the same stream with:

- `run_id`
- `status` (`IN_PROGRESS`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`)
- `mode`
- `completed`
- `total`
- `failed`
- `skipped`
- `pct`
- `ts`

### Polling fallback

Use:

`GET /api/v1/campaigns/{campaign_id}/status`

The payload includes `content_pipeline_status` and `content_summary` fields suitable for fallback
polling when SSE disconnects.

## Blog listing endpoint

`GET /api/v1/campaigns/{campaign_id}/blogs`

This endpoint still returns the actual blog rows for the campaign. If it is empty, the campaign
has no persisted `jurisdiction_blog_posts` rows yet.

## Operational guidance

- Use `GET /status` first to decide whether the problem is scraping or content generation.
- Prefer SSE for UX smoothness and use `/status` polling as reconnect fallback.
- If `scrape_summary.failed_jobs > 0`, retry failed scrape jobs before expecting complete blog coverage.
- If `content_summary.missing_blog_count > 0` and there is jurisdiction state, run
  `POST /content/backfill-missing`.
- If `content_pipeline_status` is `FAILED` or `COMPLETED_WITH_ERRORS`, use
  `POST /content/retry-failed` to rerun only the failed content slice.

## Recommended recovery flow

1. Check `GET /api/v1/campaigns/{campaign_id}/status`.
2. If scrape failures exist, run `POST /api/v1/campaigns/{campaign_id}/retry-failed-jobs`.
3. Run `POST /api/v1/campaigns/{campaign_id}/content/backfill-missing`.
4. Re-check `GET /status` until `health` is `HEALTHY` or only intentionally deferred
   jurisdictions remain.
5. Confirm `GET /api/v1/campaigns/{campaign_id}/blogs` returns the expected blog rows.
