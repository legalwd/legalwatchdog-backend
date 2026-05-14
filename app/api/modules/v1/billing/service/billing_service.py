import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.modules.v1.billing.models import (
    BillingAccount,
    BillingPlan,
    BillingStatus,
    InvoiceHistory,
    InvoiceStatus,
    PaymentMethod,
)
from app.api.modules.v1.billing.schemas import (
    BillingPlanInfo,
)
from app.api.modules.v1.billing.stripe.errors import SubscriptionAlreadyCanceledError
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    attach_payment_method as stripe_attach_payment_method,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    cancel_subscription as stripe_cancel_subscription,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_customer as stripe_create_customer,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_invoice_for_customer_with_price_id as stripe_create_invoice_for_customer_with_price_id,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    detach_payment_method as stripe_detach_payment_method,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    retrieve_subscription as stripe_retrieve_subscription,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    update_subscription_price as stripe_update_subscription_price,
)
from app.api.modules.v1.billing.utils.billings_utils import (
    map_stripe_invoice_status,
    map_stripe_status_to_billing_status,
    parse_ts,
)
from app.api.modules.v1.organization.models.organization_model import Organization

logger = logging.getLogger(__name__)

TRIAL_DURATION_DAYS = settings.TRIAL_DURATION_DAYS
DEFAULT_CURRENCY = "USD"


class BillingService:
    """
    Service layer for billing operations.

    This class encapsulates domain logic and database interactions for billing
    accounts, payment methods and invoices.
    """

    def __init__(self, db: AsyncSession):
        """Create a BillingService.

        Args:
            db: AsyncSession instance (dependency-injected) used for DB access.
        """
        self.db = db

    async def is_org_allowed_usage(
        self, organization_id: UUID
    ) -> Tuple[bool, BillingStatus | None]:
        """
        Check whether an organization is currently allowed to use the product based on its
        billing account and status.

        Args:
            organization_id (UUID): ID of the organization to evaluate for billing eligibility.

        Returns:
            Tuple[bool, BillingStatus | None]: A tuple of (allowed, effective_status) indicating
            whether usage is permitted and the resolved billing status.
        """
        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        account: BillingAccount | None = await self.db.scalar(stmt)

        if not account:
            return False, None

        now = datetime.now(timezone.utc)

        effective_status: BillingStatus = account.status

        if effective_status == BillingStatus.TRIALING:
            if account.trial_ends_at and now > account.trial_ends_at:
                effective_status = BillingStatus.UNPAID

        if effective_status == BillingStatus.ACTIVE:
            if account.current_period_end and now > account.current_period_end:
                if account.cancel_at_period_end:
                    effective_status = BillingStatus.CANCELLED
                else:
                    effective_status = BillingStatus.PAST_DUE

        allowed = False

        if effective_status in (BillingStatus.TRIALING, BillingStatus.ACTIVE):
            allowed = True

        else:
            allowed = False

        return allowed, effective_status

    async def list_active_plans(self) -> List[BillingPlan]:
        """
        Return all active subscription plans configured in the system.

        Args:
            None

        Returns:
            List[BillingPlan]: A list of active BillingPlan objects ordered by sort_order
            and then by amount.
        """
        stmt = (
            select(BillingPlan)
            .where(BillingPlan.is_active)
            .order_by(BillingPlan.sort_order.asc(), BillingPlan.amount.asc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_plan_by_id(self, plan_id: UUID) -> BillingPlan | None:
        """
        Fetch a billing plan by its primary key.

        Args:
            plan_id (UUID): ID of the plan in the `billing_plans` table.

        Returns:
            BillingPlan | None: The matching plan, or None if not found.
        """
        stmt = select(BillingPlan).where(BillingPlan.id == plan_id)
        return await self.db.scalar(stmt)

    async def get_plan_by_stripe_price_id(self, price_id: str) -> Optional[BillingPlan]:
        """
        Look up a billing plan by its Stripe price ID.
        Args:
            price_id (str): Stripe price identifier (e.g., "price_...") to look up.

        Returns:
            Optional[BillingPlan]: The BillingPlan matching the given Stripe price id
        """
        stmt = select(BillingPlan).where(BillingPlan.stripe_price_id == price_id)
        return await self.db.scalar(stmt)

    async def create_billing_account(
        self,
        organization_id: UUID,
        currency: str = DEFAULT_CURRENCY,
        initial_status: BillingStatus = BillingStatus.TRIALING,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
    ) -> BillingAccount:
        """
        Create a billing account for an organisation.

        Args:
            organization_id (UUID): The ID of the organization to create the billing account for.
            currency (str, optional): ISO currency code for the account. Defaults to "USD".
            initial_status (BillingStatus, optional): Initial billing status for the account.
                Defaults to BillingStatus.TRIALING.
            metadata (Optional[Dict[str, Any]], optional): Optional metadata to attach.
            customer_email (Optional[str]): Optional email to use to create Stripe Customer.
            customer_name (Optional[str]): Optional name for Stripe Customer.

        Raises:
            ValueError: If a billing account already exists for the given organization_id.
            Exception: If a database operation (flush/refresh/commit) fails;
                the transaction will be rolled back and the original exception re-raised.

        Returns:
            BillingAccount: persisted billing account object

        """
        currency = (currency or DEFAULT_CURRENCY).upper()

        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        existing = await self.db.scalar(stmt)
        if existing:
            logger.warning(
                f"Billing account already exists for organization: org_id={organization_id}"
            )
            raise ValueError(
                "A billing account already exists for your organization. "
                "Please contact support if you need assistance."
            )

        stripe_customer_id: Optional[str] = None
        if customer_email:
            stripe_customer = await stripe_create_customer(
                email=customer_email, name=customer_name, metadata=metadata or {}
            )
            stripe_customer_id = stripe_customer.get("id")
            if not stripe_customer_id:
                logger.error(
                    "Stripe customer creation returned no id: %s, org_id=%s",
                    stripe_customer,
                    organization_id,
                )
                raise Exception(
                    "We're unable to set up your billing account at this time. "
                    "Please try again later or contact support."
                )

            logger.info(
                "Stripe customer created: %s for org=%s", stripe_customer_id, organization_id
            )

        trial_starts_at = datetime.now(timezone.utc)
        trial_ends_at = trial_starts_at + timedelta(days=TRIAL_DURATION_DAYS)

        account = BillingAccount(
            organization_id=organization_id,
            stripe_customer_id=stripe_customer_id,
            status=initial_status,
            trial_starts_at=trial_starts_at,
            trial_ends_at=trial_ends_at,
            currency=currency,
            metadata_=(metadata or {}),
        )

        try:
            self.db.add(account)
            await self.db.flush()
            await self.db.refresh(account)
            await self.db.commit()
            logger.info("Created billing account (%s) for org=%s", account.id, organization_id)
            return account
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create billing account for org=%s: %s", organization_id, exc
            )
            raise

    async def get_billing_account_by_org(self, organization_id: UUID) -> Optional[BillingAccount]:
        """
        Retrieve the billing account for an organisation, or None if missing.

        Args:
            organization_id (UUID): The unique identifier of the organization to look up.

        Returns:
            Optional[BillingAccount]: The billing account for the organisation.
        """
        stmt = select(BillingAccount).where(BillingAccount.organization_id == organization_id)
        return await self.db.scalar(stmt)

    async def get_billing_account_by_id(self, account_id: UUID) -> BillingAccount | None:
        """
        Retrieve a billing account by its unique identifier.

        Args:
            account_id (UUID): The ID of the billing account to fetch.

        Returns:
            BillingAccount | None: The matching billing account, or None if not found.
        """

        stmt = select(BillingAccount).where(BillingAccount.id == account_id)
        return await self.db.scalar(stmt)

    async def find_billing_account_by_customer_id(
        self, stripe_customer_id: str
    ) -> Optional[BillingAccount]:
        """
        Find a BillingAccount by its Stripe customer id.

        Args:
            stripe_customer_id: The stripe Customer ID (e.g. 'cus_...').

        Returns:
            BillingAccount or None if not found.
        """
        stmt = select(BillingAccount).where(BillingAccount.stripe_customer_id == stripe_customer_id)
        return await self.db.scalar(stmt)

    async def add_payment_method(
        self,
        billing_account_id: UUID,
        stripe_payment_method_id: str,
        card_brand: Optional[str] = None,
        last4: Optional[str] = None,
        exp_month: Optional[int] = None,
        exp_year: Optional[int] = None,
        is_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentMethod:
        """
        Create a non-sensitive payment-method record for a billing account.

        Args:
            billing_account_id (UUID): ID of the billing account to attach the payment method to.
            stripe_payment_method_id (str): Stripe PaymentMethod identifier (non-sensitive).
            card_brand (Optional[str]): Card brand (e.g., "visa", "mastercard"), if known.
            last4 (Optional[str]): Last 4 digits of the card number, if known.
            exp_month (Optional[int]): Card expiration month (1-12), if known.
            exp_year (Optional[int]): Card expiration year (four digits), if known.
            is_default (bool): Whether this payment method should be the account's default.
            metadata (Optional[Dict[str, Any]]): metadata to attach to the payment method

        Returns:
            PaymentMethod: The newly created and persisted PaymentMethod

        Raises:
            ValueError: If the billing account with the provided ID does not exist.
            Exception: On database errors or other unexpected failures; the transaction
                will be rolled back before the exception is propagated.
        """
        acct_stmt = select(BillingAccount).where(BillingAccount.id == billing_account_id)
        account = await self.db.scalar(acct_stmt)
        if not account:
            logger.warning(
                f"Billing account not found for payment method: "
                f"billing_account_id={billing_account_id}"
            )
            raise ValueError(
                "We couldn't find your billing account. "
                "Please contact support if you need assistance."
            )

        pm = PaymentMethod(
            billing_account_id=billing_account_id,
            stripe_payment_method_id=stripe_payment_method_id,
            card_brand=card_brand,
            last4=last4,
            exp_month=exp_month,
            exp_year=exp_year,
            is_default=is_default,
            metadata_=(metadata or {}),
        )

        try:
            if is_default:
                await self._clear_default_payment_method(billing_account_id)

            self.db.add(pm)
            await self.db.flush()
            await self.db.refresh(pm)

            if account.stripe_customer_id:
                await stripe_attach_payment_method(
                    customer_id=account.stripe_customer_id,
                    payment_method_id=stripe_payment_method_id,
                    set_as_default=is_default,
                )
                logger.info(
                    "Attached payment method %s to stripe customer %s",
                    stripe_payment_method_id,
                    account.stripe_customer_id,
                )

            await self.db.commit()
            await self.db.refresh(pm)

            if is_default is False and account.default_payment_method_id is None:
                await self.set_default_payment_method(
                    billing_account_id=billing_account_id, payment_method_id=pm.id
                )

            logger.info("Added payment method %s for billing_account=%s", pm.id, billing_account_id)
            return pm

        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to add payment method for billing_account=%s: %s", billing_account_id, exc
            )
            raise

    async def _clear_default_payment_method(self, billing_account_id: UUID) -> None:
        """
        Clear the default payment method flag for all methods on a billing account.

        Args:
            billing_account_id (UUID): ID of the billing account whose default flags are cleared.

        Returns:
            None

        Raises:
            Exception: If the database update fails for any reason.
        """
        try:
            stmt = (
                update(PaymentMethod)
                .where(
                    PaymentMethod.billing_account_id == billing_account_id,
                    PaymentMethod.is_default,
                )
                .values(is_default=False)
            )
            await self.db.execute(stmt)
        except Exception:
            logger.exception("Failed to clear default payment methods for %s", billing_account_id)
            raise

    async def set_default_payment_method(
        self, billing_account_id: UUID, payment_method_id: UUID
    ) -> PaymentMethod:
        """
        Set a payment method as the account default

        Args:
            billing_account_id (UUID): ID of the billing account to update.
            payment_method_id (UUID): ID of the payment method to set as default.

        Returns:
            PaymentMethod: The PaymentMethod instance that was set as the default.

        Raises:
            ValueError: If the payment method does not belong to the specified billing account
                or if the billing account is not found.
            Exception: On database or transaction errors;
                the transaction will be rolled back before the exception is re-raised.
        """
        try:
            pm_check = await self.db.scalar(
                select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
            )
            if not pm_check or pm_check.billing_account_id != billing_account_id:
                logger.warning(
                    f"Payment method not found or doesn't belong to billing account: "
                    f"payment_method_id={payment_method_id}, "
                    f"billing_account_id={billing_account_id}"
                )
                raise ValueError(
                    "The payment method you selected is not available. "
                    "Please add a new payment method or select a different one."
                )

            stmt = (
                update(PaymentMethod)
                .where(PaymentMethod.billing_account_id == billing_account_id)
                .values(
                    is_default=case(
                        (PaymentMethod.id == payment_method_id, True),
                        else_=False,
                    )
                )
                .returning(PaymentMethod)
            )
            result = await self.db.execute(stmt)
            pm = None
            for row in result.scalars():
                if row.is_default:
                    pm = row
            if not pm:
                logger.error(
                    f"Failed to set default payment method: "
                    f"payment_method_id={payment_method_id}, "
                    f"billing_account_id={billing_account_id}"
                )
                raise ValueError(
                    "We couldn't set your default payment method. "
                    "Please try again or contact support."
                )

            acct_stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == billing_account_id)
                .values(default_payment_method_id=payment_method_id)
                .returning(BillingAccount)
            )
            account_result = await self.db.execute(acct_stmt)
            account = account_result.scalar_one_or_none()
            if not account:
                logger.warning(
                    f"Billing account not found during default PM update: "
                    f"billing_account_id={billing_account_id}"
                )
                raise ValueError(
                    "We couldn't find your billing account. "
                    "Please contact support if you need assistance."
                )

            await self.db.commit()
            await self.db.refresh(pm)

            if account.stripe_customer_id and pm.stripe_payment_method_id:
                try:
                    await stripe_attach_payment_method(
                        customer_id=account.stripe_customer_id,
                        payment_method_id=pm.stripe_payment_method_id,
                        set_as_default=True,
                    )
                    logger.info(
                        "Updated stripe default payment method customer=%s pm=%s",
                        account.stripe_customer_id,
                        pm.stripe_payment_method_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to update stripe default payment method for customer=%s",
                        account.stripe_customer_id,
                    )

            logger.info(
                "Set payment method %s as default for account %s",
                payment_method_id,
                billing_account_id,
            )
            return pm

        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to set default payment method %s for account %s",
                payment_method_id,
                billing_account_id,
            )
            raise

    async def get_payment_method_by_id(self, payment_method_id: UUID) -> PaymentMethod | None:
        """
        Fetch a payment method by its primary key.

        Args:
            payment_method_id (UUID): ID of the payment method row.

        Returns:
            PaymentMethod | None: The matching payment method, or None if not found.
        """
        stmt = select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
        return await self.db.scalar(stmt)

    async def find_payment_method_by_stripe_id(
        self, stripe_payment_method_id: str
    ) -> Optional[PaymentMethod]:
        """
        Find a local PaymentMethod by its Stripe payment_method id.

        Args:
            stripe_payment_method_id (str): The Stripe payment method identifier to search for.

        Returns:
            Optional[PaymentMethod]: The matching payment method, or None if not found.
        """
        stmt = select(PaymentMethod).where(
            PaymentMethod.stripe_payment_method_id == stripe_payment_method_id
        )
        return await self.db.scalar(stmt)

    async def delete_payment_method(self, payment_method_id: UUID) -> bool:
        """
        Delete a payment method record. If it was default, clear on billing account.

        Args:
            payment_method_id (UUID): Identifier of the payment method to delete.

        Returns:
            bool: True if the payment method existed and was deleted; False if no such
            payment method was found.

        Raises:
            Exception: If an error occurs during database operations; the transaction is
            rolled back and the exception is re-raised.
        """
        try:
            stmt = select(PaymentMethod).where(PaymentMethod.id == payment_method_id)
            pm = await self.db.scalar(stmt)
            if not pm:
                return False

            billing_account_id = pm.billing_account_id
            stripe_pm_id = pm.stripe_payment_method_id
            was_default = pm.is_default

            await self.db.delete(pm)

            if was_default:
                await self.db.execute(
                    update(BillingAccount)
                    .where(BillingAccount.id == billing_account_id)
                    .values(default_payment_method_id=None)
                )

            await self.db.commit()
            logger.info(
                "Deleted payment method %s (was_default=%s)", payment_method_id, was_default
            )

            if stripe_pm_id:
                try:
                    await stripe_detach_payment_method(stripe_pm_id)
                    logger.info("Detached stripe payment method %s", stripe_pm_id)
                except Exception:
                    logger.exception("Failed to detach stripe payment method %s", stripe_pm_id)

            return True
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to delete payment method %s", payment_method_id)
            raise

    async def list_payment_methods(
        self, billing_account_id: UUID, page: int = 1, limit: int = 20
    ) -> Tuple[List[PaymentMethod], int]:
        """
        Return all payment methods associated with the given billing account with pagination.

        Args:
            billing_account_id (UUID): UUID of the billing account.
            page (int): Page number.
            limit (int): Items per page.

        Returns:
            Tuple[List[PaymentMethod], int]: A tuple of (list of PaymentMethods, total count).
        """
        count_stmt = (
            select(func.count())
            .select_from(PaymentMethod)
            .where(PaymentMethod.billing_account_id == billing_account_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(PaymentMethod)
            .where(PaymentMethod.billing_account_id == billing_account_id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def attach_stripe_customer(
        self,
        billing_account_id: UUID,
        stripe_customer_id: str,
        stripe_subscription_id: Optional[str] = None,
    ) -> BillingAccount:
        """
        Attach Stripe customer and (optionally) subscription id to an account.

        Args:
            billing_account_id (UUID): The ID of the billing account to update.
            stripe_customer_id (str): The Stripe customer ID to associate with the billing account.
            stripe_subscription_id (Optional[str]): Optional Stripe subscription ID.

        Returns:
            BillingAccount: The updated and refreshed BillingAccount object with the new Stripe IDs.

        Raises:
            ValueError: If no BillingAccount exists with the provided billing_account_id.
            Exception: For unexpected failures during the database update;
                the operation will be rolled back on error.
        """
        try:
            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == billing_account_id)
                .values(
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                )
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            await self.db.commit()
            if not account:
                logger.warning(
                    f"Billing account not found for Stripe customer attachment: "
                    f"billing_account_id={billing_account_id}"
                )
                raise ValueError(
                    "We couldn't find your billing account. "
                    "Please contact support if you need assistance."
                )
            await self.db.refresh(account)
            logger.info(
                "Attached stripe customer %s to billing_account=%s",
                stripe_customer_id,
                billing_account_id,
            )
            return account
        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to attach stripe customer to billing account %s", billing_account_id
            )
            raise

    async def upsert_invoice_from_stripe(
        self,
        account: BillingAccount,
        stripe_invoice: dict,
    ) -> InvoiceHistory:
        """
        Create or update an InvoiceHistory record from a Stripe invoice object.
        Args:
            account (BillingAccount): The billing account to associate the invoice with.
            stripe_invoice (dict): The raw Stripe invoice object/payload.

        Returns:
            InvoiceHistory: The created or updated InvoiceHistory record.
        """
        stripe_invoice_id = stripe_invoice["id"]
        currency = (stripe_invoice.get("currency") or "usd").upper()

        existing = await self.find_invoice_by_stripe_invoice_id(stripe_invoice_id)

        plan_meta: dict[str, Any] = {}

        lines = stripe_invoice.get("lines", {}).get("data", []) or []
        first_line = lines[0] if lines else None

        if first_line:
            line_meta = first_line.get("metadata") or {}
            plan_meta.update(
                {
                    "plan_code": line_meta.get("plan_code"),
                    "plan_interval": line_meta.get("plan_interval"),
                    "plan_tier": line_meta.get("plan_tier"),
                }
            )

            price_details = (
                first_line.get("price") or first_line.get("pricing", {}).get("price_details") or {}
            )

            if isinstance(price_details, dict):
                stripe_price_id = price_details.get("id") or price_details.get("price")
            else:
                stripe_price_id = None

            if stripe_price_id:
                plan_stmt = select(BillingPlan).where(
                    BillingPlan.stripe_price_id == stripe_price_id
                )
                plan_result = await self.db.execute(plan_stmt)
                plan = plan_result.scalar_one_or_none()
                if plan:
                    plan_meta.setdefault("plan_code", plan.code)
                    plan_meta.setdefault("plan_interval", plan.interval.value)
                    plan_meta.setdefault("plan_tier", plan.tier.value)
                    plan_meta["plan_label"] = plan.label

        base_metadata = stripe_invoice.get("metadata") or {}
        parent = stripe_invoice.get("parent") or {}
        sub_details = (parent.get("subscription_details") or {}).get("metadata") or {}
        metadata = {**base_metadata, **sub_details, **plan_meta}

        total = stripe_invoice.get("total") or stripe_invoice.get("amount_due") or 0
        amount_paid = stripe_invoice.get("amount_paid") or 0
        stripe_payment_intent_id = stripe_invoice.get("payment_intent")

        status = map_stripe_invoice_status(stripe_invoice.get("status"))

        if existing:
            existing.amount_due = total or existing.amount_due
            existing.amount_paid = amount_paid or existing.amount_paid
            existing.currency = currency
            existing.status = status
            existing.hosted_invoice_url = stripe_invoice.get("hosted_invoice_url")
            existing.invoice_pdf_url = stripe_invoice.get("invoice_pdf")
            if stripe_payment_intent_id:
                existing.stripe_payment_intent_id = stripe_payment_intent_id
            existing.metadata_ = {**(existing.metadata_ or {}), **metadata}
            self.db.add(existing)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        try:
            invoice = await self.create_invoice_record(
                billing_account_id=account.id,
                amount_due=total,
                amount_paid=amount_paid,
                currency=currency,
                stripe_invoice_id=stripe_invoice_id,
                stripe_payment_intent_id=stripe_payment_intent_id,
                status=status,
                metadata=metadata,
                hosted_invoice_url=stripe_invoice.get("hosted_invoice_url"),
                invoice_pdf_url=stripe_invoice.get("invoice_pdf"),
            )
            return invoice
        except IntegrityError:
            await self.db.rollback()
            return await self.find_invoice_by_stripe_invoice_id(stripe_invoice_id)

    async def create_stripe_and_local_invoice(
        self,
        billing_account_id: UUID,
        stripe_price_id: str,
        quantity: int = 1,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InvoiceHistory:
        """
        Create a Stripe invoice for a billing account and persist a matching local invoice record.

        Args:
            billing_account_id (UUID): ID of the billing account to invoice.
            stripe_price_id (str): Stripe price identifier used to build the invoice items.
            quantity (int): Quantity to bill for the given Stripe price. Defaults to 1.
            description (Optional[str]): Optional human-readable description for the invoice.
            metadata (Optional[Dict[str, Any]]): Extra metadata to attach to the Stripe invoice.

        Returns:
            InvoiceHistory: The persisted invoice record mirroring the Stripe invoice.

        Raises:
            ValueError: If the billing account does not exist or lacks a Stripe customer ID.
            Exception: If Stripe invoice creation or database persistence fails.
        """
        acct_stmt = select(BillingAccount).where(BillingAccount.id == billing_account_id)
        account = await self.db.scalar(acct_stmt)
        if not account:
            logger.warning(
                f"Billing account not found for invoice creation: "
                f"billing_account_id={billing_account_id}"
            )
            raise ValueError(
                "We couldn't find your billing account. "
                "Please contact support if you need assistance."
            )

        if not account.stripe_customer_id:
            logger.error(
                f"Billing account missing Stripe customer ID: "
                f"billing_account_id={billing_account_id}"
            )
            raise ValueError(
                "Your billing account is not fully set up. "
                "Please contact support to complete your billing setup."
            )

        stripe_invoice: Dict[str, Any] = await stripe_create_invoice_for_customer_with_price_id(
            customer_id=account.stripe_customer_id,
            price_id=stripe_price_id,
            quantity=quantity,
            description=description,
            metadata=metadata or {},
        )

        pi = stripe_invoice.get("payment_intent")
        stripe_payment_intent_id: Optional[str] = None
        if isinstance(pi, dict):
            stripe_payment_intent_id = pi.get("id")
        elif isinstance(pi, str):
            stripe_payment_intent_id = pi

        stripe_status = stripe_invoice.get("status")
        hosted_invoice_url = stripe_invoice.get("hosted_invoice_url")
        invoice_pdf_url = stripe_invoice.get("invoice_pdf")

        total = stripe_invoice.get("total") or stripe_invoice.get("amount_due") or 0
        amount_paid = stripe_invoice.get("amount_paid") or 0

        status = map_stripe_invoice_status(stripe_status)

        return await self.create_invoice_record(
            billing_account_id=billing_account_id,
            amount_due=total,
            amount_paid=amount_paid,
            currency=stripe_invoice["currency"],
            stripe_invoice_id=stripe_invoice["id"],
            stripe_payment_intent_id=stripe_payment_intent_id,
            status=status,
            metadata=stripe_invoice.get("metadata"),
            hosted_invoice_url=hosted_invoice_url,
            invoice_pdf_url=invoice_pdf_url,
        )

    async def create_invoice_record(
        self,
        billing_account_id: UUID,
        amount_due: int,
        amount_paid: int = 0,
        currency: str = DEFAULT_CURRENCY,
        stripe_invoice_id: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
        status: InvoiceStatus = InvoiceStatus.DRAFT,
        metadata: Optional[Dict[str, Any]] = None,
        hosted_invoice_url: Optional[str] = None,
        invoice_pdf_url: Optional[str] = None,
    ) -> InvoiceHistory:
        """
        Create an invoice record for a billing account.

        Args:
            billing_account_id (UUID): ID of the billing account to associate the invoice with.
            amount_due (int): Amount due in cents.
            currency (str, optional): ISO currency code. Defaults to DEFAULT_CURRENCY.
            stripe_invoice_id (Optional[str], optional): Optional Stripe invoice ID.
            stripe_payment_intent_id (Optional[str], optional): Optional Stripe payment intent ID.
            status (InvoiceStatus, optional): Initial invoice status. Defaults - InvoiceStatus.DRAFT
            metadata (Optional[Dict[str, Any]], optional): metadata to attach to the invoice.

        Returns:
            InvoiceHistory: The newly created and persisted InvoiceHistory instance.

        Raises:
            Exception: Any exception raised during database operations is propagated.
        """
        invoice = InvoiceHistory(
            billing_account_id=billing_account_id,
            stripe_invoice_id=stripe_invoice_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            amount_due=amount_due,
            amount_paid=amount_paid,
            currency=currency.upper(),
            status=status,
            hosted_invoice_url=hosted_invoice_url,
            invoice_pdf_url=invoice_pdf_url,
            metadata_=(metadata or {}),
        )

        try:
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()
            logger.info("Created invoice %s for billing_account=%s", invoice.id, billing_account_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to create invoice for billing_account=%s", billing_account_id)
            raise

    async def mark_invoice_paid(
        self, invoice_id: UUID, amount_paid: Optional[int] = None
    ) -> InvoiceHistory:
        """
        Mark an invoice as paid and persist the updated invoice to the database.

        Args:
            invoice_id (UUID): The unique identifier of the invoice to mark as paid.
            amount_paid (Optional[int], optional): The amount that was paid. If None,
                the invoice's amount_due will be used (treating it as full payment).

        Returns:
            InvoiceHistory: The updated InvoiceHistory instance reflecting the new
            amount_paid and status.

        Raises:
            ValueError: If no invoice with the given invoice_id exists.
            Exception: Propagates any database or unexpected errors after rolling back
                the transaction.
        """
        try:
            stmt = select(InvoiceHistory).where(InvoiceHistory.id == invoice_id)
            invoice = await self.db.scalar(stmt)
            if not invoice:
                logger.warning(f"Invoice not found for marking as paid: invoice_id={invoice_id}")
                raise ValueError(
                    "The invoice you're looking for could not be found. "
                    "Please contact support if you need assistance."
                )

            if amount_paid is not None:
                invoice.amount_paid = amount_paid
            else:
                invoice.amount_paid = invoice.amount_due

            invoice.status = InvoiceStatus.PAID
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()

            logger.info("Marked invoice %s as PAID", invoice_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to mark invoice %s as paid", invoice_id)
            raise

    async def mark_invoice_failed(self, invoice_id: UUID) -> InvoiceHistory:
        """
        Mark an invoice as failed/failed payment attempt.

        Args:
            invoice_id (UUID): Unique identifier of the invoice to mark as failed.
        Returns:
            InvoiceHistory: The updated InvoiceHistory instance with status set to FAILED.
        Raises:
            ValueError: If no invoice exists with the given invoice_id.
            Exception: Any unexpected exception encountered is re-raised after rollback.
        """
        try:
            stmt = select(InvoiceHistory).where(InvoiceHistory.id == invoice_id)
            invoice = await self.db.scalar(stmt)
            if not invoice:
                logger.warning(f"Invoice not found for marking as failed: invoice_id={invoice_id}")
                raise ValueError(
                    "The invoice you're looking for could not be found. "
                    "Please contact support if you need assistance."
                )

            invoice.status = InvoiceStatus.FAILED
            self.db.add(invoice)
            await self.db.flush()
            await self.db.refresh(invoice)
            await self.db.commit()

            logger.info("Marked invoice %s as FAILED", invoice_id)
            return invoice
        except Exception:
            await self.db.rollback()
            logger.exception("Failed to mark invoice %s as failed", invoice_id)
            raise

    async def get_invoices_for_account(
        self, billing_account_id: UUID, page: int = 1, limit: int = 20
    ) -> Tuple[List[InvoiceHistory], int]:
        """
        Return invoices for a billing account ordered by creation time (newest first)
        with pagination.

        Args:
            billing_account_id (UUID): The UUID of the billing account to fetch invoices for.
            page (int): Page number.
            limit (int): Items per page.

        Returns:
            Tuple[List[InvoiceHistory], int]: A tuple of (list of InvoiceHistory, total count).
        """

        count_stmt = (
            select(func.count())
            .select_from(InvoiceHistory)
            .where(InvoiceHistory.billing_account_id == billing_account_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = (
            select(InvoiceHistory)
            .where(InvoiceHistory.billing_account_id == billing_account_id)
            .order_by(InvoiceHistory.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def find_invoice_by_stripe_invoice_id(
        self, stripe_invoice_id: str
    ) -> Optional[InvoiceHistory]:
        """
        Find a local InvoiceHistory record by Stripe invoice id.

        Args:
            stripe_invoice_id: The stripe invoice id (e.g. 'in_...').

        Returns:
            InvoiceHistory or None if not found.
        """
        stmt = select(InvoiceHistory).where(InvoiceHistory.stripe_invoice_id == stripe_invoice_id)
        return await self.db.scalar(stmt)

    async def find_invoice_by_payment_intent_id(
        self, stripe_payment_intent_id: str
    ) -> Optional[InvoiceHistory]:
        """
        Find a local InvoiceHistory record by Stripe PaymentIntent id.

        Args:
            stripe_payment_intent_id: The stripe PaymentIntent id (e.g. 'pi_...').

        Returns:
            InvoiceHistory or None if not found.
        """
        stmt = select(InvoiceHistory).where(
            InvoiceHistory.stripe_payment_intent_id == stripe_payment_intent_id
        )
        return await self.db.scalar(stmt)

    async def get_subscription_overview_for_org(
        self, organization_id: UUID
    ) -> Optional[BillingAccount]:
        """
        Return an organization’s billing account for exposing subscription-related details.

        Args:
            organization_id (UUID): ID of the organization whose subscription is requested.

        Returns:
            Optional[BillingAccount]: The organization’s billing account, or None if not found.
        """
        return await self.get_billing_account_by_org(organization_id)

    async def update_subscription_price_for_account(
        self,
        account: BillingAccount,
        new_price_id: str,
    ) -> BillingAccount:
        """
        Update a billing account’s Stripe subscription price and persist the new price ID.

        Args:
            account (BillingAccount): Billing account whose subscription price will be updated.
            new_price_id (str): The new Stripe price identifier to apply to the subscription.

        Returns:
            BillingAccount: The updated billing account with the new current_price_id.

        Raises:
            ValueError: If there is no Stripe subscription ID or the subscription is cancelled.
            Exception: If the Stripe update or database persistence fails.
        """
        if not account.stripe_subscription_id:
            logger.error(
                f"No Stripe subscription ID for price update: billing_account_id={account.id}"
            )
            raise ValueError(
                "Your subscription is not fully set up. "
                "Please contact support to complete your subscription setup."
            )

        account_id = account.id
        subscription_id = account.stripe_subscription_id
        account_status = getattr(account, "status", None)

        if account_status == BillingStatus.CANCELLED:
            logger.warning(
                f"Attempted to change canceled subscription: billing_account_id={account_id}"
            )
            raise ValueError(
                "Your subscription has been canceled and cannot be changed. "
                "Please create a new subscription if you'd like to continue."
            )

        try:
            await stripe_update_subscription_price(
                subscription_id=subscription_id,
                new_price_id=new_price_id,
            )

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account_id)
                .values(current_price_id=new_price_id)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()

            if not updated:
                await self.db.rollback()
                logger.warning(
                    f"Billing account not found during plan change: "
                    f"org_id={account.organization_id}"
                )
                raise ValueError(
                    "We couldn't find your billing account. Please contact support for assistance."
                )

            await self.db.commit()
            await self.db.refresh(updated)

            logger.info(
                "Updated subscription price for billing_account=%s to price=%s",
                account_id,
                new_price_id,
            )
            return updated

        except SubscriptionAlreadyCanceledError as e:
            await self.db.rollback()
            logger.warning(
                "Attempted to change plan on canceled subscription: billing_account=%s",
                account_id,
            )
            raise ValueError(str(e)) from e

        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to update subscription price for billing_account=%s",
                account_id,
            )
            raise

    async def cancel_subscription_for_account(
        self,
        account: BillingAccount,
        cancel_at_period_end: bool = True,
    ) -> BillingAccount:
        """
        Cancel a Stripe subscription for a billing account and update local billing state.

        Args:
            account (BillingAccount): Billing account whose subscription will be cancelled.
            cancel_at_period_end (bool): If True, cancel at period end; otherwise cancel
                immediately.

        Returns:
            BillingAccount: The updated billing account after the cancellation change.

        Raises:
            ValueError: If the billing account has no Stripe subscription ID or is not found.
            Exception: If Stripe cancellation or database persistence fails.
        """
        if not account.stripe_subscription_id:
            raise ValueError("Billing account has no Stripe subscription id")

        try:
            stripe_sub = await stripe_cancel_subscription(
                subscription_id=account.stripe_subscription_id,
                cancel_at_period_end=cancel_at_period_end,
            )

            update_values: Dict[str, Any] = {
                "cancel_at_period_end": cancel_at_period_end,
            }

            if not cancel_at_period_end:
                update_values["status"] = BillingStatus.CANCELLED

            update_values["next_billing_at"] = None

            period = stripe_sub.get("current_period_end")
            if period:
                try:
                    update_values["current_period_end"] = datetime.fromtimestamp(
                        int(period), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_end=%s from stripe", period)

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account.id)
                .values(**update_values)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()
            await self.db.commit()

            if not updated:
                logger.warning(
                    f"Billing account not found during cancel update: "
                    f"org_id={account.organization_id}"
                )
                raise ValueError(
                    "We couldn't update your billing account. "
                    "Please contact support for assistance."
                )

            await self.db.refresh(updated)

            logger.info(
                "Cancelled subscription for account=%s (cancel_at_period_end=%s)",
                account.id,
                cancel_at_period_end,
            )
            return updated

        except Exception:
            await self.db.rollback()
            logger.exception("Failed to cancel subscription for billing_account=%s", account.id)
            raise

    async def sync_subscription_from_stripe(
        self,
        account: BillingAccount,
    ) -> BillingAccount:
        """
        Sync a billing account’s subscription state from Stripe and update local fields.
        [Unused for now]

        Args:
            account (BillingAccount): Billing account whose subscription will be refreshed from
                Stripe.

        Returns:
            BillingAccount: The updated billing account after syncing Stripe subscription data.

        Raises:
            ValueError: If the billing account has no Stripe subscription ID.
            Exception: If Stripe retrieval or database persistence fails.
        """
        if not account.stripe_subscription_id:
            logger.warning(
                f"Cannot sync subscription - no Stripe subscription ID: "
                f"org_id={account.organization_id}"
            )
            raise ValueError(
                "Your billing account doesn't have an active subscription to sync. "
                "Please contact support if you believe this is an error."
            )

        try:
            sub = await stripe_retrieve_subscription(account.stripe_subscription_id)

            stripe_status = sub.get("status")
            period_start = sub.get("current_period_start")
            period_end = sub.get("current_period_end")
            cancel_at_period_end = sub.get("cancel_at_period_end", False)

            mapped_status = account.status
            if stripe_status in ("active", "trialing"):
                mapped_status = BillingStatus.ACTIVE
            elif stripe_status == "past_due":
                mapped_status = BillingStatus.PAST_DUE
            elif stripe_status in ("incomplete", "incomplete_expired", "unpaid"):
                mapped_status = BillingStatus.UNPAID
            elif stripe_status in ("canceled", "cancelled"):
                mapped_status = BillingStatus.CANCELLED

            update_values: Dict[str, Any] = {
                "status": mapped_status,
                "cancel_at_period_end": cancel_at_period_end,
            }

            if period_start:
                try:
                    update_values["current_period_start"] = datetime.fromtimestamp(
                        int(period_start), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_start=%s", period_start)

            if period_end:
                try:
                    update_values["current_period_end"] = datetime.fromtimestamp(
                        int(period_end), tz=timezone.utc
                    )
                except Exception:
                    logger.warning("Failed to parse current_period_end=%s", period_end)

            stmt = (
                update(BillingAccount)
                .where(BillingAccount.id == account.id)
                .values(**update_values)
                .returning(BillingAccount)
            )
            result = await self.db.execute(stmt)
            updated = result.scalar_one_or_none()
            await self.db.commit()

            if not updated:
                raise ValueError("Billing account not found during sync")

            await self.db.refresh(updated)
            logger.info(
                "Synced subscription from Stripe for billing_account=%s (status=%s)",
                account.id,
                updated.status.value,
            )
            return updated
        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to sync subscription from Stripe for billing_account=%s", account.id
            )
            raise

    async def _build_billing_account_updates_from_stripe_subscription(
        self,
        sub: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert a Stripe subscription object into BillingAccount update values.

        Args:
            sub (Dict[str, Any]): Raw Stripe subscription object returned by Stripe APIs.

        Returns:
            Dict[str, Any]: A dictionary of BillingAccount fields to update.
        """
        stripe_status = sub.get("status")
        customer_id = sub.get("customer")
        cancel_at_period_end = sub.get("cancel_at_period_end", False)

        cp_start_raw = sub.get("current_period_start")
        cp_end_raw = sub.get("current_period_end")

        trial_start_raw = sub.get("trial_start")
        trial_end_raw = sub.get("trial_end")

        price_id: Optional[str] = None
        quantity: Optional[int] = None
        currency: Optional[str] = None

        items = sub.get("items")
        if isinstance(items, dict):
            items_data = items.get("data") or []
        else:
            items_data = items or []

        if items_data and isinstance(items_data[0], dict):
            first_item = items_data[0]

            cp_start_raw = cp_start_raw or first_item.get("current_period_start")
            cp_end_raw = cp_end_raw or first_item.get("current_period_end")

            price_obj = first_item.get("price")
            if isinstance(price_obj, dict):
                price_id = price_obj.get("id")
                currency = price_obj.get("currency")
            else:
                price_id = price_obj
            quantity = first_item.get("quantity")

        cp_start_dt = parse_ts(cp_start_raw, "current_period_start")
        cp_end_dt = parse_ts(cp_end_raw, "current_period_end")
        trial_start_dt = parse_ts(trial_start_raw, "trial_start")
        trial_end_dt = parse_ts(trial_end_raw, "trial_end")

        update_values: Dict[str, Any] = {
            "status": map_stripe_status_to_billing_status(stripe_status).value,
            "cancel_at_period_end": bool(cancel_at_period_end),
        }

        if cp_start_dt is not None:
            update_values["current_period_start"] = cp_start_dt
        if cp_end_dt is not None:
            update_values["current_period_end"] = cp_end_dt
            update_values["next_billing_at"] = cp_end_dt

        if stripe_status == "trialing":
            if trial_start_dt is not None:
                update_values["trial_starts_at"] = trial_start_dt
            if trial_end_dt is not None:
                update_values["trial_ends_at"] = trial_end_dt
        else:
            update_values["trial_starts_at"] = None
            update_values["trial_ends_at"] = None

        if customer_id:
            update_values["stripe_customer_id"] = customer_id
        if price_id:
            update_values["current_price_id"] = price_id
        if currency:
            update_values["currency"] = currency

        if quantity is not None:
            update_values.setdefault("metadata_", {})
            update_values["metadata_"]["quantity"] = quantity

        if price_id:
            result = await self.db.execute(
                select(BillingPlan).where(BillingPlan.stripe_price_id == price_id)
            )
            plan: BillingPlan | None = result.scalar_one_or_none()
            if plan:
                update_values.setdefault("metadata_", {})
                update_values["metadata_"]["plan_code"] = plan.code
                update_values["metadata_"]["plan_label"] = plan.label
                update_values["metadata_"]["plan_tier"] = plan.tier.value
                update_values["metadata_"]["plan_interval"] = plan.interval.value
                update_values["currency"] = plan.currency

        return update_values

    async def _sync_org_billing_from_account(
        self,
        db: AsyncSession,
        organization_id: UUID,
        account: BillingAccount,
        plan_info: BillingPlanInfo | None,
    ) -> None:
        """
        Keep Organization.plan and Organization.billing_info in sync with the billing account.

        Args:
            db (AsyncSession): The database session.
            organization_id (UUID): The UUID of the organisation to update.
            account (BillingAccount): The billing account with the latest billing info.
            plan_info (BillingPlanInfo | None): The current plan info to set on the organisation.

        Returns:
            None

        Raises:
            Exception: If there is an error updating the organisation.
        """

        org = await db.get(Organization, organization_id)
        if not org:
            logger.warning(
                "Organization %s not found while syncing billing info; skipping org update",
                organization_id,
            )
            return

        plan_value: str | None = None
        if plan_info is not None:
            plan_value = getattr(plan_info, "tier", None) or getattr(plan_info, "label", None)

        org.plan = plan_value
        if not org.plan:
            org.plan = org.billing_info.get("current_plan", None) if org.billing_info else None
            if not org.plan:
                org.plan = org.billing_info.get("status", None) if org.billing_info else None
                if not org.plan:
                    org.plan = "trialing"

        trial_ends_at = account.trial_ends_at.isoformat() if account.trial_ends_at else None
        org.billing_info = {
            "billing_account_id": str(account.id),
            "status": account.status.value if hasattr(account.status, "value") else account.status,
            "stripe_customer_id": account.stripe_customer_id,
            "stripe_subscription_id": account.stripe_subscription_id,
            "current_price_id": account.current_price_id,
            "cancel_at_period_end": account.cancel_at_period_end or False,
            "trial_starts_at": account.trial_starts_at.isoformat()
            if account.trial_starts_at
            else None,
            "trial_ends_at": trial_ends_at,
            "current_period_start": account.current_period_start.isoformat()
            if account.current_period_start
            else None,
            "current_period_end": account.current_period_end.isoformat()
            if account.current_period_end
            else None,
            "next_billing_at": account.next_billing_at.isoformat()
            if account.next_billing_at
            else None,
            "current_plan": plan_info.model_dump(mode="json") if plan_info is not None else None,
        }

        org.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(org)


def get_billing_service(db: AsyncSession) -> BillingService:
    """
    Convenience factory used by route dependencies to obtain a BillingService instance.

    Args:
        db (AsyncSession): Asynchronous database session used to initialize the service.

    Returns:
        BillingService: An instance of BillingService bound to the provided database session.
    """
    return BillingService(db)
