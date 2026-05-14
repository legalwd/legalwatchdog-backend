#!/usr/bin/env python3
"""
Recovery script: Re-populate empty ledgers from scrape job data
and regenerate blog posts for all jurisdictions under a given project.

Usage:
    # Dry run first — see what would be recovered without writing anything:
    uv run python scripts/recover_placeholder_blogs.py --project-id <UUID> --dry-run

    # Execute the recovery:
    uv run python scripts/recover_placeholder_blogs.py --project-id <UUID>
"""

import argparse
import logging
import sys
from uuid import UUID

# Ensure project root is on sys.path
sys.path.insert(0, ".")

from sqlalchemy import select
from sqlmodel import Session

from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.models.jurisdiction_state import JurisdictionState
from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
    BlogGenerationService,
)
from app.api.modules.v1.jurisdictions.service.jurisdiction_state_service import (
    JurisdictionStateService,
)
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────


def _get_jurisdictions(db: Session, project_id: UUID) -> list[Jurisdiction]:
    """Return all jurisdictions under the given project."""
    return db.scalars(  # type: ignore[return-value]
        select(Jurisdiction).where(Jurisdiction.project_id == project_id)
    ).all()


def _ledger_field_count(db: Session, jurisdiction_id: UUID) -> int:
    """Return how many fields are in the compliance ledger for this jurisdiction."""
    return len(
        db.scalars(
            select(JurisdictionState).where(
                JurisdictionState.jurisdiction_id == jurisdiction_id
            )
        ).all()
    )


def _get_existing_blog(db: Session, jurisdiction_id: UUID) -> JurisdictionBlogPost | None:
    """Return the existing blog post for this jurisdiction, or None."""
    return db.scalars(
        select(JurisdictionBlogPost).where(
            JurisdictionBlogPost.jurisdiction_id == jurisdiction_id
        )
    ).first()


def _get_best_scrape_job(db: Session, jurisdiction_id: UUID) -> JurisdictionScrapeJob | None:
    """Return the most recent completed scrape job with non-empty extracted_data."""
    jobs = db.scalars(
        select(JurisdictionScrapeJob)
        .where(
            JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id,
            JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.COMPLETED,
            JurisdictionScrapeJob.extracted_data.isnot(None),
        )
        .order_by(JurisdictionScrapeJob.completed_at.desc())
    ).all()

    # Pick the job with the most KV pairs (best quality)
    best = None
    best_count = 0
    for job in jobs:
        kv = (
            (job.extracted_data or {})
            .get("extracted_data", {})
            .get("key_value_pairs", {})
        )
        if len(kv) > best_count:
            best = job
            best_count = len(kv)
    return best


# ─────────────────────────────────────────────────────────────────────────────


def recover_project(project_id: UUID, dry_run: bool = False) -> None:
    """
    Recover placeholder blogs for all jurisdictions under project_id.

    For each jurisdiction it:
      1. Checks the compliance ledger (jurisdiction_states).
      2. If the ledger is empty, finds the best completed scrape job and
         seeds the ledger from its key_value_pairs.
      3. Regenerates the blog post, overwriting any Coming Soon placeholder.

    Args:
        project_id: UUID of the project whose jurisdictions should be recovered.
        dry_run: If True, report what would happen without writing anything.
    """
    results: dict[str, int] = {
        "recovered": 0,
        "blog_only": 0,
        "skipped_ok": 0,
        "no_scrape_data": 0,
        "errors": 0,
    }

    mode = "[DRY RUN] " if dry_run else ""

    with SyncSessionLocal() as db:
        jurisdictions = _get_jurisdictions(db, project_id)

        if not jurisdictions:
            logger.warning(f"No jurisdictions found for project {project_id}. Nothing to do.")
            return

        logger.info(
            f"{mode}Found {len(jurisdictions)} jurisdictions under project {project_id}"
        )
        logger.info("─" * 70)

        for jur in jurisdictions:
            jur_name = jur.name
            jur_id = jur.id
            try:
                ledger_count = _ledger_field_count(db, jur.id)
                existing_blog = _get_existing_blog(db, jur.id)
                blog_is_placeholder = (
                    existing_blog is not None
                    and existing_blog.content_hash == "placeholder"
                )
                blog_status = (
                    "placeholder" if blog_is_placeholder
                    else ("real" if existing_blog else "none")
                )

                # ── Case 1: Ledger has data and blog is real — nothing to do ──
                if ledger_count > 0 and not blog_is_placeholder:
                    logger.info(
                        f"[OK]     {jur.name} ({jur.id}): "
                        f"ledger={ledger_count} fields, blog={blog_status}. Skipping."
                    )
                    results["skipped_ok"] += 1
                    continue

                # ── Find the best scrape job with extracted KV data ──
                scrape_job = _get_best_scrape_job(db, jur.id)
                if not scrape_job:
                    logger.warning(
                        f"[NO DATA] {jur.name} ({jur.id}): "
                        "No completed scrape job with extracted_data found. Cannot recover."
                    )
                    results["no_scrape_data"] += 1
                    continue

                kv_pairs: dict = (
                    (scrape_job.extracted_data or {})
                    .get("extracted_data", {})
                    .get("key_value_pairs", {})
                )

                if not kv_pairs:
                    logger.warning(
                        f"[NO KV]  {jur.name} ({jur.id}): "
                        f"Scrape job {scrape_job.id} has empty key_value_pairs. Cannot recover."
                    )
                    results["no_scrape_data"] += 1
                    continue

                # ── Case 2: Ledger empty — seed it + regenerate blog ──
                if ledger_count == 0:
                    action = "Seed ledger + regenerate blog"
                    logger.info(
                        f"[RECOVER] {jur.name} ({jur.id}): "
                        f"ledger=empty, blog={blog_status}. "
                        f"{mode}{action} from job {scrape_job.id} "
                        f"({len(kv_pairs)} fields)."
                    )
                    if not dry_run:
                        state_service = JurisdictionStateService(db)
                        state_service.initialize_state(
                            jurisdiction_id=jur.id,
                            data=kv_pairs,
                            originating_job_id=scrape_job.id,
                            user_id=None,
                        )
                        db.commit()
                        logger.info(
                            f"          Ledger committed: {len(kv_pairs)} fields."
                        )

                        blog_service = BlogGenerationService(db)
                        blog_result = blog_service.generate_blog_post_sync(
                            jurisdiction_id=jur.id,
                            job_id=None,
                            skip_placeholder=True,
                        )
                        logger.info(
                            f"          Blog result: status={blog_result.get('status')}, "
                            f"version={blog_result.get('version')}."
                        )
                    results["recovered"] += 1

                # ── Case 3: Ledger has data but blog is still placeholder ──
                else:
                    action = "Regenerate blog only"
                    logger.info(
                        f"[BLOG]   {jur.name} ({jur.id}): "
                        f"ledger={ledger_count} fields, blog={blog_status}. "
                        f"{mode}{action}."
                    )
                    if not dry_run:
                        blog_service = BlogGenerationService(db)
                        blog_result = blog_service.generate_blog_post_sync(
                            jurisdiction_id=jur.id,
                            job_id=None,
                            skip_placeholder=True,
                        )
                        logger.info(
                            f"          Blog result: status={blog_result.get('status')}, "
                            f"version={blog_result.get('version')}."
                        )
                    results["blog_only"] += 1

            except Exception as exc:
                logger.error(
                    f"[ERROR]  {jur.name} ({jur_id}): {exc}",
                    exc_info=True,
                )
                try:
                    db.rollback()
                except Exception:
                    pass
                results["errors"] += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("─" * 70)
    logger.info(f"{mode}RECOVERY COMPLETE for project {project_id}")
    logger.info(f"  Ledger seeded + blog regenerated : {results['recovered']}")
    logger.info(f"  Blog regenerated (ledger was ok) : {results['blog_only']}")
    logger.info(f"  Already healthy (skipped)        : {results['skipped_ok']}")
    logger.info(f"  No scrape data (cannot recover)  : {results['no_scrape_data']}")
    logger.info(f"  Errors                           : {results['errors']}")
    logger.info("─" * 70)

    if dry_run:
        logger.info(
            "This was a DRY RUN — no data was written. "
            "Re-run without --dry-run to apply."
        )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Recover Coming Soon placeholder blogs by seeding the compliance ledger "
            "from existing scrape job data and regenerating blog posts."
        )
    )
    parser.add_argument(
        "--project-id",
        required=True,
        metavar="UUID",
        help="UUID of the project whose jurisdictions should be recovered.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be done without writing anything to the database.",
    )
    args = parser.parse_args()

    try:
        project_uuid = UUID(args.project_id)
    except ValueError:
        logger.error(f"Invalid UUID: {args.project_id!r}")
        sys.exit(1)

    recover_project(project_uuid, dry_run=args.dry_run)
