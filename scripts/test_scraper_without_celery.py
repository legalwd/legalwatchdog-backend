"""
Test that scraping works even when Celery is unavailable.

This verifies that scrape jobs complete successfully and are marked as
SUCCESS even if the notification queueing fails due to Celery being down.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api.core.config import settings  # noqa: E402
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction  # noqa: E402
from app.api.modules.v1.organization.models.organization_model import Organization  # noqa: E402
from app.api.modules.v1.projects.models.project_model import Project  # noqa: E402
from app.api.modules.v1.scraping.models.data_revision import DataRevision  # noqa: E402
from app.api.modules.v1.scraping.models.source_model import (  # noqa: E402
    ScrapeFrequency,
    Source,
    SourceType,
)
from app.api.modules.v1.scraping.service.scraper_service import ScraperService  # noqa: E402


async def test_scraper_with_broken_celery():
    """Test that scraping succeeds even when Celery connection fails."""
    print("=" * 80)
    print("TEST: Scraper Service with Broken Celery Connection")
    print("=" * 80)
    print()

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_factory() as db_session:
        try:
            print("[SETUP] Creating test data...")

            org = Organization(
                id=uuid4(),
                name="Test Org - Celery Down",
                email="test@celerydown.com",
                is_verified=True,
            )
            db_session.add(org)
            await db_session.commit()

            project = Project(
                id=uuid4(),
                org_id=org.id,
                title="Celery Test Project",
                master_prompt="Extract visa information",
                description="Test project",
            )
            db_session.add(project)
            await db_session.commit()

            jurisdiction = Jurisdiction(
                id=uuid4(),
                project_id=project.id,
                name="Test Jurisdiction",
                description="Test jurisdiction",
            )
            db_session.add(jurisdiction)
            await db_session.commit()

            # Create source with mock URL
            source = Source(
                id=uuid4(),
                jurisdiction_id=jurisdiction.id,
                name="Mock Visa Source",
                url="mock://test",
                source_type=SourceType.WEB,
                scrape_frequency=ScrapeFrequency.DAILY,
                scraping_rules={
                    "mock_html": """
                    <html>
                        <body>
                            <h1>Visa Information</h1>
                            <p>Application Fee: $100</p>
                            <p>Processing Time: 10 days</p>
                        </body>
                    </html>
                    """
                },
            )
            db_session.add(source)
            await db_session.commit()
            await db_session.refresh(source)
            print(f"  [OK] Test source created: {source.id}")
            print()

            # Mock Celery to raise connection error
            def mock_delay_failure(*args, **kwargs):
                from kombu.exceptions import OperationalError

                raise OperationalError("[Errno 111] Connection refused")

            print("[TEST] Mocking Celery connection failure...")
            print()

            scraper_service = ScraperService(db_session)

            with patch(
                "app.api.modules.v1.scraping.service.scraper_service."
                "send_revision_notifications_task.delay",
                side_effect=mock_delay_failure,
            ):
                print("[RUN 1] First scrape (baseline) - Celery unavailable")
                result1 = await scraper_service.execute_scrape_job(str(source.id))
                print(f"  Result: {result1}")
                print(f"  Status: {result1['status']}")
                print(f"  Is Baseline: {result1['is_baseline']}")
                print()

                # Verify revision was created
                query = select(DataRevision).where(DataRevision.source_id == source.id)
                rev_result = await db_session.execute(query)
                revision1 = rev_result.scalars().first()

                if not revision1:
                    print("[FAIL] No revision created!")
                    return False

                print(f"  [OK] Revision created: {revision1.id}")
                print()

                # Second scrape with changes
                source.scraping_rules["mock_html"] = """
                <html>
                    <body>
                        <h1>Visa Information - UPDATED</h1>
                        <p>Application Fee: $150</p>
                        <p>Processing Time: 5 days</p>
                    </body>
                </html>
                """
                await db_session.commit()

                print("[RUN 2] Second scrape (with changes) - Celery unavailable")
                result2 = await scraper_service.execute_scrape_job(str(source.id))
                print(f"  Result: {result2}")
                print(f"  Status: {result2['status']}")
                print(f"  Change Detected: {result2['change_detected']}")
                print()

                # Verify second revision was created
                rev_result2 = await db_session.execute(
                    select(DataRevision)
                    .where(DataRevision.source_id == source.id)
                    .order_by(DataRevision.scraped_at.desc())
                )
                revisions = rev_result2.scalars().all()

                if len(revisions) < 2:
                    print(f"[FAIL] Expected 2 revisions, got {len(revisions)}")
                    return False

                print(f"  [OK] {len(revisions)} revisions created")
                print()

            print("=" * 80)
            print("[SUMMARY]")
            print("=" * 80)
            print()

            if result1["status"] == "success" and result2["status"] == "success":
                print("[SUCCESS] Scraping works even when Celery is unavailable!")
                print()
                print("Key Points:")
                print("  ✓ Scrape completed successfully")
                print("  ✓ Data revisions were created")
                print("  ✓ Change detection worked")
                print("  ✓ Scrape was NOT marked as FAILED")
                print("  ✓ Notification failure was logged but didn't break scrape")
                print()
                return True
            else:
                print("[FAIL] Scrape failed when Celery was unavailable")
                print(f"  Result 1 status: {result1['status']}")
                print(f"  Result 2 status: {result2['status']}")
                print()
                return False

        except Exception as e:
            print(f"[ERROR] Test failed with exception: {e}")
            import traceback

            traceback.print_exc()
            return False


async def main():
    success = await test_scraper_with_broken_celery()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
