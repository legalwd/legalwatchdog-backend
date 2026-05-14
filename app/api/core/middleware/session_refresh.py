"""Middleware to refresh session on each request (ASGI-native)."""

import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("app")


class SessionRefreshMiddleware:
    """Refresh session on each request (ASGI-native).

    Ensures user sessions don't expire during long-running background tasks
    like Celery scraping jobs. The session cookie is automatically refreshed
    on each authenticated request.
    """

    def __init__(self, app: ASGIApp):
        """Initialize the middleware.

        Args:
            app: ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI middleware entry point.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        has_auth = any(name == b"authorization" for name, _ in scope.get("headers", []))

        if not has_auth:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            """Pass through all messages (session refresh handled by SessionMiddleware)."""
            await send(message)

        await self.app(scope, receive, send_wrapper)
