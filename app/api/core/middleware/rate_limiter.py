import json
import logging
import time
import uuid

from redis.exceptions import RedisError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.core.dependencies.redis_service import get_redis_client
from app.api.core.security import detect_suspicious_activity, log_rate_limit_event

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Redis-based rate limiting middleware (ASGI-native).

    Uses Redis for distributed rate limiting. Properly handles response headers
    without triggering Content-Length mismatches.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 50,
        excluded_paths: list[str] | None = None,
    ):
        """Initialize the rate limit middleware.

        Args:
            app: ASGI application.
            requests_per_minute: Max requests per minute per client IP.
            excluded_paths: List of path prefixes to exclude from rate limiting.
        """
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.excluded_paths = excluded_paths or []

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from rate limiting."""
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True
        return False

    def _get_client_ip(self, headers_or_request) -> str:
        """Extract client IP from ASGI headers or Request object.

        Supports both:
        - ASGI headers: list of tuples [(b'x-forwarded-for', b'ip'), ...]
        - Request object: has headers attribute with get() method

        Args:
            headers_or_request: ASGI headers list or Request object.

        Returns:
            Client IP address or "unknown".
        """
        if isinstance(headers_or_request, list):
            for name, value in headers_or_request:
                if name == b"x-forwarded-for":
                    return value.decode().split(",")[0].strip()
                if name == b"x-real-ip":
                    return value.decode()
            return "unknown"

        if hasattr(headers_or_request, "headers"):
            headers = headers_or_request.headers
            x_forwarded = headers.get("X-Forwarded-For")
            if x_forwarded:
                return x_forwarded.split(",")[0].strip()
            x_real_ip = headers.get("X-Real-IP")
            if x_real_ip:
                return x_real_ip
            if hasattr(headers_or_request, "client") and headers_or_request.client is not None:
                return headers_or_request.client.host
            return "unknown"

        if hasattr(headers_or_request, "get"):
            x_forwarded = headers_or_request.get("X-Forwarded-For")
            if x_forwarded:
                return x_forwarded.split(",")[0].strip()
            x_real_ip = headers_or_request.get("X-Real-IP")
            if x_real_ip:
                return x_real_ip
            return "unknown"

        return "unknown"

    def _get_header_value(self, headers: list, header_name: bytes) -> str:
        """Extract specific header value."""
        for name, value in headers:
            if name == header_name:
                return value.decode()
        return "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI middleware entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_excluded_path(path):
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope.get("headers", []))
        current_time = time.time()
        redis_key = f"rate_limit:api:{client_ip}"

        logger.debug(
            f"Processing rate limit check for {client_ip}",
            extra={
                "client_ip": client_ip,
                "endpoint": path,
                "method": scope.get("method", "GET"),
            },
        )

        try:
            redis_client = await get_redis_client()

            one_minute_ago = current_time - 60
            await redis_client.zremrangebyscore(redis_key, 0, one_minute_ago)

            request_count = await redis_client.zcard(redis_key)

            if request_count >= self.requests_per_minute:
                oldest_request = await redis_client.zrange(redis_key, 0, 0, withscores=True)
                reset_time = int(oldest_request[0][1] + 60 - current_time) if oldest_request else 60

                log_rate_limit_event(
                    client_ip=client_ip,
                    endpoint=path,
                    event_type="exceeded",
                    remaining=0,
                    limit=self.requests_per_minute,
                    retry_after=reset_time,
                    method=scope.get("method", "GET"),
                    user_agent=self._get_header_value(scope.get("headers", []), b"user-agent"),
                )

                is_suspicious = await detect_suspicious_activity(
                    redis_client, client_ip, path, request_count
                )
                if is_suspicious:
                    log_rate_limit_event(
                        client_ip=client_ip,
                        endpoint=path,
                        event_type="suspicious",
                        violation_count=request_count,
                        pattern="excessive_violations",
                    )

                response_dict = {
                    "status": "failure",
                    "status_code": 429,
                    "message": (
                        f"Rate limit exceeded. Maximum {self.requests_per_minute} "
                        "requests per minute allowed."
                    ),
                    "error": {"retry_after": reset_time},
                }
                response_body = json.dumps(response_dict).encode("utf-8")

                await send(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [
                            [b"content-type", b"application/json"],
                            [
                                b"content-length",
                                str(len(response_body)).encode(),
                            ],
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": response_body,
                    }
                )
                return

            member = f"{current_time}:{uuid.uuid4()}"
            await redis_client.zadd(redis_key, {member: current_time})
            await redis_client.expire(redis_key, 60)

            async def send_with_headers(message: Message) -> None:
                """Intercept and add rate limit headers before sending."""
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(raw=message.get("headers", []))

                    request_count = await redis_client.zcard(redis_key)
                    remaining = self.requests_per_minute - request_count

                    oldest_request = await redis_client.zrange(redis_key, 0, 0, withscores=True)
                    reset_timestamp = (
                        int(oldest_request[0][1] + 60) if oldest_request else int(current_time + 60)
                    )

                    headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
                    headers["X-RateLimit-Remaining"] = str(remaining)
                    headers["X-RateLimit-Reset"] = str(reset_timestamp)

                    if remaining == 0:
                        log_rate_limit_event(
                            client_ip=client_ip,
                            endpoint=path,
                            event_type="exceeded",
                            remaining=remaining,
                            limit=self.requests_per_minute,
                        )
                    elif remaining <= self.requests_per_minute * 0.1:
                        percentage_used = (
                            (self.requests_per_minute - remaining) / self.requests_per_minute
                        ) * 100
                        log_rate_limit_event(
                            client_ip=client_ip,
                            endpoint=path,
                            event_type="warning",
                            remaining=remaining,
                            limit=self.requests_per_minute,
                            percentage_used=percentage_used,
                        )
                    else:
                        log_rate_limit_event(
                            client_ip=client_ip,
                            endpoint=path,
                            event_type="allowed",
                            remaining=remaining,
                            limit=self.requests_per_minute,
                        )

                await send(message)

            await self.app(scope, receive, send_with_headers)

        except RedisError as e:
            logger.error(
                f"Redis error in rate limiter: {e}",
                extra={
                    "client_ip": client_ip,
                    "endpoint": path,
                    "error": str(e),
                },
            )
            await self.app(scope, receive, send)
