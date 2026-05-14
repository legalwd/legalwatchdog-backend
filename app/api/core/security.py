import json
import logging
import time
from typing import Any, Dict

from app.api.core.config import get_cipher_suite

logger = logging.getLogger("app")


def encrypt_auth_details(data: Dict[str, Any]) -> str:
    """Converts JSON dict -> Encrypted String"""
    if not data:
        return None
    cipher_suite = get_cipher_suite()
    json_str = json.dumps(data)
    return cipher_suite.encrypt(json_str.encode()).decode()


def decrypt_auth_details(encrypted_data: str) -> Dict[str, Any]:
    """Converts Encrypted String -> JSON dict"""
    if not encrypted_data:
        return {}
    try:
        cipher_suite = get_cipher_suite()
        decrypted_json = cipher_suite.decrypt(encrypted_data.encode()).decode()
        return json.loads(decrypted_json)
    except Exception:
        return {}


async def detect_suspicious_activity(
    redis_client, client_ip: str, endpoint: str, violation_count: int
) -> bool:
    """
    Detect suspicious activity patterns from a client.

    Tracks rate limit violations and identifies potential abuse patterns such as:
    - Repeated rate limit violations
    - Rapid retry attempts
    - Distributed attacks from multiple endpoints

    Args:
        redis_client: Redis client instance.
        client_ip: The client's IP address.
        endpoint: The endpoint being accessed.
        violation_count: Number of times rate limit was violated.

    Returns:
        True if suspicious activity is detected, False otherwise.
    """
    current_time = time.time()
    violation_key = f"violations:{client_ip}"
    window_duration = 600  # 10 minutes

    try:
        # Remove violations older than 10 minutes
        await redis_client.zremrangebyscore(violation_key, 0, current_time - window_duration)

        # Add current violation
        violation_data = f"{endpoint}:{current_time}"
        await redis_client.zadd(violation_key, {violation_data: current_time})
        await redis_client.expire(violation_key, window_duration)

        # Count violations in the last 10 minutes
        recent_violations = await redis_client.zcard(violation_key)

        # Flag as suspicious if 5 or more violations in 10 minutes
        if recent_violations >= 5:
            logger.critical(
                (
                    f"Suspicious activity detected: {recent_violations} rate limit "
                    "violations in 10 minutes"
                ),
                extra={
                    "client_ip": client_ip,
                    "endpoint": endpoint,
                    "violation_count": recent_violations,
                    "pattern": "excessive_violations",
                    "time_window": "10_minutes",
                },
            )
            return True

        return False

    except Exception as e:
        logger.error(
            f"Error detecting suspicious activity: {e}",
            extra={"client_ip": client_ip, "endpoint": endpoint},
        )
        return False


def log_rate_limit_event(
    client_ip: str,
    endpoint: str,
    event_type: str,
    remaining: int = None,
    limit: int = None,
    **kwargs,
) -> None:
    """
    Log rate limiting events with structured data.

    Args:
        client_ip: The client's IP address.
        endpoint: The endpoint being accessed.
        event_type: Type of event (allowed, warning, exceeded, suspicious).
        remaining: Remaining requests in quota.
        limit: Total request limit.
        **kwargs: Additional context to log.
    """
    log_data = {
        "client_ip": client_ip,
        "endpoint": endpoint,
        "event_type": event_type,
        **kwargs,
    }

    if remaining is not None:
        log_data["remaining"] = remaining
    if limit is not None:
        log_data["limit"] = limit

    if event_type == "allowed":
        logger.info(f"Rate limit check passed for {client_ip}", extra=log_data)
    elif event_type == "warning":
        logger.warning(
            f"Client {client_ip} approaching rate limit ({remaining}/{limit})",
            extra=log_data,
        )
    elif event_type == "exceeded":
        logger.error(f"Rate limit exceeded for {client_ip} on {endpoint}", extra=log_data)
    elif event_type == "suspicious":
        logger.critical(f"Suspicious activity from {client_ip}", extra=log_data)
