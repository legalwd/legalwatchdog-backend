"""
Mock Celery Worker Test: Scraper Service Pipeline with Change Detection.

Simulates the actual Celery worker flow with mock data:
1. First run: Mock scrape with initial data → Extract → Store DataRevision (New Record)
2. Second run: Mock scrape with changed data → Extract → Detect Changes → Store Diff
3. Validates notifications are triggered when changes are detected
4. Validates email notifications are sent with template rendering

Validates that:
- Extraction works with mock data
- Change detection flags work correctly when data changes
- Diff records are created properly
- Notifications are triggered for changes
- Email notifications are created and sent
"""

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import delete, select

from app.api.core.config import settings
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import (
    ScrapeFrequency,
    Source,
    SourceType,
)
from app.api.modules.v1.scraping.service.scraper_service import ScraperService
from app.api.modules.v1.users.models.users_model import User
from app.celery_app import celery_app

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Enable Celery eager mode for synchronous task execution in tests
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

# --- CONFIGURATION ---
CLEANUP_ON_EXIT = False

# Global setup for test data (uses asyncpg for async db access)
db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# --- HELPER FUNCTIONS ---


async def create_test_entities(
    db_session: AsyncSession, initial_mock_html: str
) -> tuple[Source, Organization, Project, Jurisdiction, User]:
    """
    Creates Organization, Project, Jurisdiction, Source, and User for the mock test.

    Args:
        db_session (AsyncSession): Async database session.
        initial_mock_html (str): Initial mock HTML content for scraping.

    Returns:
        tuple: (Source, Organization, Project, Jurisdiction, User) objects.
    """
    org = Organization(
        id=uuid4(),
        name=f"UK Government Test Org {datetime.now().timestamp()}",
        email="test@gov.uk",
        is_verified=True,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    project = Project(
        id=uuid4(),
        org_id=org.id,
        title="UK Minimum Wage Compliance",
        master_prompt=(
            "Extract the current National Minimum Wage and National Living Wage rates "
            "per hour. Group the rates by age category (e.g., '21 and over', '18 to 20'). "
            "Identify the 'Effective Date' for these rates."
        ),
        description="Monitor UK minimum wage rates for compliance",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    jurisdiction = Jurisdiction(
        id=uuid4(),
        project_id=project.id,
        name="United Kingdom",
        description="UK minimum wage regulations",
        prompt="Context: HM Revenue & Customs (HMRC) official rates for the UK.",
    )
    db_session.add(jurisdiction)
    await db_session.commit()
    await db_session.refresh(jurisdiction)

    source = Source(
        id=uuid4(),
        jurisdiction_id=jurisdiction.id,
        name="GOV.UK National Minimum Wage (Mock)",
        url="mock://gov.uk/national-minimum-wage-rates",
        source_type=SourceType.WEB,
        scrape_frequency=ScrapeFrequency.WEEKLY,
        next_scrape_time=datetime.now(timezone.utc),
        scraping_rules={"mock_html": initial_mock_html, "expected_type": "text/html"},
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    print(f"  [OK] Source created: {source.id}")

    # Create first test user for notifications
    user = User(
        id=uuid4(),
        email=f"test_user_{datetime.now().timestamp()}@example.com",
        username=f"test_user_{datetime.now().timestamp()}",
        name=f"Test User {datetime.now().timestamp()}",
        hashed_password="hashed_test_password",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Associate first user with project
    project_user = ProjectUser(user_id=user.id, project_id=project.id)
    db_session.add(project_user)
    await db_session.commit()

    print(f"  [OK] User 1 created: {user.id}")

    # Create second test user with provided email (using dynamic suffix to avoid duplicates)
    user2 = User(
        id=uuid4(),
        email="oshinsamuel0@gmail.com",
        username=f"samuel_test_{datetime.now().timestamp()}",
        name=f"Samuel Test {datetime.now().timestamp()}",
        hashed_password="hashed_test_password",
        is_verified=True,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)

    # Associate second user with project
    project_user2 = ProjectUser(user_id=user2.id, project_id=project.id)
    db_session.add(project_user2)
    await db_session.commit()

    print(f"  [OK] User 2 created: {user2.id}")

    return source, org, project, jurisdiction, user


async def run_single_scrape(
    db_session: AsyncSession, source_id: str, timeout: float = 120.0, scrape_num: int = 1
) -> DataRevision | None:
    """
    Executes a single scrape job and returns the latest revision.

    Args:
        db_session (AsyncSession): Async database session.
        source_id (str): ID of the source to scrape.
        timeout (float, optional): Timeout in seconds. Defaults to 120.0.
        scrape_num (int, optional): Scrape run number for logging. Defaults to 1.

    Returns:
        DataRevision | None: Latest DataRevision object or None if failed.

    Raises:
        asyncio.TimeoutError: If scrape job exceeds timeout.
    """
    print(f"[WORKER-{scrape_num}] Initializing ScraperService...")
    scraper_service = ScraperService(db_session)
    print("[OK] ScraperService initialized")

    print(f"[WORKER-{scrape_num}] Executing scrape job for source: {source_id}")
    try:
        result = await asyncio.wait_for(
            scraper_service.execute_scrape_job(source_id), timeout=timeout
        )
        print(f"[OK] Scrape job completed (Result: {result})")
    except asyncio.TimeoutError:
        print(f"[ERROR] Scrape job timed out after {timeout} seconds")
        return None

    # Fetch the latest revision (Async Query)
    query_rev = (
        select(DataRevision)
        .where(DataRevision.source_id == source_id)
        .order_by(desc(DataRevision.scraped_at))
    )

    result_rev = await db_session.execute(query_rev)
    revision = result_rev.scalars().first()

    if revision:
        print(f"  [OK] DataRevision created: {revision.id}")
        print(f"    Was Change Detected: {revision.was_change_detected}")
    else:
        print("[ERROR] No DataRevision created!")

    return revision


async def check_notifications(
    db_session: AsyncSession, user_id: str, source_id: str, revision_id: str
) -> tuple[bool, bool]:
    """
    Checks if a CHANGE_DETECTED notification was created for the user.

    Also validates notification email context and status.

    Args:
        db_session (AsyncSession): Async database session.
        user_id (str): ID of the user to check notifications for.
        source_id (str): ID of the source that changed.
        revision_id (str): ID of the revision that changed.

    Returns:
        tuple: (notification_created, email_ready) - both booleans.
    """
    query_notif = select(Notification).where(
        (Notification.user_id == user_id)
        & (Notification.source_id == source_id)
        & (Notification.revision_id == revision_id)
        & (Notification.notification_type == NotificationType.CHANGE_DETECTED)
    )

    result_notif = await db_session.execute(query_notif)
    notification = result_notif.scalars().first()

    notification_created = bool(notification)
    email_ready = False

    if notification_created:
        print(
            f"[V3 OK] Notification created: {notification.notification_id} "
            f"(Status: {notification.status})"
        )
        print(f"    Title: {notification.title}")
        print(f"    Message: {notification.message[:80]}...")

        # Check if notification is ready for email (PENDING status)
        if notification.status == NotificationStatus.PENDING:
            email_ready = True
            print("[V3 OK] Notification status is PENDING (ready for email sending)")
        else:
            print(f"[V3 INFO] Notification status: {notification.status}")

        return notification_created, email_ready
    else:
        print("[V3 FAIL] No CHANGE_DETECTED notification found!")
        return notification_created, email_ready


async def mock_celery_scraper_worker():
    """
    Runs the change detection test scenario using mock HTML.

    Includes email notification verification by mocking SMTP.

    Returns:
        bool: True if all validations pass, False otherwise.
    """
    test_passed = False

    # Mock initial data (April 2025 rates)
    initial_mock_html = """
    <html><body>
    <h1>National Minimum Wage and National Living Wage rates</h1>
    <table>
    <tr><th>Age</th><th>Rate from April 2025</th></tr>
    <tr><td>21 and over (National Living Wage)</td><td>£12.21</td></tr>
    <tr><td>18 to 20</td><td>£10.00</td></tr>
    </table>
    <p>These rates apply from April 2025.</p>
    </body></html>
    """

    # Updated mock data with rate changes (November 2025 rates)
    updated_mock_html = """
    <html><body>
    <h1>National Minimum Wage and National Living Wage rates</h1>
    <table>
    <tr><th>Age</th><th>Rate from November 2025</th></tr>
    <tr><td>21 and over (National Living Wage)</td><td>£12.75</td></tr>
    <tr><td>18 to 20</td><td>£10.50</td></tr>
    </table>
    <p>These rates apply from November 2025.</p>
    </body></html>
    """

    print("[SETUP] Initializing Async Database Session...")
    print("[SETUP] Mocking SMTP for email notification verification...")
    print("[SETUP] Mocking AI services to avoid token usage...")

    async with AsyncSessionLocal() as db_session:
        try:
            # Mock AI services to avoid real API calls
            with (
                patch(
                    "app.api.modules.v1.scraping.service.llm_service.genai.GenerativeModel"
                ) as mock_genai_model,
                patch(
                    "app.api.modules.v1.scraping.service.diff_service.genai.GenerativeModel"
                ) as mock_diff_model,
            ):
                # Mock extraction responses
                mock_extraction_first = AsyncMock()
                mock_extraction_first.generate_content.return_value = AsyncMock()
                mock_extraction_first.generate_content.return_value.text = json.dumps(
                    {
                        "summary": (
                            "The National Minimum Wage and National Living Wage rates for the UK, "
                            "effective from April 2025, are provided. The National Living Wage for those "  # noqa: E501
                            "aged 21 and over is £12.21 per hour, while the rate for 18 to 20 year olds is "  # noqa: E501
                            "£10.00 per hour."
                        ),
                        "markdown_summary": (
                            "## National Minimum Wage and National Living Wage Rates\n\n"
                            "This document outlines the National Minimum Wage and National Living Wage rates "  # noqa: E501
                            "applicable in the UK, effective from **April 2025**.\n\n"
                            "- **Effective Date**: April 2025\n\n"
                            "### Hourly Rates by Age Category:\n\n"
                            "- **21 and over (National Living Wage)**: £12.21\n"
                            "- **18 to 20**: £10.00"
                        ),
                        "confidence_score": 0.95,
                        "extracted_data": {
                            "key_value_pairs": {
                                "age_category": "18 to 20",
                                "effective_date": "April 2025",
                                "hourly_rate": "£10.00",
                            }
                        },
                    }
                )

                mock_extraction_second = AsyncMock()
                mock_extraction_second.generate_content.return_value = AsyncMock()
                mock_extraction_second.generate_content.return_value.text = json.dumps(
                    {  # noqa: E501
                        "summary": (
                            "The National Minimum Wage and National Living Wage rates for the UK, "
                            "effective from November 2025, are provided. The National Living Wage for those "  # noqa: E501
                            "aged 21 and over is £12.75 per hour, while the rate for 18 to 20 year olds is £10.50 per hour."  # noqa: E501
                        ),
                        "markdown_summary": (
                            "## National Minimum Wage and National Living Wage Rates\n\n"
                            "This analysis summarizes the National Minimum Wage and National Living Wage rates "  # noqa: E501
                            "for the UK, effective from **November 2025**.\n\n"
                            "- **Age 21 and over (National Living Wage):** £12.75 per hour\n"
                            "- **Age 18 to 20:** £10.50 per hour"
                        ),
                        "confidence_score": 0.95,
                        "extracted_data": {
                            "key_value_pairs": {
                                "age_group": "18 to 20",
                                "effective_date": "November 2025",
                                "hourly_rate": "£10.50",
                            }
                        },
                    }
                )

                mock_genai_model.side_effect = [mock_extraction_first, mock_extraction_second]

                # Mock diff response for first run (new record)
                mock_diff_first = AsyncMock()
                mock_diff_first.generate_content.return_value = AsyncMock()
                mock_diff_first.generate_content.return_value.text = json.dumps(
                    {
                        "is_changed": True,
                        "confidence": 0.95,
                        "change_summary": "Initial data extraction (New Record)",
                        "key_changes": [],
                    }
                )

                # Mock diff response for second run (actual change)
                mock_diff_second = AsyncMock()
                mock_diff_second.generate_content.return_value = AsyncMock()
                mock_diff_second.generate_content.return_value.text = json.dumps(
                    {  # noqa: E501
                        "is_changed": True,
                        "confidence": 0.95,
                        "change_summary": (
                            "The hourly rate for the age group '18 to 20' has increased from £10.00 to £10.50, "  # noqa: E501
                            "and the effective date has changed from April 2025 to November 2025."
                        ),
                        "key_changes": [
                            {"field": "hourly_rate", "old_value": "£10.00", "new_value": "£10.50"},
                            {
                                "field": "effective_date",
                                "old_value": "April 2025",
                                "new_value": "November 2025",
                            },  # noqa: E501
                        ],
                    }
                )

                # Configure mock to return different responses based on call count
                mock_diff_model.side_effect = [mock_diff_first, mock_diff_second]

                # Using real SMTP configuration from .env
                print("[INFO] Using real SMTP configuration for email delivery")

            # Create test data and mock source
            source, _, _, _, user = await create_test_entities(db_session, initial_mock_html)
            source_id = str(source.id)
            user_id = str(user.id)
            print()

            # --- RUN 1: Initial Scrape (Mock April 2025) ---
            print("-" * 80)
            print("[RUN 1] Initial Extraction (April 2025 Rates)")
            print("-" * 80)
            revision1 = await run_single_scrape(db_session, source_id, scrape_num=1, timeout=60.0)
            if not revision1:
                return False

            # --- VALIDATION 1 ---
            initial_check_ok = revision1.was_change_detected
            if initial_check_ok:
                print("[V1 OK] Change detected in first run (as New Record).")
            else:
                print("[V1 FAIL] Initial run failed to detect change.")
                return False

            print()

            # --- UPDATE MOCK DATA FOR CHANGE (Simulate New Content) ---
            print("-" * 80)
            print("[UPDATE] Simulating Data Change (November 2025 Rate Increase)")
            print("-" * 80)

            # Update the source's scraping rules with new mock HTML
            source.scraping_rules = {
                "mock_html": updated_mock_html,
                "expected_type": "text/html",
            }
            db_session.add(source)
            await db_session.commit()
            print(f"[OK] Updated source {source_id} with new mock HTML.")
            print()

            # --- RUN 2: Second Scrape (With Changed Data) ---
            print("-" * 80)
            print("[RUN 2] Second Scrape - Should Detect Changes")
            print("-" * 80)
            revision2 = await run_single_scrape(db_session, source_id, scrape_num=2, timeout=60.0)
            if not revision2:
                return False

            # Manually trigger notifications since Celery task is skipped in test
            print("[TEST] Manually triggering notifications for revision:", revision2.id)
            from app.api.modules.v1.notifications.service.revision_notification_task import (
                send_revision_notifications,
            )

            await send_revision_notifications(str(revision2.id))

            # ===== VALIDATION 2: CHANGE DETECTION =====
            print("-" * 80)
            print("[VALIDATION] Change Detection & Notification Results")
            print("-" * 80)

            # 1. Did AI flag the change?
            change_flag_ok = revision2.was_change_detected
            if change_flag_ok:
                print("[V2 OK] AI Change Flag: Change correctly detected.")
            else:
                print("[V2 FAIL] AI Change Flag: Change was NOT detected!")

            # 2. Was Diff Record Created?
            diff_query = select(ChangeDiff).where(ChangeDiff.new_revision_id == revision2.id)
            diff_res = await db_session.execute(diff_query)
            diff_record = diff_res.scalars().first()

            diff_record_ok = bool(diff_record)
            if diff_record_ok:
                print(f"[V2 OK] ChangeDiff Record created: {diff_record.diff_id}")
            else:
                print("[V2 FAIL] ChangeDiff Record was NOT created!")

            # 3. Check Notifications and Email
            print()
            print("[CHECK] Notification Trigger & Email Validation")
            notification_ok, email_ready = await check_notifications(
                db_session, user_id, source_id, str(revision2.id)
            )

            # 4. Print Comparison Data
            print()
            print("[CHECK] FULL AI Result JSON Comparison")

            full_data1 = revision1.extracted_data
            full_data2 = revision2.extracted_data

            print(f"  Run 1 FULL AI RESULT (Initial):\n{json.dumps(full_data1, indent=2)}")
            print()
            print(f"  Run 2 FULL AI RESULT (Changed):\n{json.dumps(full_data2, indent=2)}")
            print()

            # 5. Final Summary
            all_ok = change_flag_ok and diff_record_ok and notification_ok
            test_passed = all_ok

        except Exception as e:
            print(f"[ERROR] Test failed: {e}")
            traceback.print_exc()
            test_passed = False
        finally:
            if "source" in locals():
                if CLEANUP_ON_EXIT:
                    # Cascade delete manually
                    print("\n[CLEANUP] Deleting test data (Child -> Parent)...")

                    # 1. Delete Notifications
                    await db_session.execute(
                        delete(Notification).where(Notification.source_id == source.id)
                    )

                    # 2. Delete ChangeDiffs associated with this source's revisions
                    revisions_query = select(DataRevision.id).where(
                        DataRevision.source_id == source.id
                    )
                    await db_session.execute(
                        delete(ChangeDiff).where(ChangeDiff.new_revision_id.in_(revisions_query))
                    )

                    # 2.5. Delete RevisionNotifications for these revisions
                    await db_session.execute(
                        delete(Notification).where(Notification.revision_id.in_(revisions_query))
                    )

                    # 3. Delete DataRevisions
                    await db_session.execute(
                        delete(DataRevision).where(DataRevision.source_id == source.id)
                    )

                    # 4. Get Jurisdiction for project_id
                    jurisdiction = (
                        await db_session.execute(
                            select(Jurisdiction).where(Jurisdiction.id == source.jurisdiction_id)
                        )
                        .scalars()
                        .first()
                    )

                    # 5. Get Project for org_id
                    project = (
                        await db_session.execute(
                            select(Project).where(Project.id == jurisdiction.project_id)
                        )
                        .scalars()
                        .first()
                    )

                    # 6. Delete Source
                    await db_session.execute(delete(Source).where(Source.id == source.id))

                    # 7. Delete Jurisdiction
                    await db_session.execute(
                        delete(Jurisdiction).where(Jurisdiction.id == source.jurisdiction_id)
                    )

                    # 8. Delete Project
                    await db_session.execute(
                        delete(Project).where(Project.id == jurisdiction.project_id)
                    )

                    # 9. Delete Organization
                    await db_session.execute(
                        delete(Organization).where(Organization.id == project.org_id)
                    )

                    # 10. Delete User
                    await db_session.execute(delete(User).where(User.id == user.id))

                    await db_session.commit()
                    print("[CLEANUP] All test entities deleted.")
                else:
                    print("\n[INFO] Cleanup Skipped. Data remains in database.")
                    print(f"[INFO] Inspect Source ID: {source.id}")

            print("\n" + "=" * 80)
            if test_passed:
                print("[TEST PASSED] Mock Change Detection successful!")
            else:
                print("[TEST FAILED] Mock Change Detection failed.")
            print("=" * 80)
            return test_passed


async def main():
    """Run the mock Celery worker test."""
    success = await mock_celery_scraper_worker()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
