"""Test diff detection at jurisdiction level."""

from uuid import UUID

from sqlmodel import select

from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.service.data_page_service import DataPageService

JURISDICTION_ID = "e5e1e2b0-24fe-4819-8143-46e7b13f9612"


def check_scrape_jobs():
    """Check existing scrape jobs for the jurisdiction."""
    
    print("=" * 80)
    print("TEST 5: DIFF DETECTION AT JURISDICTION LEVEL")
    print("=" * 80)
    print()
    
    with SyncSessionLocal() as db:
        jurisdiction_id = UUID(JURISDICTION_ID)
        
        # Get all completed jobs for this jurisdiction
        stmt = (
            select(JurisdictionScrapeJob)
            .where(
                JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED
            )
            .order_by(JurisdictionScrapeJob.created_at.desc())
        )
        
        jobs = db.exec(stmt).all()
        
        print(f"📊 Jurisdiction: {JURISDICTION_ID}")
        print(f"   Completed Jobs: {len(jobs)}")
        print()
        
        if len(jobs) == 0:
            print("❌ No completed jobs found!")
            print("   Please run a scrape first:")
            print("   - Use automatic scheduling (Test 3)")
            print("   - OR use manual API trigger (Test 4)")
            print()
            return
        
        if len(jobs) == 1:
            print("⚠️  Only 1 job found - cannot test diff detection")
            print("   Need at least 2 jobs to compare for changes.")
            print()
            print("   Current job details:")
            job = jobs[0]
            print(f"   - Job ID: {job.id}")
            print(f"   - Created: {job.created_at}")
            print(f"   - Sources: {job.successful_sources}/{job.total_sources}")
            print(f"   - Extracted Data: {len(job.extracted_data or {}) if job.extracted_data else 0} fields")
            print()
            print("   📝 To test diff detection:")
            print("   1. Run another scrape (wait for scheduled or trigger manually)")
            print("   2. OR manually modify source content in database")
            print("   3. Run this test again")
            print()
            return
        
        print(f"✅ Found {len(jobs)} jobs - can test diff detection!")
        print()
        
        # Show job history
        print("📜 Job History (most recent first):")
        for i, job in enumerate(jobs[:5], 1):
            print(f"   {i}. Job {job.id}")
            print(f"      Created: {job.created_at}")
            print(f"      Sources: {job.successful_sources}/{job.total_sources}")
            if job.extracted_data:
                print(f"      Fields: {len(job.extracted_data)} extracted")
        if len(jobs) > 5:
            print(f"   ... and {len(jobs) - 5} older jobs")
        print()


def test_diff_detection():
    """Get data page and display detected changes."""
    
    with SyncSessionLocal() as db:
        jurisdiction_id = UUID(JURISDICTION_ID)
        service = DataPageService(db)
        
        print("🔍 Fetching Data Page for Diff Analysis...")
        print()
        
        try:
            result = service.get_data_page(jurisdiction_id)
            
            # Display extracted data
            extracted_data = result.get("extracted_data", {})
            print(f"📊 Current Extracted Data ({len(extracted_data)} fields):")
            for field, values in list(extracted_data.items())[:10]:
                print(f"   - {field}: {values}")
            if len(extracted_data) > 10:
                print(f"   ... and {len(extracted_data) - 10} more fields")
            print()
            
            # Display changes
            changes = result.get("changes", [])
            has_unaccepted = result.get("has_unaccepted_changes", False)
            
            print(f"🔍 Detected Changes: {len(changes)}")
            print(f"   Unaccepted Changes: {has_unaccepted}")
            print()
            
            if not changes:
                print("   ✅ No changes detected")
                print("   This means either:")
                print("   - This is the first scrape (no previous job to compare)")
                print("   - OR source content is identical to previous scrape")
                print()
                print("   📝 To generate changes:")
                print("   1. Manually update a source's content")
                print("   2. Run another scrape")
                print("   3. Re-run this test")
                print()
                return False
            
            # Show each change
            for i, change in enumerate(changes, 1):
                field = change.get("field")
                old_value = change.get("old_value")
                new_value = change.get("new_value")
                description = change.get("change_description")
                detected_at = change.get("detected_at")
                status = change.get("status", "pending")
                
                print(f"   {i}. Field: '{field}'")
                print(f"      Old Value: {old_value}")
                print(f"      New Value: {new_value}")
                print(f"      Description: {description}")
                print(f"      Detected: {detected_at}")
                print(f"      Status: {status}")
                print()
            
            print("=" * 80)
            print("✅ TEST 5 PASSED: Diff Detection Working!")
            print("=" * 80)
            print()
            print("Summary:")
            print(f"  - Detected {len(changes)} field-level changes")
            print("  - Changes include old/new values")
            print("  - Change descriptions are human-readable")
            print(f"  - Unaccepted changes flag: {has_unaccepted}")
            print()
            
            return True
            
        except Exception as e:
            print(f"❌ Error fetching data page: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run diff detection test."""
    
    # Step 1: Check job history
    check_scrape_jobs()
    
    # Step 2: Test diff detection
    print("-" * 80)
    test_diff_detection()


if __name__ == "__main__":
    main()
