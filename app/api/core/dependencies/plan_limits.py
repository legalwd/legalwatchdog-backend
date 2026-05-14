import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from app.api.core.config import settings
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.db.database import get_db
from app.api.modules.v1.billing.models import PlanTier
from app.api.modules.v1.billing.service.billing_service import get_billing_service
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source

logger = logging.getLogger(__name__)


def _is_dev_env() -> bool:
    env = getattr(settings, "ENVIRONMENT", "prod")
    return env.lower() in ("dev", "development")


@dataclass
class PlanLimits:
    max_projects: Optional[int] = None
    max_jurisdictions: Optional[int] = None
    monthly_scans: Optional[int] = None


def _none_if_negative(value: int | None) -> Optional[int]:
    """
    Interpret negative values as unlimited (None).

    Args:
        value (int | None): The numeric value to interpret.
    Returns:
        Optional[int]: None if the value is None, negative, or
            cannot be converted to int; otherwise the integer value.
    """
    if value is None:
        return None
    try:
        return None if int(value) < 0 else int(value)
    except (TypeError, ValueError):
        return None


PLAN_LIMITS_BY_TIER: dict[PlanTier, PlanLimits] = {
    PlanTier.ESSENTIAL: PlanLimits(
        max_projects=_none_if_negative(settings.ESSENTIAL_MAX_PROJECTS),
        max_jurisdictions=_none_if_negative(settings.ESSENTIAL_MAX_JURISDICTIONS),
        monthly_scans=_none_if_negative(settings.ESSENTIAL_MONTHLY_SCANS),
    ),
    PlanTier.PROFESSIONAL: PlanLimits(
        max_projects=_none_if_negative(settings.PRO_MAX_PROJECTS),
        max_jurisdictions=_none_if_negative(settings.PRO_MAX_JURISDICTIONS),
        monthly_scans=_none_if_negative(settings.PRO_MONTHLY_SCANS),
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        max_projects=_none_if_negative(settings.ENTERPRISE_MAX_PROJECTS),
        max_jurisdictions=_none_if_negative(settings.ENTERPRISE_MAX_JURISDICTIONS),
        monthly_scans=_none_if_negative(settings.ENTERPRISE_MONTHLY_SCANS),
    ),
}


async def _get_org_plan_tier(
    organization_id: UUID,
    db: AsyncSession,
) -> PlanTier:
    """
    Resolve the org's current plan tier.

    Args:
        organization_id (UUID): The organization's UUID to resolve the plan for.
        db (AsyncSession): Async database session.

    Returns:
        PlanTier: The resolved plan tier for the organization.
    """
    billing_service = get_billing_service(db)
    account = await billing_service.get_billing_account_by_org(organization_id)

    if not account:
        logger.info("Org %s has no billing account, defaulting to ESSENTIAL tier", organization_id)
        return PlanTier.ESSENTIAL

    if account.current_price_id:
        plan = await billing_service.get_plan_by_stripe_price_id(account.current_price_id)
        if plan:
            return plan.tier

    meta = getattr(account, "metadata_", {}) or {}
    tier_value = meta.get("plan_tier")
    if tier_value:
        try:
            return PlanTier(tier_value)
        except ValueError:
            logger.warning("Unknown plan_tier=%s on billing account %s", tier_value, account.id)

    return PlanTier.ESSENTIAL


async def get_plan_limits_for_org(
    organization_id: UUID,
    db: AsyncSession,
) -> PlanLimits:
    """
    Resolve plan limits for an organization.

    Args:
        organization_id (UUID): The organization's UUID to resolve limits for.
        db (AsyncSession): Async database session.

    Returns:
        PlanLimits: The resolved plan limits for the organization.
    """
    tier = await _get_org_plan_tier(organization_id, db)
    limits = PLAN_LIMITS_BY_TIER.get(tier)

    if not limits:
        logger.warning("No limits configured for tier=%s, defaulting to unlimited", tier)
        return PlanLimits()

    return limits


async def _count_active_projects_for_org(
    organization_id: UUID,
    db: AsyncSession,
) -> int:
    """
    Count active (non-deleted) projects for an org.

    Args:
        organization_id (UUID): The organization's UUID to count projects for.
        db (AsyncSession): Async database session.

    Returns:
        int: Number of active (non-deleted) projects for the organization.
    """
    stmt = (
        select(func.count())
        .select_from(Project)
        .where(
            Project.org_id == organization_id,
            Project.is_deleted.is_(False),
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def require_project_creation_allowed(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Guard to run BEFORE creating a new project.

    Args:
        organization_id (UUID): The organization's UUID to check limits for.
        db (AsyncSession): Async database session (injected via Depends).

    Returns:
        None: Returns None when project creation is allowed.

    Raises:
        HTTPException(402) if the org has reached its project limit.
    """
    if _is_dev_env():
        logger.info(
            "Skipping project plan limit enforcement for org=%s in dev environment",
            organization_id,
        )
        return

    limits = await get_plan_limits_for_org(organization_id, db)

    if limits.max_projects is None:
        return

    return  # disabling billing

    current = await _count_active_projects_for_org(organization_id, db)

    if current >= limits.max_projects:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your current plan allows up to {limits.max_projects} "
                f"{'project' if limits.max_projects < 2 else 'projects'}. "
                "Please upgrade your subscription to create more projects."
            ),
        )


async def _count_jurisdictions_for_org(
    organization_id: UUID,
    db: AsyncSession,
) -> int:
    """
    Count active jurisdictions for an org.

    Args:
        organization_id (UUID): The organization's UUID to count jurisdictions for.
        db (AsyncSession): Async database session.

    Returns:
        int: Number of active (non-deleted) jurisdictions for the organization.
    """
    stmt = (
        select(func.count())
        .select_from(Jurisdiction)
        .join(Project, Jurisdiction.project_id == Project.id)
        .where(
            Project.org_id == organization_id,
            Jurisdiction.is_deleted == False,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def require_jurisdiction_creation_allowed(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Guard to run BEFORE creating a new jurisdiction.

    Args:
        organization_id (UUID): The organization's UUID to evaluate limits for.
        db (AsyncSession): Async DB session (injected via Depends).

    Returns:
        None:

    Raises:
        HTTPException if the jurisdiction limit is exceeded.
    """
    if _is_dev_env():
        logger.info(
            "Skipping jurisdiction plan limit enforcement for org=%s in dev environment",
            organization_id,
        )
        return

    limits = await get_plan_limits_for_org(organization_id, db)

    if limits.max_jurisdictions is None:
        return

    return  # disabling billing

    current = await _count_jurisdictions_for_org(organization_id, db)

    if current >= limits.max_jurisdictions:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Your current plan allows up to {limits.max_jurisdictions} "
                f"{'jurisdiction' if limits.max_jurisdictions < 2 else 'jurisdictions'}. "
                "Please upgrade your plan to add more jurisdictions."
            ),
        )


async def _count_monthly_scans_for_org(
    organization_id: UUID,
    db: AsyncSession,
) -> int:
    """
    Count scrapes (scans) for an org in the current calendar month.

    Args:
        organization_id (UUID): The organization's UUID to count scans for.
        db (AsyncSession): Async database session.

    Returns:
        int: Number of DataRevision records (scans) for the org in the current calendar month.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = (
        select(func.count())
        .select_from(DataRevision)
        .join(Source, DataRevision.source_id == Source.id)
        .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
        .join(Project, Jurisdiction.project_id == Project.id)
        .where(
            Project.org_id == organization_id,
            DataRevision.scraped_at >= month_start,
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def require_scan_allowed_for_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Guard to run BEFORE initiating a scan for a specific source.

    Args:
        source_id (UUID): The UUID of the Source to check.
        db (AsyncSession): Async database session (injected via Depends).

    Returns:
        None: Returns None when the scan is allowed.

    Raises:
        HTTPException(status_code=404): If the source is not found.
        HTTPException(status_code=402): If the organization's monthly scan limit has been reached.
    """
    if _is_dev_env():
        logger.info(
            "Skipping scan plan limit enforcement for source=%s in dev environment",
            source_id,
        )
        return

    stmt = (
        select(Project.org_id)
        .select_from(Source)
        .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
        .join(Project, Jurisdiction.project_id == Project.id)
        .where(Source.id == source_id)
    )
    result = await db.execute(stmt)
    org_id = result.scalar_one_or_none()

    if not org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    await require_billing_access(organization_id=org_id, db=db)

    limits = await get_plan_limits_for_org(org_id, db)
    if limits.monthly_scans is None:
        return

    return  # disabling billing

    used_scans = await _count_monthly_scans_for_org(org_id, db)

    if used_scans >= limits.monthly_scans:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="You’ve reached your monthly scan limit for your current plan.",
        )
