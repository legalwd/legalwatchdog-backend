"""HTTP request helpers and extractors for authentication routes."""

from typing import Optional

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.

    Checks X-Forwarded-For header first (for proxies), then client.host.

    Args:
        request: The HTTP request object.

    Returns:
        str: The client IP address, or "unknown" if unable to determine.

    Examples:
        >>> from fastapi import Request
        >>> request = Request(...)
        >>> ip = get_client_ip(request)
        >>> print(ip)
        "192.168.1.1"
    """
    if request.headers.get("x-forwarded-for"):
        return request.headers.get("x-forwarded-for").split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def extract_bearer_token(request: Request) -> Optional[str]:
    """
    Extract bearer token from Authorization header.

    Args:
        request: The HTTP request object.

    Returns:
        Optional[str]: The bearer token if present, None otherwise.

    Examples:
        >>> from fastapi import Request
        >>> request = Request(...)
        >>> token = extract_bearer_token(request)
        >>> print(token)
        "eyJ0eXAiOiJKV1QiLCJhbGc..."
    """
    auth_header = request.headers.get("authorization", "").lower()
    if auth_header.startswith("bearer "):
        return auth_header.replace("bearer ", "")
    return None


async def parse_login_request(request: Request) -> tuple[str, str]:
    """
    Parse login credentials from request (JSON or form data).

    Supports both JSON and form-encoded payloads with flexible field names.

    Args:
        request: The HTTP request object.

    Returns:
        tuple[str, str]: (email, password) tuple.

    Raises:
        ValueError: If email or password is missing.

    Examples:
        >>> email, password = await parse_login_request(request)
        >>> print(f"{email}, {password}")
        "user@example.com, secret123"
    """
    content_type = request.headers.get("content-type", "").lower()

    if "application/json" in content_type:
        data = await request.json()
        email = data.get("email")
        password = data.get("password")
    else:
        form = await request.form()
        email = form.get("email") or form.get("username")
        password = form.get("password")

    if not email or not password:
        raise ValueError("Email and password are required")

    return email, password
