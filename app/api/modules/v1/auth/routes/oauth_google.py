import logging

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.oauth import oauth
from app.api.db.database import get_db
from app.api.modules.v1.auth.service.google_oauth_service import GoogleOAuthService
from app.api.utils.cookie_helper import set_auth_cookies
from app.api.utils.response_payloads import success_response

from .docs.oauth_google_docs import (
    google_callback_custom_errors,
    google_callback_custom_success,
    google_callback_responses,
    google_login_custom_errors,
    google_login_custom_success,
    google_login_responses,
    google_profile_custom_errors,
    google_profile_custom_success,
    google_profile_responses,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth/google", tags=["Social Auth"])


@router.get(
    "/login",
    responses=google_login_responses,
)
async def google_login(
    request: Request,
    client: str = Query(
        default=settings.OAUTH_DEFAULT_CLIENT,
        description="Which frontend should receive the final redirect after Google OAuth completes."
        "Use 'local' when testing localhost frontend against staging backend.",
        pattern="^(local|staging|production)$",
        examples=["local"],
    ),
):
    """
    Initiate Google OAuth2 login flow.

    Generates CSRF state token and redirects to Google's OAuth consent screen.
    The state token prevents CSRF attacks by ensuring the callback comes from
    the same user who initiated the request.

    Args:

        request: HTTP request object

    Returns:

        RedirectResponse to Google OAuth endpoint
    """
    service = GoogleOAuthService(db=None, request=request)
    state = await service.generate_oauth_state(client=client)
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    return await oauth.google.authorize_redirect(request, redirect_uri, state=state)


google_login._custom_errors = google_login_custom_errors
google_login._custom_success = google_login_custom_success


@router.get(
    "/callback",
    responses=google_callback_responses,
)
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth2 callback.

    Processes OAuth callback with:
    - CSRF state validation
    - ID token verification
    - User creation/retrieval
    - JWT token generation
    - Profile data storage
    - Bearer token pattern (Authorization header, not cookies for access token)

    Args:
        request: HTTP request
        code: Authorization code from Google
        state: CSRF state parameter
        db: Database session

    Returns:
        RedirectResponse with tokens in URL fragment or error redirect
    """
    service = GoogleOAuthService(db=db, request=request)
    frontend_client = await service.validate_oauth_state(state)
    frontend_url = settings.OAUTH_CLIENT_FRONTEND_MAP.get(
        frontend_client,
        settings.OAUTH_CLIENT_FRONTEND_MAP[settings.OAUTH_DEFAULT_CLIENT],
    ).rstrip("/")
    token = await oauth.google.authorize_access_token(request)
    result = await service.complete_oauth_flow(token)

    access_token = result["access_token"]
    refresh_token = result["refresh_token"]
    is_new_user = result["is_new_user"]

    response = RedirectResponse(
        url=f"{frontend_url}/auth/google/callback?is_new_user={str(is_new_user).lower()}#access_token={access_token}&refresh_token={refresh_token}&token_type=bearer",
        status_code=status.HTTP_302_FOUND,
    )

    set_auth_cookies(
        response=response,
        request=request,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    return response


google_callback._custom_errors = google_callback_custom_errors
google_callback._custom_success = google_callback_custom_success


@router.get(
    "/profile",
    responses=google_profile_responses,
)
async def get_oauth_profile(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch current Google OAuth profile information.

    This endpoint is called by the frontend to retrieve the current user's
    profile data including picture and provider metadata.

    Args:
        request: HTTP request
        db: Database session

    Returns:
        Success response with user profile and OAuth metadata
    """
    from app.api.core.dependencies.auth import get_current_user

    current_user = await get_current_user(credentials=None, db=db)

    profile_data = {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "profile_picture_url": current_user.profile_picture_url,
        "auth_provider": current_user.auth_provider,
        "provider_user_id": current_user.provider_user_id,
        "provider_profile_data": current_user.provider_profile_data,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at.isoformat(),
    }

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Profile retrieved successfully",
        data=profile_data,
    )


get_oauth_profile._custom_errors = google_profile_custom_errors
get_oauth_profile._custom_success = google_profile_custom_success
