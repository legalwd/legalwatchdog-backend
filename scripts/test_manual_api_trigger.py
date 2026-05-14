"""Test manual API trigger for jurisdiction scraping."""

import json
import time
from typing import Optional

import requests

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
ORG_ID = "429d6a37-c686-4e49-aff4-a1222de05f40"  # Update with your organization ID
JURISDICTION_ID = "e5e1e2b0-24fe-4819-8143-46e7b13f9612"
AUTH_TOKEN = ""  # Update with valid token


def get_headers():
    """Get request headers with authentication."""
    return {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }


def trigger_scrape() -> Optional[str]:
    """Trigger manual jurisdiction scrape.
    
    Returns:
        str: Job ID if successful, None otherwise.
    """
    url = f"{BASE_URL}/organizations/{ORG_ID}/jurisdictions/{JURISDICTION_ID}/scrape"
    
    print("=" * 80)
    print("TEST 4: MANUAL API TRIGGER")
    print("=" * 80)
    print("\n1️⃣  Triggering scrape...")
    print(f"   POST {url}")
    print()
    
    try:
        response = requests.post(url, headers=get_headers())
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
        print()
        
        if response.status_code == 202:
            data = response.json().get("data", {})
            job_id = data.get("job_id")
            print(f"   ✅ Scrape initiated! Job ID: {job_id}")
            return job_id
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def poll_status(max_polls: int = 60, interval: int = 5):
    """Poll scrape status until completion.
    
    Args:
        max_polls: Maximum number of poll attempts.
        interval: Seconds between polls.
    """
    url = f"{BASE_URL}/organizations/{ORG_ID}/jurisdictions/{JURISDICTION_ID}/scrape-status"
    
    print(f"\n2️⃣  Polling status (every {interval}s, max {max_polls} attempts)...")
    print(f"   GET {url}")
    print()
    
    for i in range(max_polls):
        try:
            response = requests.get(url, headers=get_headers())
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                status = data.get("status")
                progress = data.get("progress_percentage", 0)
                successful = data.get("successful_sources", 0)
                total = data.get("total_sources", 0)
                
                print(f"   [{i+1}/{max_polls}] Status: {status} | Progress: {progress}% | Sources: {successful}/{total}")
                
                if status in ["COMPLETED", "FAILED"]:
                    print(f"\n   ✅ Job finished with status: {status}")
                    return status
                    
            else:
                print(f"   ⚠️  API returned {response.status_code}")
            
            time.sleep(interval)
            
        except Exception as e:
            print(f"   ❌ Poll error: {e}")
            time.sleep(interval)
    
    print(f"\n   ⚠️  Timeout after {max_polls * interval}s")
    return None


def get_data_page():
    """Retrieve full consolidated data page."""
    url = f"{BASE_URL}/organizations/{ORG_ID}/jurisdictions/{JURISDICTION_ID}/data-page"
    
    print("\n3️⃣  Fetching consolidated data page...")
    print(f"   GET {url}")
    print()
    
    try:
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            print("   ✅ Data page retrieved!")
            print(f"   Status: {data.get('status')}")
            print(f"   Summary: {data.get('summary', 'N/A')[:200]}...")
            print()
            
            # Show extracted data fields
            extracted_data = data.get("extracted_data", {})
            if extracted_data:
                print(f"   📊 Extracted Fields ({len(extracted_data)} total):")
                for field, values in list(extracted_data.items())[:5]:
                    print(f"      - {field}: {values}")
                if len(extracted_data) > 5:
                    print(f"      ... and {len(extracted_data) - 5} more")
            print()
            
            # Show changes
            changes = data.get("changes", [])
            change_detection = data.get("change_detection", {})
            
            print(f"   🔍 Detected Changes: {len(changes)}")
            
            # Show AI change detection summary
            if change_detection:
                print(f"\\n   🤖 AI Change Detection:")
                print(f"      Has Changed: {change_detection.get('has_changed')}")
                print(f"      Risk Level: {change_detection.get('risk_level')}")
                print(f"      Summary: {change_detection.get('change_summary')}")
                print()
            
            if changes:
                for change in changes[:3]:
                    print(f"      - Field: {change.get('field')}")
                    print(f"        Old: {change.get('old_value')}")
                    print(f"        New: {change.get('new_value')}")
                    print(f"        Description: {change.get('change_description')}")
                    print()
                if len(changes) > 3:
                    print(f"      ... and {len(changes) - 3} more changes")
            else:
                print("      No changes detected (first run or identical data)")
            
            return data
            
        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def main():
    """Run full manual API test."""
    
    # Check configuration
    if ORG_ID == "YOUR_ORG_ID" or AUTH_TOKEN == "YOUR_AUTH_TOKEN":
        print("=" * 80)
        print("⚠️  CONFIGURATION REQUIRED")
        print("=" * 80)
        print("\nPlease update the following variables in this script:")
        print(f"  - ORG_ID: Currently '{ORG_ID}'")
        print(f"  - AUTH_TOKEN: Currently '{AUTH_TOKEN[:20]}...'")
        print(f"\nJurisdiction ID is already set to: {JURISDICTION_ID}")
        print("\nTo get your auth token:")
        print("  1. Log in to the application")
        print("  2. Open browser DevTools (F12)")
        print("  3. Go to Application > Local Storage")
        print("  4. Find 'access_token' or similar")
        print("\nTo get your organization ID:")
        print("  1. Query: SELECT id, name FROM organizations;")
        print("  2. Or check API response from /me endpoint")
        print("=" * 80)
        return
    
    # Step 1: Trigger scrape
    job_id = trigger_scrape()
    if not job_id:
        print("\n❌ Failed to trigger scrape. Check your credentials and IDs.")
        return
    
    # Step 2: Poll status
    final_status = poll_status(max_polls=60, interval=5)
    
    # Step 3: Get results
    if final_status == "COMPLETED":
        get_data_page()
        print("\n" + "=" * 80)
        print("✅ TEST 4 PASSED: Manual API Trigger")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ TEST 4 INCOMPLETE: Check Celery logs for errors")
        print("=" * 80)


if __name__ == "__main__":
    main()
