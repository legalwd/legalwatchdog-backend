import asyncio
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.billing.models import BillingAccount
from app.api.modules.v1.billing.tasks import _expire_trials_async

# ===================== CONFIG =====================
ORGANIZATION_ID = "69046481-7af9-4988-9285-0d4d0b4a9a35"  # <-- Replace with your org ID
# ==================================================


async def simulate_trial_expiration():
    async with AsyncSessionLocal() as db:
        # 1️⃣ Fetch billing account
        stmt = select(BillingAccount).where(BillingAccount.organization_id == ORGANIZATION_ID)
        result = await db.execute(stmt)
        billing_account = result.scalar_one_or_none()

        if not billing_account:
            print(f"No billing account found for org {ORGANIZATION_ID}")
            return

        # 2️⃣ Set trial to expired yesterday
        billing_account.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(billing_account)
        await db.commit()
        print(f"Trial set to expire at: {billing_account.trial_ends_at}")

    # 3️⃣ Run the expiration task
    await _expire_trials_async()  # This will update status to BLOCKED if trial expired

    # 4️⃣ Fetch account again to check status
    async with AsyncSessionLocal() as db:
        stmt = select(BillingAccount).where(BillingAccount.organization_id == ORGANIZATION_ID)
        result = await db.execute(stmt)
        billing_account = result.scalar_one()
        print(f"Billing account status after expiration task: {billing_account.status.value}")


# Run the async function
asyncio.run(simulate_trial_expiration())
