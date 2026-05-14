"""
Check the status of recent scrape jobs to verify the fix is working.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import desc, select

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.core.config import settings  # noqa: E402
from app.api.modules.v1.scraping.models.data_revision import DataRevision  # noqa: E402
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob  # noqa: E402


async def check_recent_scrapes():
    """Check recent scrape jobs and their status."""
    print("=" * 80)
    print("RECENT SCRAPE JOBS")
    print("=" * 80)
    print()

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as db_session:
        # Get recent scrape jobs
        query = select(ScrapeJob).order_by(desc(ScrapeJob.created_at)).limit(10)
        result = await db_session.execute(query)
        jobs = result.scalars().all()

        if not jobs:
            print("No scrape jobs found.")
            return

        print(f"Found {len(jobs)} recent scrape jobs:\n")

        for i, job in enumerate(jobs, 1):
            print(f"{i}. Job ID: {job.id}")
            print(f"   Source ID: {job.source_id}")
            print(f"   Status: {job.status}")
            print(f"   Created: {job.created_at}")
            print(f"   Started: {job.started_at}")
            print(f"   Completed: {job.completed_at}")

            if job.data_revision_id:
                # Check if revision was created
                rev_query = select(DataRevision).where(DataRevision.id == job.data_revision_id)
                rev_result = await db_session.execute(rev_query)
                revision = rev_result.scalar_one_or_none()

                if revision:
                    print(f"   ✅ Data Revision Created: {revision.id}")
                    print(f"   Change Detected: {revision.was_change_detected}")
                else:
                    print("   ⚠️  Data Revision NOT Found")
            else:
                print("   ⚠️  No Data Revision ID")

            if job.error_message:
                print(f"   Error: {job.error_message}")

            print()

        # Summary
        success_count = sum(1 for job in jobs if job.status == "SUCCESS")
        failed_count = sum(1 for job in jobs if job.status == "FAILED")
        pending_count = sum(1 for job in jobs if job.status == "PENDING")
        running_count = sum(1 for job in jobs if job.status == "RUNNING")

        print("-" * 80)
        print("SUMMARY:")
        print(f"  ✅ SUCCESS: {success_count}")
        print(f"  ❌ FAILED: {failed_count}")
        print(f"  ⏳ RUNNING: {running_count}")
        print(f"  📝 PENDING: {pending_count}")
        print()

        # Check for the specific job from the log
        print("-" * 80)
        print("CHECKING FOR REVISION: 113dc80d-b366-46e5-bef6-7ff20089c4ec")
        print()

        rev_query = select(DataRevision).where(
            DataRevision.id == "113dc80d-b366-46e5-bef6-7ff20089c4ec"
        )
        rev_result = await db_session.execute(rev_query)
        revision = rev_result.scalar_one_or_none()

        if revision:
            print("✅ FOUND!")
            print(f"   Created: {revision.scraped_at}")
            print(f"   Change Detected: {revision.was_change_detected}")
            print(f"   Source ID: {revision.source_id}")

            # Find the scrape job for this revision
            job_query = select(ScrapeJob).where(ScrapeJob.data_revision_id == revision.id)
            job_result = await db_session.execute(job_query)
            job = job_result.scalar_one_or_none()

            if job:
                print("\n   Associated Scrape Job:")
                print(f"   Job ID: {job.id}")
                print(f"   Status: {job.status}")

                if job.status == "SUCCESS":
                    print("\n   ✅ FIX IS WORKING!")
                    print("   Scrape completed successfully even though Celery was unavailable.")
                elif job.status == "FAILED":
                    print("\n   ❌ FIX NOT WORKING")
                    print("   Scrape was marked as FAILED (this is the old behavior)")
            else:
                print("   ⚠️  No scrape job found for this revision")
        else:
            print("❌ NOT FOUND")
            print("   This revision might be from a previous run or different database")

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_recent_scrapes())
