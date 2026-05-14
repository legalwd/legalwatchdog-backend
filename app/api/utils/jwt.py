import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.api.core.config import settings
from app.api.core.logger import setup_logging

setup_logging()
logger = logging.getLogger("app")


try:
    import jwt as pyjwt  # type: ignore
except Exception:  # pragma: no cover - extremely unlikely
    pyjwt = None  # type: ignore

if pyjwt is not None and not hasattr(pyjwt, "encode"):
    try:
        # python-jwt: JWT class and JWK helpers
        from jwt import JWT as _JWTClass  # type: ignore
        from jwt.jwk import OctetJWK as _OctetJWK  # type: ignore

        _jwt_client = _JWTClass()

        def _module_encode(payload, key, algorithm=None):
            secret_bytes = key.encode() if isinstance(key, str) else key
            jwk = _OctetJWK(secret_bytes)

            return _jwt_client.encode(payload, jwk, alg=algorithm)

        def _module_decode(token, key=None, algorithms=None, **kwargs):
            # Support PyJWT-style `options={"verify_signature": False}`
            options = kwargs.get("options") or {}
            verify_signature = options.get("verify_signature", True)

            secret_bytes = key.encode() if isinstance(key, str) else key
            jwk = _OctetJWK(secret_bytes) if key is not None else None
            algs_set = set(algorithms) if algorithms is not None else None

            if not verify_signature:
                return _jwt_client.decode(token, None, do_verify=False, algorithms=None)

            # do_verify True path
            return _jwt_client.decode(token, jwk, do_verify=True, algorithms=algs_set)

        def _module_decode_no_verify(token, **kwargs):
            # decode without verifying signature (used to extract jti/exp)
            return _jwt_client.decode(token, None, do_verify=False, algorithms=None)

        # Attach adapter functions to the module object so callers using the
        # PyJWT-style API (module.encode/module.decode) continue to work.
        setattr(pyjwt, "encode", _module_encode)
        setattr(pyjwt, "decode", _module_decode)
        setattr(pyjwt, "_decode_no_verify", _module_decode_no_verify)
    except Exception:
        # If adaptation fails, leave pyjwt as-is and let callers handle errors.
        pass

if pyjwt is None:  # pragma: no cover - environment misconfiguration
    raise RuntimeError(
        "No 'jwt' package is importable.Install 'PyJWT' or 'python-jwt' in the virtualenv."
    )


def create_access_token(
    user_id: str,
    role_id: str,
    organization_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token with user and organization context.

    Args:
        user_id: UUID of the user
        organization_id: UUID of the organization
        role_id: UUID of the user's role
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRY_HOURS)

    jti = str(uuid.uuid4())

    iat = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "role_id": str(role_id),
        "exp": int(expire.timestamp()),
        "iat": int(iat.timestamp()),
        "jti": jti,
    }
    if organization_id:
        payload["organization_id"] = organization_id

    encoded_jwt = pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    logger.info(f"Created JWT for user {user_id}, org {organization_id}, jti: {jti}")
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        InvalidTokenError: If token is invalid
        TokenExpiredError: If token has expired
    """
    from app.api.core.custom_exceptions.exceptions import (
        InvalidTokenError,
        TokenExpiredError,
    )

    try:
        payload = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except pyjwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise TokenExpiredError()
    except Exception as e:
        logger.warning(f"Invalid or expired JWT token: {str(e)}")
        raise InvalidTokenError()


def get_token_jti(token: str) -> Optional[str]:
    """
    Extract the JWT ID (jti) from a token without full validation.
    Used for adding tokens to the denylist during logout.

    Args:
        token: JWT token string

    Returns:
        JWT ID (jti) or None if extraction fails
    """
    try:
        # Decode without verification to get jti even for expired tokens
        unverified_payload = pyjwt.decode(token, options={"verify_signature": False})
        return unverified_payload.get("jti")
    except Exception as e:
        logger.error(f"Failed to extract jti from token: {str(e)}")
        return None


def calculate_token_ttl(token: str) -> int:
    """
    Calculate remaining time-to-live for a token in seconds.
    Used to set Redis TTL when denylisting tokens.

    Args:
        token: JWT token string

    Returns:
        TTL in seconds, or default if calculation fails
    """
    try:
        unverified_payload = pyjwt.decode(token, options={"verify_signature": False})
        exp = unverified_payload.get("exp")
        if exp:
            ttl = exp - datetime.now(timezone.utc).timestamp()
            return max(int(ttl), 0)
        return settings.JWT_EXPIRY_HOURS * 3600
    except Exception:
        return settings.JWT_EXPIRY_HOURS * 3600
