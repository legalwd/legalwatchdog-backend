import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.registeration_redis import get_redis
from app.api.db.database import get_db
from app.api.modules.v1.auth.routes.docs.oauth_microsoft import (
    microsoft_callback_custom_errors,
    microsoft_callback_custom_success,
    microsoft_callback_responses,
    microsoft_login_custom_errors,
    microsoft_login_custom_success,
    microsoft_login_responses,
)
from app.api.modules.v1.auth.schemas.oauth_microsoft import MicrosoftAuthResponse
from app.api.modules.v1.auth.service.oauth_microsoft import MicrosoftOAuthService
from app.api.utils.cookie_helper import set_auth_cookies
from app.api.utils.response_payloads import success_response

router = APIRouter(prefix="/oauth/microsoft", tags=["Social Auth"])

logger = logging.getLogger("app")


@router.get(
    "/login",
    response_model=MicrosoftAuthResponse,
    status_code=status.HTTP_200_OK,
    responses=microsoft_login_responses,  # type: ignore
)
async def microsoft_login(
    redirect_uri: Optional[str] = Query(None, description="Custom redirect URI"),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Initiate Microsoft OAuth login flow.

    Returns authorization URL that the client should redirect to.
    The user will authenticate with Microsoft and be redirected back
    to the callback endpoint with an authorization code.

    Args:
        redirect_uri: Optional custom redirect URI (must be registered in Azure AD)
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        Authorization URL and state parameter for CSRF protection

    Raises:
        HTTPException:
            - 422 Unprocessable Entity if validation fails
            - 500 Internal Server Error if OAuth URL generation fails
    """
    logger.info("Initiating Microsoft OAuth login flow")

    service = MicrosoftOAuthService(db, redis_client)
    authorization_url, state = await service.generate_authorization_url(redirect_uri)

    logger.info("Microsoft OAuth URL generated successfully")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Authorization URL generated successfully",
        data={
            "authorization_url": authorization_url,
            "state": state,
        },
    )


microsoft_login._custom_errors = microsoft_login_custom_errors  # type: ignore
microsoft_login._custom_success = microsoft_login_custom_success  # type: ignore


@router.get(
    "/callback",
    status_code=status.HTTP_302_FOUND,
    responses=microsoft_callback_responses,  # type: ignore
)
async def microsoft_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Microsoft"),
    state: str = Query(..., description="State parameter for validation"),
    error: Optional[str] = Query(None, description="Error from Microsoft"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """
    Handle Microsoft OAuth callback and redirect to frontend with cookies set.
    Uses frontend URLs from environment variables.

    Args:
        request: FastAPI request object
        code: Authorization code from Microsoft
        state: State parameter for validation
        error: Optional error from Microsoft
        error_description: Optional error description from Microsoft
        db: Database session dependency
        redis_client: Redis client dependency

    Returns:
        RedirectResponse to frontend with authentication cookies

    Raises:
        HTTPException:
            - 401 Unauthorized if authentication fails (invalid state, token exchange failed,
            missing access token)
            - 422 Unprocessable Entity if validation fails
            - 500 Internal Server Error if OAuth flow fails or external service error occurs
    """
    service = MicrosoftOAuthService(db, redis_client)

    if error:
        error_redirect_url = service.handle_microsoft_oauth_error(error, error_description)
        return RedirectResponse(url=error_redirect_url)

    logger.info(f"Processing Microsoft OAuth callback with state: {state}")

    result = await service.complete_oauth_flow(code, state)

    response = RedirectResponse(url=result["redirect_url"], status_code=status.HTTP_302_FOUND)

    set_auth_cookies(
        response=response,
        request=request,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )

    logger.info(
        f"Successfully authenticated user {result['email']} via Microsoft OAuth, "
        f"redirecting to {result['redirect_url']}"
    )

    return response


microsoft_callback._custom_errors = microsoft_callback_custom_errors  # type: ignore
microsoft_callback._custom_success = microsoft_callback_custom_success  # type: ignore
