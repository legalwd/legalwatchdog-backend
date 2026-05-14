import logging
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.utils.response_payloads import error_response

logger = logging.getLogger("app")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle Pydantic request validation errors and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (RequestValidationError): The validation error raised by FastAPI/Pydantic.

    Returns:
        JSONResponse: Standardized error response containing field-level validation messages.
    """
    errors = {}
    for err in exc.errors():
        loc = err["loc"][-1]
        msg = err["msg"]
        if msg.startswith("Value error,"):
            msg = msg.replace("Value error,", "").strip()
        errors[loc] = [msg]

    return error_response(
        status_code=422,
        message="Validation failed",
        error_code="VALIDATION_ERROR",
        errors=errors,
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle HTTP exceptions (4xx/5xx) and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (HTTPException): The HTTP exception raised by FastAPI.

    Returns:
        JSONResponse: Standardized error response with HTTP status code and message.
    """
    logger.error(f"HTTP exception: {exc.detail} ({exc.status_code})")

    return error_response(
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        message=exc.detail,
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (Exception): The unhandled exception.

    Returns:
        JSONResponse: Standardized 500 error response.
    """
    logger.exception(f"Unhandled exception: {exc}")

    return error_response(
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message="Internal server error",
    )


class NotFoundException(Exception):
    """
    Custom exception for when resources are not found.

    Attributes:
        detail: Description of what wasn't found
        resource_type: Type of resource (optional)
        resource_id: ID of the resource (optional)
    """

    def __init__(
        self, detail: str = "Resource not found", resource_type: str = None, resource_id: str = None
    ):
        self.detail = detail
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(detail)


async def not_found_exception_handler(request: Request, exc: NotFoundException):
    """
    Handle not found exceptions.

    Returns:
        JSONResponse: Standardized 404 error response.
    """
    logger.warning(
        f"Resource not found: {exc.detail} (Type: {exc.resource_type}, ID: {exc.resource_id})"
    )

    return error_response(
        status_code=404,
        error_code="NOT_FOUND",
        message=exc.detail,
    )


class RateLimitExceeded(Exception):
    """
    Custom exception for rate limit violations.

    Attributes:
        retry_after: Number of seconds until the rate limit resets
        detail: Additional details about the rate limit violation
    """

    def __init__(self, retry_after: int = 3600, detail: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        self.detail = detail
        super().__init__(detail)


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    """
    Handle rate limit exceptions and return a standardized JSON response.

    Args:
        request (Request): The incoming HTTP request.
        exc (RateLimitExceeded): The rate limit exception.

    Returns:
        JSONResponse: Standardized 429 error response with retry information.
    """
    logger.warning(
        f"Rate limit exceeded for {request.client.host if request.client else 'unknown'} "
        f"on {request.url.path}"
    )

    response = error_response(
        status_code=429,
        message=exc.detail,
        error_code="RATE_LIMIT_EXCEEDED",
    )

    response.headers["Retry-After"] = str(exc.retry_after)

    return response


class ParallelExtractError(Exception):
    """Raised when Parallel.ai extraction fails."""

    pass


class ParallelRateLimitError(ParallelExtractError):
    """Raised when Parallel.ai rate limit is exceeded (429 error)."""

    pass


class OpenRouterError(Exception):
    """Base exception for OpenRouter provider errors."""

    pass


class OpenRouterRateLimitError(OpenRouterError):
    """Raised when OpenRouter rate limit is exceeded."""

    pass


class OpenRouterAuthenticationError(OpenRouterError):
    """Raised when OpenRouter authentication fails."""

    pass


class DiffAIServiceError(Exception):
    """Raised when change detection fails after all retries."""

    pass


class ClosedTicketError(Exception):
    """Raised when attempting to invite participants to a closed ticket."""

    def __init__(self, ticket_id: str = None, detail: str = None):
        self.ticket_id = ticket_id
        self.detail = detail or "Cannot invite participants to a closed ticket"
        super().__init__(self.detail)


class TicketNotFoundError(Exception):
    """Raised when ticket is not found."""

    def __init__(self, ticket_id: str = None, detail: str = None):
        self.ticket_id = ticket_id
        self.detail = detail or "The ticket you're trying to add participants to doesn't exist."
        super().__init__(self.detail)


class UserNotInOrganizationError(Exception):
    """Raised when user is not a member of the organization."""

    def __init__(self, user_id: str = None, org_id: UUID = None, detail: str = None):
        self.user_id = user_id
        self.org_id = org_id
        self.detail = detail or "You must be a member of the organization to invite participants"
        super().__init__(self.detail)


class InsufficientPermissionError(Exception):
    """Raised when user lacks permission to invite participants."""

    def __init__(self, user_id: str = None, org_id: UUID = None, detail: str = None):
        self.user_id = user_id
        self.org_id = org_id
        self.detail = detail or "You don't have permission to invite participants to tickets."
        super().__init__(self.detail)
