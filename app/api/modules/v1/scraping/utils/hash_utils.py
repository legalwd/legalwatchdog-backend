"""Hash utilities for content deduplication.

Provides functions for calculating combined content hashes across
jurisdiction sources and checking if consolidation can be skipped.
"""

import hashlib
import logging
from typing import TYPE_CHECKING, List, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob


def calculate_jurisdiction_content_hash(
    completed_jobs: List["ScrapeJob"], jurisdiction_prompt: Optional[str]
) -> str:
    """Calculate combined hash from all source hashes + prompt.

    Creates a deterministic hash by:
    1. Sorting jobs by source_id for consistent ordering
    2. Extracting content_hash from each job's result
    3. Including the jurisdiction prompt (to detect prompt changes)
    4. Combining all hashes with a delimiter

    Args:
        completed_jobs: List of completed ScrapeJobs with content_hash in result
        jurisdiction_prompt: The jurisdiction's monitoring prompt

    Returns:
        SHA-256 hash of combined source hashes and prompt
    """
    source_hashes = []
    for job in sorted(completed_jobs, key=lambda j: str(j.source_id)):
        if job.result and job.result.get("content_hash"):
            source_hashes.append(job.result["content_hash"])
        else:
            logger.warning(
                f"Completed job {job.id} for source {job.source_id} "
                f"has no content_hash in result: {job.result}"
            )

    prompt_hash = hashlib.sha256((jurisdiction_prompt or "").encode()).hexdigest()
    combined = "|".join(source_hashes + [prompt_hash])

    return hashlib.sha256(combined.encode()).hexdigest()


def should_skip_consolidation(current_hash: Optional[str], previous_hash: Optional[str]) -> bool:
    """Check if consolidation can be skipped due to unchanged content.

    Args:
        current_hash: Hash of current jurisdiction scrape job
        previous_hash: Hash of previous completed jurisdiction scrape job

    Returns:
        True if hashes match and consolidation can be skipped
    """
    if not current_hash or not previous_hash:
        return False
    return current_hash == previous_hash
