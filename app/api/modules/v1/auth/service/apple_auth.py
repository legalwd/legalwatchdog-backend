import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

import httpx
import jwt
from jwt import PyJWKClient, decode
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AuthenticationError,
    MissingIDTokenError,
    OAuthTokenExchangeError,
    OAuthTokenVerificationError,
    ProcessingError,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import create_access_token

logger = logging.getLogger("app")

APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


class AppleAuthClient:
    """Service for handling Apple Sign-In OAuth authentication.
    Handles Apple Sign-In OAuth authentication.

    Exchanges authorization codes for tokens, verifies ID tokens,
    creates or retrieves users, and issues app JWTs. Supports both
    real and mock flows for testing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.team_id = settings.APPLE_TEAM_ID
        self.client_id = settings.APPLE_CLIENT_ID
        self.key_id = settings.APPLE_KEY_ID
        self.private_key = settings.APPLE_PRIVATE_KEY
        self.algorithm = "ES256"
        self.client_secret_lifetime = settings.APPLE_CLIENT_SECRET_LIFETIME

        missing = [
            name
            for name, value in [
                ("APPLE_TEAM_ID", self.team_id),
                ("APPLE_CLIENT_ID", self.client_id),
                ("APPLE_KEY_ID", self.key_id),
                ("APPLE_PRIVATE_KEY", self.private_key),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing Apple config env vars: {', '.join(missing)}")

    def generate_apple_client_secret(self) -> str:
        """Generate Apple JWT client secret."""
        now = int(datetime.now(timezone.utc).timestamp())
        headers = {"kid": self.key_id, "alg": self.algorithm}
        payload = {
            "iss": self.team_id,
            "iat": now,
            "exp": now + self.client_secret_lifetime,
            "aud": "https://appleid.apple.com",
            "sub": self.client_id,
        }
        client_secret = jwt.encode(
            payload, self.private_key, algorithm=self.algorithm, headers=headers
        )
        if isinstance(client_secret, bytes):
            return client_secret.decode("utf-8")
        return client_secret

    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, str]:
        """
        Exchange authorization code for Apple tokens.

        Raises:
            ProcessingError: If token exchange fails
        """
        try:
            client_secret = self.generate_apple_client_secret()
            payload = {
                "client_id": self.client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(APPLE_TOKEN_URL, data=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Apple token exchange failed with status {e.response.status_code}: {e}")
            raise OAuthTokenExchangeError(
                message="The login information from Apple is invalid. Please try again."
            )
        except httpx.RequestError as e:
            logger.error(f"Network error during Apple token exchange: {e}")
            raise ProcessingError(
                message="Unable to connect to Apple. Please check your connection and try again."
            )
        except Exception as e:
            logger.exception(f"Unexpected error during token exchange: {e}")
            raise ProcessingError(
                message="We're unable to complete Apple sign-in at this time. "
                "Please try again later."
            )

    def mock_exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, str]:
        """MOCK FOR TESTING: return fake token instead of calling Apple."""
        logger.info(f"Mock exchange_code_for_tokens called with code={code}")
        return {
            "id_token": "mock_id_token",
            "access_token": "mock_access_token",
        }

    def mock_verify_id_token(self, id_token: str) -> Dict:
        """MOCK FOR TESTING: return fake user info instead of decoding real Apple ID token"""
        logger.info(f"Mock verify_id_token called with id_token={id_token}")
        return {"sub": "apple-user-123", "email": "testuser@apple.com", "name": "Test User"}

    async def verify_id_token(self, id_token: str) -> Dict:
        """
        Verify Apple ID token and extract user info.

        Raises:
            OAuthTokenVerificationError: If token has expired or is invalid
            ProcessingError: If token verification fails
        """
        try:
            jwks_client = PyJWKClient(APPLE_JWKS_URL)
            signing_key = await asyncio.to_thread(jwks_client.get_signing_key_from_jwt, id_token)
            data = await asyncio.to_thread(
                decode,
                id_token,
                signing_key.key,
                audience=self.client_id,
                algorithms=[self.algorithm],
            )
            return data
        except jwt.ExpiredSignatureError:
            logger.warning("Apple ID token has expired")
            raise OAuthTokenVerificationError(
                message="Your Apple login session has expired. Please try signing in again."
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid Apple ID token: {e}")
            raise OAuthTokenVerificationError(
                message="The login information from Apple is invalid. Please try again."
            )
        except Exception as e:
            logger.exception(f"Unexpected error during token verification: {e}")
            raise ProcessingError(
                message="We're unable to verify your Apple login. Please try again later."
            )

    async def get_or_create_user(self, user_info: Dict) -> Tuple[User, bool]:
        """
        Get existing user or create a new one.

        Raises:
            ProcessingError: If user creation/retrieval fails
        """
        try:
            provider_user_id = user_info["sub"]
            email = user_info.get("email") or f"{provider_user_id}@appleid.fake"
            name = user_info.get("name") or "Apple User"
            dummy_password = secrets.token_urlsafe(32)

            result = await self.db.execute(
                select(User).where(
                    (User.auth_provider == "apple")
                    & ((User.provider_user_id == provider_user_id) | (User.email == email))
                )
            )
            user = result.scalars().first()
            is_new_user = False

            if not user:
                user = User(
                    email=email,
                    name=name,
                    hashed_password=dummy_password,
                    provider_user_id=provider_user_id,
                    auth_provider="apple",
                    is_active=True,
                    is_verified=True,
                )
                self.db.add(user)
                await self.db.commit()
                await self.db.refresh(user)
                is_new_user = True
                logger.info(f"Created new Apple user: {email}")
            else:
                logger.info(f"Existing Apple user logged in: {email}")

            return user, is_new_user

        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating/retrieving Apple user: {e}")
            raise ProcessingError(message="Failed to create your account. Please try again.")

    async def complete_oauth_flow(self, code: str, redirect_uri: str | None) -> Dict:
        """
        Complete the Apple OAuth flow:
        - Exchange code for tokens
        - Verify ID token
        - Get or create user
        - Issue app JWT

        Raises:
            ProcessingError: If any step of the OAuth flow fails
        """
        try:
            # Exchange code for tokens
            tokens = await self.exchange_code_for_tokens(code, redirect_uri)
            id_token = tokens.get("id_token")

            if not id_token:
                logger.error("No id_token returned from Apple")
                raise MissingIDTokenError(provider="Apple")

            # Verify ID token and extract user info
            user_info = await self.verify_id_token(id_token)

            # Get or create user
            user, is_new_user = await self.get_or_create_user(user_info)

            # Create access token
            access_token = create_access_token(
                user_id=str(user.id),
                role_id=getattr(user, "role_id", None),
                organization_id=getattr(user, "organization_id", None),
                expires_delta=timedelta(days=2),
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user_id": str(user.id),
                "email": user.email,
                "is_new_user": is_new_user,
            }

        except (
            AuthenticationError,
            OAuthTokenExchangeError,
            OAuthTokenVerificationError,
            MissingIDTokenError,
        ):
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in Apple OAuth flow: {e}")
            raise ProcessingError(
                message="We're unable to complete Apple sign-in at this time. "
                "Please try again later or use email login."
            )
