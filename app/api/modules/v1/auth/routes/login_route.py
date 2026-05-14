import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.http_helpers import (
    extract_bearer_token,
    get_client_ip,
)
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.login_route_docs import (
    login_custom_errors,
    login_custom_success,
    login_responses,
    logout_custom_errors,
    logout_custom_success,
    logout_responses,
    refresh_custom_errors,
    refresh_custom_success,
    refresh_token_responses,
)
from app.api.modules.v1.auth.schemas.login import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
)
from app.api.modules.v1.auth.service.login_service import LoginService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.cookie_helper import clear_auth_cookies, set_auth_cookies
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses=login_responses,  # type: ignore
)
async def login(login_data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Authenticate a user and issue access and refresh tokens.

    This endpoint supports:
    - Secure password verification
    - Token rotation for refresh tokens
    - OAuth2-style form login or JSON login payload

    Args:
        login_data: Login credentials (email and password).
        request: The incoming HTTP request.
        db: Database session dependency.

    Returns:
        JSON response with access and refresh tokens on success.
    """
    login_service = LoginService(db)
    client_ip = get_client_ip(request)

    result = await login_service.login(
        email=login_data.email, password=login_data.password, ip_address=client_ip
    )

    response = success_response(
        status_code=status.HTTP_200_OK,
        message="Login successful",
        data={
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "token_type": result["token_type"],
            "expires_in": result["expires_in"],
        },
    )

    set_auth_cookies(
        response=response,
        request=request,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )

    return response


login._custom_errors = login_custom_errors  # type: ignore
login._custom_success = login_custom_success  # type: ignore


@router.post(
    "/token/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    responses=refresh_token_responses,  # type: ignore
)
async def refresh_token(
    request: Request,
    refresh_data: Optional[RefreshTokenRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access and refresh tokens using a valid refresh token.

    This endpoint:
    - Extracts refresh token from request or cookies
    - Calls service to validate and rotate tokens
    - Blacklists the old refresh token
    - Issues new access and refresh tokens

    Args:
        request: The incoming HTTP request.
        refresh_data: Pydantic schema containing the refresh token.
        db: Database session dependency.

    Returns:
        JSON response with new tokens.
    """
    token = refresh_data.refresh_token if refresh_data else None
    if not token:
        token = request.cookies.get("lwd_refresh_token")

    login_service = LoginService(db)
    result = await login_service.refresh_access_token(refresh_token=token)

    response = success_response(
        status_code=status.HTTP_200_OK,
        message="Token refreshed successfully",
        data=result,
    )

    set_auth_cookies(
        response,
        request,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )

    return response


refresh_token._custom_errors = refresh_custom_errors  # type: ignore
refresh_token._custom_success = refresh_custom_success  # type: ignore


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses=logout_responses,
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout the current user by invalidating their tokens.

    This endpoint:
    - Blacklists the user's current access token
    - Blacklists the user's current refresh token

    Args:
        request: HTTP request to extract token from header.
        current_user: Currently authenticated user from dependency.
        db: Database session dependency.

    Returns:
        JSON response confirming logout.
    """
    token = extract_bearer_token(request)

    login_service = LoginService(db)

    await login_service.logout(user_id=str(current_user.id), token=token)

    response = success_response(
        status_code=status.HTTP_200_OK,
        message="Logged out successfully",
        data={},
    )

    clear_auth_cookies(response=response, request=request)

    logger.info("User %s logged out successfully", str(current_user.id))

    return response


logout._custom_errors = logout_custom_errors
logout._custom_success = logout_custom_success
