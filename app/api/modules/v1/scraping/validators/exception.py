from app.api.core.custom_exceptions.exceptions import CustomDomainException


class ExtractionFailedError(CustomDomainException):
    def __init__(self, message: str = ""):
        message = "Extraction failed" if not message else message
        super().__init__(message=message, code="EXTRACTION_FAILED")


class SourceInactiveError(CustomDomainException):
    def __init__(self, message: str = ""):
        message = "Source is inactive" if not message else message
        super().__init__(message=message, code="SOURCE_INACTIVE")


class ScrapeAlreadyInProgressError(CustomDomainException):
    def __init__(self, message: str = ""):
        message = (
            "Unable to process scrape request.A scrape is already in progress for this source."
            if not message
            else message
        )
        super().__init__(message=message, code="SCRAPE_IN_PROGRESS")


class JobNotFoundError(CustomDomainException):
    def __init__(self, message: str = ""):
        message = "Scrape job not found" if not message else message
        super().__init__(message=message, code="JOB_NOT_FOUND")


class SourceNotFoundError(CustomDomainException):
    def __init__(self, message: str = ""):
        message = "Source not found" if not message else message
        super().__init__(message=message, code="SOURCE_NOT_FOUND")


class InvalidSuggestionDataError(CustomDomainException):
    """Raised when suggested source data fails validation."""

    def __init__(self, message: str = "", field_errors: dict | None = None):
        message = "Invalid suggestion data" if not message else message
        self.field_errors = field_errors
        super().__init__(message=message, code="INVALID_SUGGESTION_DATA")


class DuplicateSourceError(CustomDomainException):
    def __init__(self, message: str = "", field_errors: dict | None = None):
        message = "Source URLs already exist" if not message else message
        self.field_errors = field_errors
        super().__init__(message=message, code="DUPLICATE_ENTRY")


class ExternalSearchServiceError(CustomDomainException):
    def __init__(self, message: str = "", field_errors: dict | None = None):
        message = "parallel.ai search failed" if not message else message
        self.field_errors = field_errors
        super().__init__(message=message, code="PARALLEL_AI_SEARCH_FAILED")
