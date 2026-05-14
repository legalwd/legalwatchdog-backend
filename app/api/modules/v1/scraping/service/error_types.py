"""Error classification and handling for scraping pipeline.

This module provides error categorization, user-friendly error messages,
and retry decision logic for the scraping pipeline.
"""

import logging
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur during scraping."""

    CONFIGURATION_ERROR = "configuration"
    NETWORK_ERROR = "network"
    RATE_LIMIT_ERROR = "rate_limit"
    VALIDATION_ERROR = "validation"
    RESOURCE_ERROR = "resource"
    UNKNOWN_ERROR = "unknown"


RETRIABLE_ERRORS = {
    ErrorCategory.NETWORK_ERROR,
    ErrorCategory.RATE_LIMIT_ERROR,
    ErrorCategory.RESOURCE_ERROR,
}


ERROR_MESSAGES = {
    ErrorCategory.CONFIGURATION_ERROR: (
        "Service temporarily unavailable due to configuration issue. "
        "Our team has been notified. Please try again later or contact support."
    ),
    ErrorCategory.NETWORK_ERROR: (
        "Unable to connect to external service. "
        "Please check your internet connection and try again."
    ),
    ErrorCategory.RATE_LIMIT_ERROR: (
        "Service is experiencing high demand. "
        "Your request will be retried automatically. Please wait a few moments."
    ),
    ErrorCategory.VALIDATION_ERROR: (
        "The content could not be processed due to invalid data format. "
        "Please verify the source URL and try again."
    ),
    ErrorCategory.RESOURCE_ERROR: (
        "Database or storage service temporarily unavailable. Please try again in a few moments."
    ),
    ErrorCategory.UNKNOWN_ERROR: (
        "An unexpected error occurred. Our team has been notified. Please try again later."
    ),
}


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an error into a category.

    Args:
        error (Exception): The error to classify.

    Returns:
        ErrorCategory: The error category.

    Examples:
        >>> classify_error(ValueError("API Key not found"))
        ErrorCategory.CONFIGURATION_ERROR
        >>> classify_error(ConnectionError("timeout"))
        ErrorCategory.NETWORK_ERROR
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()

    if any(
        keyword in error_str
        for keyword in [
            "api key",
            "api_key",
            "invalid api key",
            "api_key_invalid",
            "authentication",
            "unauthorized",
            "gemini_api_key",
            "openrouter_api_key",
            "configuration",
            "not configured",
            "not found",
        ]
    ):
        return ErrorCategory.CONFIGURATION_ERROR

    if (
        any(
            keyword in error_str
            for keyword in [
                "rate limit",
                "rate_limit",
                "429",
                "too many requests",
                "quota exceeded",
                "throttle",
            ]
        )
        or "429" in error_type
    ):
        return ErrorCategory.RATE_LIMIT_ERROR

    if any(
        keyword in error_str
        for keyword in [
            "timeout",
            "timed out",
            "connection",
            "connect",
            "network",
            "dns",
            "socket",
            "unreachable",
        ]
    ) or error_type in [
        "connectionerror",
        "timeouterror",
        "httperror",
        "requestexception",
    ]:
        return ErrorCategory.NETWORK_ERROR

    if any(
        keyword in error_str
        for keyword in [
            "validation",
            "invalid",
            "schema",
            "parse",
            "json",
            "decode",
            "400",
        ]
    ) or error_type in [
        "validationerror",
        "valueerror",
        "jsondecodeerror",
        "typeerror",
    ]:
        return ErrorCategory.VALIDATION_ERROR

    if any(
        keyword in error_str
        for keyword in [
            "database",
            "db",
            "minio",
            "storage",
            "integrity",
            "constraint",
            "foreign key",
        ]
    ) or error_type in [
        "integrityerror",
        "databaseerror",
        "operationalerror",
    ]:
        return ErrorCategory.RESOURCE_ERROR

    return ErrorCategory.UNKNOWN_ERROR


def get_user_friendly_message(category: ErrorCategory) -> str:
    """Get user-friendly error message for a category.

    Args:
        category (ErrorCategory): The error category.

    Returns:
        str: User-friendly error message.

    Examples:
        >>> get_user_friendly_message(ErrorCategory.NETWORK_ERROR)
        'Unable to connect to external service. ...'
    """
    return ERROR_MESSAGES.get(category, ERROR_MESSAGES[ErrorCategory.UNKNOWN_ERROR])


def should_retry_error(category: ErrorCategory) -> bool:
    """Determine if an error should trigger a retry.

    Args:
        category (ErrorCategory): The error category.

    Returns:
        bool: True if the error should be retried, False otherwise.

    Examples:
        >>> should_retry_error(ErrorCategory.NETWORK_ERROR)
        True
        >>> should_retry_error(ErrorCategory.CONFIGURATION_ERROR)
        False
    """
    return category in RETRIABLE_ERRORS


def analyze_error(error: Exception) -> Tuple[ErrorCategory, str, bool]:
    """Analyze an error and return category, message, and retry decision.

    Args:
        error (Exception): The error to analyze.

    Returns:
        Tuple[ErrorCategory, str, bool]: Category, user-friendly message, should retry.

    Examples:
        >>> category, message, retry = analyze_error(ValueError("API Key not found"))
        >>> category == ErrorCategory.CONFIGURATION_ERROR
        True
        >>> retry
        False
    """
    category = classify_error(error)
    message = get_user_friendly_message(category)
    retry = should_retry_error(category)

    logger.info(
        f"Error analyzed: category={category.value}, should_retry={retry}, "
        f"error_type={type(error).__name__}"
    )

    return category, message, retry


class ScrapingError(Exception):
    """Base exception for scraping pipeline errors.

    Attributes:
        technical_message (str): Technical error message for logging.
        user_message (str): User-friendly error message.
        error_category (ErrorCategory): The error category.
        should_retry (bool): Whether this error should trigger a retry.
        original_error (Optional[Exception]): The original exception.
    """

    def __init__(
        self,
        technical_message: str,
        user_message: Optional[str] = None,
        error_category: Optional[ErrorCategory] = None,
        should_retry: Optional[bool] = None,
        original_error: Optional[Exception] = None,
    ):
        """Initialize scraping error.

        Args:
            technical_message (str): Technical error message for logging.
            user_message (Optional[str]): User-friendly message. Auto-generated if None.
            error_category (Optional[ErrorCategory]): Error category. Auto-detected if None.
            should_retry (Optional[bool]): Should retry. Auto-determined if None.
            original_error (Optional[Exception]): Original exception.
        """
        super().__init__(technical_message)
        self.technical_message = technical_message
        self.original_error = original_error

        if error_category is None:
            if original_error:
                error_category = classify_error(original_error)
            else:
                error_category = classify_error(Exception(technical_message))

        self.error_category = error_category

        if user_message is None:
            user_message = get_user_friendly_message(error_category)

        self.user_message = user_message

        if should_retry is None:
            should_retry = should_retry_error(error_category)

        self.should_retry = should_retry

    def to_dict(self) -> dict:
        """Convert error to dictionary for job result.

        Returns:
            dict: Error information as dictionary.
        """
        return {
            "status": "failed",
            "error_category": self.error_category.value,
            "user_message": self.user_message,
            "technical_message": self.technical_message,
            "should_retry": self.should_retry,
        }
