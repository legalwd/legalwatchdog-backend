import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.http_helpers import get_client_ip
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.reset_password_docs import (
    confirm_reset_custom_errors,
    confirm_reset_custom_success,
    confirm_reset_responses,
    request_reset_custom_errors,
    request_reset_custom_success,
    request_reset_responses,
    verify_reset_custom_errors,
    verify_reset_custom_success,
    verify_reset_responses,
)
from app.api.modules.v1.auth.schemas.reset_password import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerify,
)
from app.api.modules.v1.auth.service.rate_limit_service import RateLimitService
from app.api.modules.v1.auth.service.reset_password import (
    request_password_reset as service_request_reset,
)
from app.api.modules.v1.auth.service.reset_password import (
    reset_password as service_reset_password,
)
from app.api.modules.v1.auth.service.reset_password import (
    verify_reset_code as service_verify_code,
)
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/password", tags=["Auth"])

MAX_RESET_REQUEST_ATTEMPTS = 3
MAX_VERIFY_ATTEMPTS = 5
MAX_CONFIRM_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600
IP_RATE_LIMIT_MULTIPLIER = 3


@router.post(
    "/resets",
    status_code=status.HTTP_200_OK,
    responses=request_reset_responses,  # type: ignore
    response_model=PasswordResetRequest,
)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset for a user.

    - Validates the email address.
    - Generates a One-Time Password (OTP) and stores it securely.
    - Sends the OTP to the user's email.

    Rate Limited:
    - Maximum 3 requests per hour per email.
    - Maximum 9 requests per hour per IP address.

    Args:
        payload: Contains the user's email.
        request: HTTP request for IP extraction.
        background_tasks: For sending the email asynchronously.
        db: Database session dependency.

    Returns:
        JSON response confirming reset code was sent.
    """
    logger.info("Password reset requested for email=%s", payload.email)

    rate_limiter = RateLimitService(
        max_email_attempts=MAX_RESET_REQUEST_ATTEMPTS,
        max_ip_attempts=MAX_RESET_REQUEST_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
        rate_limit_window=RATE_LIMIT_WINDOW_SECONDS,
    )

    ip_address = get_client_ip(request)
    await rate_limiter.check_combined_limits(
        email=payload.email,
        ip_address=ip_address,
        key_prefix="password_reset",
    )

    result = await service_request_reset(db, payload.email, background_tasks)

    logger.info("Password reset code sent for email=%s", payload.email)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Reset code sent to email.",
        data=result,
    )


request_password_reset._custom_errors = request_reset_custom_errors  # type: ignore
request_password_reset._custom_success = request_reset_custom_success  # type: ignore


@router.post(
    "/resets/verification",
    status_code=status.HTTP_200_OK,
    responses=verify_reset_responses,  # type: ignore
    response_model=PasswordResetVerify,
)
async def verify_reset_code(
    payload: PasswordResetVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the OTP code sent to user's email.

    - Validates the provided code.
    - Returns a temporary reset token if valid.

    Rate Limited:
    - Maximum 5 requests per hour per email.
    - Maximum 15 requests per hour per IP address.

    Args:
        payload: Contains email and OTP code.
        request: HTTP request for IP extraction.
        db: Database session dependency.

    Returns:
        JSON response containing the temporary reset token.
    """
    logger.info("Verifying password reset code for email=%s", payload.email)

    rate_limiter = RateLimitService(
        max_email_attempts=MAX_VERIFY_ATTEMPTS,
        max_ip_attempts=MAX_VERIFY_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
        rate_limit_window=RATE_LIMIT_WINDOW_SECONDS,
    )

    ip_address = get_client_ip(request)
    await rate_limiter.check_combined_limits(
        email=payload.email,
        ip_address=ip_address,
        key_prefix="password_verify",
    )

    reset_token = await service_verify_code(db, payload.email, payload.code)

    logger.info("Reset code verified for email=%s", payload.email)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Token verified successfully.",
        data={"reset_token": reset_token},
    )


verify_reset_code._custom_errors = verify_reset_custom_errors  # type: ignore
verify_reset_code._custom_success = verify_reset_custom_success  # type: ignore


@router.post(
    "/resets/confirmation",
    status_code=status.HTTP_200_OK,
    responses=confirm_reset_responses,  # type: ignore
    response_model=PasswordResetConfirm,
)
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm and reset the user's password using the temporary token.

    - Validates the temporary reset token.
    - Updates the user's password.
    - Prevents reuse of previous passwords.

    Rate Limited:
    - Maximum 5 requests per hour per token.
    - Maximum 15 requests per hour per IP address.

    Args:
        payload: Contains reset_token and new_password.
        request: HTTP request for IP extraction.
        db: Database session dependency.

    Returns:
        JSON response confirming password reset success.
    """
    logger.info("Confirming password reset for reset_token=%s", payload.reset_token[:10])

    rate_limiter = RateLimitService(
        max_email_attempts=MAX_CONFIRM_ATTEMPTS,
        max_ip_attempts=MAX_CONFIRM_ATTEMPTS * IP_RATE_LIMIT_MULTIPLIER,
        rate_limit_window=RATE_LIMIT_WINDOW_SECONDS,
    )

    ip_address = get_client_ip(request)
    await rate_limiter.check_combined_limits(
        email=payload.reset_token,
        ip_address=ip_address,
        key_prefix="password_confirm",
    )

    await service_reset_password(db, payload.reset_token, payload.new_password)

    logger.info("Password reset completed successfully")
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Password reset successful.",
    )


confirm_password_reset._custom_errors = confirm_reset_custom_errors  # type: ignore
confirm_password_reset._custom_success = confirm_reset_custom_success  # type: ignore
