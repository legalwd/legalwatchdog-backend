import base64
import logging
import os
from datetime import timedelta
from typing import Optional, Tuple

import msal
from fastapi import BackgroundTasks
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AuthenticationError,
    MissingIDTokenError,
    OAuthTokenExchangeError,
    ProcessingError,
)
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.auth.schemas.oauth_microsoft import MicrosoftUserInfo
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import create_access_token
from app.api.utils.password import hash_password

logger = logging.getLogger(__name__)

MICROSOFT_SCOPES: list[str] = settings.MICROSOFT_SCOPES
MICROSOFT_OAUTH_STATE_TTL: int = settings.MICROSOFT_OAUTH_STATE_TTL
ENVIRONMENT = settings.ENVIRONMENT.lower()


class MicrosoftOAuthService:
    """Service for handling Microsoft OAuth authentication using MSAL."""

    def __init__(self, db: AsyncSession, redis_client: Redis):
        self.db = db
        self.redis_client = redis_client

        self.msal_app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        )

    async def generate_authorization_url(
        self, redirect_uri: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate Microsoft OAuth authorization URL.

        Args:
            redirect_uri: Optional custom redirect URI

        Returns:
            Tuple of (authorization_url, state)

        Raises:
            ProcessingError: If URL generation fails
        """
        try:
            state = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("utf-8")

            await self.redis_client.setex(
                f"{ENVIRONMENT}:microsoft_oauth_state:{state}", MICROSOFT_OAUTH_STATE_TTL, "pending"
            )

            redirect = redirect_uri or settings.MICROSOFT_REDIRECT_URI

            from urllib.parse import urlencode

            params = {
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "response_type": "code",
                "redirect_uri": redirect,
                "response_mode": "query",
                "scope": " ".join(MICROSOFT_SCOPES),
                "state": state,
                "prompt": "select_account",
            }

            base_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
            auth_url = f"{base_url}?{urlencode(params)}"

            logger.info("Generated Microsoft auth URL")
            return auth_url, state

        except Exception as e:
            logger.exception(f"Failed to generate Microsoft OAuth URL: {str(e)}")
            raise ProcessingError(message="Failed to initiate Microsoft login. Please try again.")

    async def validate_state(self, state: str) -> bool:
        """
        Validate OAuth state parameter against Redis storage.

        Args:
            state: State parameter to validate

        Returns:
            True if state is valid, False otherwise
        """
        try:
            redis_state = await self.redis_client.get(
                f"{ENVIRONMENT}:microsoft_oauth_state:{state}"
            )
            if redis_state:
                return True
            logger.warning(f"Invalid or expired OAuth state: {state}")
            return False
        except Exception as e:
            logger.error(f"Error validating OAuth state: {str(e)}")
            return False

    async def exchange_code_for_token(
        self, code: str, state: str, redirect_uri: Optional[str] = None
    ) -> dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from Microsoft
            state: State parameter for validation
            redirect_uri: Optional redirect URI

        Returns:
            Token response dictionary

        Raises:
            OAuthTokenExchangeError: If token exchange fails
            ProcessingError: If unexpected error occurs
        """
        try:
            redirect = redirect_uri or settings.MICROSOFT_REDIRECT_URI

            result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=MICROSOFT_SCOPES,
                redirect_uri=redirect,
            )

            await self.redis_client.delete(f"{ENVIRONMENT}:microsoft_oauth_state:{state}")

            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Microsoft token exchange failed: {error_msg}")
                raise OAuthTokenExchangeError(
                    message=(
                        "We couldn't connect to your Microsoft account. "
                        "Please try signing in again or contact support if the problem persists."
                    )
                )

            logger.info("Successfully exchanged authorization code for tokens")
            return result

        except OAuthTokenExchangeError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error exchanging code for token: {str(e)}")
            raise ProcessingError(
                message="Failed to complete Microsoft authentication. Please try again."
            )

    async def get_user_info(self, access_token: str) -> MicrosoftUserInfo:
        """
        Fetch user information from Microsoft Graph API.

        Args:
            access_token: Microsoft access token

        Returns:
            MicrosoftUserInfo object

        Raises:
            ProcessingError: If user info fetch fails
        """
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Failed to fetch user info. Status: {response.status_code}, "
                        f"Body: {response.text}"
                    )
                    raise ProcessingError(message="Failed to fetch user information from Microsoft")

                user_data = response.json()

                return MicrosoftUserInfo(
                    id=user_data.get("id"),
                    email=user_data.get("mail") or user_data.get("userPrincipalName"),
                    display_name=user_data.get("displayName"),
                    given_name=user_data.get("givenName"),
                    surname=user_data.get("surname"),
                    user_principal_name=user_data.get("userPrincipalName"),
                )

        except ProcessingError:
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching user info: {str(e)}", exc_info=True)
            raise ProcessingError(message="Failed to communicate with Microsoft Graph API")
        except Exception as e:
            logger.exception(f"Error fetching user info: {str(e)}")
            raise ProcessingError(message="Failed to retrieve user information. Please try again.")

    async def get_or_create_user(self, microsoft_user_info: MicrosoftUserInfo) -> Tuple[User, bool]:
        """
        Get existing user or create new one from Microsoft user info.
        Only creates the User - no organization or other models.

        Args:
            microsoft_user_info: User information from Microsoft

        Returns:
            Tuple of (User, is_new_user)

        Raises:
            ProcessingError: If user creation/update fails
        """
        try:
            existing_user = await self.db.scalar(
                select(User).where(User.email == microsoft_user_info.email)
            )

            if existing_user:
                if existing_user.auth_provider == "local":
                    existing_user.auth_provider = "microsoft"
                    existing_user.is_verified = True
                    await self.db.commit()
                    await self.db.refresh(existing_user)

                logger.info(f"Existing user logged in via Microsoft: {microsoft_user_info.email}")
                return existing_user, False

            logger.info(f"Creating new user from Microsoft OAuth: {microsoft_user_info.email}")

            random_password = hash_password(base64.urlsafe_b64encode(os.urandom(32)).decode())

            user_name = microsoft_user_info.display_name or microsoft_user_info.email

            new_user = User(
                email=microsoft_user_info.email,
                name=user_name,
                hashed_password=random_password,
                auth_provider="microsoft",
                is_active=True,
                is_approved=False,
                is_verified=True,
            )

            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)

            logger.info(
                f"Created new user via Microsoft OAuth: user_id={new_user.id}, "
                f"email={new_user.email}"
            )

            return new_user, True

        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating/updating user: {str(e)}")
            raise ProcessingError(
                message="Failed to create or update user account. Please try again."
            )

    def handle_microsoft_oauth_error(
        self, error: Optional[str], error_description: Optional[str]
    ) -> str:
        """
        Handle Microsoft OAuth provider errors and return error redirect URL.

        Args:
            error: Error code from Microsoft
            error_description: Error description from Microsoft

        Returns:
            Frontend redirect URL with error parameter
        """
        logger.warning(f"Microsoft OAuth error: {error} - {error_description or 'No description'}")

        frontend_redirect_url = settings.MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL
        return f"{frontend_redirect_url}?error={error}"

    async def complete_oauth_flow(
        self,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
        background_tasks: BackgroundTasks = None,
    ) -> dict:
        """
        Complete the OAuth flow: validate state, exchange code, get user info, create/update user.

        Args:
            code: Authorization code from Microsoft
            state: State parameter for validation
            redirect_uri: Optional redirect URI

        Returns:
            Dictionary with access token, refresh token, redirect URL, and user info

        Raises:
            AuthenticationError: If state validation fails
            OAuthTokenExchangeError: If token exchange fails
            MissingIDTokenError: If access token is missing from response
            ProcessingError: If any other step of the OAuth flow fails
        """
        try:
            if not await self.validate_state(state):
                logger.warning(f"Invalid OAuth state received: {state}")
                raise AuthenticationError(
                    message="Invalid or expired authentication session. Please try again."
                )

            token_response = await self.exchange_code_for_token(code, state, redirect_uri)
            ms_access_token = token_response.get("access_token")

            if not ms_access_token:
                logger.error("No access token in Microsoft response")
                raise MissingIDTokenError(provider="Microsoft")

            user_info = await self.get_user_info(ms_access_token)

            user, is_new_user = await self.get_or_create_user(user_info)

            # Send pending approval email for new users
            if is_new_user and background_tasks:
                background_tasks.add_task(
                    send_email,
                    "account_pending_approval.html",
                    "Your Account is Pending Approval",
                    user.email,
                    {"full_name": user.name},
                )
                logger.info(
                    f"Queued pending approval email for new Microsoft OAuth user_id={user.id}"
                )

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

            # Determine redirect URL based on user status
            if is_new_user:
                redirect_url = settings.MICROSOFT_OAUTH_REDIRECT_NEW_USER_URL
            else:
                redirect_url = settings.MICROSOFT_OAUTH_REDIRECT_EXISTING_USER_URL

            logger.info(
                f"Successful Microsoft OAuth login: {user.email}, is_new_user: {is_new_user}"
            )

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 172800,
                "user_id": str(user.id),
                "email": user.email,
                "is_new_user": is_new_user,
                "redirect_url": redirect_url,
            }

        except (AuthenticationError, OAuthTokenExchangeError, MissingIDTokenError):
            await self.db.rollback()
            raise
        except ProcessingError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error completing OAuth flow: {str(e)}")
            raise ProcessingError(
                message="Failed to complete Microsoft authentication. Please try again."
            )
