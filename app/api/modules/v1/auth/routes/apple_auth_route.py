import logging

from fastapi import APIRouter, Depends, Form, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.db.database import get_db
from app.api.modules.v1.auth.schemas.apple_auth import AppleAuthRequest
from app.api.modules.v1.auth.service.apple_auth import AppleAuthClient
from app.api.utils.cookie_helper import set_auth_cookies
from app.api.utils.response_payloads import auth_response, success_response

from .docs.apple_auth_route_docs import (
    apple_callback_custom_errors,
    apple_callback_custom_success,
    apple_callback_responses,
    apple_login_custom_errors,
    apple_login_custom_success,
    apple_login_responses,
)

router = APIRouter(prefix="/oauth/apple", tags=["Social Auth"])
logger = logging.getLogger("app")


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    responses=apple_login_responses,
)
async def apple_login(
    req: AppleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Apple sign-in.

    Accepts an authorization code from the frontend, completes the OAuth flow,
    and returns a JWT access token along with user info.

    Args:
        req (AppleAuthRequest): Request containing authorization code and optional redirect URI
        request (Request): FastAPI request object for cookie handling
        response (Response): FastAPI response object for setting cookies
        db (AsyncSession): Database session for query execution

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Apple login successful"
            - access_token (str): JWT access token
            - data (dict): User information including:
                - user_id (str): Unique identifier for the user
                - email (str): User's email address
                - is_new_user (bool): Whether this is a newly created user

    Raises:
        HTTPException:
            - 401 Unauthorized if Apple authentication fails (invalid token, expired token,
            missing ID token)
            - 422 Unprocessable Entity if request validation fails
            - 500 Internal Server Error if unexpected operation fails
    """
    logger.info("Initiating Apple login with code")

    apple_client = AppleAuthClient(db)
    result = await apple_client.complete_oauth_flow(
        code=req.code, redirect_uri=req.redirect_uri or settings.APPLE_REDIRECT_URI
    )

    set_auth_cookies(
        response=response,
        request=request,
        access_token=result["access_token"],
        refresh_token=None,
    )

    logger.info(f"Apple login successful for user_id={result['user_id']}")

    return auth_response(
        status_code=status.HTTP_200_OK,
        message="Apple login successful",
        access_token=result["access_token"],
        data={
            "user_id": result["user_id"],
            "email": result["email"],
            "is_new_user": result["is_new_user"],
        },
    )


apple_login._custom_errors = apple_login_custom_errors
apple_login._custom_success = apple_login_custom_success


@router.post(
    "/callback",
    status_code=status.HTTP_200_OK,
    responses=apple_callback_responses,
)
async def apple_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    code: str = Form(...),
):
    """
    Callback endpoint for Apple OAuth.

    Receives POST data from Apple after user login, completes the OAuth flow,
    and returns JWT access token and user details.

    Args:
        request (Request): FastAPI request object for cookie handling
        response (Response): FastAPI response object for setting cookies
        db (AsyncSession): Database session for query execution
        code (str): Authorization code from Apple

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Login successful"
            - data (dict): Complete OAuth flow result including:
                - access_token (str): JWT access token
                - token_type (str): Type of token ("bearer")
                - user_id (str): Unique identifier for the user
                - email (str): User's email address
                - is_new_user (bool): Whether this is a newly created user

    Raises:
        HTTPException:
            - 401 Unauthorized if Apple authentication fails (invalid token, expired token,
            missing ID token)
            - 422 Unprocessable Entity if request validation fails
            - 500 Internal Server Error if unexpected operation fails
    """
    logger.info("Processing Apple OAuth callback")

    apple_client = AppleAuthClient(db)
    result = await apple_client.complete_oauth_flow(
        code=code, redirect_uri=settings.APPLE_REDIRECT_URI
    )

    set_auth_cookies(
        response=response,
        request=request,
        access_token=result["access_token"],
        refresh_token=None,
    )

    logger.info(f"Apple callback successful for user_id={result['user_id']}")

    return success_response(status_code=status.HTTP_200_OK, message="Login successful", data=result)


apple_callback._custom_errors = apple_callback_custom_errors
apple_callback._custom_success = apple_callback_custom_success
