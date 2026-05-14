"""Middleware to track user activity (last_active timestamp)."""

import logging
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.db.database import get_db

logger = logging.getLogger(__name__)


class ActivityTrackerMiddleware(BaseHTTPMiddleware):
    """Middleware to update user last_active timestamp on authenticated requests.

    Updates last_active every 5 minutes to reduce database writes while maintaining
    reasonable activity tracking accuracy.

    Examples:
        >>> app.add_middleware(ActivityTrackerMiddleware)
    """

    ACTIVITY_UPDATE_INTERVAL = 300

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and update user activity if authenticated.

        Args:
            request (Request): Incoming HTTP request.
            call_next (RequestResponseEndpoint): Next middleware/endpoint.

        Returns:
            Response: HTTP response from downstream handler.
        """

        response = await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return response

        token = auth_header.replace("Bearer ", "")

        try:
            user = await get_current_user_from_token(token)

            if user and user.is_active:
                now = datetime.now(timezone.utc)
                should_update = False

                if user.last_active is None:
                    should_update = True
                else:
                    last_active = user.last_active
                    if last_active.tzinfo is None:
                        last_active = last_active.replace(tzinfo=timezone.utc)

                    seconds_since_last_update = (now - last_active).total_seconds()
                    should_update = seconds_since_last_update >= self.ACTIVITY_UPDATE_INTERVAL

                if should_update:
                    async for db in get_db():
                        try:
                            from sqlalchemy import update

                            from app.api.modules.v1.users.models.users_model import (
                                User,
                            )

                            stmt = update(User).where(User.id == user.id).values(last_active=now)
                            await db.execute(stmt)
                            await db.commit()

                            logger.debug(f"Updated last_active for user {user.id} at {now}")
                        except Exception as e:
                            logger.error(f"Failed to update last_active for user {user.id}: {e}")
                            await db.rollback()
                        finally:
                            break

        except Exception as e:
            logger.warning(f"Activity tracking failed: {e}")

        return response


async def get_current_user_from_token(token: str):
    """Extract user from JWT token without full dependency injection.

    Args:
        token (str): JWT access token.

    Returns:
        User: User object if token valid, None otherwise.

    Raises:
        Exception: If token decoding fails.
    """
    from jose import JWTError, jwt

    from app.api.core.config import settings
    from app.api.modules.v1.users.models.users_model import User

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        async for db in get_db():
            try:
                from sqlalchemy import select

                stmt = select(User).where(User.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                return user
            finally:
                break

    except JWTError:
        return None
