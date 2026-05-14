# Architecture Review: Jurisdiction Scraping & Campaign Pipeline

**Date:** 2026-05-04
**Scope:** Jurisdiction scraping module + Campaign orchestration pipeline
**Severity Levels:** Critical (system-breaking), High (degradation), Medium (scalability)

---

## Executive Summary

This audit examined the jurisdiction scraping and campaign design implementations across 8 core files. **23 issues** were identified:

- **6 Critical** — Will cause data corruption, deadlocks, or worker starvation in production
- **6 High** — Severe performance degradation and resource leaks
- **11 Medium** — Design flaws that compound under scale

The most urgent issues are: **N+1 commit patterns**, **60-minute busy-poll blocking workers**, **unsafe Redis lock release**, and **N+1 database queries** in the blog generation task. These will manifest within days of running at scale (100+ jurisdictions, 2+ concurrent campaigns).

---

## Issue #1: `dispatch_due_jurisdictions` — N+1 Commit Pattern

**Severity:** CRITICAL
**File:** `tasks.py:696-707`
**Impact:** Partial dispatch, no rollback, I/O bottleneck

### Problem
Each jurisdiction is committed individually inside the dispatch loop. If jurisdiction #7 fails, jurisdictions 1-6 are already committed and their scrapes are dispatched. No atomicity.

```python
for jurisdiction in jurisdictions:
    service.trigger_jurisdiction_scrape(jurisdiction.id)
    jurisdiction.next_scrape_time = next_time
    jurisdiction.last_scraped_at = now
    db.add(jurisdiction)
    db.commit()  # ← COMMIT INSIDE LOOP
```

At 10 jurisdictions = 10 disk flushes. At 100 = 100. Each `commit()` forces a WAL (write-ahead log) flush to disk.

### Fix: Single Commit with Partial Failure Tracking

```python
# BEFORE (tasks.py:696-707)
for jurisdiction in jurisdictions:
    service.trigger_jurisdiction_scrape(jurisdiction.id)
    jurisdiction.next_scrape_time = next_time
    jurisdiction.last_scraped_at = now
    db.add(jurisdiction)
    db.commit()

# AFTER
dispatched = []
for jurisdiction in jurisdictions:
    try:
        service.trigger_jurisdiction_scrape(jurisdiction.id)
        jurisdiction.next_scrape_time = next_time
        jurisdiction.last_scraped_at = now
        db.add(jurisdiction)
        dispatched.append(jurisdiction)
    except Exception as e:
        logger.error(f"Failed to dispatch jurisdiction {jurisdiction.id}: {e}", exc_info=True)

if dispatched:
    db.commit()  # ← SINGLE COMMIT after all dispatches
```

**Estimated Impact:** 10 jurisdictions: ~50ms → ~5ms. 100 jurisdictions: ~500ms → ~5ms. Eliminates partial dispatch race condition.

---

## Issue #2: `check_batch_completion` — Double Query Anti-Pattern

**Severity:** CRITICAL
**File:** `jurisdiction_scraping_service.py:240-245`
**Impact:** Wasted DB queries, race window

### Problem
The identical query is executed twice — once before calculating the content hash, and immediately after. The first result set is discarded.

```python
completed_jobs = self.db.exec(select(ScrapeJob)...).all()  # Query 1

# ... calculates hash using completed_jobs ...

completed_jobs = self.db.exec(select(ScrapeJob)...).all()  # Query 2 — SAME QUERY
```

### Fix: Reuse the First Result Set

```python
# BEFORE
completed_jobs = self.db.exec(
    select(ScrapeJob).where(
        ScrapeJob.jurisdiction_scrape_job_id == jurisdiction_job_id,
        ScrapeJob.status == ScrapeJobStatus.COMPLETED,
    )
).all()

if not completed_jobs:
    # ... handle failure ...

completed_jobs = self.db.exec(
    select(ScrapeJob).where(
        ScrapeJob.jurisdiction_scrape_job_id == jurisdiction_job_id,
        ScrapeJob.status == ScrapeJobStatus.COMPLETED,
    )
).all()  # ← REDUNDANT

jurisdiction = self.db.get(Jurisdiction, job.jurisdiction_id)
job.content_hash = calculate_jurisdiction_content_hash(completed_jobs, jurisdiction_prompt)

# AFTER
completed_jobs = self.db.exec(
    select(ScrapeJob).where(
        ScrapeJob.jurisdiction_scrape_job_id == jurisdiction_job_id,
        ScrapeJob.status == ScrapeJobStatus.COMPLETED,
    )
).all()

if not completed_jobs:
    # ... handle failure ...

jurisdiction = self.db.get(Jurisdiction, job.jurisdiction_id)
jurisdiction_prompt = (jurisdiction.prompt if jurisdiction else None) or ""
job.content_hash = calculate_jurisdiction_content_hash(completed_jobs, jurisdiction_prompt)
```

**Estimated Impact:** Eliminates 1 redundant query per batch completion. At 500 batch completions/day → 500 fewer queries/day.

---

## Issue #3: `_dispatch_sources` — Commit Per Source

**Severity:** CRITICAL
**File:** `jurisdiction_scraping_service.py:152`
**Impact:** Orphaned scrape jobs, inconsistent state

### Problem
Each source gets its own commit + Celery task dispatch. If source #15 fails to dispatch, sources 1-14 are already committed and running. The jurisdiction job shows `total_sources=N` but only N-15 actually dispatched.

```python
for source in sources:
    self.db.add(scrape_job)
    self.db.add(source)
    self.db.commit()  # ← PER-SOURCE COMMIT
    celery_app.send_task(...)
```

### Fix: Batch Commit, Then Dispatch

```python
# BEFORE
for source in sources:
    scrape_job = ScrapeJob(...)
    self.db.add(scrape_job)
    source.next_scrape_time = ...
    self.db.add(source)
    self.db.commit()
    celery_app.send_task(...)

# AFTER
jobs_to_dispatch = []
for source in sources:
    scrape_job_id = uuid4()
    scrape_job = ScrapeJob(
        id=scrape_job_id,
        source_id=source.id,
        jurisdiction_scrape_job_id=job.id,
        status=ScrapeJobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    self.db.add(scrape_job)
    if source.scrape_frequency:
        source.next_scrape_time = self._calculate_next_scrape_time(
            datetime.now(timezone.utc), source.scrape_frequency
        )
        self.db.add(source)
    jobs_to_dispatch.append((str(source.id), str(scrape_job_id)))

self.db.commit()  # ← SINGLE COMMIT for all sources

for source_id, job_id in jobs_to_dispatch:
    celery_app.send_task(
        "app.api.modules.v1.scraping.service.tasks.scrape_source_stage1",
        args=[source_id, job_id],
        queue="scraping",
    )
```

**Estimated Impact:** 20 sources: 20 commits → 1 commit. Eliminates orphaned scrape jobs. Reduces DB I/O by ~95%.

---

## Issue #4: `dispatch_campaign_scrapes_task` — Synchronous Serial Dispatch

**Severity:** CRITICAL
**File:** `campaign_tasks.py:656-665`
**Impact:** Blocks processing worker for minutes

### Problem
A single Celery `prefork` worker (concurrency=4) dispatches ALL jurisdiction scrapes sequentially. 500 jurisdictions × ~50ms each = 25 seconds of blocking. During this time, the worker cannot process any other tasks.

```python
for jurisdiction in eligible_jurisdictions:
    try:
        service.trigger_jurisdiction_scrape(jurisdiction.id)  # Sync, serial
        dispatched_count += 1
    except Exception as ex:
        logger.warning(...)
```

### Fix: Batch Dispatch with `send_task` (No DB Round-Trips in Loop)

```python
# BEFORE
for jurisdiction in eligible_jurisdictions:
    service.trigger_jurisdiction_scrape(jurisdiction.id)  # Creates DB records synchronously

# AFTER — use bulk insert + async dispatch
jurisdiction_ids = [j.id for j in eligible_jurisdictions]
# Bulk trigger via service method that uses bulk insert
dispatched = service.trigger_batch_scrapes(jurisdiction_ids)
dispatched_count = len(dispatched)
```

Alternatively, dispatch asynchronously without waiting for each trigger:

```python
from celery import group

tasks = group(
    dispatch_single_jurisdiction_scrape.s(str(j.id))
    for j in eligible_jurisdictions
)
result = tasks.apply_async(queue="processing")
dispatched_count = len(eligible_jurisdictions)
```

**Estimated Impact:** 500 jurisdictions: ~25s blocking → ~2s. Processing queue freed for other tasks.

---

## Issue #5: `publish_campaign_blogs_task` — 60-Minute Busy Poll

**Severity:** CRITICAL
**File:** `campaign_tasks.py:707`
**Impact:** Blocks ALL processing workers with 2+ concurrent campaigns

### Problem
This task polls the database every 30 seconds for up to 60 minutes (`max_retries=120, default_retry_delay=30`). It holds a Celery worker slot the entire time. With `concurrency=4` on the processing queue, a single campaign consumes 25% of worker capacity for an hour.

```python
@celery_app.task(bind=True, queue="processing", max_retries=120, default_retry_delay=30)
def publish_campaign_blogs_task(self, campaign_id, run_id=None):
    active_jobs = db.exec(select(JurisdictionScrapeJob)...).all()
    if active_jobs:
        raise self.retry(countdown=30)  # ← BUSY POLL
```

### Fix: Adaptive Polling Based on Job Stage

```python
@celery_app.task(bind=True, queue="processing", max_retries=24, default_retry_delay=60)
def publish_campaign_blogs_task(self, campaign_id, run_id=None):
    with SyncSessionLocal() as db:
        active_jobs = db.exec(
            select(JurisdictionScrapeJob)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionScrapeJob.jurisdiction_id)
            .where(Jurisdiction.campaign_id == UUID(campaign_id))
            .where(JurisdictionScrapeJob.status.notin_([COMPLETED, FAILED]))
        ).all()

        if active_jobs:
            # Check if any are still in early stages (SCRAPING, FILTERING, etc.)
            # If all are in late stages (CONSOLIDATING, ANALYZING), poll more aggressively
            late_stage_statuses = {CONSOLIDATING, FILTERING, ANALYZING}
            all_late = all(j.status in late_stage_statuses for j in active_jobs)

            if all_late:
                raise self.retry(countdown=10)  # Fast poll for late stages
            raise self.retry(countdown=60)  # Slow poll for early stages

        # Finalize campaign...
```

**Estimated Impact:** Processing queue freed from 25% → ~2% utilization per campaign. 5 campaigns no longer cause total queue starvation.

---

## Issue #6: `_reset_campaign_for_discovery_retry` — Zombie Campaign State

**Severity:** CRITICAL
**File:** `campaign_tasks.py:184-220`
**Impact:** Campaign stuck in `DISCOVERING_SOURCES` with no running task

### Problem
Status is reset BEFORE the retry fires. If the worker crashes between the reset and the retry, the campaign is in `DISCOVERING_SOURCES` state with no task running. The orchestration service's idempotency guard won't catch this because there are no `task_ids` in `pipeline_control`.

```python
def _reset_campaign_for_discovery_retry(campaign_id):
    campaign.status = CampaignStatus.DISCOVERING_SOURCES
    db.commit()  # ← Status reset before retry fires
    raise self.retry(exc=e, countdown=120)  # ← If worker crashes here, campaign is ZOMBIE
```

### Fix: Reset AFTER Retry is Enqueued

```python
# BEFORE
except SoftTimeLimitExceeded as e:
    _reset_campaign_for_discovery_retry(campaign_id)
    raise self.retry(exc=e, countdown=120)

# AFTER
except SoftTimeLimitExceeded as e:
    result = self.retry(exc=e, countdown=120)  # Retry is enqueued first
    _reset_campaign_for_discovery_retry(campaign_id)  # Reset after enqueue succeeds
    raise result
```

**OR** use a separate recovery mechanism:

```python
# Add a "zombie detection" Celery Beat task that finds campaigns stuck in
# DISCOVERING_SOURCES for > CAMPAIGN_SOURCE_DISCOVERY_HARD_TIME_LIMIT_SECONDS
# and restarts them.

@celery_app.task(bind=True)
def detect_zombie_campaigns(self):
    with SyncSessionLocal() as db:
        threshold = datetime.now(timezone.utc) - timedelta(
            seconds=settings.CAMPAIGN_SOURCE_DISCOVERY_HARD_TIME_LIMIT_SECONDS + 300
        )
        zombies = db.exec(
            select(Campaign).where(
                Campaign.status == CampaignStatus.DISCOVERING_SOURCES,
                Campaign.updated_at <= threshold,
            )
        ).all()
        for z in zombies:
            logger.warning(f"Zombie campaign detected: {z.id}, restarting")
            CampaignOrchestrationService(db).run(str(z.id))
```

**Estimated Impact:** Eliminates zombie campaigns. Recovery task catches any edge cases.

---

## Issue #7: `generate_campaign_content_task` — N+1 Query Catastrophe

**Severity:** HIGH
**File:** `campaign_tasks.py:394-430`
**Impact:** 1,001 queries for 500 jurisdictions → minutes of latency

### Problem
For each jurisdiction, two separate queries are executed — one for blog post check and one for state check. This is inside a Python loop, not batched.

```python
all_jurs = db.exec(jurisdiction_stmt).all()  # Query 1

for j in all_jurs:
    db.exec(select(JurisdictionBlogPost.id).where(...)).first()  # Query 2 per jur
    db.exec(select(JurisdictionState.jurisdiction_id).where(...)).first()  # Query 3 per jur
```

500 jurisdictions → 1 + (500 × 2) = **1,001 queries**.

### Fix: Single JOIN Query

```python
# BEFORE
target_ids = [
    j.id for j in all_jurs
    if (db.exec(select(JurisdictionState.jurisdiction_id).where(...)).first())
    and not db.exec(select(JurisdictionBlogPost.id).where(...)).first()
]

# AFTER — single query with LEFT OUTER JOIN
from sqlalchemy.orm import joinedload

stmt = (
    select(Jurisdiction.id)
    .outerjoin(JurisdictionState, JurisdictionState.jurisdiction_id == Jurisdiction.id)
    .outerjoin(JurisdictionBlogPost, JurisdictionBlogPost.jurisdiction_id == Jurisdiction.id)
    .where(Jurisdiction.campaign_id == UUID(campaign_id))
    .where(JurisdictionState.jurisdiction_id.isnot(None))  # Has state
    .where(JurisdictionBlogPost.id.is_(None))  # No blog post
)
target_ids = [row for row in db.exec(stmt).all()]
```

**Estimated Impact:** 500 jurisdictions: 1,001 queries (~5s) → 1 query (~50ms). **100x improvement**.

---

## Issue #8: `_get_previous_completed_job` — Missing Composite Index

**Severity:** HIGH
**File:** `consolidated_extraction_service.py:683-692`
**Impact:** Full table scan on every consolidation

### Problem
Query filters by `jurisdiction_id` + `status`, then sorts by `completed_at DESC`. Without a composite index, PostgreSQL does a full table scan + sort.

```python
stmt = (
    select(JurisdictionScrapeJob)
    .where(
        JurisdictionScrapeJob.jurisdiction_id == current_job.jurisdiction_id,
        JurisdictionScrapeJob.id != current_job.id,
        JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
    )
    .order_by(JurisdictionScrapeJob.completed_at.desc())
)
```

### Fix: Add Migration for Composite Index

```python
# alembic/versions/XXXX_add_composite_index_on_jurisdiction_scrape_jobs.py

def upgrade():
    op.create_index(
        "ix_jurisdiction_scrape_jobs_jurisdiction_status_completed",
        "jurisdiction_scrape_jobs",
        ["jurisdiction_id", "status", "completed_at"],
    )

def downgrade():
    op.drop_index("ix_jurisdiction_scrape_jobs_jurisdiction_status_completed")
```

**Estimated Impact:** Full table scan (~50ms on 10K rows) → index seek (~1ms). **50x improvement**.

---

## Issue #9: `_gather_content` — Sequential MinIO Fetches

**Severity:** HIGH
**File:** `consolidated_extraction_service.py:281-319`
**Impact:** 2+ seconds of sequential I/O per jurisdiction

### Problem
Content is fetched from MinIO one source at a time. 10 sources × 200ms each = 2 seconds of sequential network I/O.

```python
for sj in completed_jobs:
    content_bytes = minio_storage.get_content_from_minio(...)  # Sequential
```

### Fix: Parallel Fetch with ThreadPoolExecutor

```python
# BEFORE
for sj in completed_jobs:
    content_bytes = minio_storage.get_content_from_minio(...)

# AFTER
from concurrent.futures import ThreadPoolExecutor, as_completed

def _fetch_source_content(sj):
    if sj.result and isinstance(sj.result, dict):
        minio_key = sj.result.get("minio_key")
        if minio_key:
            return minio_storage.get_content_from_minio(...)
    return None

results = []
with ThreadPoolExecutor(max_workers=min(10, len(completed_jobs))) as executor:
    futures = {executor.submit(_fetch_source_content, sj): sj for sj in completed_jobs}
    for future in as_completed(futures):
        sj = futures[future]
        try:
            content_bytes = future.result()
            if content_bytes:
                # ... build result dict ...
        except Exception as e:
            logger.warning(f"Failed to load content for source {sj.source_id}: {e}")
```

**Estimated Impact:** 10 sources × 200ms sequential (2s) → parallel (~200ms). **10x improvement**.

---

## Issue #10: `Stage1ScrapingService.execute` — Unsafe Redis Lock Release

**Severity:** HIGH
**File:** `stage1_scraping_service.py:424-437`
**Impact:** Can delete another worker's lock, causing double-scraping

### Problem
Lock release uses GET then DELETE (two separate operations). Between GET and DELETE, the lock can expire and another worker acquires it. Then your DELETE deletes the NEW worker's lock.

```python
@staticmethod
def _release_lock(redis_client, lock_key, lock_value):
    current_value = redis_client.get(lock_key)  # ← Step 1: GET
    if current_value == lock_value:
        redis_client.delete(lock_key)  # ← Step 2: DELETE (not atomic!)
```

### Fix: Atomic Release with Lua Script

```python
# BEFORE
current_value = redis_client.get(lock_key)
if current_value == lock_value:
    redis_client.delete(lock_key)

# AFTER
_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""

@staticmethod
def _release_lock(redis_client, lock_key, lock_value):
    redis_client.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, lock_value)
```

**Estimated Impact:** Eliminates race condition where two workers scrape the same source simultaneously.

---

## Issue #11: `CampaignSourceDiscoveryService` — Sleep Serializes Persistence

**Severity:** HIGH
**File:** `campaign_source_discovery_service.py:312-317`
**Impact:** 250 seconds of wasted idle time for 500 jurisdictions

### Problem
A 0.5s sleep is applied between each jurisdiction during the **persistence** phase, not during the discovery phase where rate limiting is needed. This serializes what should be a fast DB write operation.

```python
for idx, jur_snap in enumerate(jurisdiction_snapshots):
    # ... process jurisdiction (DB writes only, no external API calls) ...
    await asyncio.sleep(delay_seconds)  # ← Unnecessary sleep during persistence
```

### Fix: Remove Sleep from Persistence, Keep It in Discovery

```python
# BEFORE
for idx, jur_snap in enumerate(jurisdiction_snapshots):
    await self._persist_jurisdiction_sources(jur_snap)
    await asyncio.sleep(delay_seconds)

# AFTER
# Batch persist all results without sleep
for jur_snap in jurisdiction_snapshots:
    await self._persist_jurisdiction_sources(jur_snap)
# Sleep only during the discovery phase (external API calls), not persistence
```

**Estimated Impact:** 500 jurisdictions × 0.5s = 250s → ~5s (DB writes only). **50x improvement**.

---

## Issue #12: `ConsolidatedExtractionService.execute` — Multi-Commit Without Savepoints

**Severity:** HIGH
**File:** `consolidated_extraction_service.py:79-97`
**Impact:** Job stuck in intermediate state on failure

### Problem
Three separate commits for status updates (FILTERING → CONSOLIDATING → ANALYZING). If the LLM analysis fails at step 3, the job is stuck in `ANALYZING` with no way to know it was interrupted.

```python
job.status = JurisdictionScrapeJobStatus.FILTERING; self.db.commit()  # Commit 1
job.status = JurisdictionScrapeJobStatus.CONSOLIDATING; self.db.commit()  # Commit 2
job.status = JurisdictionScrapeJobStatus.ANALYZING; self.db.commit()  # Commit 3
```

### Fix: Single Commit for Status Progression

```python
# BEFORE — three commits
job.status = FILTERING; self.db.commit()
filtered_items = self._filter_content(...)
job.status = CONSOLIDATING; self.db.commit()
consolidated_text = self._consolidate_content(filtered_items)
job.status = ANALYZING; self.db.commit()

# AFTER — single commit after all prep work
job.status = FILTERING  # Track internally, don't commit yet
filtered_items = self._filter_content(content_items, jurisdiction.prompt if jurisdiction else "")
job.filtered_sources = len(content_items) - len(filtered_items)
consolidated_text = self._consolidate_content(filtered_items)

# Only commit once, right before the expensive LLM call
job.status = JurisdictionScrapeJobStatus.ANALYZING
self.db.add(job)
self.db.commit()

analysis_result = self.llm_service.run_consolidated_analysis(consolidated_text, ...)
```

**Estimated Impact:** 3 commits → 1 commit. Job always in a consistent state (either FILTERING or ANALYZING).

---

## Issue #13: `_consolidate_content` — Arbitrary Token Limit Drops Sources

**Severity:** MEDIUM
**File:** `consolidated_extraction_service.py:334`
**Impact:** Critical regulatory sources silently dropped

### Problem
Sources past 100K tokens are silently dropped. Sources are sorted alphabetically by URL, not by relevance or importance.

```python
MAX_TOKENS = 100000
sorted_items = sorted(items, key=lambda x: x.get("source_url", ""))  # ← Alphabetical, not by relevance
for idx, item in enumerate(sorted_items, 1):
    if current_tokens + block_tokens > MAX_TOKENS:
        break  # ← Silently drops remaining sources
```

### Fix: Prioritize Sources by Importance

```python
# BEFORE — alphabetical sort
sorted_items = sorted(items, key=lambda x: x.get("source_url", ""))

# AFTER — prioritize by source type/authority
def _source_priority(item):
    url = item.get("source_url", "")
    # Official sources get higher priority
    if ".gov" in url:
        return 0  # Highest priority
    elif ".org" in url:
        return 1
    else:
        return 2

sorted_items = sorted(items, key=lambda x: (_source_priority(x), x.get("source_url", "")))
```

**Estimated Impact:** Ensures .gov sources are never dropped. Reduces risk of missing critical regulatory changes.

---

## Issue #14: `CampaignOrchestrationService.run` — Unbounded Stats JSONB Growth

**Severity:** MEDIUM
**File:** `campaign_orchestration_service.py:343-350`
**Impact:** Slows down every campaign query over time

### Problem
Every pipeline run appends metadata to `campaign.stats` (JSONB column). With retries, resets, and re-runs, this grows unbounded. PostgreSQL JSONB has a 1GB limit, but even at 100KB it slows queries.

### Fix: Trim Old Pipeline Control Data

```python
# In CampaignOrchestrationService.run():
stats = campaign.stats or {}
pipeline_control = stats.get("pipeline_control", {})

# Keep only the last 5 runs of metadata
if "run_history" not in pipeline_control:
    pipeline_control["run_history"] = []
pipeline_control["run_history"].append({
    "run_id": run_id,
    "task_ids": task_ids,
    "timestamp": datetime.now(timezone.utc).isoformat(),
})
pipeline_control["run_history"] = pipeline_control["run_history"][-5:]  # ← Trim to last 5

campaign.stats = stats
```

**Estimated Impact:** Keeps stats under 10KB regardless of retry count.

---

## Issue #15: `discover_sources_task` — Redis Connection Pool Leaks

**Severity:** MEDIUM
**File:** `campaign_tasks.py:54-63, 153-169`
**Impact:** Hundreds of leaked Redis connections under load

### Problem
Every task invocation creates a new async Redis connection pool with 20 connections. If the task crashes before `aclose()`, those connections leak.

```python
async def run() -> dict:
    async_redis = _make_async_redis_client()  # Creates new pool (20 conns)
    try:
        # ... work ...
    finally:
        await async_redis.aclose()  # ← Only closed if try succeeds
```

### Fix: Use the Global Pool

```python
# BEFORE — new pool per task
async_redis = _make_async_redis_client()

# AFTER — reuse global pool
async_redis = aioredis.Redis(connection_pool=_async_progress_pool)
```

Create a shared async pool at module level:

```python
_async_progress_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
    socket_connect_timeout=5,
    socket_timeout=5,
)
```

**Estimated Impact:** Eliminates connection leaks. 100 concurrent campaigns: 2,000 leaked connections → 0.

---

## Issue #16: `Jurisdiction` Model — Missing Composite Index

**Severity:** MEDIUM
**File:** `jurisdiction_model.py`
**Impact:** Bitmap scan instead of index seek

### Problem
Both `campaign_id` and `discovery_status` have individual indexes, but the common query uses both:
```sql
WHERE campaign_id = X AND discovery_status = 'DISCOVERED'
```
PostgreSQL can't efficiently combine two individual indexes for this — it does a bitmap scan.

### Fix: Add Composite Index Migration

```python
# alembic/versions/XXXX_add_jurisdiction_composite_index.py
def upgrade():
    op.create_index(
        "ix_jurisdictions_campaign_discovery",
        "jurisdictions",
        ["campaign_id", "discovery_status"],
    )

def downgrade():
    op.drop_index("ix_jurisdictions_campaign_discovery")
```

**Estimated Impact:** Bitmap scan (~10ms on 10K rows) → index seek (~1ms). **10x improvement**.

---

## Issue #17: `ScrapeJob` — Missing Index for Batch Completion

**Severity:** MEDIUM
**Impact:** Full scan on every batch completion check

### Problem
`check_batch_completion` queries by `jurisdiction_scrape_job_id` + `status` but there's no covering index.

### Fix: Add Composite Index

```python
def upgrade():
    op.create_index(
        "ix_scrape_jobs_jurisdiction_job_status",
        "scrape_jobs",
        ["jurisdiction_scrape_job_id", "status"],
    )
```

**Estimated Impact:** Full scan → index seek. ~10ms → ~1ms per batch completion check.

---

## Issue #18: `_send_jurisdiction_notifications` — N+1 Notifications

**Severity:** MEDIUM
**File:** `consolidated_extraction_service.py:1036-1090`
**Impact:** 20 DB commits + sync email sends per jurisdiction

### Problem
For each user: create notification → commit → send email → update notification → commit. 10 users = 20 commits + 10 synchronous email sends, all within the consolidation task.

```python
for project_user in project_users:
    notification = Notification(...)
    self.db.add(notification)
    self.db.commit()  # ← Commit 1
    syncify(send_email)(...)  # ← Sync email blocks Celery worker
    notification.status = NotificationStatus.SENT
    self.db.add(notification)
    self.db.commit()  # ← Commit 2
```

### Fix: Batch Create, Async Email

```python
# BEFORE
for project_user in project_users:
    notification = Notification(...)
    self.db.add(notification)
    self.db.commit()
    syncify(send_email)(...)
    notification.status = SENT
    self.db.add(notification)
    self.db.commit()

# AFTER
notifications = []
for project_user in project_users:
    user = self.db.get(User, project_user.user_id)
    if not user:
        continue
    notification = Notification(
        user_id=user.id,
        notification_type=NotificationType.CHANGE_DETECTED,
        title=notification_title,
        message=change_summary,
        jurisdiction_id=jurisdiction.id,
        organization_id=project.org_id,
        action_url=action_url,
        status=NotificationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    notifications.append((notification, user.email))
    self.db.add(notification)

self.db.commit()  # ← SINGLE COMMIT for all notifications

# Send emails asynchronously (don't block consolidation)
for notification, email in notifications:
    try:
        success = syncify(send_email)(...)
        notification.status = NotificationStatus.SENT if success else NotificationStatus.FAILED
    except Exception:
        notification.status = NotificationStatus.FAILED
    notification.sent_at = datetime.now(timezone.utc)

self.db.commit()  # ← SINGLE COMMIT for all updates
```

**Estimated Impact:** 10 users: 20 commits → 2 commits. Consolidation task freed from email blocking.

---

## Issue #19: `CampaignHydrationService` — IntegrityError Swallowing

**Severity:** MEDIUM
**File:** `campaign_hydration_service.py:229-240`
**Impact:** Masks real constraint violations

### Problem
Catches `IntegrityError` on the `begin_nested()` call itself, not on the insert. This masks any constraint violation during savepoint creation.

```python
try:
    async with nested_ctx:
        pass
except IntegrityError:
    logger.debug("Ignored begin_nested integrity error...")  # ← Swallows ALL IntegrityErrors
```

### Fix: Only Swallow Duplicate Key Errors on Insert

```python
# BEFORE
try:
    async with nested_ctx:
        pass
except IntegrityError:
    logger.debug("Ignored begin_nested integrity error...")

# AFTER
try:
    async with nested_ctx:
        # Actual insert here
        await db.execute(insert_stmt)
except IntegrityError as e:
    if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
        logger.debug("Idempotent skip: jurisdiction already exists")
    else:
        raise  # Re-raise non-idempotency errors
```

**Estimated Impact:** Real constraint violations are no longer silently swallowed.

---

## Issue #20: `ScrapeJob.result` — Unbounded JSON Field

**Severity:** MEDIUM
**Impact:** 1.8GB of JSON data over 1 year

### Problem
The `result` field stores entire scrape responses. At 10K sources × daily scrapes × 365 days = 3.65M rows. With JSON payloads averaging 500 bytes → ~1.8GB.

### Fix: Archive Old Results

```python
# Option A: Only store essential fields
job.result = {
    "content_hash": content_hash,
    "minio_key": minio_key,
    "status": "scraped",
}
# Don't store full response content in result

# Option B: Add a periodic cleanup task
@celery_app.task(bind=True)
def archive_old_scrape_results(self):
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    old_jobs = db.exec(
        select(ScrapeJob).where(
            ScrapeJob.completed_at <= cutoff,
            ScrapeJob.result.isnot(None),
        )
    ).all()
    for job in old_jobs:
        job.result = {
            "content_hash": job.result.get("content_hash"),
            "minio_key": job.result.get("minio_key"),
        }
    db.commit()
```

**Estimated Impact:** Keeps result field under 200 bytes per row. 1.8GB → ~700MB over 1 year.

---

## Issue #21: No Checkpoint/Resume on Celery Chain

**Severity:** MEDIUM
**Impact:** Wasted API calls on retry

### Problem
If discovery partially succeeds (200/500 jurisdictions done) and the worker crashes, the retry re-runs discovery for ALL jurisdictions.

### Fix: Track Per-Jurisdiction Progress

```python
# Store completed jurisdiction IDs in Redis during discovery
async def _persist_jurisdiction_sources(self, jur_snap):
    # ... persist to DB ...
    # Mark as completed in Redis
    await self.redis.sadd(f"campaign_discovery_done:{self.campaign_id}", str(jur_snap.jurisdiction_id))

# On retry, skip already-done jurisdictions
async def discover_all(self, campaign_id):
    done_ids = await self.redis.smembers(f"campaign_discovery_done:{campaign_id}")
    jurisdictions_to_discover = [
        j for j in all_jurisdictions
        if str(j.id) not in done_ids
    ]
```

**Estimated Impact:** 200/500 jurisdictions done + crash → only 300 re-discovered instead of 500. 40% API cost savings.

---

## Issue #22: No Backpressure on Scraping Queue

**Severity:** MEDIUM
**Impact:** Scraping queue floods, processing queue starved

### Problem
`dispatch_due_jurisdictions` fires and dispatches 50 jurisdictions × 10 sources = 500 tasks to the scraping queue instantly. The gevent pool (concurrency=200) handles 200, 300 queue up. Meanwhile the processing queue (concurrency=4) is starved.

### Fix: Rate-Limited Dispatch

```python
# In _dispatch_sources:
MAX_PENDING_PER_QUEUE = 100

# Check queue depth before dispatching
queue_depth = self.redis.llen("celery:scraping")  # Approximate
if queue_depth > MAX_PENDING_PER_QUEUE:
    # Re-schedule dispatch for later
    celery_app.send_task(
        "app.api.modules.v1.scraping.service.tasks.dispatch_single_jurisdiction_scrape",
        args=[str(jurisdiction_id)],
        queue="processing",
        countdown=60,  # Retry in 60s
    )
    return
```

**Estimated Impact:** Scraping queue depth: 500 → ~200. Processing queue no longer starved.

---

## Issue #23: `_filter_content` — Sequential LLM Calls

**Severity:** MEDIUM
**File:** `consolidated_extraction_service.py:321-328`
**Impact:** 30+ seconds for 10 sources

### Problem
Each source is filtered through the LLM sequentially. 10 sources × 3s per call = 30 seconds.

```python
def _filter_content(self, items, prompt):
    filtered = []
    for item in items:
        is_relevant = self.llm_service.check_source_relevance(item["content"], prompt)
        if is_relevant:
            filtered.append(item)
```

### Fix: Parallel LLM Calls

```python
# BEFORE
for item in items:
    is_relevant = self.llm_service.check_source_relevance(item["content"], prompt)

# AFTER
from concurrent.futures import ThreadPoolExecutor

def _check_relevance(item):
    is_relevant = self.llm_service.check_source_relevance(item["content"], prompt)
    return (item, is_relevant)

filtered = []
with ThreadPoolExecutor(max_workers=min(5, len(items))) as executor:
    results = list(executor.map(_check_relevance, items))
    for item, is_relevant in results:
        if is_relevant:
            filtered.append(item)
```

**Estimated Impact:** 10 sources × 3s sequential (30s) → parallel (~6s with 5 workers). **5x improvement**.

---

## Missing Indexes Summary

| Table | Missing Index | Query Pattern | Current | After Fix |
|-------|--------------|---------------|---------|-----------|
| `scrape_jobs` | `(jurisdiction_scrape_job_id, status)` | `check_batch_completion` | Full scan ~10ms | Index seek ~1ms |
| `jurisdiction_scrape_jobs` | `(jurisdiction_id, status, completed_at DESC)` | `_get_previous_completed_job` | Scan+sort ~50ms | Index seek ~1ms |
| `jurisdictions` | `(campaign_id, discovery_status)` | `dispatch_campaign_scrapes_task` | Bitmap scan ~10ms | Index seek ~1ms |
| `jurisdictions` | `(next_scrape_time, enable_auto_scrape, is_deleted)` | `dispatch_due_jurisdictions` | Partial scan | Covering index |
| `sources` | `(jurisdiction_id, is_active, is_deleted)` | `trigger_jurisdiction_scrape` | Full scan | Index seek |

### Alembic Migration for All Missing Indexes

```python
# alembic/versions/XXXX_add_missing_performance_indexes.py
"""Add missing performance indexes for scraping and campaign queries.

Revision ID: XXXX
Revises: YYYY
Create Date: 2026-05-04
"""
from alembic import op

def upgrade():
    op.create_index(
        "ix_scrape_jobs_jurisdiction_job_status",
        "scrape_jobs",
        ["jurisdiction_scrape_job_id", "status"],
    )
    op.create_index(
        "ix_jurisdiction_scrape_jobs_jurisdiction_status_completed",
        "jurisdiction_scrape_jobs",
        ["jurisdiction_id", "status", "completed_at"],
    )
    op.create_index(
        "ix_jurisdictions_campaign_discovery",
        "jurisdictions",
        ["campaign_id", "discovery_status"],
    )
    op.create_index(
        "ix_jurisdictions_next_scrape_auto",
        "jurisdictions",
        ["next_scrape_time", "enable_auto_scrape", "is_deleted"],
    )
    op.create_index(
        "ix_sources_jurisdiction_active",
        "sources",
        ["jurisdiction_id", "is_active", "is_deleted"],
    )

def downgrade():
    op.drop_index("ix_sources_jurisdiction_active")
    op.drop_index("ix_jurisdictions_next_scrape_auto")
    op.drop_index("ix_jurisdictions_campaign_discovery")
    op.drop_index("ix_jurisdiction_scrape_jobs_jurisdiction_status_completed")
    op.drop_index("ix_scrape_jobs_jurisdiction_job_status")
```

---

## Prioritized Fix Roadmap

### Phase 1: Critical (Do Immediately)
1. **#1** — Single commit in `dispatch_due_jurisdictions` (5 min fix)
2. **#3** — Batch commit in `_dispatch_sources` (10 min fix)
3. **#5** — Adaptive polling in `publish_campaign_blogs_task` (15 min fix)
4. **#10** — Atomic Redis lock release with Lua script (5 min fix)
5. **#6** — Zombie campaign prevention (10 min fix)
6. **#2** — Remove double query in `check_batch_completion` (2 min fix)

### Phase 2: High (Do This Week)
7. **#7** — N+1 query fix in `generate_campaign_content_task` (15 min fix + migration)
8. **#4** — Batch dispatch in `dispatch_campaign_scrapes_task` (20 min fix)
9. **#9** — Parallel MinIO fetches (15 min fix)
10. **#8** — Composite index migration (5 min migration)
11. **#11** — Remove unnecessary sleep (2 min fix)
12. **#12** — Single commit in consolidation (5 min fix)

### Phase 3: Medium (Do This Sprint)
13. **#15** — Redis connection pool reuse (10 min fix)
14. **#18** — Batch notifications (15 min fix)
15. **#23** — Parallel LLM filtering (10 min fix)
16. **#13** — Source prioritization (5 min fix)
17. **#14** — Stats JSONB trimming (10 min fix)
18. **#20** — Result field archiving (15 min fix)
19. **#19** — IntegrityError handling fix (5 min fix)
20. **#16, #17, #22** — Remaining indexes and backpressure (20 min fix + migration)
21. **#21** — Checkpoint/resume (30 min fix)

---

## Total Estimated Effort
- **Phase 1:** ~47 minutes
- **Phase 2:** ~72 minutes
- **Phase 3:** ~120 minutes
- **Total:** ~4 hours of focused work

## Risk Assessment
- **Phase 1 fixes** are low-risk (mostly removing redundant commits and adding atomicity).
- **Phase 2 fixes** require testing with realistic data volumes (500+ jurisdictions).
- **Phase 3 fixes** are safe but should be deployed incrementally with monitoring.
