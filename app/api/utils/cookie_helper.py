"""Cookie management utilities for OAuth and authentication."""

import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import Response

from app.api.core.config import settings

logger = logging.getLogger(__name__)

# Cookie name constants
ACCESS_TOKEN_COOKIE_NAME = "lwd_access_token"
REFRESH_TOKEN_COOKIE_NAME = "lwd_refresh_token"


def get_cookie_settings(request: Request) -> Dict:
    """
    Determine dynamic cookie settings based on request origin and environment.

    Validates origin against request to prevent cookie misconfiguration.
    Uses HTTPS and SameSite=None in production, relaxed settings in development.

    Args:
        request: HTTP request object.

    Returns:
        Dictionary with cookie configuration:
            - domain: Cookie domain (None for localhost)
            - secure: Whether to set Secure flag
            - samesite: SameSite attribute value
            - frontend_url: Frontend URL for redirects

    Examples:
        >>> settings = get_cookie_settings(request)
        >>> response.set_cookie("token", value, **settings)
    """
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")

    source_url = origin if origin else referer

    logger.debug(f"Getting cookie settings for origin: {origin}, referer: {referer}")

    # Check if request is from localhost
    is_local = "localhost" in source_url or "127.0.0.1" in source_url

    if is_local:
        return {
            "domain": None,
            "secure": False,
            "samesite": "lax",
            "frontend_url": settings.DEV_URL,
        }

    # Production settings
    if settings.ENVIRONMENT == "production":
        parsed = urlparse(settings.APP_URL)

        # Determine domain from parsed URL
        domain = None
        if parsed.netloc:
            # Strip 'www.' prefix to ensure cookie works on root and all subdomains
            domain = parsed.netloc[4:] if parsed.netloc.startswith("www.") else parsed.netloc
            if not domain.startswith("."):
                domain = f".{domain}"

        return {
            "domain": domain,
            "secure": True,
            "samesite": "none",
            "frontend_url": settings.APP_URL,
        }

    # Development/staging settings
    return {
        "domain": None,
        "secure": False,
        "samesite": "lax",
        "frontend_url": settings.DEV_URL,
    }


def set_auth_cookies(
    response: Response,
    request: Request,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    access_token_max_age: int = 172800,  # 2 days
    refresh_token_max_age: int = 2592000,  # 30 days
) -> None:
    """
    Set authentication cookies with consistent settings across all OAuth providers.

    Args:
        response: FastAPI response object to set cookies on.
        request: HTTP request object to determine cookie settings.
        access_token: Access token value (optional).
        refresh_token: Refresh token value (optional).
        access_token_max_age: Max age for access token cookie in seconds (default: 2 days).
        refresh_token_max_age: Max age for refresh token cookie in seconds (default: 30 days).

    Examples:
        >>> response = RedirectResponse(url=frontend_url)
        >>> set_auth_cookies(
        ...     response, request,
        ...     access_token=access_token,
        ...     refresh_token=refresh_token
        ... )
    """
    cookie_settings = get_cookie_settings(request)

    # Set access token cookie if provided
    if access_token:
        response.set_cookie(
            key=ACCESS_TOKEN_COOKIE_NAME,
            value=access_token,
            httponly=True,
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            max_age=access_token_max_age,
            path="/",
            domain=cookie_settings["domain"],
        )

    # Set refresh token cookie if provided
    if refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=cookie_settings["secure"],
            samesite=cookie_settings["samesite"],
            max_age=refresh_token_max_age,
            path="/",
            domain=cookie_settings["domain"],
        )

    logger.debug(
        f"Set auth cookies with domain={cookie_settings['domain']}, "
        f"secure={cookie_settings['secure']}, samesite={cookie_settings['samesite']}"
    )


def clear_auth_cookies(response: Response, request: Request) -> None:
    """
    Clear all authentication cookies.

    Used during logout to remove access and refresh token cookies.

    Args:
        response: FastAPI response object to clear cookies from.
        request: HTTP request object to determine cookie settings.

    Examples:
        >>> response = JSONResponse(content={"message": "Logged out"})
        >>> clear_auth_cookies(response, request)
    """
    cookie_settings = get_cookie_settings(request)

    # Clear access token cookie
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        path="/",
        domain=cookie_settings["domain"],
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
    )

    # Clear refresh token cookie
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path="/",
        domain=cookie_settings["domain"],
        secure=cookie_settings["secure"],
        samesite=cookie_settings["samesite"],
    )

    logger.debug(f"Cleared auth cookies with domain={cookie_settings['domain']}")


def set_single_cookie(
    response: Response,
    key: str,
    value: str,
    request: Request,
    max_age: int = None,
    httponly: bool = True,
    **kwargs,
) -> None:
    """
    Set a single cookie with environment-aware defaults.

    Provides a flexible way to set custom cookies while maintaining
    consistent security settings across environments.

    Args:
        response: FastAPI response object to set cookie on.
        key: Cookie name.
        value: Cookie value.
        request: HTTP request object to determine cookie settings.
        max_age: Cookie expiration in seconds (None for session cookie).
        httponly: Whether cookie is HTTP-only (default: True).
        **kwargs: Additional cookie parameters to override defaults.

    Examples:
        >>> set_single_cookie(response, "custom_token", token_value, request, max_age=3600)
    """
    cookie_settings = get_cookie_settings(request)

    # Merge default settings with any overrides
    cookie_params = {
        "key": key,
        "value": value,
        "httponly": httponly,
        "secure": cookie_settings["secure"],
        "samesite": cookie_settings["samesite"],
        "path": "/",
        "domain": cookie_settings["domain"],
    }

    if max_age is not None:
        cookie_params["max_age"] = max_age

    # Override with any custom parameters
    cookie_params.update(kwargs)

    response.set_cookie(**cookie_params)

    logger.debug(f"Set cookie '{key}' with custom settings")
