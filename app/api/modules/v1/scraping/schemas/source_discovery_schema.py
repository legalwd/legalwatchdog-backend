from typing import Optional

from pydantic import BaseModel, Field


class SuggestedSource(BaseModel):
    """Represents an enriched source URL suggested by the AI search pipeline.

    Fields beyond the core five (title, url, snippet, confidence_reason, is_official)
    are populated by the SourceDiscoveryService and carry default values so that
    existing accept-suggestion payloads remain backward-compatible.
    """

    title: str
    url: str
    snippet: str
    confidence_reason: str
    is_official: bool
    source_category: str = "other"
    """Authority category: official_gov | intergovernmental | trusted_secondary |
    news_media | other."""
    content_depth_score: int = 0
    """0-100 score reflecting how much extractable factual content was found
    in the Parallel.ai excerpts (higher = more data-dense page)."""
    extraction_suitability: str = "medium"
    """Estimated AI extraction yield: high | medium | low."""


class SuggestionRequest(BaseModel):
    """Request model for source suggestion.

    Acts as a search query wrapper where jurisdiction provides the scope/boundary,
    and the search_query (optional) allows specific targeting.
    """

    jurisdiction_name: Optional[str] = Field(
        None, description="Optional name of the jurisdiction (e.g., 'Nigeria')."
    )
    search_query: Optional[str] = Field(
        None,
        description="Specific user input to narrow the search "
        "(e.g., '2024 crypto licensing requirements').",
    )
    max_results: int = Field(default=10, description="Number of results to return (default: 10).")
    processor: str = Field(
        default="base",
        description="Search processor: 'base' for speed (<5s) or 'pro' for quality (15-60s).",
    )
