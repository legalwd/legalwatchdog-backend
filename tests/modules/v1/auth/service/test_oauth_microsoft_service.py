from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPError, Response

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    AuthenticationError,
    MissingIDTokenError,
    OAuthTokenExchangeError,
    ProcessingError,
)
from app.api.modules.v1.auth.schemas.oauth_microsoft import MicrosoftUserInfo
from app.api.modules.v1.auth.service.oauth_microsoft import MicrosoftOAuthService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.password import hash_password

ENVIRONMENT = settings.ENVIRONMENT.lower()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    redis_mock = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_msal_app():
    """Create a mock MSAL application"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ) as mock:
        msal_instance = MagicMock()
        mock.return_value = msal_instance
        yield msal_instance


@pytest.fixture
def microsoft_service(pg_async_session, mock_redis, mock_msal_app):
    """Create MicrosoftOAuthService instance with mocked dependencies"""
    service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
    service.msal_app = mock_msal_app
    return service


@pytest.mark.asyncio
async def test_generate_authorization_url(microsoft_service, mock_redis):
    """Test generating Microsoft OAuth authorization URL"""
    auth_url, state = await microsoft_service.generate_authorization_url()

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == f"{ENVIRONMENT}:microsoft_oauth_state:{state}"
    assert call_args[0][1] == settings.MICROSOFT_OAUTH_STATE_TTL
    assert call_args[0][2] == "pending"

    assert "https://login.microsoftonline.com/" in auth_url
    assert "oauth2/v2.0/authorize" in auth_url
    assert f"state={state}" in auth_url
    assert "response_type=code" in auth_url
    assert "prompt=select_account" in auth_url


@pytest.mark.asyncio
async def test_generate_authorization_url_handles_error(pg_async_session, mock_redis):
    """Test that errors during URL generation raise ProcessingError"""
    mock_redis.setex.side_effect = Exception("Redis error")

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        with pytest.raises(ProcessingError) as exc_info:
            await service.generate_authorization_url()

        assert "failed to initiate" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_validate_state_success(microsoft_service, mock_redis):
    """Test successful OAuth state validation"""
    test_state = "valid_state_123"
    mock_redis.get.return_value = "pending"

    result = await microsoft_service.validate_state(test_state)

    assert result is True
    mock_redis.get.assert_called_once_with(f"{ENVIRONMENT}:microsoft_oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_validate_state_failure(microsoft_service, mock_redis):
    """Test failed OAuth state validation"""
    test_state = "invalid_state_456"
    mock_redis.get.return_value = None

    result = await microsoft_service.validate_state(test_state)

    assert result is False
    mock_redis.get.assert_called_once_with(f"{ENVIRONMENT}:microsoft_oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_validate_state_handles_exception(microsoft_service, mock_redis):
    """Test that exceptions during state validation return False"""
    test_state = "error_state"
    mock_redis.get.side_effect = Exception("Redis error")

    result = await microsoft_service.validate_state(test_state)

    assert result is False


@pytest.mark.asyncio
async def test_exchange_code_for_token_success(microsoft_service, mock_redis, mock_msal_app):
    """Test successful token exchange"""
    test_code = "auth_code_123"
    test_state = "state_456"
    mock_token_response = {
        "access_token": "ms_access_token_xyz",
        "refresh_token": "ms_refresh_token_abc",
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    mock_msal_app.acquire_token_by_authorization_code.return_value = mock_token_response

    result = await microsoft_service.exchange_code_for_token(test_code, test_state)

    assert result == mock_token_response
    assert "access_token" in result
    mock_redis.delete.assert_called_once_with(f"{ENVIRONMENT}:microsoft_oauth_state:{test_state}")
    mock_msal_app.acquire_token_by_authorization_code.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_for_token_error(microsoft_service, mock_redis, mock_msal_app):
    """Test token exchange with error response raises OAuthTokenExchangeError"""
    test_code = "invalid_code"
    test_state = "state_789"
    mock_error_response = {
        "error": "invalid_grant",
        "error_description": "The authorization code is invalid or expired",
    }

    mock_msal_app.acquire_token_by_authorization_code.return_value = mock_error_response

    with pytest.raises(OAuthTokenExchangeError) as exc_info:
        await microsoft_service.exchange_code_for_token(test_code, test_state)

    assert "couldn't connect" in str(exc_info.value).lower()
    mock_redis.delete.assert_called_once_with(f"{ENVIRONMENT}:microsoft_oauth_state:{test_state}")


@pytest.mark.asyncio
async def test_exchange_code_for_token_unexpected_error(
    microsoft_service, mock_redis, mock_msal_app
):
    """Test that unexpected errors during token exchange raise ProcessingError"""
    test_code = "error_code"
    test_state = "error_state"

    mock_msal_app.acquire_token_by_authorization_code.side_effect = Exception("Unexpected error")

    with pytest.raises(ProcessingError) as exc_info:
        await microsoft_service.exchange_code_for_token(test_code, test_state)

    assert "failed to complete" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_user_info_uses_user_principal_name_fallback(microsoft_service):
    """Test user info falls back to userPrincipalName when mail is not available"""
    test_access_token = "ms_access_token_xyz"
    mock_user_data = {
        "id": "ms_user_456",
        "userPrincipalName": "user@tenant.onmicrosoft.com",
        "displayName": "Fallback User",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        user_info = await microsoft_service.get_user_info(test_access_token)

    assert user_info.email == "user@tenant.onmicrosoft.com"


@pytest.mark.asyncio
async def test_get_user_info_api_error(microsoft_service):
    """Test handling of Microsoft Graph API errors raises ProcessingError"""
    test_access_token = "invalid_token"

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        with pytest.raises(ProcessingError) as exc_info:
            await microsoft_service.get_user_info(test_access_token)

    assert "failed to fetch user information" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_user_info_http_error(microsoft_service):
    """Test handling of HTTP errors when fetching user info raises ProcessingError"""
    test_access_token = "ms_access_token_xyz"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=HTTPError("Connection failed")
        )

        with pytest.raises(ProcessingError) as exc_info:
            await microsoft_service.get_user_info(test_access_token)

    assert "failed to communicate with microsoft" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_or_create_user_existing_user(pg_async_session, mock_redis):
    """Test retrieving an existing user"""
    session = pg_async_session

    existing_user = User(
        email="existing@example.com",
        hashed_password=hash_password("password123"),
        name="Existing User",
        is_verified=True,
        is_active=True,
        auth_provider="microsoft",
    )
    session.add(existing_user)
    await session.commit()

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_123",
            email="existing@example.com",
            display_name="Existing User",
            given_name="Existing",
            surname="User",
            user_principal_name="existing@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is False
    assert user.email == "existing@example.com"
    assert user.auth_provider == "microsoft"


@pytest.mark.asyncio
async def test_get_or_create_user_converts_local_to_microsoft(pg_async_session, mock_redis):
    """Test converting a local auth user to Microsoft auth"""
    session = pg_async_session

    local_user = User(
        email="local@example.com",
        hashed_password=hash_password("password123"),
        name="Local User",
        is_verified=False,
        is_active=True,
        auth_provider="local",
    )
    session.add(local_user)
    await session.commit()

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_456",
            email="local@example.com",
            display_name="Local User",
            given_name="Local",
            surname="User",
            user_principal_name="local@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is False
    assert user.email == "local@example.com"
    assert user.auth_provider == "microsoft"
    assert user.is_verified is True


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new_user(pg_async_session, mock_redis):
    """Test creating a new user from Microsoft OAuth"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_789",
            email="newuser@example.com",
            display_name="New User",
            given_name="New",
            surname="User",
            user_principal_name="newuser@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is True
    assert user.email == "newuser@example.com"
    assert user.name in ["New User", "newuser@example.com"]
    assert user.auth_provider == "microsoft"
    assert user.is_verified is True
    assert user.is_active is True
    assert user.is_approved is False
    assert user.hashed_password is not None


@pytest.mark.asyncio
async def test_get_or_create_user_uses_email_as_name_fallback(pg_async_session, mock_redis):
    """Test using email as name when display_name is not available"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_999",
            email="noname@example.com",
            display_name=None,
            given_name=None,
            surname=None,
            user_principal_name="noname@example.com",
        )

        user, is_new_user = await service.get_or_create_user(microsoft_user_info)

    assert is_new_user is True
    assert user.name == "noname@example.com"


@pytest.mark.asyncio
async def test_get_or_create_user_handles_error(pg_async_session, mock_redis):
    """Test that database errors raise ProcessingError"""
    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)

        # 🔧 CHANGE: mock scalar instead of execute
        pg_async_session.scalar = AsyncMock(side_effect=Exception("Database error"))
        pg_async_session.rollback = AsyncMock()

        microsoft_user_info = MicrosoftUserInfo(
            id="ms_error",
            email="error@example.com",
            display_name="Error User",
            user_principal_name="error@example.com",
        )

        with pytest.raises(ProcessingError) as exc_info:
            await service.get_or_create_user(microsoft_user_info)

        assert "failed to create or update" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_oauth_flow_success(pg_async_session, mock_redis, mock_msal_app):
    """Test complete OAuth flow with new user"""
    test_code = "auth_code_abc"
    test_state = "state_xyz"

    mock_redis.get.return_value = "pending"

    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "ms_access_token_123",
        "refresh_token": "ms_refresh_token_456",
    }

    mock_user_data = {
        "id": "ms_user_complete",
        "mail": "complete@example.com",
        "displayName": "Complete User",
        "givenName": "Complete",
        "surname": "User",
        "userPrincipalName": "complete@example.com",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await service.complete_oauth_flow(test_code, test_state)

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["email"] == "complete@example.com"
    assert result["is_new_user"] is True
    assert "user_id" in result


@pytest.mark.asyncio
async def test_complete_oauth_flow_invalid_state(microsoft_service, mock_redis):
    """Test complete OAuth flow fails with invalid state - raises AuthenticationError"""
    mock_redis.get.return_value = None

    with pytest.raises(AuthenticationError) as exc_info:
        await microsoft_service.complete_oauth_flow("code", "invalid_state")

    assert "invalid or expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_oauth_flow_no_access_token(pg_async_session, mock_redis, mock_msal_app):
    """Test complete OAuth flow fails when no access token - raises MissingIDTokenError"""
    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "refresh_token": "ms_refresh_token_only",
    }

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with pytest.raises(MissingIDTokenError) as exc_info:
            await service.complete_oauth_flow("code", "state")

    assert "didn't receive complete authentication" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_oauth_flow_existing_user(pg_async_session, mock_redis, mock_msal_app):
    """Test complete OAuth flow with existing user"""
    session = pg_async_session

    existing_user = User(
        email="existing.flow@example.com",
        hashed_password=hash_password("password123"),
        name="Existing Flow User",
        is_verified=True,
        is_active=True,
        auth_provider="microsoft",
    )
    session.add(existing_user)
    await session.commit()

    test_code = "auth_code_existing"
    test_state = "state_existing"

    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "ms_access_token_existing",
    }

    mock_user_data = {
        "id": "ms_user_existing",
        "mail": "existing.flow@example.com",
        "displayName": "Existing Flow User",
        "userPrincipalName": "existing.flow@example.com",
    }

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_user_data

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await service.complete_oauth_flow(test_code, test_state)

    assert result["email"] == "existing.flow@example.com"
    assert result["is_new_user"] is False


@pytest.mark.asyncio
async def test_complete_oauth_flow_propagates_oauth_errors(
    pg_async_session, mock_redis, mock_msal_app
):
    """Test that OAuth-specific errors are propagated correctly"""
    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "error": "invalid_grant",
        "error_description": "Token exchange failed",
    }

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with pytest.raises(OAuthTokenExchangeError):
            await service.complete_oauth_flow("code", "state")


@pytest.mark.asyncio
async def test_complete_oauth_flow_handles_processing_error(
    pg_async_session, mock_redis, mock_msal_app
):
    """Test that ProcessingError during user info fetch is propagated"""
    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.return_value = {
        "access_token": "ms_access_token",
    }

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=HTTPError("Network error")
            )

            with pytest.raises(ProcessingError):
                await service.complete_oauth_flow("code", "state")


@pytest.mark.asyncio
async def test_complete_oauth_flow_handles_unexpected_error(
    pg_async_session, mock_redis, mock_msal_app
):
    """Test that unexpected errors are wrapped in ProcessingError"""
    mock_redis.get.return_value = "pending"
    mock_msal_app.acquire_token_by_authorization_code.side_effect = Exception("Unexpected error")

    with patch(
        "app.api.modules.v1.auth.service.oauth_microsoft.msal.ConfidentialClientApplication"
    ):
        service = MicrosoftOAuthService(db=pg_async_session, redis_client=mock_redis)
        service.msal_app = mock_msal_app

        with pytest.raises(ProcessingError) as exc_info:
            await service.complete_oauth_flow("code", "state")

        assert "failed to complete" in str(exc_info.value).lower()
