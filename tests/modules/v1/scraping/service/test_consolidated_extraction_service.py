"""Unit tests for consolidated extraction service helpers."""

from app.api.modules.v1.scraping.service.consolidated_extraction_service import (
    ConsolidatedExtractionService,
)


def test_consolidate_content_prioritizes_official_sources_before_token_cutoff():
    """Official sources should survive truncation ahead of lower-authority URLs."""
    service = ConsolidatedExtractionService.__new__(ConsolidatedExtractionService)
    oversized_commercial_content = "A" * 410_000

    consolidated = service._consolidate_content(
        [
            {
                "source_name": "Commercial Blog",
                "source_url": "https://aaa.example.com/legal",
                "content": oversized_commercial_content,
            },
            {
                "source_name": "Official Gazette",
                "source_url": "https://regulator.gov/legal",
                "content": "Official statutory update",
            },
        ]
    )

    assert "Official Gazette" in consolidated
    assert "Official statutory update" in consolidated
    assert "Commercial Blog" not in consolidated


def test_source_priority_ranks_authoritative_domains_first():
    """Domain priority should prefer public/legal authority domains."""
    assert ConsolidatedExtractionService._source_priority({"source_url": "https://agency.gov"}) == 0
    assert (
        ConsolidatedExtractionService._source_priority({"source_url": "https://university.edu"})
        == 1
    )
    assert (
        ConsolidatedExtractionService._source_priority({"source_url": "https://nonprofit.org"}) == 2
    )
    assert ConsolidatedExtractionService._source_priority({"source_url": "https://vendor.com"}) == 3
