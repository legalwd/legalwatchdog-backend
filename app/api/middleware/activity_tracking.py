"""Activity tracking middleware for user last_active updates."""

import logging
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import update
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.db.database import get_db_context
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger(__name__)


class ActivityTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track user activity timestamps.

    Updates User.last_active field every 5 minutes to avoid excessive database writes.
    Skips updates for non-authenticated requests and static assets.
    """

    ACTIVITY_UPDATE_INTERVAL = 300  # 5 minutes in seconds

    def __init__(self, app):
        """
        Initialize activity tracking middleware.

        Args:
            app: FastAPI application instance
        """
        super().__init__(app)
        self._last_updates = {}  # user_id -> timestamp cache

    async def dispatch(self, request: Request, call_next):
        """
        Process request and update user activity if needed.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response

        Examples:
            >>> # Automatically called by FastAPI for each request
        """
        # Process the request
        response = await call_next(request)

        # Skip activity tracking for certain paths
        if self._should_skip_tracking(request):
            return response

        # Extract user ID from request state (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return response

        # Check if we should update (throttle to every 5 minutes)
        if not self._should_update_activity(user_id):
            return response

        # Update user activity asynchronously (don't block response)
        try:
            await self._update_user_activity(user_id)
        except Exception as e:
            # Log error but don't fail the request
            logger.error(f"Failed to update activity for user {user_id}: {e}", exc_info=True)

        return response

    def _should_skip_tracking(self, request: Request) -> bool:
        """
        Determine if activity tracking should be skipped for this request.

        Args:
            request: HTTP request

        Returns:
            True if tracking should be skipped

        Examples:
            >>> middleware._should_skip_tracking(request)
            False
        """
        path = request.url.path

        # Skip static assets and health checks
        skip_prefixes = (
            "/static/",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
        )

        return any(path.startswith(prefix) for prefix in skip_prefixes)

    def _should_update_activity(self, user_id: str) -> bool:
        """
        Check if enough time has passed since last update.

        Args:
            user_id: User ID to check

        Returns:
            True if activity should be updated

        Examples:
            >>> middleware._should_update_activity("user-id-123")
            True
        """
        now = datetime.now(timezone.utc)
        last_update = self._last_updates.get(user_id)

        if last_update is None:
            # First time seeing this user
            self._last_updates[user_id] = now
            return True

        # Check if interval has elapsed
        elapsed = (now - last_update).total_seconds()
        if elapsed >= self.ACTIVITY_UPDATE_INTERVAL:
            self._last_updates[user_id] = now
            return True

        return False

    async def _update_user_activity(self, user_id: str):
        """
        Update user's last_active timestamp in database.

        Args:
            user_id: User ID to update

        Examples:
            >>> await middleware._update_user_activity("user-id-123")
        """
        try:
            async with get_db_context() as db:
                now = datetime.now(timezone.utc)

                # Update only last_active field
                stmt = update(User).where(User.id == user_id).values(last_active=now)

                await db.execute(stmt)
                await db.commit()

                logger.debug(f"Updated last_active for user {user_id}")

        except Exception as e:
            logger.error(f"Error updating user activity: {e}", exc_info=True)
            raise
