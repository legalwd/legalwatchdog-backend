"""
Custom domain exceptions for the application.
All exceptions inherit from CustomDomainException base class.
"""


class CustomDomainException(Exception):
    """
    Base exception for all domain-specific errors.

    Attributes:
        message (str): Human-readable error description
        code (str): Machine-readable error code for API responses
    """

    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class EmailAlreadyExistsError(CustomDomainException):
    """Raised when attempting to add a duplicate email"""

    def __init__(self, message: str):
        message = "Email is already exists" if not message else message
        super().__init__(message=message, code="EMAIL_ALREADY_EXISTS")


class ProcessingError(CustomDomainException):
    """Raised when processing fails due to unexpected error"""

    def __init__(self, message: str = ""):
        message = (
            "Unable to process your request at this time. Please try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="PROCESSING_ERROR")


class NotFoundError(CustomDomainException):
    """Raised when a requested resource is not found"""

    def __init__(self, message: str = ""):
        message = "The requested resource was not found." if not message else message
        super().__init__(message=message, code="NOT_FOUND")


class PermissionDeniedError(CustomDomainException):
    """Raised when a user does not have permission to access a resource"""

    def __init__(self, message: str = ""):
        message = "You do not have permission to access this resource." if not message else message
        super().__init__(message=message, code="PERMISSION_DENIED")


class AlreadyExistsError(CustomDomainException):
    """Raised when attempting to create a resource that already exists"""

    def __init__(self, message: str = ""):
        message = (
            "The resource you are trying to create already exists. " if not message else message
        )
        super().__init__(message=message, code="RESOURCE_EXISTS")


class ClosedTicketError(CustomDomainException):
    """Raised when attempting to invite participants to a closed ticket."""

    def __init__(self, message: str = ""):
        message = "Cannot invite participants to a closed ticket." if not message else message
        self.message = message
        super().__init__(message, code="CLOSED_TICKET")


# Authentication & Credentials Exceptions


class InvalidCredentialsError(CustomDomainException):
    """Raised when email or password is incorrect"""

    def __init__(self, message: str = ""):
        message = (
            "The email or password you entered is incorrect. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_CREDENTIALS")


class InvalidTokenError(CustomDomainException):
    """Raised when a token is invalid or malformed"""

    def __init__(self, message: str = ""):
        message = "Your session is invalid. Please log in again." if not message else message
        super().__init__(message=message, code="INVALID_TOKEN")


class TokenExpiredError(CustomDomainException):
    """Raised when a token has expired"""

    def __init__(self, message: str = ""):
        message = (
            "Your session has expired. Please log in again to continue." if not message else message
        )
        super().__init__(message=message, code="TOKEN_EXPIRED")


class AccountInactiveError(CustomDomainException):
    """Raised when attempting to authenticate with an inactive account"""

    def __init__(self, message: str = ""):
        message = (
            "Your account has been deactivated. Please contact our support team for assistance."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_INACTIVE")


class AccountPendingApprovalError(CustomDomainException):
    """Raised when user tries to access features before account approval"""

    def __init__(self, message: str = ""):
        message = (
            "Your account is pending approval. "
            "You'll receive an email notification once your account is approved by our team."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_PENDING_APPROVAL")


class AccountUnverifiedError(CustomDomainException):
    """Raised when attempting to login with an unverified email"""

    def __init__(self, message: str = ""):
        message = (
            "Please verify your email address before logging in. "
            "Check your inbox for the verification link."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_UNVERIFIED")


class AccountLockedError(CustomDomainException):
    """Raised when account is locked due to too many failed login attempts"""

    def __init__(self, message: str = ""):
        message = (
            "Your account has been temporarily locked for security reasons. Please try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="ACCOUNT_LOCKED")


# Rate Limiting & Throttling Exceptions


class RateLimitExceededError(CustomDomainException):
    """Raised when rate limit is exceeded"""

    def __init__(self, message: str = ""):
        message = "Too many requests. Please try again later." if not message else message
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED")


class TooManyAttemptsError(CustomDomainException):
    """Raised when too many attempts are made (login, OTP, etc.)"""

    def __init__(self, message: str = ""):
        message = "Too many attempts. Please try again later." if not message else message
        super().__init__(message=message, code="TOO_MANY_ATTEMPTS")


# Registration & Verification Exceptions


class InvalidOTPError(CustomDomainException):
    """Raised when OTP code is invalid or expired"""

    def __init__(self, message: str = ""):
        message = (
            "The code you entered is invalid or has expired. Please request a new one."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_OTP")


class UserAlreadyRegisteredError(CustomDomainException):
    """Raised when attempting to register with an email that already exists"""

    def __init__(self, message: str = ""):
        message = "User with this email already exists" if not message else message
        super().__init__(message=message, code="USER_ALREADY_REGISTERED")


class RegistrationPendingError(CustomDomainException):
    """Raised when a pending registration already exists for an email"""

    def __init__(self, message: str = ""):
        message = (
            "A pending registration already exists for this email. "
            "Please check your inbox or try again later."
            if not message
            else message
        )
        super().__init__(message=message, code="REGISTRATION_PENDING")


# OAuth & Social Auth Exceptions


class OAuthFlowError(CustomDomainException):
    """Raised when OAuth authentication flow fails"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"Unable to complete sign-in with {provider}. Please try again or use email login."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_FLOW_ERROR")


class OAuthStateInvalidError(CustomDomainException):
    """Raised when OAuth CSRF state validation fails"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            "For your security, we need you to start the login process again. "
            "Please try signing in once more."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_STATE_INVALID")


class OAuthTokenInvalidError(CustomDomainException):
    """Raised when OAuth provider token is invalid"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We encountered an issue with {provider} authentication. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_INVALID")


class MissingEmailError(CustomDomainException):
    """Raised when email is missing from OAuth provider response"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We couldn't retrieve your email from {provider}. "
            f"Please make sure your {provider} account has a verified email address."
            if not message
            else message
        )
        super().__init__(message=message, code="MISSING_EMAIL")


class MissingIDTokenError(CustomDomainException):
    """Raised when ID token is missing from OAuth response"""

    def __init__(self, message: str = "", provider: str = "OAuth"):
        message = (
            f"We didn't receive complete authentication information from {provider}. "
            f"Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="MISSING_ID_TOKEN")


class InvalidClientError(CustomDomainException):
    """Raised when OAuth client is invalid or not allowed"""

    def __init__(self, message: str = ""):
        message = (
            "There's an issue with the login request. Please try again." if not message else message
        )
        super().__init__(message=message, code="INVALID_CLIENT")


# Password Reset Exceptions


class InvalidResetCodeError(CustomDomainException):
    """Raised when password reset code is invalid or expired"""

    def __init__(self, message: str = ""):
        message = (
            "The reset code you entered is invalid or has expired. Please request a new one."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_RESET_CODE")


class ResetTokenExpiredError(CustomDomainException):
    """Raised when password reset token has expired"""

    def __init__(self, message: str = ""):
        message = (
            "Your reset link has expired for security reasons. Please request a new password reset."
            if not message
            else message
        )
        super().__init__(message=message, code="RESET_TOKEN_EXPIRED")


class UserNotInOrganizationError(CustomDomainException):
    """Raised when a user is not part of the organization."""

    def __init__(self, message: str = ""):
        message = "The user is not part of the organization." if not message else message
        self.message = message
        super().__init__(message, code="USER_NOT_IN_ORGANIZATION")

    # admin llm monitoring


class LLMUsageError(CustomDomainException):
    """Base exception for LLM usage tracking errors"""

    def __init__(self, message: str):
        super().__init__(message=message, code="LLM_USAGE_ERROR")


class LLMProviderError(CustomDomainException):
    """Raised when LLM provider operations fail"""

    def __init__(self, message: str):
        super().__init__(message=message, code="LLM_PROVIDER_ERROR")


class LLMQueryError(CustomDomainException):
    """Raised when LLM usage query fails"""

    def __init__(self, message: str):
        super().__init__(message=message, code="LLM_QUERY_ERROR")


class InvalidDateRangeError(CustomDomainException):
    """Raised when date range parameters are invalid"""

    def __init__(self, message: str = "Invalid date range provided"):
        super().__init__(message=message, code="INVALID_INPUT")


class BadRequestError(CustomDomainException):
    """Raised when the request is invalid or malformed"""

    def __init__(self, message: str = ""):
        message = "The request is invalid or malformed." if not message else message
        super().__init__(message=message, code="BAD_REQUEST")


class DataRevisionNotFoundError(CustomDomainException):
    """Raised when a specific data revision is not found."""

    def __init__(self, message: str = ""):
        message = "The data revision was not found." if not message else message
        super().__init__(message=message, code="DATA_REVISION_NOT_FOUND")


class ForbiddenError(CustomDomainException):
    """Raised when access to a resource is forbidden"""

    def __init__(self, message: str = ""):
        message = "Access to this resource is forbidden." if not message else message
        super().__init__(message=message, code="FORBIDDEN")


class AuthenticationError(CustomDomainException):
    """Raised when authentication fails"""

    def __init__(self, message: str = ""):
        message = "Authentication failed. Please try again." if not message else message
        super().__init__(message=message, code="AUTHENTICATION_ERROR")


class OAuthTokenExchangeError(CustomDomainException):
    """Raised when OAuth token exchange fails"""

    def __init__(self, message: str = ""):
        message = (
            "Failed to exchange authorization code for tokens. Please try again."
            if not message
            else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_EXCHANGE_FAILED")


class OAuthTokenVerificationError(CustomDomainException):
    """Raised when OAuth token verification fails"""

    def __init__(self, message: str = ""):
        message = (
            "Failed to verify authentication token. Please try again." if not message else message
        )
        super().__init__(message=message, code="OAUTH_TOKEN_VERIFICATION_FAILED")


class PasswordReuseError(CustomDomainException):
    """Raised when user attempts to reuse a previously used password"""

    def __init__(self, message: str = ""):
        message = "New password cannot be the same as your old password" if not message else message
        super().__init__(message=message, code="PASSWORD_REUSE_ERROR")


class ValidationError(CustomDomainException):
    """Raised when input validation fails"""

    def __init__(self, message: str = ""):
        message = "Input validation failed. Please check and try again." if not message else message
        super().__init__(message=message, code="VALIDATION_ERROR")


# admin parallel monitoring


class ParallelUsageError(CustomDomainException):
    """Base exception for Parallel.ai usage tracking errors"""

    def __init__(self, message: str):
        super().__init__(message=message, code="PARALLEL_USAGE_ERROR")


class ParallelQueryError(CustomDomainException):
    """Raised when Parallel.ai usage query fails"""

    def __init__(self, message: str):
        super().__init__(message=message, code="PARALLEL_QUERY_ERROR")


class ParallelProviderError(CustomDomainException):
    """Raised when Parallel.ai provider operations fail"""

    def __init__(self, message: str):
        super().__init__(message=message, code="PARALLEL_PROVIDER_ERROR")


class ParallelProviderConnectionError(ParallelProviderError):
    """Exception raised when there's a connection error with Parallel.ai service."""

    def __init__(self, message: str = "Parallel.ai service connection failed"):
        super().__init__(message)


class InvalidFileTypeError(CustomDomainException):
    """Raised when an uploaded file has an invalid type"""

    def __init__(self, message: str = ""):
        message = "Invalid file type." if not message else message
        super().__init__(message=message, code="INVALID_FILE_TYPE")


class FileTooLargeError(CustomDomainException):
    """Raised when an uploaded file exceeds the size limit"""

    def __init__(self, message: str = ""):
        message = "File is too large." if not message else message
        super().__init__(message=message, code="FILE_TOO_LARGE")


class NoFieldsToUpdateError(CustomDomainException):
    """Raised when an update request contains no fields to update"""

    def __init__(self, message: str = ""):
        message = "No fields to update." if not message else message
        super().__init__(message=message, code="NO_FIELDS_TO_UPDATE")


# Scraping Exceptions


class ScrapeAlreadyInProgressError(CustomDomainException):
    """Raised when attempting to start a scrape while one is already active for the source."""

    def __init__(self, message: str = ""):
        message = (
            "A scrape is already in progress for this jurisdiction. "
            "Please wait for it to complete before starting a new one."
            if not message
            else message
        )
        super().__init__(message=message, code="SCRAPE_IN_PROGRESS")


# Storage/Infrastructure Exceptions


class StorageError(CustomDomainException):
    """Raised when MinIO/S3 storage operations fail"""

    def __init__(self, message: str = ""):
        message = "Failed to access storage. Please try again later." if not message else message
        super().__init__(message=message, code="STORAGE_ERROR")


class StorageConnectionError(StorageError):
    """Raised when can't connect to storage service"""

    def __init__(self, message: str = ""):
        message = "Storage service unavailable. Please try again later." if not message else message
        super().__init__(message=message, code="STORAGE_CONNECTION_ERROR")


class StorageNotFoundError(StorageError):
    """Raised when content not found in storage"""

    def __init__(self, message: str = ""):
        message = "The requested content was not found in storage." if not message else message
        super().__init__(message=message, code="STORAGE_NOT_FOUND")


# Scraping/Content Extraction Exceptions


class ScrapingError(CustomDomainException):
    """Base exception for scraping failures"""

    def __init__(self, message: str = "", code: str = "SCRAPING_ERROR"):
        message = "Failed to scrape content from source." if not message else message
        super().__init__(message=message, code=code)


class ScrapingTimeoutError(ScrapingError):
    """Raised when scraping times out"""

    def __init__(self, message: str = ""):
        message = (
            "Scraping timed out. The source may be slow or unavailable." if not message else message
        )
        super().__init__(message=message, code="SCRAPING_TIMEOUT")


class ScrapingConnectionError(ScrapingError):
    """Raised when can't connect to source"""

    def __init__(self, message: str = ""):
        message = (
            "Could not connect to the source. Please check the URL." if not message else message
        )
        super().__init__(message=message, code="SCRAPING_CONNECTION_ERROR")


class InvalidSourceError(ScrapingError):
    """Raised when source URL is invalid or returns errors"""

    def __init__(self, message: str = ""):
        message = "The source URL is invalid or returned an error." if not message else message
        super().__init__(message=message, code="INVALID_SOURCE")


class EmptyContentError(ScrapingError):
    """Raised when scraped content is empty"""

    def __init__(self, message: str = ""):
        message = "No content found at the source URL." if not message else message
        super().__init__(message=message, code="EMPTY_CONTENT")


# LLM/AI Extraction Exceptions


class LLMExtractionError(CustomDomainException):
    """Base exception for LLM extraction failures"""

    def __init__(self, message: str = ""):
        message = "AI extraction failed. Please try again." if not message else message
        super().__init__(message=message, code="LLM_EXTRACTION_ERROR")


class LLMInvalidResponseError(LLMExtractionError):
    """Raised when LLM returns invalid/unparseable JSON"""

    def __init__(self, message: str = ""):
        message = "AI returned invalid response format. Retrying..." if not message else message
        self.code = "LLM_INVALID_RESPONSE"
        super().__init__(message=message)


class LLMValidationError(LLMExtractionError):
    """Raised when LLM response fails schema validation"""

    def __init__(self, message: str = ""):
        message = "AI response validation failed. Please try again." if not message else message
        self.code = "LLM_VALIDATION_ERROR"
        super().__init__(message=message)


class LLMRateLimitError(LLMExtractionError):
    """Raised when LLM API rate limit exceeded"""

    def __init__(self, message: str = ""):
        message = (
            "AI service rate limit exceeded. Please try again in a few moments."
            if not message
            else message
        )
        self.code = "LLM_RATE_LIMIT"
        super().__init__(message=message)


class LLMAPIError(LLMExtractionError):
    """Raised when LLM API returns error"""

    def __init__(self, message: str = ""):
        message = "AI service error. Please try again later." if not message else message
        self.code = "LLM_API_ERROR"
        super().__init__(message=message)


class LLMConfigurationError(LLMExtractionError):
    """Raised when LLM is misconfigured (missing API keys, etc.)"""

    def __init__(self, message: str = ""):
        message = (
            "AI service not configured properly. Contact administrator." if not message else message
        )
        self.code = "LLM_CONFIGURATION_ERROR"
        super().__init__(message=message)


# Job/State Management Exceptions


class JobNotFoundError(NotFoundError):
    """Raised when scrape job doesn't exist"""

    def __init__(self, message: str = ""):
        message = "The scrape job was not found." if not message else message
        super().__init__(message=message)


class JobAlreadyCompletedError(AlreadyExistsError):
    """Raised when trying to process completed job"""

    def __init__(self, message: str = ""):
        message = "This scrape job has already completed." if not message else message
        super().__init__(message=message)


class JobInvalidStateError(ProcessingError):
    """Raised when job is in wrong state for operation"""

    def __init__(self, message: str = ""):
        message = "Job is in an invalid state for this operation." if not message else message
        super().__init__(message=message)


class ProjectBulkBlogInProgressError(CustomDomainException):
    """Raised when attempting to start a bulk blog generation for a project that
    already has one running."""

    def __init__(self, message: str = ""):
        message = (
            "A bulk blog generation is already in progress for this project. "
            "Please wait for it to complete."
            if not message
            else message
        )
        super().__init__(message=message, code="BULK_BLOG_IN_PROGRESS")


class EmptyJurisdictionSetError(CustomDomainException):
    """Raised when attempting to bulk generate blogs for a project with no jurisdictions."""

    def __init__(self, message: str = ""):
        message = "Industry type or jurisdiction is missing." if not message else message
        super().__init__(message=message, code="EMPTY_JURISDICTION_SET")


# Content Processing Exceptions


class ContentProcessingError(ProcessingError):
    """Raised when content processing fails"""

    def __init__(self, message: str = ""):
        message = "Failed to process content. Please try again." if not message else message
        super().__init__(message=message)


class PDFProcessingError(ContentProcessingError):
    """Raised when PDF extraction fails"""

    def __init__(self, message: str = ""):
        message = "Failed to extract text from PDF." if not message else message
        super().__init__(message=message)


class ContentTooLargeError(ProcessingError):
    """Raised when content exceeds size limits"""

    def __init__(self, message: str = ""):
        message = "Content is too large to process." if not message else message
        super().__init__(message=message)


# Source Configuration Exceptions


class SourceConfigurationError(ProcessingError):
    """Raised when source is misconfigured"""

    def __init__(self, message: str = ""):
        message = "Source configuration is invalid." if not message else message
        super().__init__(message=message)


class SourceInactiveError(ProcessingError):
    """Raised when trying to scrape inactive source"""

    def __init__(self, message: str = ""):
        message = "This source is currently inactive." if not message else message
        super().__init__(message=message)


# Parallel AI Exceptions


class ParallelExtractionError(CustomDomainException):
    """Raised when Parallel.ai extraction fails"""

    def __init__(self, message: str = ""):
        message = "Parallel AI extraction failed." if not message else message
        super().__init__(message=message, code="PARALLEL_EXTRACTION_ERROR")


class ParallelRateLimitError(ParallelExtractionError):
    """Raised when Parallel.ai rate limit exceeded"""

    def __init__(self, message: str = ""):
        message = "Parallel AI rate limit exceeded. Try again later." if not message else message
        self.code = "PARALLEL_RATE_LIMIT"
        super().__init__(message=message)


# Data Validation Exceptions


class DataValidationError(ValidationError):
    """Raised when extracted data fails validation"""

    def __init__(self, message: str = ""):
        message = "Extracted data validation failed." if not message else message
        super().__init__(message=message)


class SchemaValidationError(DataValidationError):
    """Raised when data doesn't match expected schema"""

    def __init__(self, message: str = ""):
        message = "Data schema validation failed." if not message else message
        super().__init__(message=message)


class DashboardError(CustomDomainException):
    """Base exception for dashboard-related errors."""

    def __init__(self, message: str, code: str = "DASHBOARD_ERROR"):
        super().__init__(message=message, code=code)


class DashboardOverviewError(DashboardError):
    """Raised when dashboard overview retrieval fails."""

    def __init__(self, message: str = "Unable to load dashboard overview"):
        super().__init__(message=message, code="DASHBOARD_OVERVIEW_ERROR")


class RevenueTrendError(DashboardError):
    """Raised when revenue trend retrieval fails."""

    def __init__(self, message: str = "Unable to load revenue trends"):
        super().__init__(message=message, code="REVENUE_TREND_ERROR")


class AICreditsTrendError(DashboardError):
    """Raised when AI credits trend retrieval fails."""

    def __init__(self, message: str = "Unable to load AI credit trends"):
        super().__init__(message=message, code="AI_CREDITS_TREND_ERROR")


class PaymentBreakdownError(DashboardError):
    """Raised when payment breakdown retrieval fails."""

    def __init__(self, message: str = "Unable to load payment breakdown"):
        super().__init__(message=message, code="PAYMENT_BREAKDOWN_ERROR")


class CustomerNotFoundError(CustomDomainException):
    """Raised when a specific customer is not found."""

    def __init__(self, message: str = ""):
        message = "Customer not found." if not message else message
        super().__init__(message=message, code="CUSTOMER_NOT_FOUND")


class InvalidCustomerFilterError(CustomDomainException):
    """Raised when customer filter parameters are invalid."""

    def __init__(self, message: str = ""):
        message = "Invalid customer filter parameters." if not message else message
        super().__init__(message=message, code="INVALID_CUSTOMER_FILTER")


class CustomerDataRetrievalError(CustomDomainException):
    """Raised when there's an error retrieving customer data."""

    def __init__(self, message: str = ""):
        message = "Failed to retrieve customer data." if not message else message
        super().__init__(message=message, code="CUSTOMER_DATA_RETRIEVAL_ERROR")


class CustomerActivityError(CustomDomainException):
    """Raised when there's an error retrieving customer activity data."""

    def __init__(self, message: str = ""):
        message = "Failed to retrieve customer activity data." if not message else message
        super().__init__(message=message, code="CUSTOMER_ACTIVITY_ERROR")


class PaymentStatusError(CustomDomainException):
    """Raised when payment status validation fails."""

    def __init__(self, message: str = ""):
        message = "Invalid payment status." if not message else message
        super().__init__(message=message, code="PAYMENT_STATUS_ERROR")


class CustomerUsageError(CustomDomainException):
    """Raised when there's an error retrieving customer usage data."""

    def __init__(self, message: str = ""):
        message = "Failed to retrieve customer usage data." if not message else message
        super().__init__(message=message, code="CUSTOMER_USAGE_ERROR")


# Metrics Service Exceptions


class MetricsError(CustomDomainException):
    """Base exception for metrics-related errors."""

    def __init__(self, message: str, code: str = "METRICS_ERROR"):
        super().__init__(message=message, code=code)


class RevenueMetricsError(MetricsError):
    """Raised when revenue metrics calculation fails."""

    def __init__(self, message: str = "Unable to calculate revenue metrics"):
        super().__init__(message=message, code="REVENUE_METRICS_ERROR")


class UserMetricsError(MetricsError):
    """Raised when user metrics calculation fails."""

    def __init__(self, message: str = "Unable to calculate user metrics"):
        super().__init__(message=message, code="USER_METRICS_ERROR")


class AICreditsMetricsError(MetricsError):
    """Raised when AI credits metrics calculation fails."""

    def __init__(self, message: str = "Unable to calculate AI credits metrics"):
        super().__init__(message=message, code="AI_CREDITS_METRICS_ERROR")


class ParallelMetricsError(MetricsError):
    """Raised when parallel AI metrics calculation fails."""

    def __init__(self, message: str = "Unable to calculate parallel AI metrics"):
        super().__init__(message=message, code="PARALLEL_METRICS_ERROR")


class UserPaymentStatusError(MetricsError):
    """Raised when user payment status retrieval fails."""

    def __init__(self, message: str = "Unable to retrieve user payment status"):
        super().__init__(message=message, code="USER_PAYMENT_STATUS_ERROR")

    # scrape-admin


class ScrapingJobError(CustomDomainException):
    """Base exception for scraping job operations."""

    def __init__(self, message: str = ""):
        message = "Scraping job operation failed." if not message else message
        super().__init__(message=message, code="SCRAPING_JOB_ERROR")


class ManualScrapeError(CustomDomainException):
    """Raised when manual scraping fails."""

    def __init__(self, message: str = ""):
        message = "Manual scraping failed." if not message else message
        super().__init__(message=message, code="MANUAL_SCRAPE_ERROR")


class StuckJobRetryError(CustomDomainException):
    """Raised when retrying stuck jobs fails."""

    def __init__(self, message: str = ""):
        message = "Failed to retry stuck jobs." if not message else message
        super().__init__(message=message, code="STUCK_JOB_RETRY_ERROR")


class ClearStuckJobsError(CustomDomainException):
    """Raised when clearing stuck jobs fails."""

    def __init__(self, message: str = ""):
        message = "Failed to clear stuck jobs." if not message else message
        super().__init__(message=message, code="CLEAR_STUCK_JOBS_ERROR")


class SourceNotFoundError(CustomDomainException):
    """Raised when a specific source is not found."""

    def __init__(self, message: str = ""):
        message = "Source not found." if not message else message
        super().__init__(message=message, code="SOURCE_NOT_FOUND")


class TaskInitiationError(CustomDomainException):
    """Raised when task initiation fails."""

    def __init__(self, message: str = ""):
        message = "Failed to initiate task." if not message else message
        super().__init__(message=message, code="TASK_INITIATION_ERROR")


# Jurisdiction Change Exceptions


class ChangeAlreadyAcceptedError(CustomDomainException):
    """Raised when attempting to accept a change that's already been accepted."""

    def __init__(self, message: str = ""):
        message = "This change has already been accepted." if not message else message
        super().__init__(message=message, code="CHANGE_ALREADY_ACCEPTED")


class ChangeAlreadyHasTicketError(CustomDomainException):
    """Raised when attempting to create a ticket for a change that already has one."""

    def __init__(self, message: str = ""):
        message = (
            "A ticket has already been created for this change. "
            "Please view the existing ticket instead."
            if not message
            else message
        )
        super().__init__(message=message, code="CHANGE_ALREADY_HAS_TICKET")


class JurisdictionChangeNotFoundError(CustomDomainException):
    """Raised when a specific jurisdiction change is not found."""

    def __init__(self, message: str = ""):
        message = "The jurisdiction change was not found." if not message else message
        super().__init__(message=message, code="JURISDICTION_CHANGE_NOT_FOUND")


class JurisdictionScrapeJobNotFoundError(CustomDomainException):
    """Raised when a jurisdiction scrape job is not found."""

    def __init__(self, message: str = ""):
        message = "The jurisdiction scrape job was not found." if not message else message
        super().__init__(message=message, code="JURISDICTION_SCRAPE_JOB_NOT_FOUND")


# Comment Exceptions


class CommentNotFoundError(CustomDomainException):
    """Raised when a comment doesn't exist."""

    def __init__(self, message: str = ""):
        message = "The comment you're looking for doesn't exist." if not message else message
        super().__init__(message=message, code="COMMENT_NOT_FOUND")


class CommentDeletedError(CustomDomainException):
    """Raised when trying to update or access a deleted comment."""

    def __init__(self, message: str = ""):
        message = "This comment has been deleted." if not message else message
        super().__init__(message=message, code="COMMENT_DELETED")


class CommentOwnershipError(CustomDomainException):
    """Raised when user tries to modify someone else's comment."""

    def __init__(self, message: str = ""):
        message = "You can only modify your own comments." if not message else message
        super().__init__(message=message, code="COMMENT_OWNERSHIP_ERROR")


class InvalidCommentDataError(CustomDomainException):
    """Raised when comment data is invalid."""

    def __init__(self, message: str = ""):
        message = (
            "At least one of 'content' or 'attachments' must be provided."
            if not message
            else message
        )
        super().__init__(message=message, code="INVALID_COMMENT_DATA")


class AttachmentUploadError(CustomDomainException):
    """Raised when attachment upload to MinIO fails."""

    def __init__(self, message: str = ""):
        message = "Failed to upload attachment. Please try again." if not message else message
        super().__init__(message=message, code="ATTACHMENT_UPLOAD_ERROR")


# Image Upload Exceptions


class ImageValidationError(CustomDomainException):
    """Raised when image validation fails."""

    def __init__(self, message: str = ""):
        message = "Image validation failed." if not message else message
        super().__init__(message=message, code="IMAGE_VALIDATION_ERROR")


class InvalidImageFormatError(CustomDomainException):
    """Raised when image format is not allowed (not JPEG/PNG/WebP)."""

    def __init__(self, message: str = ""):
        message = "Unsupported image format" if not message else message
        super().__init__(message=message, code="INVALID_IMAGE_FORMAT")


class ImageTooLargeError(CustomDomainException):
    """Raised when image exceeds 2MB size limit."""

    def __init__(self, message: str = ""):
        message = "Each image must be 2 MB or less" if not message else message
        super().__init__(message=message, code="IMAGE_TOO_LARGE")


class TooManyImagesError(CustomDomainException):
    """Raised when more than 5 images are submitted."""

    def __init__(self, message: str = ""):
        message = "Maximum of 5 images allowed" if not message else message
        super().__init__(message=message, code="TOO_MANY_IMAGES")


class GifNotAllowedError(CustomDomainException):
    """Raised when a GIF image is submitted."""

    def __init__(self, message: str = ""):
        message = "GIFs are not allowed" if not message else message
        super().__init__(message=message, code="GIF_NOT_ALLOWED")


# Organization Management Exceptions


class OrganizationDataRetrievalError(CustomDomainException):
    """Raised when there's an error retrieving organization data."""

    def __init__(self, message: str = ""):
        message = "Failed to retrieve organization data." if not message else message
        super().__init__(message=message, code="ORGANIZATION_DATA_RETRIEVAL_ERROR")


class OrganizationExportError(CustomDomainException):
    """Raised when there's an error exporting organization data."""

    def __init__(self, message: str = ""):
        message = "Failed to export organization data." if not message else message
        super().__init__(message=message, code="ORGANIZATION_EXPORT_ERROR")


class InvalidOrganizationFilterError(CustomDomainException):
    """Raised when invalid organization filter parameters are provided."""

    def __init__(self, message: str = ""):
        message = "Invalid filter parameter." if not message else message
        super().__init__(message=message, code="INVALID_ORGANIZATION_FILTER")


class ResourceNotFoundError(CustomDomainException):
    """Raised when a requested resource cannot be located."""

    def __init__(self, message: str = ""):
        message = "The requested resource was not found." if not message else message
        super().__init__(message=message, code="RESOURCE_NOT_FOUND")


# Blog Generation Exceptions


class BlogGenerationInProgressError(CustomDomainException):
    """Raised when a blog generation is already in progress for a jurisdiction."""

    def __init__(self, message: str = ""):
        message = (
            "A blog generation is already in progress for this jurisdiction. "
            "Please wait for it to complete."
            if not message
            else message
        )
        super().__init__(message=message, code="BLOG_GENERATION_IN_PROGRESS")


class ResourceLockedError(CustomDomainException):
    """Raised when an operation is rejected because the resource is locked or not editable."""

    def __init__(self, message: str = ""):
        message = (
            "This resource is locked and cannot be modified in its current state."
            if not message
            else message
        )
        super().__init__(message=message, code="RESOURCE_LOCKED")
