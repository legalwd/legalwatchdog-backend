from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    MissingIDTokenError,
    OAuthTokenExchangeError,
    OAuthTokenVerificationError,
    ProcessingError,
)
from app.api.modules.v1.auth.service.apple_auth import AppleAuthClient
from app.api.modules.v1.users.models.users_model import User


def _set_apple_env(monkeypatch):
    monkeypatch.setattr(settings, "APPLE_TEAM_ID", "team-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "client-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_KEY_ID", "key-id", raising=False)
    monkeypatch.setattr(settings, "APPLE_PRIVATE_KEY", "-private-key-", raising=False)
    monkeypatch.setattr(settings, "APPLE_CLIENT_SECRET_LIFETIME", 3600, raising=False)


def test_generate_apple_client_secret(monkeypatch):
    _set_apple_env(monkeypatch)

    with patch("app.api.modules.v1.auth.service.apple_auth.jwt.encode") as mock_encode:
        mock_encode.return_value = "signed-token"
        client = AppleAuthClient(db=MagicMock())

        token = client.generate_apple_client_secret()

    assert isinstance(token, str)
    assert token == "signed-token"


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_success(monkeypatch):
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    with patch.object(client, "generate_apple_client_secret", return_value="secret"):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"id_token": "id.123", "access_token": "acc"}
        with patch(
            "app.api.modules.v1.auth.service.apple_auth.httpx.AsyncClient"
        ) as mock_async_client:
            mock_inst = mock_async_client.return_value
            mock_inst.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

            out = await client.exchange_code_for_tokens(
                "auth-code-1", redirect_uri="https://app/cb"
            )

    mock_async_client.assert_called_once()
    assert out["id_token"] == "id.123"


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_http_status_error(monkeypatch):
    """Test that HTTPStatusError raises OAuthTokenExchangeError"""
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    with patch.object(client, "generate_apple_client_secret", return_value="secret"):
        mock_resp = MagicMock()
        mock_resp.status_code = 400

        import httpx

        with patch(
            "app.api.modules.v1.auth.service.apple_auth.httpx.AsyncClient"
        ) as mock_async_client:
            mock_inst = mock_async_client.return_value
            mock_inst.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=MagicMock(), response=mock_resp
                )
            )

            with pytest.raises(OAuthTokenExchangeError) as exc_info:
                await client.exchange_code_for_tokens("auth-code-1", redirect_uri="https://app/cb")

            assert "invalid" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_exchange_code_for_tokens_request_error(monkeypatch):
    """Test that RequestError raises ProcessingError"""
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    with patch.object(client, "generate_apple_client_secret", return_value="secret"):
        import httpx

        with patch(
            "app.api.modules.v1.auth.service.apple_auth.httpx.AsyncClient"
        ) as mock_async_client:
            mock_inst = mock_async_client.return_value
            mock_inst.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RequestError("Network error")
            )

            with pytest.raises(ProcessingError) as exc_info:
                await client.exchange_code_for_tokens("auth-code-1", redirect_uri="https://app/cb")

            assert "connect" in str(exc_info.value).lower()


def test_verify_id_token_uses_jwks_and_decode(monkeypatch):
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    fake_signing_key = MagicMock()
    fake_signing_key.key = "public-key"

    async def _run():
        with patch("app.api.modules.v1.auth.service.apple_auth.PyJWKClient") as mock_jwks:
            inst = mock_jwks.return_value
            inst.get_signing_key_from_jwt.return_value = fake_signing_key

            with patch("app.api.modules.v1.auth.service.apple_auth.decode") as mock_decode:
                mock_decode.return_value = {"sub": "apple-1", "email": "a@b.com"}

                data = await client.verify_id_token("some-token")

        return data

    import asyncio

    data = asyncio.get_event_loop().run_until_complete(_run())

    assert data["sub"] == "apple-1"


@pytest.mark.asyncio
async def test_verify_id_token_expired_signature(monkeypatch):
    """Test that ExpiredSignatureError raises OAuthTokenVerificationError"""
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    fake_signing_key = MagicMock()
    fake_signing_key.key = "public-key"

    with patch("app.api.modules.v1.auth.service.apple_auth.PyJWKClient") as mock_jwks:
        inst = mock_jwks.return_value
        inst.get_signing_key_from_jwt.return_value = fake_signing_key

        with patch("app.api.modules.v1.auth.service.apple_auth.decode") as mock_decode:
            mock_decode.side_effect = jwt.ExpiredSignatureError("Token expired")

            with pytest.raises(OAuthTokenVerificationError) as exc_info:
                await client.verify_id_token("expired-token")

            assert "expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_verify_id_token_invalid_token(monkeypatch):
    """Test that InvalidTokenError raises OAuthTokenVerificationError"""
    _set_apple_env(monkeypatch)

    client = AppleAuthClient(db=MagicMock())

    fake_signing_key = MagicMock()
    fake_signing_key.key = "public-key"

    with patch("app.api.modules.v1.auth.service.apple_auth.PyJWKClient") as mock_jwks:
        inst = mock_jwks.return_value
        inst.get_signing_key_from_jwt.return_value = fake_signing_key

        with patch("app.api.modules.v1.auth.service.apple_auth.decode") as mock_decode:
            mock_decode.side_effect = jwt.InvalidTokenError("Invalid token")

            with pytest.raises(OAuthTokenVerificationError) as exc_info:
                await client.verify_id_token("invalid-token")

            assert "invalid" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_or_create_user_creates_and_returns_user(monkeypatch):
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = None
    result.scalars.return_value = scalars
    db.execute.return_value = result

    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    client = AppleAuthClient(db=db)

    user_info = {"sub": "apple-sub", "email": "new@apple.test", "name": "Apple Test"}

    user, is_new = await client.get_or_create_user(user_info)

    assert is_new is True
    assert isinstance(user, User)
    assert user.email == "new@apple.test"


@pytest.mark.asyncio
async def test_get_or_create_user_handles_error(monkeypatch):
    """Test that database errors raise ProcessingError"""
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    db.execute.side_effect = Exception("Database error")
    db.rollback = AsyncMock()

    client = AppleAuthClient(db=db)

    user_info = {"sub": "apple-sub", "email": "new@apple.test", "name": "Apple Test"}

    with pytest.raises(ProcessingError) as exc_info:
        await client.get_or_create_user(user_info)

    assert "failed to create" in str(exc_info.value).lower()
    db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_complete_oauth_flow_success(monkeypatch):
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    fake_user = MagicMock(id=123, email="ok@a.com")

    client = AppleAuthClient(db=db)

    with (
        patch.object(client, "exchange_code_for_tokens", return_value={"id_token": "id-1"}),
        patch.object(
            client,
            "verify_id_token",
            return_value={"sub": "apple-xyz", "email": "ok@a.com", "name": "Ok"},
        ),
        patch.object(client, "get_or_create_user", AsyncMock(return_value=(fake_user, True))),
        patch(
            "app.api.modules.v1.auth.service.apple_auth.create_access_token", return_value="app.jwt"
        ),
    ):
        result = await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")

    assert result["access_token"] == "app.jwt"
    assert result["email"] == "ok@a.com"
    assert result["is_new_user"] is True


@pytest.mark.asyncio
async def test_complete_oauth_flow_raises_when_no_id_token(monkeypatch):
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    client = AppleAuthClient(db=db)

    with patch.object(client, "exchange_code_for_tokens", return_value={}):
        with pytest.raises(MissingIDTokenError) as exc_info:
            await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")

        assert "didn't receive complete authentication" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_complete_oauth_flow_propagates_oauth_errors(monkeypatch):
    """Test that OAuth-specific errors are propagated correctly"""
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    client = AppleAuthClient(db=db)

    with patch.object(
        client,
        "exchange_code_for_tokens",
        side_effect=OAuthTokenExchangeError(message="Token exchange failed"),
    ):
        with pytest.raises(OAuthTokenExchangeError):
            await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")


@pytest.mark.asyncio
async def test_complete_oauth_flow_handles_unexpected_error(monkeypatch):
    """Test that unexpected errors are wrapped in ProcessingError"""
    _set_apple_env(monkeypatch)

    db = AsyncMock()
    client = AppleAuthClient(db=db)

    with patch.object(
        client, "exchange_code_for_tokens", side_effect=Exception("Unexpected error")
    ):
        with pytest.raises(ProcessingError) as exc_info:
            await client.complete_oauth_flow("code-123", redirect_uri="https://app/cb")

        assert "unable to complete" in str(exc_info.value).lower()
