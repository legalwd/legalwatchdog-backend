import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.billing.models import BillingAccount, BillingStatus
from app.api.modules.v1.organization.models.organization_model import Organization


async def create_test_data():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Create two organizations
            org1 = Organization(
                id=uuid.uuid4(),
                name="Test Org 1",
                settings={},
                billing_info={},
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            org2 = Organization(
                id=uuid.uuid4(),
                name="Test Org 2",
                settings={},
                billing_info={},
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add_all([org1, org2])

        await session.commit()

        async with session.begin():
            # Create expired trial account
            expired_trial = BillingAccount(
                id=uuid.uuid4(),
                organization_id=org1.id,
                stripe_customer_id="cus_test_expired",
                status=BillingStatus.TRIALING,
                trial_starts_at=datetime.now(timezone.utc) - timedelta(days=15),
                trial_ends_at=datetime.now(timezone.utc) - timedelta(days=1),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            # Create trial expiring in 3 days
            expiring_3d = BillingAccount(
                id=uuid.uuid4(),
                organization_id=org2.id,
                stripe_customer_id="cus_test_3d",
                status=BillingStatus.TRIALING,
                trial_starts_at=datetime.now(timezone.utc),
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=3),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            session.add_all([expired_trial, expiring_3d])

        await session.commit()

        created_objects = {
            "organizations": [org1, org2],
            "billing_accounts": [expired_trial, expiring_3d],
        }

        return created_objects


if __name__ == "__main__":
    created_objects = asyncio.run(create_test_data())
    print(created_objects)
    print(" All test data created successfully!")
