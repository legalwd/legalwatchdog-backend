"""Regenerate blog posts for all jurisdictions in a campaign.

Refreshes all existing blog posts with:
- Updated prompts (no organization references)
- Precomputed breadcrumbs
- Latest LLM content from current jurisdiction state

Usage:
    uv run python scripts/regenerate_campaign_blogs.py <campaign_id>
    uv run python scripts/regenerate_campaign_blogs.py <campaign_id> --mode run
    uv run python scripts/regenerate_campaign_blogs.py <campaign_id> --mode backfill_missing
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import app.celery_app  # noqa: E402
from app.api.modules.v1.campaigns.tasks.campaign_tasks import (  # noqa: E402
    generate_campaign_content_task,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("regenerate_blogs")


def main():
    parser = argparse.ArgumentParser(description="Regenerate campaign blog posts.")
    parser.add_argument("campaign_id", help="Campaign UUID")
    parser.add_argument(
        "--mode",
        default="backfill_missing",
        choices=["run", "retry_failed", "backfill_missing"],
        help="Content pipeline mode (default: backfill_missing)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Campaign Blog Regeneration (direct Celery)")
    logger.info("=" * 60)
    logger.info("Campaign ID: %s", args.campaign_id)
    logger.info("Mode:        %s", args.mode)
    logger.info("=" * 60)

    run_id = str(uuid4())
    logger.info(
        "Dispatching generate_campaign_content_task (run_id=%s)...", run_id
    )

    result = generate_campaign_content_task.apply_async(
        args=[args.campaign_id, run_id, args.mode],
        queue="processing",
    )
    logger.info(
        "Task dispatched: id=%s", result.id
    )
    logger.info(
        "Monitor with: celery -A app.celery_app inspect active"
    )


if __name__ == "__main__":
    main()