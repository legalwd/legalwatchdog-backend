"""
Quick script to clear stuck jurisdiction scrape jobs.

Run this when jurisdiction scrape jobs get stuck (e.g., after worker crashes).
This will:
1. Mark stuck jurisdiction jobs as FAILED
2. Mark all associated source scrape jobs as FAILED
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import models
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus

# Load environment
load_dotenv()

# Get sync database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def clear_stuck_jurisdiction_jobs(jurisdiction_id: str = None, job_id: str = None):
    """Clear stuck jurisdiction scrape jobs and their associated source jobs.
    
    Args:
        jurisdiction_id: Optional UUID of specific jurisdiction to clear
        job_id: Optional UUID of specific jurisdiction job to clear
    """

    engine = create_engine(DATABASE_URL, echo=True)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        # Find stuck jurisdiction jobs
        query = select(JurisdictionScrapeJob).where(
            JurisdictionScrapeJob.status.in_([
                JurisdictionScrapeJobStatus.PENDING,
                JurisdictionScrapeJobStatus.SCRAPING,
                JurisdictionScrapeJobStatus.CONSOLIDATING,
                JurisdictionScrapeJobStatus.FILTERING,
                JurisdictionScrapeJobStatus.ANALYZING,
            ])
        )

        if job_id:
            query = query.where(JurisdictionScrapeJob.id == job_id)
        elif jurisdiction_id:
            query = query.where(JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id)

        result = session.execute(query)
        stuck_jobs = result.scalars().all()

        if not stuck_jobs:
            print("✅ No stuck jurisdiction jobs found!")
            return

        print(f"\nFound {len(stuck_jobs)} stuck jurisdiction job(s):")
        for job in stuck_jobs:
            print(f"  - Job ID: {job.id}")
            print(f"    Jurisdiction: {job.jurisdiction_id}")
            print(f"    Status: {job.status}")
            print(f"    Started: {job.started_at}")
            print(f"    Sources: {job.successful_sources}/{job.total_sources}")
            
            # Count associated source jobs
            source_jobs_query = select(ScrapeJob).where(
                ScrapeJob.jurisdiction_scrape_job_id == job.id
            )
            source_jobs = session.execute(source_jobs_query).scalars().all()
            
            pending_count = sum(1 for sj in source_jobs if sj.status in [
                ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS
            ])
            print(f"    Associated source jobs: {len(source_jobs)} total, {pending_count} still pending/in-progress")
            print()

        # Ask for confirmation
        confirm = input("Mark these jurisdiction jobs and their source jobs as FAILED? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return

        total_source_jobs_cleared = 0

        # Mark jurisdiction jobs and their source jobs as failed
        for job in stuck_jobs:
            # Mark jurisdiction job as failed
            job.status = JurisdictionScrapeJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = "Job cleared manually due to worker crash/system error"
            session.add(job)

            # Find and mark all associated source jobs as failed
            source_jobs_query = select(ScrapeJob).where(
                ScrapeJob.jurisdiction_scrape_job_id == job.id,
                ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS])
            )
            source_jobs = session.execute(source_jobs_query).scalars().all()

            for source_job in source_jobs:
                source_job.status = ScrapeJobStatus.FAILED
                source_job.completed_at = datetime.now(timezone.utc)
                source_job.error_message = "Parent jurisdiction job cleared manually"
                source_job.result = {
                    "status": "failed",
                    "reason": "jurisdiction_job_cleared",
                    "message": "Parent jurisdiction job was stuck and cleared by admin",
                }
                session.add(source_job)
                total_source_jobs_cleared += 1

        session.commit()
        print(f"✅ Marked {len(stuck_jobs)} jurisdiction job(s) as FAILED")
        print(f"✅ Marked {total_source_jobs_cleared} associated source job(s) as FAILED")


if __name__ == "__main__":
    import sys

    job_id = None
    jurisdiction_id = None

    # Parse command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.startswith("--job="):
            job_id = arg.split("=")[1]
            print(f"Clearing specific jurisdiction job: {job_id}")
        elif arg.startswith("--jurisdiction="):
            jurisdiction_id = arg.split("=")[1]
            print(f"Clearing stuck jobs for jurisdiction: {jurisdiction_id}")
        else:
            job_id = arg
            print(f"Clearing specific jurisdiction job: {job_id}")
    else:
        print("Clearing ALL stuck jurisdiction jobs")

    print("\nThis will mark stuck jurisdiction jobs and their source jobs as FAILED.")
    print("Users will be able to retry the scrape from the UI.\n")

    clear_stuck_jurisdiction_jobs(jurisdiction_id, job_id)
