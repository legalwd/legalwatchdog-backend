"""
Test Celery and Redis connection.
"""

import sys
from pathlib import Path

from app.api.core.config import settings

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("TESTING CELERY AND REDIS CONNECTION")
print("=" * 80)
print()

# Test 1: Check settings
print("1. Checking Settings...")

print(f"   REDIS_BROKER_URL: {settings.REDIS_BROKER_URL}")
print(f"   REDIS_BACKEND_URL: {settings.REDIS_BACKEND_URL}")
print()

# Test 2: Test Redis connection directly
print("2. Testing Redis Connection...")
try:
    import redis

    # Test broker URL
    broker_url = settings.REDIS_BROKER_URL
    r = redis.from_url(broker_url)
    pong = r.ping()
    print(f"   ✅ Redis BROKER connection: {pong}")

    # Test backend URL
    backend_url = settings.REDIS_BACKEND_URL
    r2 = redis.from_url(backend_url)
    pong2 = r2.ping()
    print(f"   ✅ Redis BACKEND connection: {pong2}")
except Exception as e:
    print(f"   ❌ Redis connection failed: {e}")
print()

# Test 3: Check Celery app configuration
print("3. Checking Celery App Configuration...")
try:
    from app.celery_app import celery_app

    print(f"   Celery broker: {celery_app.conf.broker_url}")
    print(f"   Celery backend: {celery_app.conf.result_backend}")
    print(f"   Broker connection retry: {celery_app.conf.broker_connection_retry_on_startup}")
except Exception as e:
    print(f"   ❌ Failed to load Celery app: {e}")
print()

# Test 4: Try to send a test task
print("4. Testing Task Queue...")
try:
    from app.api.modules.v1.notifications.service.revision_notification_task import (
        send_revision_notifications_task,
    )
    from app.celery_app import celery_app

    print(f"   Task name: {send_revision_notifications_task.name}")
    print(f"   Task registered: {send_revision_notifications_task.name in celery_app.tasks}")

    # Try to get task info
    print("   Attempting to queue test task...")

    # This should fail with the same error if there's a connection issue
    result = send_revision_notifications_task.delay("test-revision-id")
    print(f"   ✅ Task queued successfully: {result.id}")
    print(f"   Task ID: {result.id}")

except Exception as e:
    print(f"   ❌ Failed to queue task: {e}")
    import traceback

    traceback.print_exc()
print()

# Test 5: Check if Celery worker is running
print("5. Checking Celery Worker Status...")
try:
    from celery.app.control import Inspect

    i = Inspect(app=celery_app)

    # Check active workers
    stats = i.stats()
    if stats:
        print(f"   ✅ Active workers: {list(stats.keys())}")

        # Check registered tasks
        registered = i.registered()
        if registered:
            for worker, tasks in registered.items():
                print(f"   Worker {worker} has {len(tasks)} registered tasks")
                if "send_revision_notifications" in str(tasks):
                    print("   ✅ send_revision_notifications is registered")
    else:
        print("   ⚠️  No active workers found")

except Exception as e:
    print(f"   ❌ Failed to inspect workers: {e}")
print()

print("=" * 80)
print("DIAGNOSIS:")
print("=" * 80)

# Diagnosis
print()
print("If you see 'Connection refused' in test 4, it means:")
print("  - FastAPI app can't connect to Redis broker")
print("  - Even though Celery worker IS connected")
print()
print("This could be because:")
print("  1. FastAPI app is using different settings/env")
print("  2. Redis URL format is incorrect for kombu")
print("  3. Network/firewall issue")
print()
print("If test 4 succeeds, the issue is somewhere else.")
print()
