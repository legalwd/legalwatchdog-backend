"""
Backfill Script for Jurisdiction Changes

Populates JurisdictionChange records for existing completed jurisdiction scrape jobs.
Run this as a one-time migration after deployment.

Usage:
    python -m app.scripts.backfill_jurisdiction_changes [--days N]
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)


async def backfill_jurisdiction_changes(days: int = 90):
    """
    Backfill JurisdictionChange records for completed jurisdiction scrape jobs.

    Args:
        days: Number of days to look back (default: 90)
    """
    print(f"🔄 Starting backfill for jurisdiction scrape jobs from last {days} days...")

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        # Fetch completed jobs from the specified timeframe
        result = await db.execute(
            select(JurisdictionScrapeJob).where(
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
                JurisdictionScrapeJob.completed_at >= cutoff_date,
            )
        )
        jobs = result.scalars().all()

        print(f"📊 Found {len(jobs)} completed jobs to process")

        total_created = 0
        jobs_processed = 0
        jobs_skipped = 0

        for job in jobs:
            try:
                # Check if changes already exist for this job
                existing_check = await db.execute(
                    select(JurisdictionChange).where(
                        JurisdictionChange.jurisdiction_scrape_job_id == job.id
                    )
                )
                if existing_check.scalar_one_or_none():
                    jobs_skipped += 1
                    continue

                # Extract changes from job data
                extracted_data = job.extracted_data or {}
                change_detection = extracted_data.get("change_detection", {})

                if not change_detection:
                    # Try legacy changes format
                    changes = extracted_data.get("changes", [])
                    field_changes = [
                        {
                            "field_name": c.get("field", ""),
                            "old_value": c.get("old_value"),
                            "new_value": c.get("new_value"),
                            "change_description": c.get("change_description", ""),
                        }
                        for c in changes
                    ]
                else:
                    field_changes = change_detection.get("field_changes", [])

                if not field_changes:
                    jobs_skipped += 1
                    continue

                # Create JurisdictionChange records
                for idx, fc in enumerate(field_changes):
                    jurisdiction_change = JurisdictionChange(
                        jurisdiction_scrape_job_id=job.id,
                        field_name=fc.get("field_name", fc.get("field", "unknown")),
                        old_value=str(fc.get("old_value")) if fc.get("old_value") else None,
                        new_value=str(fc.get("new_value")) if fc.get("new_value") else None,
                        change_description=fc.get(
                            "change_description",
                            f"{fc.get('field_name', 'Field')} changed",
                        ),
                        change_index=idx,
                        ticket_created=False,
                        change_accepted=False,
                        created_at=job.completed_at or datetime.now(timezone.utc),
                    )
                    db.add(jurisdiction_change)
                    total_created += 1

                await db.commit()
                jobs_processed += 1

                if jobs_processed % 10 == 0:
                    print(f"   Processed {jobs_processed}/{len(jobs)} jobs...")

            except Exception as e:
                print(f"❌ Error processing job {job.id}: {str(e)}")
                await db.rollback()
                continue

        print("\n✅ Backfill complete!")
        print(f"   Jobs processed: {jobs_processed}")
        print(f"   Jobs skipped (no changes or already backfilled): {jobs_skipped}")
        print(f"   Total JurisdictionChange records created: {total_created}")


def main():
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill JurisdictionChange records for old jurisdiction scrape jobs"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days to look back (default: 90)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(backfill_jurisdiction_changes(days=args.days))
    except KeyboardInterrupt:
        print("\n⚠️  Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Backfill failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
