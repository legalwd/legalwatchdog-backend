import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.auth import require_billing_admin
from app.api.db.database import get_db
from app.api.modules.v1.billing.models import InvoiceHistory
from app.api.modules.v1.billing.models.billing_account import BillingAccount
from app.api.modules.v1.billing.routes.docs.billing_routes_docs import (
    cancel_subscription_custom_errors,
    cancel_subscription_custom_success,
    cancel_subscription_responses,
    change_subscription_plan_custom_errors,
    change_subscription_plan_custom_success,
    change_subscription_plan_responses,
    create_billing_account_custom_errors,
    create_billing_account_custom_success,
    create_billing_account_responses,
    create_checkout_custom_errors,
    create_checkout_custom_success,
    create_checkout_responses,
    delete_payment_method_custom_errors,
    delete_payment_method_custom_success,
    delete_payment_method_responses,
    get_billing_account_custom_errors,
    get_billing_account_custom_success,
    get_billing_account_responses,
    list_invoices_custom_errors,
    list_invoices_custom_success,
    list_invoices_responses,
    list_payment_methods_custom_errors,
    list_payment_methods_custom_success,
    list_payment_methods_responses,
    subscription_status_custom_errors,
    subscription_status_custom_success,
    subscription_status_responses,
)
from app.api.modules.v1.billing.schemas import (
    BillingAccountResponse,
    BillingPlanInfo,
    CheckoutSessionCreateRequest,
    CheckoutSessionResponse,
    InvoiceResponse,
    PaymentMethodResponse,
    SubscriptionChangePlanRequest,
    SubscriptionStatusResponse,
)
from app.api.modules.v1.billing.service.billing_service import BillingService, get_billing_service
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_checkout_session as stripe_create_checkout_session,
)
from app.api.modules.v1.billing.stripe.stripe_adapter import (
    create_customer,
)
from app.api.modules.v1.billing.utils.billings_utils import map_plan_to_plan_info
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations/{organization_id}/billing",
    tags=["Billing"],
    dependencies=[Depends(require_billing_admin)],
)


@router.post(
    "/accounts",
    status_code=status.HTTP_201_CREATED,
    response_model=BillingAccountResponse,
    summary="Create billing account for your organisation",
    responses=create_billing_account_responses,
)
async def create_billing_account(
    organization_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a billing account for the authenticated user's organisation.

    Args:
        organization_id (UUID): The UUID of the organisation.
        current_user (Depends(require_billing_admin)): The authenticated user object.
        db (AsyncSession, Depends(get_db)): Asynchronous database session injected
            by FastAPI dependencies.

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the created billing account

    Raises:
        ValueError: If validation of the input payload fails.
        Exception: For unexpected errors encountered while creating the billing account
    """
    try:
        billing_service: BillingService = get_billing_service(db)

        account = await billing_service.create_billing_account(
            organization_id=organization_id,
            customer_email=current_user.email,
            customer_name=current_user.name,
            metadata={"created_by": str(current_user.id)},
        )

        return success_response(
            status_code=status.HTTP_201_CREATED,
            message="Billing account created",
            data=BillingAccountResponse.model_validate(account.model_dump()),
        )
    except ValueError as e:
        logger.warning("Create billing account validation failed: %s", str(e))
        return error_response(status_code=status.HTTP_400_BAD_REQUEST, message=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating billing account: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create billing account",
        )


create_billing_account._custom_errors = create_billing_account_custom_errors
create_billing_account._custom_success = create_billing_account_custom_success


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=BillingAccountResponse,
    summary="Get billing account for your organisation",
    responses=get_billing_account_responses,
)
async def get_billing_account(
    organization_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the billing account for the authenticated user's organisation.

    Args:
        organization_id (UUID): The UUID of the organisation.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the retrieved billing account

    Raises:
        Exception: For unexpected errors encountered while fetching the billing account
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found for organisation",
            )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Billing account retrieved",
            data=BillingAccountResponse.model_validate(account.model_dump()),
        )
    except Exception as e:
        logger.exception("Failed to fetch billing account: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to fetch billing account",
        )


get_billing_account._custom_errors = get_billing_account_custom_errors
get_billing_account._custom_success = get_billing_account_custom_success


@router.post(
    "/checkout",
    status_code=status.HTTP_200_OK,
    response_model=CheckoutSessionResponse,
    summary="Create Stripe Checkout session for subscription",
    responses=create_checkout_responses,
)
async def create_checkout_session(
    organization_id: UUID,
    payload: CheckoutSessionCreateRequest,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session for the organisation’s subscription.

    Args:
        organization_id (UUID):
            The UUID of the organisation creating a subscription.
        payload (CheckoutSessionCreateRequest):
            Request payload specifying plan_id.
        current_user (Depends(require_billing_admin)):
            The authenticated user; must have billing permissions.
        db (AsyncSession, Depends(get_db)):
            The database session injected by FastAPI.

    Returns:
        dict: A standard API response containing:
            - `status_code`: HTTP status code.
            - `message`: A success message.
            - `data`: A `CheckoutSessionResponse` containing:
                - `checkout_url`: URL to redirect the user to Stripe Checkout.
                - `session_id`: The created Checkout session ID.

    Raises:
        HTTPException:
            - 400 if the plan is invalid.
            - 500 if Stripe customer creation fails or billing config is invalid.
        Exception:
            Any unexpected errors during checkout creation.
    """
    try:
        billing_service: BillingService = get_billing_service(db)

        account: BillingAccount = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            account = await billing_service.create_billing_account(
                organization_id=organization_id,
                currency="USD",
                customer_email=current_user.email,
                customer_name=current_user.name,
                metadata={"created_by": str(current_user.id)},
            )

        stripe_customer_id = account.stripe_customer_id
        if not stripe_customer_id:
            stripe_customer = await create_customer(
                email=current_user.email,
                name=current_user.name,
                metadata={"organization_id": str(organization_id)},
            )
            stripe_customer_id = stripe_customer.get("id")
            if not stripe_customer_id:
                logger.error("Stripe customer creation returned no id for org=%s", account.id)
                return error_response(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="Failed to create Stripe customer",
                )

            await billing_service.attach_stripe_customer(
                billing_account_id=account.id,
                stripe_customer_id=stripe_customer_id,
            )

        plan = await billing_service.get_plan_by_id(payload.plan_id)
        if not plan:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing plan not found",
            )

        if not plan.is_active:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Billing plan is not active",
            )

        if not plan.stripe_price_id:
            logger.error(
                "Billing plan %s has no stripe_price_id configured",
                plan.id,
            )
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Billing is not correctly configured for this plan. Contact support.",
            )

        price_id = plan.stripe_price_id

        success_url = settings.STRIPE_CHECKOUT_SUCCESS_URL
        cancel_url = settings.STRIPE_CHECKOUT_CANCEL_URL

        base_metadata = {
            "organization_id": str(organization_id),
            "billing_account_id": str(account.id),
            "plan_id": str(plan.id),
            "plan_code": plan.code,
            "plan_tier": plan.tier.value,
            "plan_interval": plan.interval.value,
            "created_by": str(current_user.id),
        }

        if payload.metadata:
            base_metadata.update(payload.metadata)

        session = await stripe_create_checkout_session(
            success_url=str(success_url),
            cancel_url=str(cancel_url),
            customer_id=stripe_customer_id,
            mode="subscription",
            price_id=price_id,
            metadata=base_metadata,
        )

        response_payload = CheckoutSessionResponse(
            checkout_url=session["url"],
            session_id=session["id"],
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Checkout session created",
            data=response_payload,
        )

    except Exception as e:
        logger.exception("Failed to create Stripe checkout session: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to create checkout session",
        )


create_checkout_session._custom_errors = create_checkout_custom_errors
create_checkout_session._custom_success = create_checkout_custom_success


@router.get(
    "/subscription",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Get current subscription status for your organisation",
    responses=subscription_status_responses,
)
async def get_subscription_status(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Return subscription status for the organisation
    Args:
        organization_id (UUID): The UUID of the organisation.
        db (AsyncSession, Depends(get_db)): Asynchronous database session
    Returns:
        SubscriptionStatusResponse: The current subscription status of the organisation.
    Raises:
        Exception: If there is an error retrieving the subscription status.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        current_plan_info: BillingPlanInfo | None = None
        if account.current_price_id:
            plan = await billing_service.get_plan_by_stripe_price_id(account.current_price_id)
            if plan:
                current_plan_info = map_plan_to_plan_info(plan)

        data = SubscriptionStatusResponse(
            billing_account_id=account.id,
            stripe_customer_id=account.stripe_customer_id,
            stripe_subscription_id=account.stripe_subscription_id,
            status=account.status,
            cancel_at_period_end=account.cancel_at_period_end or False,
            trial_starts_at=account.trial_starts_at,
            trial_ends_at=account.trial_ends_at,
            current_period_start=account.current_period_start,
            current_period_end=account.current_period_end,
            next_billing_at=account.next_billing_at,
            current_plan=current_plan_info,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Subscription status retrieved",
            data=data,
        )
    except Exception as e:
        logger.exception("Failed to get subscription status: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to get subscription status",
        )


get_subscription_status._custom_errors = subscription_status_custom_errors
get_subscription_status._custom_success = subscription_status_custom_success


@router.post(
    "/subscription/change-plan",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Change subscription plan for your organisation",
    responses=change_subscription_plan_responses,
)
async def change_subscription_plan(
    organization_id: UUID,
    payload: SubscriptionChangePlanRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Change the organisation's current subscription to a different configured plan.
    Args:
        organization_id (UUID): The UUID of the organisation.
        payload (SubscriptionChangePlanRequest): Payload containing the target plan_id to switch to.
        db (AsyncSession, Depends(get_db)): Asynchronous database session injected by FastAPI.

    Returns:
        dict: Standard API response containing:
            - status_code: HTTP status code.
            - message: Human-readable message.
            - data: SubscriptionStatusResponse with the updated subscription details on success.

    Raises:
        ValueError: If validation fails (e.g., no active subscription, invalid plan).
        Exception: For unexpected errors while changing the subscription plan.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        if not account.stripe_subscription_id:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No active subscription to change",
            )

        plan = await billing_service.get_plan_by_id(payload.plan_id)
        if not plan:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Target billing plan not found",
            )

        if not plan.is_active:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Target billing plan is not active",
            )

        if not plan.stripe_price_id:
            logger.error(
                "Billing plan %s has no stripe_price_id configured",
                plan.id,
            )
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Billing is not correctly configured for this plan. Contact support.",
            )

        updated_account = await billing_service.update_subscription_price_for_account(
            account=account,
            new_price_id=plan.stripe_price_id,
        )

        current_plan_info: BillingPlanInfo | None = None
        if updated_account.current_price_id:
            current_plan_info = map_plan_to_plan_info(plan)

        await billing_service._sync_org_billing_from_account(
            db=db,
            organization_id=organization_id,
            account=updated_account,
            plan_info=current_plan_info,
        )

        data = SubscriptionStatusResponse(
            billing_account_id=updated_account.id,
            stripe_customer_id=updated_account.stripe_customer_id,
            stripe_subscription_id=updated_account.stripe_subscription_id,
            status=updated_account.status,
            cancel_at_period_end=updated_account.cancel_at_period_end or False,
            trial_starts_at=updated_account.trial_starts_at,
            trial_ends_at=updated_account.trial_ends_at,
            current_period_start=updated_account.current_period_start,
            current_period_end=updated_account.current_period_end,
            next_billing_at=updated_account.next_billing_at,
            current_plan=current_plan_info,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message=f"Subscription plan changed to {plan.code}",
            data=data,
        )

    except ValueError as ve:
        logger.warning("Change plan validation failed: %s", str(ve))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(ve),
        )
    except Exception as e:
        logger.exception("Failed to change subscription plan: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to change subscription plan",
        )


change_subscription_plan._custom_errors = change_subscription_plan_custom_errors
change_subscription_plan._custom_success = change_subscription_plan_custom_success


@router.post(
    "/subscription/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusResponse,
    summary="Schedule subscription cancellation at period end",
    responses=cancel_subscription_responses,
)
async def cancel_subscription(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Schedule subscription cancellation at period end.

    Args:
        organization_id (UUID): The UUID of the organisation.
        db (AsyncSession, Depends(get_db)): Asynchronous database session.

    Returns:
        dict: Standard API response containing:
            - status_code: HTTP status code.
            - message: Human-readable message.
            - data: SubscriptionStatusResponse with the updated subscription details.

    Raises:
        ValueError: If validation fails (e.g., no active subscription).
        Exception: For unexpected errors while cancelling the subscription.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Billing account not found",
            )

        if not account.stripe_subscription_id:
            return error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="No active subscription to cancel",
            )

        updated = await billing_service.cancel_subscription_for_account(
            account=account,
            cancel_at_period_end=True,
        )

        current_plan_info: BillingPlanInfo | None = None
        if updated.current_price_id:
            plan = await billing_service.get_plan_by_stripe_price_id(updated.current_price_id)
            if plan:
                current_plan_info = map_plan_to_plan_info(plan)

        await billing_service._sync_org_billing_from_account(
            db=db,
            organization_id=organization_id,
            account=updated,
            plan_info=current_plan_info,
        )

        data = SubscriptionStatusResponse(
            billing_account_id=updated.id,
            stripe_customer_id=updated.stripe_customer_id,
            stripe_subscription_id=updated.stripe_subscription_id,
            status=updated.status,
            cancel_at_period_end=updated.cancel_at_period_end or False,
            trial_starts_at=updated.trial_starts_at,
            trial_ends_at=updated.trial_ends_at,
            current_period_start=updated.current_period_start,
            current_period_end=updated.current_period_end,
            next_billing_at=updated.next_billing_at,
            current_plan=current_plan_info,
        )

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Subscription set to cancel at period end",
            data=data,
        )

    except ValueError as ve:
        logger.warning("Cancel subscription validation failed: %s", str(ve))
        return error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=str(ve),
        )
    except Exception as e:
        logger.exception("Failed to cancel subscription: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to cancel subscription",
        )


cancel_subscription._custom_errors = cancel_subscription_custom_errors
cancel_subscription._custom_success = cancel_subscription_custom_success


@router.get(
    "/payment-methods",
    status_code=status.HTTP_200_OK,
    summary="List payment methods for account",
    responses=list_payment_methods_responses,
)
async def list_payment_methods(
    organization_id: UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all payment methods associated with the caller's billing account with pagination.
    Args:
        organization_id (UUID): The UUID of the organisation.
        page (int): Page number.
        limit (int): Items per page.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the retrieved billing account
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        pms, total = await billing_service.list_payment_methods(account.id, page, limit)
        data = [PaymentMethodResponse.model_validate(pm.model_dump()) for pm in pms]
        pagination = calculate_pagination(total, page, limit)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Payment methods retrieved",
            data={"items": data, "pagination": pagination},
        )
    except Exception as e:
        logger.exception("Failed to list payment methods: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list payment methods",
        )


list_payment_methods._custom_errors = list_payment_methods_custom_errors
list_payment_methods._custom_success = list_payment_methods_custom_success


@router.delete(
    "/payment-methods/{payment_method_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment method",
    responses=delete_payment_method_responses,
)
async def delete_payment_method(
    organization_id: UUID,
    payment_method_id: UUID,
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a payment method record.

    Args:
        organization_id (UUID): The UUID of the organisation
        payment_method_id (UUID): The ID of the payment method to delete.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will indicate deletion status.

    Raises:
        ValueError: If the payment method does not belong to the caller's billing account.
        Exception: For unexpected errors encountered while deleting the payment method.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        success = await billing_service.delete_payment_method(payment_method_id=payment_method_id)
        if not success:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Payment method not found"
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.exception("Failed to delete payment method: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to delete payment method",
        )


delete_payment_method._custom_errors = delete_payment_method_custom_errors
delete_payment_method._custom_success = delete_payment_method_custom_success


@router.get(
    "/invoices",
    status_code=status.HTTP_200_OK,
    summary="List payment history for billing account",
    responses=list_invoices_responses,
)
async def list_invoices(
    organization_id: UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_billing_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all payment / invoice records for the caller's billing account (newest first).

    Args:
        organization_id (UUID): The UUID of the organisation.
        page (int): Page number.
        limit (int): Items per page.
        current_user (Depends(require_billing_admin)): The authenticated user object
        db (AsyncSession, Depends(get_db)): Asynchronous database session

    Returns:
        dict: containing keys like `status_code`, `message`, and `data`. On
        success `data` will be the list of invoices.
    """
    try:
        billing_service: BillingService = get_billing_service(db)
        account = await billing_service.get_billing_account_by_org(organization_id)
        if not account:
            return error_response(
                status_code=status.HTTP_404_NOT_FOUND, message="Billing account not found"
            )

        invoices, total = await billing_service.get_invoices_for_account(account.id, page, limit)
        data = [map_invoice_to_response(inv) for inv in invoices]
        pagination = calculate_pagination(total, page, limit)

        return success_response(
            status_code=status.HTTP_200_OK,
            message="Payment history retrieved",
            data={"items": data, "pagination": pagination},
        )
    except Exception as e:
        logger.exception("Failed to list payment history: %s", str(e))
        return error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Failed to list payment history",
        )


list_invoices._custom_errors = list_invoices_custom_errors
list_invoices._custom_success = list_invoices_custom_success


def map_invoice_to_response(inv: InvoiceHistory) -> InvoiceResponse:
    """
    Args:
        inv (InvoiceHistory): The invoice history record to map.

    Returns:
        InvoiceResponse: The mapped invoice response object for the API.
    """
    meta = inv.metadata_ or {}
    return InvoiceResponse(
        id=inv.id,
        billing_account_id=inv.billing_account_id,
        amount_due=inv.amount_due,
        amount_paid=inv.amount_paid,
        currency=inv.currency,
        status=inv.status,
        stripe_invoice_id=inv.stripe_invoice_id,
        stripe_payment_intent_id=inv.stripe_payment_intent_id,
        hosted_invoice_url=inv.hosted_invoice_url,
        invoice_pdf_url=inv.invoice_pdf_url,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        plan_code=meta.get("plan_code"),
        plan_tier=meta.get("plan_tier"),
        plan_label=meta.get("plan_label"),
        plan_interval=meta.get("plan_interval"),
    )
