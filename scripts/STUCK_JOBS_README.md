# Stuck Job Cleanup Scripts

This directory contains scripts to manually clear stuck scrape jobs when the Celery worker crashes or jobs get stuck.

## Scripts

### 1. `clear_stuck_jobs.py` - Clear Source Scrape Jobs

Clears individual source scrape jobs that are stuck in PENDING or IN_PROGRESS status.

**Usage:**

```bash
# Clear ALL stuck source jobs
python scripts/clear_stuck_jobs.py

# Clear stuck jobs for a specific source
python scripts/clear_stuck_jobs.py <source_id>
```

**Example:**
```bash
python scripts/clear_stuck_jobs.py e236fe52-34c8-4844-ac19-4dc3027e4943
```

---

### 2. `clear_stuck_jurisdiction_jobs.py` - Clear Jurisdiction Scrape Jobs

Clears jurisdiction-level scrape jobs (batch operations) that are stuck. This will also clear all associated source scrape jobs.

**Usage:**

```bash
# Clear ALL stuck jurisdiction jobs
python scripts/clear_stuck_jurisdiction_jobs.py

# Clear a specific jurisdiction job by ID
python scripts/clear_stuck_jurisdiction_jobs.py <job_id>
# OR
python scripts/clear_stuck_jurisdiction_jobs.py --job=<job_id>

# Clear all stuck jobs for a specific jurisdiction
python scripts/clear_stuck_jurisdiction_jobs.py --jurisdiction=<jurisdiction_id>
```

**Examples:**
```bash
# Clear all stuck jurisdiction jobs
python scripts/clear_stuck_jurisdiction_jobs.py

# Clear specific job
python scripts/clear_stuck_jurisdiction_jobs.py e236fe52-34c8-4844-ac19-4dc3027e4943

# Clear all stuck jobs for a jurisdiction
python scripts/clear_stuck_jurisdiction_jobs.py --jurisdiction=a1b2c3d4-5678-90ab-cdef-1234567890ab
```

---

## When to Use These Scripts

### Use `clear_stuck_jobs.py` when:
- Individual source scrapes are stuck
- A single source is locked and won't accept new scrapes
- You see jobs stuck in PENDING/IN_PROGRESS for a long time

### Use `clear_stuck_jurisdiction_jobs.py` when:
- Jurisdiction-level scrapes are stuck (showing 30% progress for hours)
- Celery worker crashed during a jurisdiction scrape
- Multiple sources in a jurisdiction are stuck
- Jobs show status like SCRAPING, CONSOLIDATING, FILTERING, or ANALYZING for too long

---

## What These Scripts Do

Both scripts will:
1. Query the database for stuck jobs
2. Show you a list of what will be cleared
3. Ask for confirmation (type `yes` to proceed)
4. Mark jobs as FAILED with appropriate error messages
5. Set `completed_at` timestamp
6. Allow users to retry the scrape from the UI

**Note:** The jurisdiction script will also clear all associated source jobs to prevent orphaned tasks.

---

## Safety

- Both scripts require explicit confirmation before making changes
- They use transactions, so changes are atomic
- Jobs are marked as FAILED (not deleted), preserving history
- Error messages indicate manual clearing for audit purposes

---

## Prevention

To prevent jobs from getting stuck in the future:

1. **Enable automatic monitoring** - Uncomment the Celery Beat tasks in `app/celery_app.py`:
   - `monitor_stalled_jobs` - Marks jobs as failed after timeout
   - `retry_stuck_jobs` - Automatically retries stuck jobs

2. **Ensure worker stability** - Make sure the Celery worker has all required dependencies installed

3. **Monitor worker logs** - Check for crashes or errors regularly
