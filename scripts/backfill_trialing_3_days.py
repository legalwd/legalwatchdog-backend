import asyncio
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.api.db.database import AsyncSessionLocal
from app.api.modules.v1.billing.models.billing_account import BillingAccount, BillingStatus
from app.api.modules.v1.billing.service.billing_service import get_billing_service
from app.api.modules.v1.organization.models.organization_model import Organization

TRIAL_MAX_DAYS = 3
DRY_RUN = False


async def backfill_trialing_accounts():
    now = datetime.now(timezone.utc)
    target_end = now + timedelta(days=TRIAL_MAX_DAYS)

    async with AsyncSessionLocal() as db:
        billing_service = get_billing_service(db)

        stmt = select(Organization).where(
            Organization.plan.is_(None) | Organization.plan.in_(["free"])
        )
        result = await db.execute(stmt)
        organizations = result.scalars().all()

        print(f"Found {len(organizations)} organizations to inspect.")

        updated = 0
        created = 0

        for org in organizations:
            account = await billing_service.get_billing_account_by_org(org.id)

            if not account and DRY_RUN:
                print(f"[DRY RUN] Would create billing account for org={org.id}")
                continue

            if not account:
                account = await billing_service.create_billing_account(
                    organization_id=org.id,
                    metadata={"backfill": "trialing_3_days"},
                )
                created += 1

            changed = False

            if account.status != BillingStatus.TRIALING:
                account.status = BillingStatus.TRIALING
                changed = True

            if account.trial_starts_at is None:
                account.trial_starts_at = now
                changed = True

            if account.trial_ends_at is None or account.trial_ends_at > target_end:
                account.trial_ends_at = target_end
                changed = True

            if DRY_RUN:
                print(
                    "[DRY RUN] Would update org=%s billing_account=%s "
                    "status=%s trial_ends_at=%s"
                    % (
                        org.id,
                        account.id if isinstance(account, BillingAccount) else "new",
                        BillingStatus.TRIALING.value,
                        target_end.isoformat(),
                    )
                )
                continue

            if changed:
                db.add(account)
                await db.commit()
                await db.refresh(account)
                await billing_service._sync_org_billing_from_account(
                    db=db,
                    organization_id=org.id,
                    account=account,
                    plan_info=None,
                )
                updated += 1

        if DRY_RUN:
            print("Dry run complete.")
        else:
            print(f"Created {created} billing accounts, updated {updated} accounts.")


if __name__ == "__main__":
    asyncio.run(backfill_trialing_accounts())
