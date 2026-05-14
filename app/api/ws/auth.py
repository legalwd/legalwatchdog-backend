"""Authentication helpers dedicated to websocket connections."""

from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.dependencies.redis_service import is_token_denylisted
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.jwt import decode_token
from app.api.ws.exceptions import WebSocketException


async def authenticate_websocket_user(token: str, db: AsyncSession) -> User:
    """Validate JWT tokens for websocket connections.

    Args:
        token (str): Raw bearer token supplied by the client.
        db (AsyncSession): Database session for user lookups.

    Returns:
        User: Authenticated user record.

    Raises:
        WebSocketException: If validation fails for any reason.

    Examples:
        >>> # inside websocket endpoint
        >>> user = await authenticate_websocket_user(token, db)
        >>> user.email
        'user@example.com'
    """

    try:
        payload = decode_token(token)
    except Exception as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)) from exc

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token payload",
        )

    if await is_token_denylisted(jti):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Token has been revoked",
        )

    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User not found",
        )
    if not user.is_active:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Inactive account",
        )
    if not user.is_verified:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Email not verified",
        )

    return user
