"""
Test Celery connection from FastAPI context.
This simulates what happens when the scraper runs from the API.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_in_async_context():
    """Test task queueing in async context like FastAPI."""
    print("=" * 80)
    print("TESTING CELERY FROM ASYNC CONTEXT (like FastAPI)")
    print("=" * 80)
    print()

    # This is what happens in the scraper
    print("1. Importing notification task...")
    from app.api.modules.v1.notifications.service.revision_notification_task import (
        send_revision_notifications_task,
    )

    print(f"   ✅ Task imported: {send_revision_notifications_task.name}")
    print()

    print("2. Checking task configuration...")
    print(f"   Task app: {send_revision_notifications_task.app}")
    print(f"   Task broker: {send_revision_notifications_task.app.conf.broker_url}")
    print()

    print("3. Attempting to queue task (like scraper does)...")
    try:
        # This is exactly what line 211 in scraper_service.py does
        result = send_revision_notifications_task.delay("test-revision-id-123")
        print(f"   ✅ Task queued: {result.id}")
        print(f"   Task state: {result.state}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback

        traceback.print_exc()
    print()

    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_in_async_context())
