"""Tests for security logging and suspicious activity detection."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.api.core.security import detect_suspicious_activity, log_rate_limit_event


@pytest.mark.asyncio
async def test_detect_suspicious_activity_below_threshold():
    """Test that normal activity is not flagged as suspicious."""
    mock_redis = AsyncMock()
    mock_redis.zremrangebyscore = AsyncMock()
    mock_redis.zadd = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=3)

    is_suspicious = await detect_suspicious_activity(mock_redis, "192.168.1.1", "/api/test", 3)

    assert is_suspicious is False
    mock_redis.zremrangebyscore.assert_called_once()
    mock_redis.zadd.assert_called_once()
    mock_redis.expire.assert_called_once()
    mock_redis.zcard.assert_called_once()


@pytest.mark.asyncio
async def test_detect_suspicious_activity_above_threshold():
    """Test that excessive violations are flagged as suspicious."""
    mock_redis = AsyncMock()
    mock_redis.zremrangebyscore = AsyncMock()
    mock_redis.zadd = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=5)

    is_suspicious = await detect_suspicious_activity(mock_redis, "192.168.1.1", "/api/test", 5)

    assert is_suspicious is True
    mock_redis.zcard.assert_called_once()


@pytest.mark.asyncio
async def test_detect_suspicious_activity_redis_error():
    """Test graceful handling of Redis errors."""
    mock_redis = AsyncMock()
    mock_redis.zremrangebyscore = AsyncMock(side_effect=Exception("Redis error"))

    is_suspicious = await detect_suspicious_activity(mock_redis, "192.168.1.1", "/api/test", 3)

    assert is_suspicious is False


@pytest.mark.asyncio
async def test_detect_suspicious_activity_removes_old_violations():
    """Test that old violations are properly removed."""
    mock_redis = AsyncMock()
    current_time = time.time()
    mock_redis.zremrangebyscore = AsyncMock()
    mock_redis.zadd = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.zcard = AsyncMock(return_value=2)

    await detect_suspicious_activity(mock_redis, "192.168.1.1", "/api/test", 2)

    # Verify zremrangebyscore was called with correct time window (10 minutes)
    mock_redis.zremrangebyscore.assert_called_once()
    call_args = mock_redis.zremrangebyscore.call_args[0]
    assert call_args[0] == "violations:192.168.1.1"
    assert call_args[1] == 0
    # Should remove entries older than 10 minutes (600 seconds)
    assert abs(call_args[2] - (current_time - 600)) < 2  # Allow 2 second tolerance


def test_log_rate_limit_event_allowed():
    """Test logging of allowed requests."""
    with patch("app.api.core.security.logger") as mock_logger:
        log_rate_limit_event(
            client_ip="192.168.1.1",
            endpoint="/api/test",
            event_type="allowed",
            remaining=45,
            limit=50,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "192.168.1.1" in call_args[0][0]
        assert call_args[1]["extra"]["event_type"] == "allowed"
        assert call_args[1]["extra"]["remaining"] == 45
        assert call_args[1]["extra"]["limit"] == 50


def test_log_rate_limit_event_warning():
    """Test logging of warning when approaching rate limit."""
    with patch("app.api.core.security.logger") as mock_logger:
        log_rate_limit_event(
            client_ip="192.168.1.1",
            endpoint="/api/test",
            event_type="warning",
            remaining=5,
            limit=50,
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "192.168.1.1" in call_args[0][0]
        assert "5/50" in call_args[0][0]


def test_log_rate_limit_event_exceeded():
    """Test logging of rate limit exceeded."""
    with patch("app.api.core.security.logger") as mock_logger:
        log_rate_limit_event(
            client_ip="192.168.1.1",
            endpoint="/api/test",
            event_type="exceeded",
            remaining=0,
            limit=50,
            retry_after=30,
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "192.168.1.1" in call_args[0][0]
        assert call_args[1]["extra"]["retry_after"] == 30


def test_log_rate_limit_event_suspicious():
    """Test logging of suspicious activity."""
    with patch("app.api.core.security.logger") as mock_logger:
        log_rate_limit_event(
            client_ip="192.168.1.1",
            endpoint="/api/test",
            event_type="suspicious",
            violation_count=10,
            pattern="excessive_violations",
        )

        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args
        assert "192.168.1.1" in call_args[0][0]
        assert call_args[1]["extra"]["violation_count"] == 10
        assert call_args[1]["extra"]["pattern"] == "excessive_violations"


def test_log_rate_limit_event_with_extra_kwargs():
    """Test logging with additional keyword arguments."""
    with patch("app.api.core.security.logger") as mock_logger:
        log_rate_limit_event(
            client_ip="192.168.1.1",
            endpoint="/api/test",
            event_type="allowed",
            remaining=40,
            limit=50,
            user_agent="TestBot/1.0",
            method="POST",
        )

        call_args = mock_logger.info.call_args
        assert call_args[1]["extra"]["user_agent"] == "TestBot/1.0"
        assert call_args[1]["extra"]["method"] == "POST"
