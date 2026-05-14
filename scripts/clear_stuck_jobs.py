"""
Quick script to clear stuck scrape jobs.

Run this when a job fails and leaves the source locked.
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
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus

# Load environment
load_dotenv()

# Get sync database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def clear_stuck_jobs(source_id: str = None):
    """Clear stuck jobs (PENDING or IN_PROGRESS without completed_at)."""

    engine = create_engine(DATABASE_URL, echo=True)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        # Find stuck jobs
        query = select(ScrapeJob).where(
            ScrapeJob.status.in_([ScrapeJobStatus.PENDING, ScrapeJobStatus.IN_PROGRESS])
        )

        if source_id:
            query = query.where(ScrapeJob.source_id == source_id)

        result = session.execute(query)
        stuck_jobs = result.scalars().all()

        if not stuck_jobs:
            print("✅ No stuck jobs found!")
            return

        print(f"Found {len(stuck_jobs)} stuck job(s):")
        for job in stuck_jobs:
            print(f"  - Job ID: {job.id}, Source: {job.source_id}, Status: {job.status}")

        # Ask for confirmation
        confirm = input("\nMark these jobs as FAILED? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return

        # Mark as failed
        for job in stuck_jobs:
            job.status = ScrapeJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = "Job cleared manually due to system error"
            job.result = {
                "status": "failed",
                "reason": "manually_cleared",
                "message": "Job was stuck and cleared by admin",
            }
            session.add(job)

        session.commit()
        print(f"✅ Marked {len(stuck_jobs)} job(s) as FAILED")


if __name__ == "__main__":
    import sys

    source_id = sys.argv[1] if len(sys.argv) > 1 else None

    if source_id:
        print(f"Clearing stuck jobs for source: {source_id}")
    else:
        print("Clearing ALL stuck jobs")

    clear_stuck_jobs(source_id)
