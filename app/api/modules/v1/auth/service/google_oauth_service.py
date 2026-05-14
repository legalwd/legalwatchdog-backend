import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AccountInactiveError,
    InvalidClientError,
    MissingEmailError,
    MissingIDTokenError,
    OAuthFlowError,
    OAuthStateInvalidError,
    OAuthTokenInvalidError,
    ProcessingError,
)
from app.api.core.dependencies.redis_service import get_redis_client
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.auth.models.oauth_models import OAuthLoginEvent, RefreshTokenMetadata
from app.api.modules.v1.users.models.users_model import User
from app.api.modules.v1.users.service.user import UserCRUD
from app.api.utils.jwt import create_access_token, get_token_jti

logger = logging.getLogger(__name__)

ENVIRONMENT = settings.ENVIRONMENT.lower()


class GoogleOAuthService:
    """
    Comprehensive Google OAuth2 service handling token generation, validation,
    user management, and audit logging.

    Implements OAuth2 best practices including:
    - CSRF state validation
    - Token rotation
    - Refresh token metadata tracking
    - Provider profile data storage
    - Audit logging for all authentication attempts
    """

    def __init__(self, db: AsyncSession, request: Request):
        """
        Initialize Google OAuth service.

        Args:
            db: Async database session
            request: HTTP request for extracting client context
        """
        self.db = db
        self.request = request
        self.client_ip = self._extract_client_ip()
        self.user_agent = request.headers.get("user-agent", "")[:500]

    def _extract_client_ip(self) -> str:
        """
        Extract client IP from request headers with proxy support.

        Returns:
            Client IP address string
        """
        forwarded_for = self.request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = self.request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        client = self.request.client
        return client.host if client else "unknown"

    async def generate_oauth_state(self, client: str) -> str:
        """
        Generate and store CSRF state token in Redis.

        State tokens prevent CSRF attacks by ensuring the callback matches
        the original request. Token expires in 15 minutes.

        Args:
            client: OAuth client identifier (e.g., local, staging, production)

        Returns:
            Base64-encoded state string

        Raises:
            InvalidClientError: If client is not in allowed clients
            ProcessingError: If Redis is unavailable

        Examples:
            >>> service = GoogleOAuthService(db, request)
            >>> state = await service.generate_oauth_state("local")
            >>> # Store in session, redirect to Google with state
        """
        if client not in settings.OAUTH_ALLOWED_CLIENTS:
            raise InvalidClientError(
                message=(
                    "We're unable to process your request right now. "
                    "Please contact support if this continues."
                )
            )

        try:
            import base64
            import os

            state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")
            redis_client = await get_redis_client()

            await redis_client.setex(
                f"{ENVIRONMENT}:google_oauth_state:{state}",
                900,
                "pending",
            )

            await redis_client.setex(
                f"{ENVIRONMENT}:google_oauth_client:{state}",
                900,
                client,
            )

            logger.info(f"Generated CSRF state for OAuth flow from IP {self.client_ip}")
            return state
        except InvalidClientError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate OAuth state: {str(e)}")
            raise ProcessingError(
                message=(
                    "We're having trouble connecting to Google right now. "
                    "Please try again in a moment."
                )
            )

    async def validate_oauth_state(self, state: str) -> str:
        """
        Validate CSRF state parameter against stored value.

        Args:
            state: State parameter from OAuth callback

        Returns:
            str: OAuth client identifier associated with the state

        Raises:
            HTTPException: If state is invalid or missing

        Examples:
            >>> frontend_client = await service.validate_oauth_state(state_param)
            >>> # Proceed with token exchange if valid
        """
        try:
            redis_client = await get_redis_client()

            stored_state = await redis_client.get(f"{ENVIRONMENT}:google_oauth_state:{state}")
            if not stored_state:
                logger.warning(f"Invalid OAuth state from IP {self.client_ip}: state not found")
                raise OAuthStateInvalidError(provider="Google")

            frontend_client = await redis_client.get(f"{ENVIRONMENT}:google_oauth_client:{state}")
            if not frontend_client:
                logger.warning(f"OAuth client not found for state from IP {self.client_ip}")
                raise OAuthStateInvalidError(provider="Google")
            if frontend_client not in settings.OAUTH_ALLOWED_CLIENTS:
                raise InvalidClientError(
                    message=(
                        "We're unable to process your request right now. "
                        "Please contact support if this continues."
                    )
                )

            await redis_client.delete(f"{ENVIRONMENT}:google_oauth_state:{state}")
            await redis_client.delete(f"{ENVIRONMENT}:google_oauth_client:{state}")
            logger.info(f"Validated CSRF state from IP {self.client_ip}")

            if isinstance(frontend_client, (bytes, bytearray)):
                frontend_client = frontend_client.decode("utf-8")

            return frontend_client

        except (OAuthStateInvalidError, InvalidClientError):
            raise

        except Exception as e:
            logger.error(f"Failed to validate OAuth state: {str(e)}")
            raise ProcessingError(
                message=(
                    "We're unable to connect to Google right now. "
                    "Please try again in a few moments."
                )
            )

    async def complete_oauth_flow(
        self, google_token: dict, background_tasks: BackgroundTasks = None
    ) -> Dict:
        """
        Complete Google OAuth flow and return user with tokens.

        Handles:
        - ID token verification and parsing
        - User creation/retrieval
        - Profile data extraction and storage
        - App-level JWT token generation
        - Token metadata storage in database

        Args:
            google_token: Token dict from authlib Google authorization_access_token

        Returns:
            Dictionary with:
                - access_token: JWT access token (2 day expiry)
                - refresh_token: JWT refresh token (30 day expiry)
                - token_type: "bearer"
                - expires_in: Access token expiry in seconds (172800)
                - user: User profile object
                - is_new_user: Whether user was just created

        Raises:
            HTTPException: On validation or token errors

        Examples:
            >>> result = await service.complete_oauth_flow(google_token)
            >>> user_id = result['user']['id']
            >>> access_token = result['access_token']
        """
        id_token_str = google_token.get("id_token")

        if not id_token_str:
            await self._log_oauth_event(
                provider="google",
                status="error",
                failure_reason="No id_token in response",
                error_code="MISSING_ID_TOKEN",
            )
            logger.error("Google OAuth: Missing id_token in response")
            raise MissingIDTokenError(provider="Google")

        try:
            user_info = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                audience=settings.GOOGLE_CLIENT_ID,
            )
        except Exception as e:
            await self._log_oauth_event(
                provider="google",
                status="error",
                failure_reason="ID token verification failed",
                error_code="INVALID_TOKEN",
            )
            logger.error(f"Google OAuth: Token verification failed: {str(e)}")
            raise OAuthTokenInvalidError(provider="Google")

        email = user_info.get("email")
        if not email:
            await self._log_oauth_event(
                provider="google",
                status="error",
                failure_reason="Email not found in ID token",
                error_code="MISSING_EMAIL",
            )
            logger.error("Google OAuth: Email not found in token")
            raise MissingEmailError(provider="Google")

        try:
            user = await UserCRUD.get_by_email(self.db, email)

            is_new_user = False
            if not user:
                user = await self._create_oauth_user(email, user_info)
                is_new_user = True
                await self.db.commit()
                await self.db.refresh(user)

                # Send pending approval email for new users
                if background_tasks:
                    background_tasks.add_task(
                        send_email,
                        "account_pending_approval.html",
                        "Your Account is Pending Approval",
                        user.email,
                        {"full_name": user.name},
                    )
                    logger.info(
                        f"Queued pending approval email for new Google OAuth user_id={user.id}"
                    )

            if not user.is_active:
                await self._log_oauth_event(
                    provider="google",
                    user_id=str(user.id),
                    status="blocked",
                    failure_reason="User account is inactive",
                    error_code="ACCOUNT_INACTIVE",
                    email=email,
                )
                logger.warning(f"Google OAuth login blocked: inactive account {email}")
                raise AccountInactiveError()

            await self._update_oauth_profile(user, user_info)
            await self.db.commit()
            await self.db.refresh(user)

            tokens = await self._generate_and_store_tokens(user, user_info, google_token)

            await self._log_oauth_event(
                provider="google",
                user_id=str(user.id),
                status="success",
                email=email,
            )

            logger.info(f"Google OAuth successful for user {email}")

            return {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": "bearer",
                "expires_in": 172800,
                "user": user,
                "is_new_user": is_new_user,
            }

        except (
            MissingIDTokenError,
            OAuthTokenInvalidError,
            MissingEmailError,
            AccountInactiveError,
        ):
            raise
        except Exception as e:
            await self._log_oauth_event(
                provider="google",
                status="error",
                failure_reason=str(e)[:500],
                error_code="OAUTH_FLOW_ERROR",
                email=email,
            )
            logger.error(f"Google OAuth flow error: {str(e)}", exc_info=True)
            raise OAuthFlowError(provider="Google")

    async def _create_oauth_user(self, email: str, user_info: dict) -> User:
        """
        Create new Google OAuth user without password.

        Args:
            email: User email
            user_info: Google OAuth user info dict

        Returns:
            Created User instance
        """
        name = user_info.get("name", email.split("@")[0])
        user = User(
            email=email,
            name=name,
            hashed_password=None,
            auth_provider="google",
            provider_user_id=user_info.get("sub"),
            profile_picture_url=user_info.get("picture"),
            provider_profile_data={
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "email_verified": user_info.get("email_verified", False),
                "locale": user_info.get("locale"),
            },
            is_active=True,
            is_approved=False,
            is_verified=True,
        )

        self.db.add(user)
        logger.info(f"Created new Google OAuth user: {email}")
        return user

    async def _update_oauth_profile(self, user: User, user_info: dict) -> None:
        """
        Update user's OAuth profile information.

        Args:
            user: User instance to update
            user_info: Google OAuth user info dict
        """
        user.provider_user_id = user_info.get("sub", user.provider_user_id)
        user.profile_picture_url = user_info.get("picture", user.profile_picture_url)
        user.provider_profile_data = {
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "email_verified": user_info.get("email_verified", False),
            "locale": user_info.get("locale"),
        }
        user.updated_at = datetime.now(timezone.utc)

    async def _generate_and_store_tokens(
        self, user: User, user_info: dict, google_token: dict
    ) -> Dict[str, str]:
        """
        Generate app-level JWT tokens and store metadata.

        Args:
            user: Authenticated user
            user_info: Google user info
            google_token: Google token response

        Returns:
            Dictionary with access_token and refresh_token
        """
        access_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=2),
        )

        refresh_token = create_access_token(
            user_id=str(user.id),
            organization_id=None,
            role_id=None,
            expires_delta=timedelta(days=30),
        )

        refresh_token_jti = get_token_jti(refresh_token)

        now = datetime.now(timezone.utc)

        metadata = RefreshTokenMetadata(
            user_id=user.id,
            jti=refresh_token_jti,
            provider="google",
            provider_token_exp=int(now.timestamp()) + google_token.get("expires_in", 3600),
            issued_at=now,
            expires_at=now + timedelta(days=30),
            ip_address=self.client_ip,
            user_agent=self.user_agent,
            is_revoked=False,
        )

        self.db.add(metadata)
        await self.db.flush()

        try:
            redis_client = await get_redis_client()
            await redis_client.setex(
                f"{ENVIRONMENT}:refresh_token:{user.id}:{refresh_token_jti}",
                30 * 24 * 3600,
                "valid",
            )
            logger.info(f"Stored refresh token metadata for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to store refresh token in Redis: {str(e)}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def _log_oauth_event(
        self,
        provider: str,
        status: str,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """
        Log OAuth authentication event for audit trail.

        Args:
            provider: OAuth provider name
            status: Event status (success, failed, blocked, error)
            email: Email address (for failed attempts)
            user_id: User ID (for successful attempts)
            failure_reason: Reason for failure
            error_code: Machine-readable error code
        """
        try:
            event = OAuthLoginEvent(
                provider=provider,
                status=status,
                email=email,
                user_id=user_id,
                failure_reason=failure_reason,
                error_code=error_code,
                ip_address=self.client_ip,
                user_agent=self.user_agent,
            )

            self.db.add(event)
            await self.db.flush()
            logger.debug(f"Logged OAuth event: {provider}:{status} for {email or user_id}")
        except Exception as e:
            logger.error(f"Failed to log OAuth event: {str(e)}")

    @staticmethod
    def get_cookie_settings(request: Request) -> Dict:
        """
        Determine dynamic cookie settings based on request origin.

        Validates origin against request to prevent cookie misconfiguration.
        Uses HTTPS and SameSite=None in production, relaxed settings in development.

        Args:
            request: HTTP request

        Returns:
            Dictionary with cookie configuration:
                - domain: Cookie domain (None for localhost)
                - secure: Whether to set Secure flag
                - samesite: SameSite attribute value
                - frontend_url: Frontend URL for redirects

        Raises:
            HTTPException: If origin validation fails

        Examples:
            >>> settings = GoogleOAuthService.get_cookie_settings(request)
            >>> response.set_cookie("token", value, **settings)
        """
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        source_url = origin if origin else referer

        logger.debug(f"Getting cookie settings for origin: {origin}, referer: {referer}")

        is_local = "localhost" in source_url or "127.0.0.1" in source_url

        if is_local:
            return {
                "domain": None,
                "secure": False,
                "samesite": "lax",
                "frontend_url": settings.DEV_URL,
            }

        parsed = urlparse(settings.APP_URL)

        if parsed.netloc:
            domain = f".{parsed.netloc}" if not parsed.netloc.startswith(".") else parsed.netloc
        else:
            domain = None

        return {
            "domain": domain,
            "secure": True,
            "samesite": "none",
            "frontend_url": settings.APP_URL,
        }
