import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.registeration_redis import get_redis
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.auth_routes_docs import (
    company_signup_custom_errors,
    company_signup_custom_success,
    company_signup_responses,
    request_new_otp_custom_errors,
    request_new_otp_custom_success,
    request_new_otp_responses,
    verify_otp_custom_errors,
    verify_otp_custom_success,
    verify_otp_responses,
)
from app.api.modules.v1.auth.routes.docs.invitation_docs import (
    accept_invitation_custom_errors,
    accept_invitation_custom_success,
    accept_invitation_responses,
)
from app.api.modules.v1.auth.schemas.register import (
    RegisterRequest,
    RegisterResponse,
)
from app.api.modules.v1.auth.schemas.resend_otp import ResendOTPRequest
from app.api.modules.v1.auth.schemas.verify_otp import (
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.api.modules.v1.auth.service.register_service import RegistrationService
from app.api.modules.v1.organization.service.invitation_service import InvitationCRUD
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import (
    error_response,
    success_response,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

logger = logging.getLogger("app")

MAX_OTP_REQUEST_ATTEMPTS = 3
MAX_OTP_VERIFY_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600
IP_RATE_LIMIT_MULTIPLIER = 3


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses=company_signup_responses,
)
async def company_signup(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
    token: Optional[str] = None,
):
    """
    Initiate company registration with email verification.

    Creates a pending registration, generates an OTP, and sends it to the provided
    email address. Actual organization and user creation occurs after OTP verification.

    Args:
        payload (RegisterRequest): Registration details including name, email, and password.
        background_tasks (BackgroundTasks): FastAPI background tasks instance for async operations.
        db (AsyncSession, optional): Async SQLAlchemy session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP management.
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response with status, message, and data/error details.
    """
    service = RegistrationService(db, redis_client)
    result = await service.register_user_with_validation(payload, background_tasks, token)

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration initiated. Verify the OTP sent to your email.",
        data=result,
    )


company_signup._custom_errors = company_signup_custom_errors
company_signup._custom_success = company_signup_custom_success


@router.post(
    "/otp/verification",
    response_model=VerifyOTPResponse,
    status_code=status.HTTP_201_CREATED,
    responses=verify_otp_responses,
)
async def verify_otp(
    payload: VerifyOTPRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Verify OTP and complete company registration.

    Validates the one-time password sent to the user's email and completes the
    registration process by creating the organization, admin role, and admin user account.

    Rate Limited:
    - Maximum 5 verification attempts per hour per email.
    - Maximum 15 verification attempts per hour per IP address.

    Args:
        payload (VerifyOTPRequest): Object containing email and OTP code.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP validation
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response indicating OTP verification status.

    Raises:
        RateLimitExceeded: If the email or IP exceeds the allowed number of verification attempts.
        ValueError: If the OTP is invalid or expired.
        HTTPException: 500 for internal server errors.
    """
    ip_address = request.client.host if request.client else None

    service = RegistrationService(db, redis_client)
    result = await service.verify_otp_with_rate_limit(
        email=payload.email,
        code=payload.code,
        ip_address=ip_address,
        background_tasks=background_tasks,
    )

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Registration completed successfully",
        data=result,
    )


verify_otp._custom_errors = verify_otp_custom_errors
verify_otp._custom_success = verify_otp_custom_success


@router.post(
    "/otp/requests",
    response_model=RegisterResponse,
    status_code=status.HTTP_200_OK,
    responses=request_new_otp_responses,
)
async def request_new_otp(
    payload: ResendOTPRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Resend OTP for pending registration.

    Generates and sends a new OTP code to an email address with a pending registration
    that has not yet completed verification. The previous OTP is invalidated.

    Rate Limited:
    - Maximum 3 requests per hour per email.
    - Maximum 9 requests per hour per IP address.

    Args:
        payload (ResendOTPRequest): Object containing the email to resend OTP for.
        background_tasks (BackgroundTasks): FastAPI background tasks instance for async operations.
        db (AsyncSession, optional): Async database session. Defaults to Depends(get_db).
        redis_client (Redis, optional): Redis client for OTP management.
        Defaults to Depends(get_redis).

    Returns:
        dict: Standardized success or error response containing OTP resend status.

    Raises:
        RateLimitExceeded: If the email or IP exceeds the allowed number of requests.
        HTTPException: 400 for validation errors or 500 for internal server errors.
    """
    ip_address = request.client.host if request.client else None

    service = RegistrationService(db, redis_client)
    result = await service.resend_otp_with_rate_limit(
        email=payload.email,
        background_tasks=background_tasks,
        ip_address=ip_address,
    )

    minutes = settings.REDIS_RESEND_TTL / 60
    minutes_display = int(minutes) if minutes.is_integer() else round(minutes, 2)
    unit = "minute" if minutes_display == 1 else "minutes"
    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"A new OTP has been sent to your email, expiring in {minutes_display} {unit}.",
        data=result,
    )


request_new_otp._custom_errors = request_new_otp_custom_errors
request_new_otp._custom_success = request_new_otp_custom_success


request_new_otp._custom_errors = request_new_otp_custom_errors
request_new_otp._custom_success = request_new_otp_custom_success


@router.post(
    "/invitations/{token}/accept",
    status_code=status.HTTP_200_OK,
    response_model=None,
    responses=accept_invitation_responses,  # type: ignore
)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Accept an organization invitation.

    This endpoint handles invitation acceptance for both registered and unregistered users:
    - Registered & authenticated users: Validates email match and adds to organization
    - Unregistered users or unauthenticated: Returns 401 with instructions to register

    SECURITY: For authenticated users, validates that their email matches the invitation's
    invited_email to prevent unauthorized access.

    Args:
        token: The unique invitation token.
        db: Database session dependency.
        current_user: The authenticated user (optional, from JWT token if provided).

    Returns:
        dict: Success response (200) for authenticated users with organization details
        dict: Error response (401) for unauthenticated users needing to register

    Raises:
        NotFoundError: If invitation token is invalid
        BadRequestError: If invitation is expired or already processed
        PermissionDeniedError: If email mismatch for authenticated users
        ProcessingError: For unexpected processing failures
    """
    logger.info(f"Accepting invitation token={token}")

    user_id = current_user.id if current_user else None
    user_email = current_user.email if current_user else None

    result = await InvitationCRUD.accept_invitation(
        db=db,
        token=token,
        current_user_id=user_id,
        current_user_email=user_email,
    )

    if result.get("already_member"):
        return success_response(
            status_code=status.HTTP_200_OK,
            message=result["message"],
            data={"organization_id": result["organization_id"]},
        )

    if result.get("requires_registration"):
        logger.info(f"Unauthenticated user for invitation token={token}. Registration required.")
        return error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Please register or log in to accept this invitation.",
            error_code="AUTHORIZATION_REQUIRED",
        )

    logger.info(f"Invitation accepted successfully for token={token}")
    return success_response(
        status_code=status.HTTP_200_OK,
        message=result["message"],
        data={
            "organization_id": result["organization_id"],
            "organization_name": result.get("organization_name"),
            "role_name": result.get("role_name"),
        },
    )


accept_invitation._custom_errors = accept_invitation_custom_errors  # type: ignore
accept_invitation._custom_success = accept_invitation_custom_success  # type: ignore
