"""
Test script for manual ticket creation endpoint
Run this after the server is started
"""

import asyncio
import json

import httpx

BASE_URL = "http://localhost:8000"


async def login():
    """Login and get access token"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "ticket.test@example.com", "password": "Test123!"},
        )
        if response.status_code == 200:
            data = response.json()
            return data["data"]["access_token"]
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(response.text)
            return None


async def get_user_orgs(token):
    """Get user organizations"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/users/me/organizations",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            data = response.json()
            # Extract organizations from the paginated response
            return data["data"]["organizations"]
        else:
            print(f"❌ Get orgs failed: {response.status_code}")
            print(response.text)
            return []


async def get_projects(token, org_id):
    """Get organization projects"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/organizations/{org_id}/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            data = response.json()
            # The response structure is: {data: {projects: [...], total, page, limit, total_pages}}
            projects_data = data.get("data", {})
            if isinstance(projects_data, dict):
                return projects_data.get("projects", [])
            return []
        else:
            print(f"❌ Get projects failed: {response.status_code}")
            print(response.text)
            return []


async def get_change_diffs(token, org_id, project_id):
    """Get change diffs for a project"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/organizations/{org_id}/projects/{project_id}/changes",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            print(f"⚠️  Get change diffs: {response.status_code}")
            return []


async def create_manual_ticket_without_change(token, org_id, project_id):
    """Test creating a manual ticket without change_diff_id"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {
            "title": "Manual Test Ticket - No Change",
            "description": "This is a manually created ticket for testing purposes.",
            "content": {"test": "data", "manually_created": True},
            "priority": "medium",
            "status": "open",
            "project_id": project_id,
        }

        response = await client.post(
            f"{BASE_URL}/api/v1/organizations/{org_id}/projects/{project_id}/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )

        print("\n" + "=" * 60)
        print("TEST 1: Manual Ticket WITHOUT change_diff_id")
        print("=" * 60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 201:
            print("✅ SUCCESS: Ticket created without change_diff_id")
            return response.json()
        else:
            print("❌ FAILED: Could not create ticket")
            return None


async def create_manual_ticket_with_change(token, org_id, project_id, change_diff_id):
    """Test creating a manual ticket with change_diff_id (auto-population)"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        payload = {
            "change_diff_id": change_diff_id,
            "status": "open",
            "priority": "high",
            "project_id": project_id,
        }

        response = await client.post(
            f"{BASE_URL}/api/v1/organizations/{org_id}/projects/{project_id}/tickets",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )

        print("\n" + "=" * 60)
        print("TEST 2: Manual Ticket WITH change_diff_id (Auto-population)")
        print("=" * 60)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 201:
            print("✅ SUCCESS: Ticket created with auto-population from ChangeDiff")
            data = response.json()["data"]
            print("\nAuto-populated fields:")
            print(f"  - Title: {data.get('title')}")
            print(f"  - Content: {json.dumps(data.get('content', {}), indent=4)}")
            return data
        else:
            print("❌ FAILED: Could not create ticket with change_diff_id")
            return None


async def main():
    print("=" * 60)
    print("Manual Ticket Creation Endpoint Test")
    print("=" * 60)

    # Step 1: Login
    print("\n1. Logging in...")
    token = await login()
    if not token:
        print("❌ Login failed. Make sure:")
        print("   - Server is running (uv run python main.py)")
        print("   - Test user exists (run scripts/quick_setup_test_data.py)")
        return
    print("✅ Login successful")

    # Step 2: Get organizations
    print("\n2. Getting organizations...")
    orgs = await get_user_orgs(token)
    if not orgs:
        print("❌ No organizations found")
        return
    org_id = orgs[0]["organization_id"]
    print(f"✅ Using organization: {orgs[0]['name']} ({org_id})")

    # Step 3: Get projects
    print("\n3. Getting projects...")
    projects = await get_projects(token, org_id)
    if not projects:
        print("❌ No projects found")
        print("\n💡 To fix this, run: uv run python scripts/quick_setup_test_data.py")
        print("   This will create a test project in your organization.")
        return
    project_id = projects[0]["id"]
    print(f"✅ Using project: {projects[0]['title']} ({project_id})")

    # Step 4: Test manual ticket creation WITHOUT change_diff_id
    await create_manual_ticket_without_change(token, org_id, project_id)

    # Step 5: Get change diffs and test WITH change_diff_id
    print("\n4. Getting change diffs...")
    change_diffs = await get_change_diffs(token, org_id, project_id)

    if change_diffs:
        change_diff_id = change_diffs[0]["diff_id"]
        print(f"✅ Found change diff: {change_diff_id}")
        await create_manual_ticket_with_change(token, org_id, project_id, change_diff_id)
    else:
        print("⚠️  No change diffs found. Skipping auto-population test.")
        print("   To test auto-population, create a change diff first.")

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
