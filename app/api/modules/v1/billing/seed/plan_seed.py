import logging
from typing import Dict, List, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.modules.v1.billing.models import BillingPlan, PlanInterval, PlanTier

logger = logging.getLogger(__name__)


def _discounted_yearly(monthly_amount: int, discount_percent: int = 20) -> int:
    """
    Compute a yearly price from a monthly amount with a % discount.
    Args:
        monthly_amount (int): Monthly amount in cents (e.g. 2900 == $29.00).
        discount_percent (int, optional): Percentage discount to apply to the annual total.

    Returns:
        int: Discounted yearly amount in the same units as monthly_amount (rounded down).
    """
    yearly_no_discount = monthly_amount * 12
    discounted = int(yearly_no_discount * (100 - discount_percent) / 100)
    return discounted


# Plan Prices USD

# ESSENTIAL
ESSENTIAL_MONTHLY_PRICE_USD = getattr(settings, "ESSENTIAL_MONTHLY_PRICE", 2900)
ESSENTIAL_YEARLY_PRICE_USD = getattr(
    settings,
    "ESSENTIAL_YEARLY_PRICE",
    _discounted_yearly(ESSENTIAL_MONTHLY_PRICE_USD),
)

# PROFESSIONAL (PRO)
PRO_MONTHLY_PRICE_USD = getattr(settings, "PROFESSIONAL_MONTHLY_PRICE", 9900)

PRO_YEARLY_PRICE_USD = getattr(
    settings,
    "PROFESSIONAL_YEARLY_PRICE",
    _discounted_yearly(PRO_MONTHLY_PRICE_USD),
)

# ENTERPRISE
ENTERPRISE_MONTHLY_PRICE_USD = getattr(
    settings,
    "ENTERPRISE_MONTHLY_PRICE",
    29900,
)
ENTERPRISE_YEARLY_PRICE_USD = getattr(
    settings,
    "ENTERPRISE_YEARLY_PRICE",
    _discounted_yearly(ENTERPRISE_MONTHLY_PRICE_USD),
)


# Plan Stripe IDs

# ESSENTIAL
STRIPE_ESSENTIAL_MONTHLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_ESSENTIAL_MONTHLY_PRODUCT_ID",
    "prod_ESSENTIAL_MONTHLY_PLACEHOLDER",
)
STRIPE_ESSENTIAL_MONTHLY_PRICE_ID = getattr(
    settings,
    "STRIPE_ESSENTIAL_MONTHLY_PRICE_ID",
    "price_ESSENTIAL_MONTHLY_PLACEHOLDER",
)

STRIPE_ESSENTIAL_YEARLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_ESSENTIAL_YEARLY_PRODUCT_ID",
    "prod_ESSENTIAL_YEARLY_PLACEHOLDER",
)
STRIPE_ESSENTIAL_YEARLY_PRICE_ID = getattr(
    settings,
    "STRIPE_ESSENTIAL_YEARLY_PRICE_ID",
    "price_ESSENTIAL_YEARLY_PLACEHOLDER",
)

# PROFESSIONAL
STRIPE_PRO_MONTHLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_PRO_MONTHLY_PRODUCT_ID",
    "prod_PRO_MONTHLY_PLACEHOLDER",
)
STRIPE_PRO_MONTHLY_PRICE_ID = getattr(
    settings,
    "STRIPE_PRO_MONTHLY_PRICE_ID",
    "price_PRO_MONTHLY_PLACEHOLDER",
)

STRIPE_PRO_YEARLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_PRO_YEARLY_PRODUCT_ID",
    "prod_PRO_YEARLY_PLACEHOLDER",
)
STRIPE_PRO_YEARLY_PRICE_ID = getattr(
    settings,
    "STRIPE_PRO_YEARLY_PRICE_ID",
    "price_PRO_YEARLY_PLACEHOLDER",
)

# ENTERPRISE
STRIPE_ENTERPRISE_MONTHLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_ENTERPRISE_MONTHLY_PRODUCT_ID",
    "prod_ENTERPRISE_MONTHLY_PLACEHOLDER",
)
STRIPE_ENTERPRISE_MONTHLY_PRICE_ID = getattr(
    settings,
    "STRIPE_ENTERPRISE_MONTHLY_PRICE_ID",
    "price_ENTERPRISE_MONTHLY_PLACEHOLDER",
)

STRIPE_ENTERPRISE_YEARLY_PRODUCT_ID = getattr(
    settings,
    "STRIPE_ENTERPRISE_YEARLY_PRODUCT_ID",
    "prod_ENTERPRISE_YEARLY_PLACEHOLDER",
)
STRIPE_ENTERPRISE_YEARLY_PRICE_ID = getattr(
    settings,
    "STRIPE_ENTERPRISE_YEARLY_PRICE_ID",
    "price_ENTERPRISE_YEARLY_PLACEHOLDER",
)


BILLING_PLAN_SEED: List[dict] = [
    # ---------------- ESSENTIAL ----------------
    {
        "code": "ESSENTIAL_MONTHLY",
        "tier": PlanTier.ESSENTIAL,
        "label": "Essential",
        "description": "Best for individual consultants and small teams.",
        "interval": PlanInterval.MONTH,
        "currency": "USD",
        "amount": ESSENTIAL_MONTHLY_PRICE_USD,
        "stripe_product_id": STRIPE_ESSENTIAL_MONTHLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_ESSENTIAL_MONTHLY_PRICE_ID,
        "features": [
            "Up to 1 projects",
            "Up to 2 jurisdictions",
            "1-day snapshot history",
            "20 monthly scans",
            "Email summaries",
            "AI summaries",
        ],
        "is_most_popular": False,
        "is_active": True,
        "sort_order": 10,
    },
    {
        "code": "ESSENTIAL_YEARLY",
        "tier": PlanTier.ESSENTIAL,
        "label": "Essential (Yearly)",
        "description": "Best for individual consultants and small teams. \
Billed yearly with a 20% discount.",
        "interval": PlanInterval.YEAR,
        "currency": "USD",
        "amount": ESSENTIAL_YEARLY_PRICE_USD,
        "stripe_product_id": STRIPE_ESSENTIAL_YEARLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_ESSENTIAL_YEARLY_PRICE_ID,
        "features": [
            "Up to 1 projects",
            "Up to 2 jurisdictions",
            "1-day snapshot history",
            "20 monthly scans",
            "Email summaries",
            "AI summaries",
        ],
        "is_most_popular": False,
        "is_active": True,
        "sort_order": 15,
    },
    # ---------------- PROFESSIONAL ----------------
    {
        "code": "PRO_MONTHLY",
        "tier": PlanTier.PROFESSIONAL,
        "label": "Professional",
        "description": "Designed for growing legal and compliance teams.",
        "interval": PlanInterval.MONTH,
        "currency": "USD",
        "amount": PRO_MONTHLY_PRICE_USD,
        "stripe_product_id": STRIPE_PRO_MONTHLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_PRO_MONTHLY_PRICE_ID,
        "features": [
            "Up to 20 projects",
            "Up to 50 jurisdictions",
            "Unlimited scans",
            "Priority AI summaries",
            "Team notifications",
            "API access",
            "1-year snapshot history",
        ],
        "is_most_popular": True,
        "is_active": True,
        "sort_order": 20,
    },
    {
        "code": "PRO_YEARLY",
        "tier": PlanTier.PROFESSIONAL,
        "label": "Professional (Yearly)",
        "description": "Designed for growing legal and compliance teams. \
Billed yearly with a 20% discount.",
        "interval": PlanInterval.YEAR,
        "currency": "USD",
        "amount": PRO_YEARLY_PRICE_USD,
        "stripe_product_id": STRIPE_PRO_YEARLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_PRO_YEARLY_PRICE_ID,
        "features": [
            "Up to 20 projects",
            "Up to 50 jurisdictions",
            "Unlimited scans",
            "Priority AI summaries",
            "Team notifications",
            "API access",
            "1-year snapshot history",
        ],
        "is_most_popular": False,
        "is_active": True,
        "sort_order": 25,
    },
    # ---------------- ENTERPRISE ----------------
    {
        "code": "ENTERPRISE_MONTHLY",
        "tier": PlanTier.ENTERPRISE,
        "label": "Enterprise",
        "description": "For large organizations with complex regulatory needs.",
        "interval": PlanInterval.MONTH,
        "currency": "USD",
        "amount": ENTERPRISE_MONTHLY_PRICE_USD,
        "stripe_product_id": STRIPE_ENTERPRISE_MONTHLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_ENTERPRISE_MONTHLY_PRICE_ID,
        "features": [
            "Unlimited projects and jurisdictions",
            "Dedicated CSM",
            "Custom AI configuration",
            "SSO & advanced roles",
            "Unlimited snapshot history",
            "Full audit logs",
        ],
        "is_most_popular": False,
        "is_active": True,
        "sort_order": 30,
    },
    {
        "code": "ENTERPRISE_YEARLY",
        "tier": PlanTier.ENTERPRISE,
        "label": "Enterprise (Yearly)",
        "description": "For large organizations with complex regulatory needs. \
Billed yearly with a 20% discount.",
        "interval": PlanInterval.YEAR,
        "currency": "USD",
        "amount": ENTERPRISE_YEARLY_PRICE_USD,
        "stripe_product_id": STRIPE_ENTERPRISE_YEARLY_PRODUCT_ID,
        "stripe_price_id": STRIPE_ENTERPRISE_YEARLY_PRICE_ID,
        "features": [
            "Unlimited projects and jurisdictions",
            "Dedicated CSM",
            "Custom AI configuration",
            "SSO & advanced roles",
            "Unlimited snapshot history",
            "Full audit logs",
        ],
        "is_most_popular": False,
        "is_active": True,
        "sort_order": 35,
    },
]


async def seed_billing_plans(db: AsyncSession) -> None:
    """
    Upsert the default billing plans into the database.
    Args:
        db (AsyncSession): Asynchronous SQLAlchemy session

    Returns:
        None: Commits changes to the database; does not return a value.
    """

    result = await db.execute(select(BillingPlan))
    existing_by_key: Dict[Tuple[str, str, str], BillingPlan] = {}

    for plan in result.scalars():
        key = (plan.code, plan.interval.value, plan.currency.upper())
        existing_by_key[key] = plan

    seen_keys: Set[Tuple[str, str, str]] = set()

    for cfg in BILLING_PLAN_SEED:
        key = (cfg["code"], cfg["interval"].value, cfg["currency"].upper())
        seen_keys.add(key)
        existing = existing_by_key.get(key)

        if existing:
            existing.tier = cfg["tier"]
            existing.label = cfg["label"]
            existing.description = cfg["description"]
            existing.interval = cfg["interval"]
            existing.currency = cfg["currency"]
            existing.amount = cfg["amount"]
            existing.stripe_product_id = cfg["stripe_product_id"]
            existing.stripe_price_id = cfg["stripe_price_id"]
            existing.features_ = cfg["features"]
            existing.is_most_popular = cfg["is_most_popular"]
            existing.is_active = cfg["is_active"]
            existing.sort_order = cfg["sort_order"]

            logger.info(
                "Updated billing plan code=%s interval=%s currency=%s",
                key[0],
                key[1],
                key[2],
            )
        else:
            plan = BillingPlan(
                code=cfg["code"],
                tier=cfg["tier"],
                label=cfg["label"],
                description=cfg["description"],
                interval=cfg["interval"],
                currency=cfg["currency"],
                amount=cfg["amount"],
                stripe_product_id=cfg["stripe_product_id"],
                stripe_price_id=cfg["stripe_price_id"],
                features_=cfg["features"],
                is_most_popular=cfg["is_most_popular"],
                is_active=cfg["is_active"],
                sort_order=cfg["sort_order"],
            )
            db.add(plan)
            logger.info(
                "Created billing plan code=%s interval=%s currency=%s",
                key[0],
                key[1],
                key[2],
            )

    # Mark any old plans (no longer in the seed list) as inactive
    for key, plan in existing_by_key.items():
        if key not in seen_keys and plan.is_active:
            plan.is_active = False
            logger.info(
                "Marked plan inactive (no longer in seed) code=%s interval=%s currency=%s",
                key[0],
                key[1],
                key[2],
            )

    await db.commit()
