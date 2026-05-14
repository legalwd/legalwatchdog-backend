"""Feature mapping utility for tracking usage by feature category."""

from enum import Enum


class FeatureCategory(str, Enum):
    """Feature categories for usage tracking."""

    AI_EXTRACTION = "AI Source Extraction"
    CHANGE_DETECTION = "Change Detection"
    AI_SUMMARIZATION = "AI Summarization"
    PARALLEL_SEARCH = "Parallel Search"
    PARALLEL_EXTRACT = "Parallel Extract"
    SOURCE_SCANNING = "Source Scanning"
    JURISDICTION_TRACKING = "Jurisdiction Tracking"
    TICKETING = "Ticketing"
    OTHER = "Other"


# Mapping of endpoint patterns to feature names
FEATURE_ENDPOINT_MAPPING = {
    "/celery/scraping/stage2": FeatureCategory.AI_EXTRACTION,
    "/celery/scraping/stage4": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/scraping/ai-extract": FeatureCategory.AI_EXTRACTION,
    "/api/v1/scraping/extract": FeatureCategory.AI_EXTRACTION,
    "/api/v1/scrape/extract": FeatureCategory.AI_EXTRACTION,
    "/api/v1/scraping/detect-changes": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/scraping/diff": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/diff/detect": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/diff/detect-sync": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/jurisdictions/consolidate": FeatureCategory.JURISDICTION_TRACKING,
    "/api/v1/jurisdictions/consolidate/diff": FeatureCategory.CHANGE_DETECTION,
    "/api/v1/jurisdictions/filter": FeatureCategory.JURISDICTION_TRACKING,
    "/api/v1/jurisdictions/track": FeatureCategory.JURISDICTION_TRACKING,
    "/api/v1/tickets/summarize": FeatureCategory.AI_SUMMARIZATION,
    "/api/v1/tickets/ai-summary": FeatureCategory.AI_SUMMARIZATION,
    "/api/v1/search/parallel": FeatureCategory.PARALLEL_SEARCH,
    "/api/v1/extract/parallel": FeatureCategory.PARALLEL_EXTRACT,
    "/api/v1/scraping/scan": FeatureCategory.SOURCE_SCANNING,
    "/api/v1/tickets/create": FeatureCategory.TICKETING,
}


def get_feature_from_endpoint(endpoint: str) -> FeatureCategory:
    """Map endpoint to feature category.

    Uses exact matching first, then checks prefix matches prioritized by
    pattern length (longest patterns checked first to avoid overly broad
    matches).

    Args:
        endpoint (str): API endpoint path.

    Returns:
        FeatureCategory: Matched feature category or OTHER.

    Examples:
        >>> get_feature_from_endpoint("/api/v1/scraping/ai-extract")
        FeatureCategory.AI_EXTRACTION
        >>> get_feature_from_endpoint("/api/v1/scraping/detect-changes")
        FeatureCategory.CHANGE_DETECTION
        >>> get_feature_from_endpoint("/api/v1/unknown/endpoint")
        FeatureCategory.OTHER
    """
    if endpoint in FEATURE_ENDPOINT_MAPPING:
        return FEATURE_ENDPOINT_MAPPING[endpoint]

    sorted_patterns = sorted(
        FEATURE_ENDPOINT_MAPPING.items(),
        key=lambda x: len(x[0]),
        reverse=True,
    )

    for pattern, feature in sorted_patterns:
        if endpoint.startswith(pattern):
            return feature

    return FeatureCategory.OTHER


def get_payment_status_display(subscription_status: str | None) -> str:
    """Map BillingAccount subscription_status to user-friendly display label.

    Args:
        subscription_status (str | None): Subscription status from BillingAccount.

    Returns:
        str: Display label for payment status.

    Examples:
        >>> get_payment_status_display("TRIALING")
        'Trial'
        >>> get_payment_status_display("ACTIVE")
        'Paid'
        >>> get_payment_status_display(None)
        'Free'
    """
    status_mapping = {
        "TRIALING": "Trial",
        "ACTIVE": "Paid",
        "PAST_DUE": "Past Due",
        "UNPAID": "Unpaid",
        "CANCELLED": "Cancelled",
        "BLOCKED": "Blocked",
        None: "Free",
    }

    return status_mapping.get(subscription_status, "Unknown")
