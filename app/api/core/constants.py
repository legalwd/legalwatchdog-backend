"""Constants for the application.

This module contains constants used across the application,
including error codes for standardized error responses.
"""


class ErrorCodes:
    """Standard error codes for consistent error handling."""

    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"

    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    NETWORK_ERROR = "NETWORK_ERROR"

    ASYNC_LOOP_CONFLICT = "ASYNC_LOOP_CONFLICT"
