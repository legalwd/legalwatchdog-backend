"""Unit tests for ParallelExtractService."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    EmptyContentError,
    ParallelExtractionError,
    ParallelRateLimitError,
)
from app.api.modules.v1.scraping.service.parallel_extract_service import (
    ParallelExtractService,
)


@pytest.fixture
def mock_settings():
    """Mock settings with Parallel.ai API key."""
    with patch("app.api.modules.v1.scraping.service.parallel_extract_service.settings") as mock_cfg:
        mock_cfg.PARALLEL_API_KEY = "test-api-key"
        mock_cfg.REDIS_URL = "redis://localhost:6379/0"
        yield mock_cfg


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for rate limiting."""
    mock_redis = MagicMock()
    mock_redis.zremrangebyscore = MagicMock()
    mock_redis.zcard = MagicMock(return_value=0)
    mock_redis.zadd = MagicMock()
    mock_redis.expire = MagicMock()
    mock_redis.close = MagicMock()
    return mock_redis


@pytest.fixture
def mock_parallel_client():
    """Mock Parallel.ai Parallel client."""
    mock_client = MagicMock()
    mock_client._http_client = MagicMock()
    mock_client._http_client.close = MagicMock()
    # Mock the beta.extract method
    mock_client.beta.extract = MagicMock()
    return mock_client


@pytest.fixture
def service(mock_settings, mock_redis_client, mock_parallel_client):
    """Fixture for ParallelExtractService instance with mocked dependencies."""
    with (
        patch("httpx.Client") as mock_httpx,
        patch(
            "app.api.modules.v1.scraping.service.parallel_extract_service.Parallel",
            return_value=mock_parallel_client,
        ),
        patch("redis.from_url", return_value=mock_redis_client),
    ):
        mock_httpx.return_value = MagicMock()
        service_instance = ParallelExtractService()
        service_instance.redis_client = mock_redis_client
        service_instance.parallel = mock_parallel_client
        yield service_instance


def test_service_initialization_success(mock_settings):
    """Test successful service initialization with valid configuration."""
    with (
        patch("httpx.Client"),
        patch("app.api.modules.v1.scraping.service.parallel_extract_service.Parallel"),
        patch("redis.from_url"),
    ):
        service = ParallelExtractService()
        assert service.max_requests_per_minute == 600
        assert service.rate_limit_window == 60
        assert service.rate_limit_key == "parallel_ai:extract:requests"


def test_service_initialization_missing_api_key():
    """Test service initialization fails without API key."""
    with patch("app.api.modules.v1.scraping.service.parallel_extract_service.settings") as mock_cfg:
        mock_cfg.PARALLEL_API_KEY = None
        with pytest.raises(ValueError, match="PARALLEL_API_KEY is not set"):
            ParallelExtractService()


def test_check_rate_limit_allowed(service, mock_redis_client):
    """Test rate limit check allows request when under limit."""
    service.redis_client = mock_redis_client
    mock_redis_client.zcard.return_value = 100

    status = service._check_rate_limit()

    assert status["allowed"] is True
    assert status["current_count"] == 101
    assert status["limit"] == 600
    assert status["remaining"] == 499


def test_check_rate_limit_exceeded(service, mock_redis_client):
    """Test rate limit check blocks request when limit exceeded."""
    service.redis_client = mock_redis_client
    mock_redis_client.zcard.return_value = 600

    status = service._check_rate_limit()

    assert status["allowed"] is False
    assert status["current_count"] == 600
    assert status["limit"] == 600
    assert status["remaining"] == 0


def test_check_rate_limit_redis_failure_allows_request(service, mock_redis_client):
    """Test rate limit check allows request on Redis failure."""
    mock_redis_client.zremrangebyscore.side_effect = Exception("Redis connection failed")

    status = service._check_rate_limit()

    assert status["allowed"] is True
    assert status["current_count"] == 0
    assert status["remaining"] == 600


def test_check_rate_limit_sliding_window_cleanup(service, mock_redis_client):
    """Test rate limit check removes expired entries from sliding window."""
    service.redis_client = mock_redis_client
    now = datetime.now(timezone.utc).timestamp()
    window_start = now - 60

    service._check_rate_limit()

    mock_redis_client.zremrangebyscore.assert_called_once()
    call_args = mock_redis_client.zremrangebyscore.call_args
    assert call_args[0][0] == "parallel_ai:extract:requests"
    assert call_args[0][1] == 0
    assert abs(call_args[0][2] - window_start) < 1


def test_extract_and_save_success(service, mock_redis_client, mock_parallel_client):
    """Test successful content extraction and storage."""
    service.redis_client = mock_redis_client
    mock_redis_client.zcard.return_value = 50

    mock_result = Mock()
    mock_extracted = Mock()
    mock_extracted.full_content = "# Test Page\n\nThis is test content."
    mock_extracted.title = "Test Page"
    mock_result.results = [mock_extracted]

    # Use regular Mock, not AsyncMock
    mock_parallel_client.beta.extract.return_value = mock_result

    with patch(
        "app.api.modules.v1.scraping.service.parallel_extract_service.upload_raw_content"
    ) as mock_upload:
        mock_upload.return_value = "clean-key-123"

        result = service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="project/source/123.md",
            objective="Extract legal text",
        )

    assert result["full_text"] == "# Test Page\n\nThis is test content."
    assert result["clean_key"] == "project/source/123.md"
    assert result["title"] == "Test Page"
    assert result["source"] == "parallel"
    assert result["rate_limit_remaining"] == 549

    call_args = mock_parallel_client.beta.extract.call_args
    assert call_args is not None
    assert len(call_args[1]["urls"]) == 1
    assert call_args[1]["urls"][0].startswith("https://example.com?")
    assert "_cache_bust=" in call_args[1]["urls"][0]
    assert call_args[1]["objective"] == "Extract legal text"
    assert call_args[1]["full_content"] is True
    assert call_args[1]["excerpts"] is False

    mock_upload.assert_called_once_with(
        file_data=b"# Test Page\n\nThis is test content.",
        bucket_name="clean-content",
        object_name="project/source/123.md",
    )


def test_extract_and_save_no_objective(service, mock_redis_client, mock_parallel_client):
    """Test extraction without objective parameter."""
    mock_redis_client.zcard.return_value = 0

    mock_result = Mock()
    mock_extracted = Mock()
    mock_extracted.full_content = "Content without objective"
    mock_extracted.title = None
    mock_result.results = [mock_extracted]

    mock_parallel_client.beta.extract.return_value = mock_result

    with patch("app.api.modules.v1.scraping.service.parallel_extract_service.upload_raw_content"):
        result = service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )

    assert result["title"] == "Untitled"
    call_args = mock_parallel_client.beta.extract.call_args
    assert call_args is not None
    assert len(call_args[1]["urls"]) == 1
    assert call_args[1]["urls"][0].startswith("https://example.com?")
    assert "_cache_bust=" in call_args[1]["urls"][0]
    assert call_args[1]["objective"] is None
    assert call_args[1]["full_content"] is True
    assert call_args[1]["excerpts"] is False


def test_extract_and_save_rate_limit_exceeded_local(service, mock_redis_client):
    """Test extraction raises error when local rate limit exceeded."""
    service.redis_client = mock_redis_client
    mock_redis_client.zcard.return_value = 600

    with pytest.raises(ParallelRateLimitError, match="Rate limit exceeded: 600/600"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_api_429_error(service, mock_redis_client, mock_parallel_client):
    """Test extraction raises ParallelRateLimitError on 429 response."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception("429 Rate limit exceeded")

    with pytest.raises(ParallelRateLimitError, match="Parallel AI rate limit exceeded"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_api_ratelimit_text_error(
    service, mock_redis_client, mock_parallel_client
):
    """Test extraction detects rate limit error in error message text."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception("RateLimit error occurred")

    with pytest.raises(ParallelRateLimitError, match="Parallel AI rate limit exceeded"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_timeout_error(service, mock_redis_client, mock_parallel_client):
    """Test extraction raises ParallelExtractionError on timeout."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception("Request timed out after 60s")

    with pytest.raises(ParallelExtractionError, match="Parallel AI extraction timed out"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_authentication_error_401(
    service, mock_redis_client, mock_parallel_client
):
    """Test extraction raises ParallelExtractionError on 401 authentication error."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception("401 Unauthorized")

    with pytest.raises(ParallelExtractionError, match="Parallel AI authentication failed"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_authentication_error_text(
    service, mock_redis_client, mock_parallel_client
):
    """Test extraction detects authentication error in message text."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception(
        "Authentication failed: invalid API key"
    )

    with pytest.raises(ParallelExtractionError, match="Parallel AI authentication failed"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_no_results(service, mock_redis_client, mock_parallel_client):
    """Test extraction raises EmptyContentError when API returns no results."""
    mock_redis_client.zcard.return_value = 0

    mock_result = Mock()
    mock_result.results = []

    mock_parallel_client.beta.extract.return_value = mock_result

    with pytest.raises(EmptyContentError, match="Parallel AI returned no content"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_empty_content(service, mock_redis_client, mock_parallel_client):
    """Test extraction raises EmptyContentError when extracted content is empty."""
    mock_redis_client.zcard.return_value = 0

    mock_result = Mock()
    mock_extracted = Mock()
    mock_extracted.full_content = None
    mock_result.results = [mock_extracted]

    mock_parallel_client.beta.extract.return_value = mock_result

    with pytest.raises(EmptyContentError, match="Parallel AI returned no extractable content"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_generic_error(service, mock_redis_client, mock_parallel_client):
    """Test extraction raises ParallelExtractionError on generic errors."""
    mock_redis_client.zcard.return_value = 0

    mock_parallel_client.beta.extract.side_effect = Exception("Network connection failed")

    with pytest.raises(ParallelExtractionError, match="Parallel AI extraction failed"):
        service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )


def test_extract_and_save_minio_upload_failure(service, mock_redis_client, mock_parallel_client):
    """Test extraction handles MinIO upload failure."""
    mock_redis_client.zcard.return_value = 0

    mock_result = Mock()
    mock_extracted = Mock()
    mock_extracted.full_content = "Test content"
    mock_extracted.title = "Test"
    mock_result.results = [mock_extracted]

    mock_parallel_client.beta.extract.return_value = mock_result

    with patch(
        "app.api.modules.v1.scraping.service.parallel_extract_service.upload_raw_content"
    ) as mock_upload:
        mock_upload.side_effect = Exception("MinIO connection error")

        with pytest.raises(ParallelExtractionError, match="Parallel AI extraction failed"):
            service.extract_and_save(
                url="https://example.com",
                clean_bucket="clean-content",
                clean_key="test.md",
            )


def test_close_cleanup(service, mock_redis_client, mock_parallel_client):
    """Test close method properly cleans up resources."""
    service.close()

    mock_parallel_client._http_client.close.assert_called_once()
    mock_redis_client.close.assert_called_once()


def test_close_without_http_client(service, mock_redis_client, mock_parallel_client):
    """Test close method handles missing http_client gracefully."""
    delattr(mock_parallel_client, "_http_client")

    service.close()

    mock_redis_client.close.assert_called_once()


def test_rate_limit_integration_with_extract(service, mock_redis_client, mock_parallel_client):
    """Test rate limiting is checked before extraction request."""
    service.redis_client = mock_redis_client
    mock_redis_client.zcard.return_value = 599

    mock_result = Mock()
    mock_extracted = Mock()
    mock_extracted.full_content = "Content"
    mock_extracted.title = "Title"
    mock_result.results = [mock_extracted]

    mock_parallel_client.beta.extract.return_value = mock_result

    with patch("app.api.modules.v1.scraping.service.parallel_extract_service.upload_raw_content"):
        result = service.extract_and_save(
            url="https://example.com",
            clean_bucket="clean-content",
            clean_key="test.md",
        )

    assert result["rate_limit_remaining"] == 0
    mock_redis_client.zadd.assert_called_once()
    mock_redis_client.expire.assert_called_once_with("parallel_ai:extract:requests", 120)
