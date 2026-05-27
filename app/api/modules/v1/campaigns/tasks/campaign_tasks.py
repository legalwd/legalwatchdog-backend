"""Celery tasks for campaign orchestration pipeline."""

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis as sync_redis
import redis.asyncio as aioredis
from billiard.exceptions import SoftTimeLimitExceeded
from celery.result import AsyncResult
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.db.database import CeleryAsyncSessionLocal, SyncSessionLocal
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignStatus,
)
from app.api.modules.v1.campaigns.service.campaign_hydration_service import (
    CampaignHydrationService,
)
from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
    CampaignSourceDiscoveryService,
)
from app.api.modules.v1.campaigns.service.taxonomy_generation_service import (
    TaxonomyGenerationService,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
    DiscoveryStatus,
    Jurisdiction,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_state import JurisdictionState
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.scraping.service.source_verification_service import (
    SourceVerificationService,
)
from app.api.utils.celery_utils import retry_on_db_exhaustion, syncify
from app.celery_app import celery_app

logger = logging.getLogger(__name__)
AsyncSessionLocal = CeleryAsyncSessionLocal

_progress_pool = sync_redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=20,
    socket_connect_timeout=5,
    socket_timeout=5,
    socket_keepalive=True,
    retry_on_timeout=True,
    health_check_interval=30,
)
_sync_redis_client = sync_redis.Redis(connection_pool=_progress_pool)
FORCE_FAIL_AFTER_RETRIES = settings.CAMPAIGN_FORCE_FAIL_AFTER_RETRIES

# Lazy-initialized in _enqueue_sitemap_rebuild; declared at module level so
# tests can patch it before the first call.
sitemap_rebuild_debounced = None

_BILLING_ERROR_MARKERS = (
    "payment required",
    "http 402",
    "requires more credits",
    "upgrade to a paid account",
    "insufficient",
    "billing",
    "llm_billing_limit",
)


def _iter_exception_text(exc: Exception | None) -> list[str]:
    """Collect error strings from exception, cause chain, and context chain."""
    values: list[str] = []
    seen: set[int] = set()
    current = exc

    while current and id(current) not in seen:
        seen.add(id(current))
        text = str(current)
        if text:
            values.append(text)
        current = current.__cause__ or current.__context__

    return values


def _is_non_retryable_billing_error(exc: Exception) -> bool:
    """Return True when error text indicates upstream LLM billing exhaustion."""
    for text in _iter_exception_text(exc):
        normalized = text.lower()
        if any(marker in normalized for marker in _BILLING_ERROR_MARKERS):
            return True
    return False


def _classify_failure(exc: Exception) -> dict[str, object]:
    """Build frontend-friendly failure metadata for campaign task failures."""
    if _is_non_retryable_billing_error(exc):
        return {
            "category": "billing",
            "error_code": "LLM_BILLING_LIMIT",
            "message": (
                "Campaign failed because LLM credits are insufficient. "
                "Upgrade OpenRouter credits or reduce token limits."
            ),
            "retryable": False,
        }

    return {
        "category": "processing",
        "error_code": "CAMPAIGN_PIPELINE_FAILED",
        "message": "Campaign pipeline failed. Please review logs and retry.",
        "retryable": True,
    }


def _publish_progress(
    campaign_id: str,
    phase: str,
    completed: int,
    total: int,
    run_id: str | None = None,
    *,
    status: str | None = None,
    mode: str | None = None,
    failed: int | None = None,
    skipped: int | None = None,
) -> None:
    """Publish campaign progress to Redis Pub/Sub (best-effort)."""
    pct = (completed / total * 100) if total > 0 else 0.0
    payload = {
        "phase": phase,
        "completed": completed,
        "total": total,
        "pct": round(pct, 2),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if run_id:
        payload["run_id"] = run_id
    if status:
        payload["status"] = status
    if mode:
        payload["mode"] = mode
    if failed is not None:
        payload["failed"] = failed
    if skipped is not None:
        payload["skipped"] = skipped
    try:
        _sync_redis_client.publish(f"campaign_progress:{campaign_id}", json.dumps(payload))
    except Exception:
        logger.warning(
            "Failed to publish progress for campaign %s (phase=%s). Continuing.",
            campaign_id,
            phase,
            exc_info=True,
        )


def _make_async_redis_client() -> aioredis.Redis:
    """Create a scoped async Redis client for use within a single coroutine.

    Must be created inside the coroutine so its pool is bound to the correct
    event loop. Caller is responsible for ``await client.aclose()``.
    """
    pool = aioredis.ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5,
        socket_keepalive=True,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    return aioredis.Redis(connection_pool=pool)


def _enqueue_sitemap_rebuild() -> None:
    """Enqueue a debounced sitemap rebuild task."""
    global sitemap_rebuild_debounced
    if sitemap_rebuild_debounced is None:
        from app.api.modules.v1.jurisdictions.service.sitemap_tasks import (
            sitemap_rebuild_debounced as sitemap_task,
        )

        sitemap_rebuild_debounced = sitemap_task
    sitemap_rebuild_debounced.delay()


def _reset_campaign_status(campaign_id: str, status: CampaignStatus) -> None:
    """Reset a campaign to a specific status after a time-limit or retry event.

    This is a generic helper used by multiple tasks (taxonomy, discovery, etc.)
    to ensure the campaign status is correct before a retry is scheduled,
    preventing ``ResourceLockedError`` from the service layer's validation.

    Args:
        campaign_id: String UUID of the campaign to reset.
        status: The CampaignStatus to reset to.
    """
    try:
        with SyncSessionLocal() as db:
            campaign = db.get(Campaign, UUID(campaign_id))
            if campaign and campaign.status != status:
                campaign.status = status
                campaign.updated_at = datetime.now(timezone.utc)
                db.add(campaign)
                db.commit()
                logger.info(
                    "Reset campaign %s to %s for retry after time limit.",
                    campaign_id,
                    status.value,
                )
    except Exception as reset_err:
        logger.error(
            "Failed to reset campaign %s status to %s: %s",
            campaign_id,
            status.value,
            reset_err,
            exc_info=True,
        )


def _reset_campaign_for_discovery_retry(campaign_id: str) -> None:
    """Reset a FAILED or PAUSED campaign back to DISCOVERING_SOURCES.

    Called before scheduling a retry after SoftTimeLimitExceeded so that
    _validate_status() in the service layer does not block the next attempt.
    Uses the sync session to avoid any async/event-loop complications in the
    signal/exception handler context.

    Args:
        campaign_id: String UUID of the campaign to reset.
    """
    try:
        with SyncSessionLocal() as db:
            campaign = db.get(Campaign, UUID(campaign_id))
            if campaign and campaign.status in (
                CampaignStatus.FAILED,
                CampaignStatus.PAUSED,
                CampaignStatus.HYDRATING,
                CampaignStatus.DISCOVERING_SOURCES,  # already correct, still safe
            ):
                campaign.status = CampaignStatus.DISCOVERING_SOURCES
                campaign.updated_at = datetime.now(timezone.utc)
                db.add(campaign)
                db.commit()
                logger.info(
                    "Reset campaign %s to DISCOVERING_SOURCES for retry after time limit.",
                    campaign_id,
                )
    except Exception as reset_err:
        # Non-fatal: log and let the retry fire anyway; if status is wrong
        # the retry will raise ResourceLockedError and retry again after delay.
        logger.error(
            "Failed to reset campaign %s status for retry: %s",
            campaign_id,
            reset_err,
            exc_info=True,
        )


def _mark_campaign_phase_started(
    campaign_id: str,
    *,
    status: CampaignStatus,
    run_id: str | None = None,
) -> None:
    """Persist campaign phase transition and pipeline_control metadata eagerly."""
    try:
        with SyncSessionLocal() as db:
            campaign = db.get(Campaign, UUID(campaign_id))
            if campaign is None:
                return

            campaign.status = status
            campaign.updated_at = datetime.now(timezone.utc)

            stats = dict(campaign.stats) if isinstance(campaign.stats, dict) else {}
            pipeline_control = dict(stats.get("pipeline_control") or {})
            pipeline_control["last_started_status"] = status.value
            pipeline_control["updated_at"] = datetime.now(timezone.utc).isoformat()
            if run_id:
                pipeline_control["run_id"] = run_id
            stats["pipeline_control"] = pipeline_control
            campaign.stats = stats

            db.add(campaign)
            db.commit()
    except Exception as exc:
        logger.warning(
            "Failed to persist campaign phase transition for %s -> %s: %s",
            campaign_id,
            status.value,
            exc,
            exc_info=True,
        )


def _merge_content_pipeline_stats(
    stats: dict[str, object] | None,
    *,
    status: str,
    run_id: str | None = None,
    mode: str | None = None,
    generated_count: int | None = None,
    skipped_count: int | None = None,
    failed_count: int | None = None,
    eligible_jurisdictions: int | None = None,
    total_jurisdictions: int | None = None,
    error_summary: str | None = None,
) -> dict[str, object]:
    """Merge content pipeline metadata into campaign stats."""
    new_stats = dict(stats) if isinstance(stats, dict) else {}
    content_pipeline = dict(new_stats.get("content_pipeline") or {})
    content_pipeline["status"] = status
    content_pipeline["updated_at"] = datetime.now(timezone.utc).isoformat()

    if run_id is not None:
        content_pipeline["run_id"] = run_id
    if mode is not None:
        content_pipeline["mode"] = mode
    if generated_count is not None:
        content_pipeline["generated_count"] = generated_count
    if skipped_count is not None:
        content_pipeline["skipped_count"] = skipped_count
    if failed_count is not None:
        content_pipeline["failed_count"] = failed_count
    if eligible_jurisdictions is not None:
        content_pipeline["eligible_jurisdictions"] = eligible_jurisdictions
    if total_jurisdictions is not None:
        content_pipeline["total_jurisdictions"] = total_jurisdictions
    if error_summary is not None:
        content_pipeline["error_summary"] = error_summary

    new_stats["content_pipeline"] = content_pipeline
    return new_stats


def _persist_content_pipeline_stats(
    db,
    campaign: Campaign,
    *,
    status: str,
    run_id: str,
    mode: str,
    generated_count: int | None = None,
    skipped_count: int | None = None,
    failed_count: int | None = None,
    eligible_jurisdictions: int | None = None,
    total_jurisdictions: int | None = None,
    error_summary: str | None = None,
    countries: list[str] | None = None,
    states: list[str] | None = None,
) -> None:
    """Persist content pipeline fields on campaign.stats."""
    campaign.stats = _merge_content_pipeline_stats(
        campaign.stats,
        status=status,
        run_id=run_id,
        mode=mode,
        generated_count=generated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        eligible_jurisdictions=eligible_jurisdictions,
        total_jurisdictions=total_jurisdictions,
        error_summary=error_summary,
    )
    # Also merge countries and states into campaign.stats["content_pipeline"]
    if isinstance(campaign.stats, dict) and "content_pipeline" in campaign.stats:
        cp = dict(campaign.stats["content_pipeline"])
        if countries is not None:
            cp["target_countries"] = countries
        if states is not None:
            cp["target_states"] = states
        campaign.stats["content_pipeline"] = cp

    campaign.updated_at = datetime.now(timezone.utc)
    db.add(campaign)


@celery_app.task(
    bind=True,
    queue="processing",
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=settings.CAMPAIGN_TAXONOMY_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.CAMPAIGN_TAXONOMY_HARD_TIME_LIMIT_SECONDS,
)
def generate_taxonomy_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Task to generate campaign taxonomy.

    On ``SoftTimeLimitExceeded`` the campaign status is reset to
    ``GENERATING_TAXONOMY`` before the retry is scheduled so that
    subsequent attempts are not blocked by a stale status.
    """
    logger.info("generate_taxonomy_task started for campaign %s (run_id=%s)", campaign_id, run_id)
    _publish_progress(campaign_id, "taxonomy", 0, 1, run_id)

    try:

        async def run() -> dict:
            async with AsyncSessionLocal() as db:
                service = TaxonomyGenerationService(db)
                return await service.generate(UUID(campaign_id), run_id=run_id)

        result = syncify(run)()
        _publish_progress(campaign_id, "taxonomy", 1, 1, run_id)
        return {"status": "completed", "result": result}
    except SoftTimeLimitExceeded as e:
        logger.warning(
            "generate_taxonomy_task soft time limit exceeded for campaign %s. "
            "Resetting status and scheduling retry.",
            campaign_id,
        )
        _reset_campaign_status(campaign_id, CampaignStatus.GENERATING_TAXONOMY)
        raise self.retry(exc=e, countdown=120)
    except Exception as e:
        logger.error("generate_taxonomy_task failed: %s", e, exc_info=True)
        if _is_non_retryable_billing_error(e):
            logger.error(
                "generate_taxonomy_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        raise self.retry(exc=e)


def syncify_generate_blog(db, jurisdiction_id: UUID) -> dict:
    """Synchronous wrapper for BlogGenerationService.generate_blog_post_sync.

    Args:
        db: Sync SQLAlchemy session.
        jurisdiction_id: Jurisdiction to generate blog for.

    Returns:
        dict: Generation result with status, message, version.
    """
    from sqlalchemy.orm import selectinload
    from sqlmodel import select

    from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
        BlogGenerationService,
    )

    # Re-load jurisdiction with project.org eagerly
    jur_stmt = (
        select(Jurisdiction)
        .options(selectinload(Jurisdiction.project).selectinload(Project.organization))
        .where(Jurisdiction.id == jurisdiction_id)
    )
    jurisdiction = db.exec(jur_stmt).first()
    if not jurisdiction:
        return {
            "status": "failed",
            "jurisdiction_id": str(jurisdiction_id),
            "message": f"Jurisdiction {jurisdiction_id} not found",
            "version": None,
        }

    service = BlogGenerationService(db)
    try:
        return service.generate_blog_post_sync(jurisdiction_id, skip_placeholder=False)
    except Exception as e:
        logger.error("Blog generation failed for %s: %s", jurisdiction_id, e, exc_info=True)
        return {
            "status": "failed",
            "jurisdiction_id": str(jurisdiction_id),
            "message": str(e),
            "version": None,
        }


def _select_campaign_blog_target_ids(
    db,
    campaign_id: UUID,
    mode: str,
    countries: list[str] | None = None,
    states: list[str] | None = None,
) -> list[UUID]:
    """Return jurisdiction IDs that need campaign blog generation.

    Supports optional country/state filtering.
    """
    from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import (
        JurisdictionBlogPost,
    )

    if mode == "retry_failed":
        stmt = (
            select(Jurisdiction.id)
            .outerjoin(
                JurisdictionBlogPost,
                JurisdictionBlogPost.jurisdiction_id == Jurisdiction.id,
            )
            .where(Jurisdiction.campaign_id == campaign_id)
            .where(JurisdictionBlogPost.id.is_(None))
            .distinct()
        )
    elif mode == "backfill_missing":
        stmt = (
            select(Jurisdiction.id)
            .join(
                JurisdictionState,
                JurisdictionState.jurisdiction_id == Jurisdiction.id,
            )
            .where(Jurisdiction.campaign_id == campaign_id)
            .distinct()
        )
    else:
        stmt = (
            select(Jurisdiction.id)
            .join(
                JurisdictionState,
                JurisdictionState.jurisdiction_id == Jurisdiction.id,
            )
            .outerjoin(
                JurisdictionBlogPost,
                JurisdictionBlogPost.jurisdiction_id == Jurisdiction.id,
            )
            .where(Jurisdiction.campaign_id == campaign_id)
            .where(JurisdictionBlogPost.id.is_(None))
            .distinct()
        )

    all_eligible_ids = list(db.exec(stmt).all())
    if not all_eligible_ids:
        return []

    # If no country/state filters are active, return the full list immediately
    if not countries and not states:
        return all_eligible_ids

    # Memory-based hierarchical resolver for robust SQLite / Postgres compat
    # 1. Load all jurisdictions in the campaign to construct tree
    all_jur_stmt = select(Jurisdiction).where(Jurisdiction.campaign_id == campaign_id)
    jurisdictions = db.exec(all_jur_stmt).all()
    jur_map = {j.id: j for j in jurisdictions}

    # 2. Helper to traverse hierarchy and resolve (country_name, state_name)
    def resolve_hierarchy(jur) -> tuple[str | None, str | None]:
        curr = jur
        path = []
        while curr:
            path.append(curr)
            if curr.parent_id:
                curr = jur_map.get(curr.parent_id)
            else:
                curr = None

        country_name = path[-1].name if path else None
        state_name = path[-2].name if len(path) >= 2 else None
        return country_name, state_name

    # 3. Normalize filters using TaxonomyGeoValidator
    from app.api.modules.v1.campaigns.service.taxonomy_geo_validator import TaxonomyGeoValidator

    geo_validator = TaxonomyGeoValidator()

    normalized_countries = set()
    if countries:
        for c in countries:
            resolved = geo_validator._resolve_country(c)
            if resolved:
                normalized_countries.add(resolved["name"].upper())
                normalized_countries.add(resolved["iso_code"].upper())
            else:
                normalized_countries.add(c.strip().upper())

    normalized_states = set()
    if states:
        for s in states:
            normalized_states.add(s.strip().upper())

    # 4. Filter the eligible jurisdiction IDs
    filtered_ids = []
    for j_id in all_eligible_ids:
        j = jur_map.get(j_id)
        if not j:
            continue

        country_name, state_name = resolve_hierarchy(j)

        if normalized_countries:
            if not country_name or country_name.upper() not in normalized_countries:
                continue

        if normalized_states:
            if state_name:
                if state_name.upper() not in normalized_states:
                    continue
            else:
                if j.name.upper() not in normalized_states:
                    continue

        filtered_ids.append(j_id)

    return filtered_ids


@celery_app.task(bind=True, queue="processing", max_retries=3, default_retry_delay=60)
def generate_campaign_content_task(
    self,
    campaign_id: str,
    run_id: str | None = None,
    mode: str | None = None,
    countries: list[str] | None = None,
    states: list[str] | None = None,
) -> dict:
    """Generate or backfill blog posts for all campaign jurisdictions.

    Supports three modes:
    - run:           Process only jurisdictions that have state data.
    - retry_failed:  Re-attempt generation for jurisdictions that previously failed.
    - backfill_missing: Generate blogs for all jurisdictions with state, even if
                      a blog post already exists (to pick up updated content).

    Args:
        campaign_id: Campaign UUID string.
        run_id: Optional run identifier for tracking.
        mode: One of "run", "retry_failed", "backfill_missing".
        countries: Optional list of countries to filter by.
        states: Optional list of states to filter by.

    Returns:
        dict: Summary with success/failed counts.
    """
    logger.info(
        "generate_campaign_content_task started for campaign %s (run_id=%s, mode=%s)",
        campaign_id,
        run_id,
        mode,
    )

    effective_mode = mode or "run"
    effective_run_id = run_id or self.request.id or ""
    progress_phase = "content_generation"
    db_progress_update_interval = 5
    try:
        with SyncSessionLocal() as db:
            campaign = db.exec(select(Campaign).where(Campaign.id == UUID(campaign_id))).first()
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            campaign_uuid = UUID(campaign_id)
            all_jurisdiction_ids = list(
                db.exec(
                    select(Jurisdiction.id).where(Jurisdiction.campaign_id == campaign_uuid)
                ).all()
            )

            total_jurisdictions = len(all_jurisdiction_ids)
            if not all_jurisdiction_ids:
                logger.info("No jurisdictions found for campaign %s", campaign_id)
                _persist_content_pipeline_stats(
                    db,
                    campaign,
                    status="COMPLETED",
                    run_id=effective_run_id,
                    mode=effective_mode,
                    generated_count=0,
                    skipped_count=0,
                    failed_count=0,
                    eligible_jurisdictions=0,
                    total_jurisdictions=0,
                    countries=countries,
                    states=states,
                )
                db.commit()
                _publish_progress(
                    campaign_id,
                    progress_phase,
                    0,
                    0,
                    effective_run_id,
                    status="COMPLETED",
                    mode=effective_mode,
                    failed=0,
                    skipped=0,
                )
                return {
                    "status": "completed",
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                }

            target_ids = _select_campaign_blog_target_ids(
                db, campaign_uuid, effective_mode, countries, states
            )

            if not target_ids:
                logger.info(
                    "No jurisdictions need blog generation for campaign %s (mode=%s)",
                    campaign_id,
                    effective_mode,
                )
                _persist_content_pipeline_stats(
                    db,
                    campaign,
                    status="COMPLETED",
                    run_id=effective_run_id,
                    mode=effective_mode,
                    generated_count=0,
                    skipped_count=total_jurisdictions,
                    failed_count=0,
                    eligible_jurisdictions=0,
                    total_jurisdictions=total_jurisdictions,
                    countries=countries,
                    states=states,
                )
                db.commit()
                _publish_progress(
                    campaign_id,
                    progress_phase,
                    0,
                    0,
                    effective_run_id,
                    status="COMPLETED",
                    mode=effective_mode,
                    failed=0,
                    skipped=total_jurisdictions,
                )
                return {
                    "status": "completed",
                    "total": len(all_jurisdiction_ids),
                    "success": 0,
                    "failed": 0,
                    "skipped": len(all_jurisdiction_ids),
                }

            logger.info(
                "Generating blogs for %d jurisdictions (mode=%s, campaign=%s)",
                len(target_ids),
                effective_mode,
                campaign_id,
            )

            success_count = 0
            failed_count = 0
            runtime_skipped_count = 0
            total_targets = len(target_ids)
            baseline_skipped_count = total_jurisdictions - total_targets

            _persist_content_pipeline_stats(
                db,
                campaign,
                status="IN_PROGRESS",
                run_id=effective_run_id,
                mode=effective_mode,
                generated_count=0,
                skipped_count=baseline_skipped_count,
                failed_count=0,
                eligible_jurisdictions=total_targets,
                total_jurisdictions=total_jurisdictions,
                error_summary="",
                countries=countries,
                states=states,
            )
            db.commit()
            _publish_progress(
                campaign_id,
                progress_phase,
                0,
                total_targets,
                effective_run_id,
                status="IN_PROGRESS",
                mode=effective_mode,
                failed=0,
                skipped=baseline_skipped_count,
            )

            for jur_id in target_ids:
                result = syncify_generate_blog(db, jur_id)
                if result.get("status") in {"success", "placeholder"}:
                    success_count += 1
                elif result.get("status") == "failed":
                    failed_count += 1
                else:
                    runtime_skipped_count += 1

                completed = success_count + failed_count + runtime_skipped_count
                skipped_count = baseline_skipped_count + runtime_skipped_count

                _publish_progress(
                    campaign_id,
                    progress_phase,
                    completed,
                    total_targets,
                    effective_run_id,
                    status="IN_PROGRESS",
                    mode=effective_mode,
                    failed=failed_count,
                    skipped=skipped_count,
                )

                if completed % db_progress_update_interval == 0 or completed == total_targets:
                    _persist_content_pipeline_stats(
                        db,
                        campaign,
                        status="IN_PROGRESS",
                        run_id=effective_run_id,
                        mode=effective_mode,
                        generated_count=success_count,
                        skipped_count=skipped_count,
                        failed_count=failed_count,
                        eligible_jurisdictions=total_targets,
                        total_jurisdictions=total_jurisdictions,
                        countries=countries,
                        states=states,
                    )
                    db.commit()

            total = len(target_ids)
            skipped_total = baseline_skipped_count + runtime_skipped_count
            terminal_status = "COMPLETED_WITH_ERRORS" if failed_count else "COMPLETED"
            error_summary = (
                f"{failed_count} jurisdiction blog generation jobs failed." if failed_count else ""
            )

            _persist_content_pipeline_stats(
                db,
                campaign,
                status=terminal_status,
                run_id=effective_run_id,
                mode=effective_mode,
                generated_count=success_count,
                skipped_count=skipped_total,
                failed_count=failed_count,
                eligible_jurisdictions=total,
                total_jurisdictions=total_jurisdictions,
                error_summary=error_summary,
                countries=countries,
                states=states,
            )
            db.add(
                CampaignExecutionLog(
                    campaign_id=campaign.id,
                    phase=(
                        "content_pipeline_completed_with_errors"
                        if failed_count
                        else "content_pipeline_completed"
                    ),
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    error_log={
                        "run_id": effective_run_id,
                        "mode": effective_mode,
                        "generated_count": success_count,
                        "failed_count": failed_count,
                        "skipped_count": skipped_total,
                        "eligible_jurisdictions": total,
                        "total_jurisdictions": total_jurisdictions,
                        "message": error_summary,
                    },
                )
            )
            db.commit()

            _publish_progress(
                campaign_id,
                progress_phase,
                total,
                total,
                effective_run_id,
                status=terminal_status,
                mode=effective_mode,
                failed=failed_count,
                skipped=skipped_total,
            )
            logger.info(
                "generate_campaign_content_task completed for campaign %s: "
                "success=%d, failed=%d, total=%d",
                campaign_id,
                success_count,
                failed_count,
                total,
            )
            return {
                "status": "completed",
                "mode": effective_mode,
                "total": total,
                "success": success_count,
                "failed": failed_count,
                "skipped": skipped_total,
            }

    except Exception as e:
        logger.error(
            "generate_campaign_content_task failed for campaign %s: %s",
            campaign_id,
            e,
            exc_info=True,
        )
        error_summary = str(e)
        if self.request.retries >= self.max_retries or _is_non_retryable_billing_error(e):
            try:
                with SyncSessionLocal() as db:
                    campaign = db.exec(
                        select(Campaign).where(Campaign.id == UUID(campaign_id))
                    ).first()
                    if campaign:
                        existing_pipeline = (
                            campaign.stats.get("content_pipeline", {})
                            if isinstance(campaign.stats, dict)
                            else {}
                        )
                        generated_count = int(existing_pipeline.get("generated_count") or 0)
                        skipped_count = int(existing_pipeline.get("skipped_count") or 0)
                        failed_count = int(existing_pipeline.get("failed_count") or 0)
                        _persist_content_pipeline_stats(
                            db,
                            campaign,
                            status="FAILED",
                            run_id=effective_run_id,
                            mode=effective_mode,
                            generated_count=generated_count,
                            skipped_count=skipped_count,
                            failed_count=failed_count,
                            eligible_jurisdictions=existing_pipeline.get("eligible_jurisdictions")
                            if isinstance(existing_pipeline, dict)
                            else None,
                            total_jurisdictions=existing_pipeline.get("total_jurisdictions")
                            if isinstance(existing_pipeline, dict)
                            else None,
                            error_summary=error_summary,
                            countries=countries,
                            states=states,
                        )
                        db.add(
                            CampaignExecutionLog(
                                campaign_id=campaign.id,
                                phase="content_pipeline_failed",
                                started_at=datetime.now(timezone.utc),
                                completed_at=datetime.now(timezone.utc),
                                error_log={
                                    "run_id": effective_run_id,
                                    "mode": effective_mode,
                                    "generated_count": generated_count,
                                    "failed_count": failed_count,
                                    "skipped_count": skipped_count,
                                    "message": error_summary,
                                },
                            )
                        )
                        db.commit()
                    _publish_progress(
                        campaign_id,
                        progress_phase,
                        0,
                        0,
                        effective_run_id,
                        status="FAILED",
                        mode=effective_mode,
                        failed=None,
                        skipped=None,
                    )
            except Exception as persist_err:
                logger.warning(
                    "Failed to persist content pipeline failure metadata for campaign %s: %s",
                    campaign_id,
                    persist_err,
                    exc_info=True,
                )
        if _is_non_retryable_billing_error(e):
            raise
        if self.request.retries >= self.max_retries:
            raise
        raise self.retry(exc=e, countdown=120)


@celery_app.task(bind=True, queue="processing", max_retries=3, default_retry_delay=60)
def hydrate_campaign_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Task to hydrate campaign taxonomy into DB jurisdictions."""
    logger.info("hydrate_campaign_task started for campaign %s (run_id=%s)", campaign_id, run_id)
    _publish_progress(campaign_id, "hydration", 0, 1, run_id)

    try:

        async def run() -> int:
            async with AsyncSessionLocal() as db:
                service = CampaignHydrationService(db)
                jurisdiction_ids = await service.hydrate(UUID(campaign_id))
                return len(jurisdiction_ids)

        count = syncify(run)()
        _publish_progress(campaign_id, "hydration", count, count, run_id)
        return {"status": "completed", "jurisdictions_created_or_updated": count}
    except Exception as e:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return {"status": "retrying", "campaign_id": campaign_id}
        logger.error("hydrate_campaign_task failed: %s", e, exc_info=True)
        if _is_non_retryable_billing_error(e):
            logger.error(
                "hydrate_campaign_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    queue="processing",
    max_retries=3,
    default_retry_delay=120,
    # 32 jurisdictions × ~17s average = ~544s worst-case sequential.
    # Give 30 minutes of headroom so partial runs aren't killed mid-flight.
    # The hard time_limit adds a final safety net 5 minutes beyond that.
    soft_time_limit=settings.CAMPAIGN_SOURCE_DISCOVERY_SOFT_TIME_LIMIT_SECONDS,
    time_limit=settings.CAMPAIGN_SOURCE_DISCOVERY_HARD_TIME_LIMIT_SECONDS,
)
def discover_sources_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Discover scrape sources for every jurisdiction in a campaign.

    Bridge pattern: Celery prefork worker (sync) → ThreadPoolExecutor thread
    owning its own event loop → async CampaignSourceDiscoveryService.

    ``syncify()`` from ``celery_utils`` always runs the coroutine in a
    dedicated thread so the event loop is fully owned by that thread and
    SQLAlchemy's greenlet context is properly established.  The
    ``CeleryAsyncSessionLocal`` engine uses ``NullPool``, so connections are
    closed cleanly when the session exits — no cross-loop pool corruption.

    On ``SoftTimeLimitExceeded`` the campaign status is reset to
    ``DISCOVERING_SOURCES`` before the retry is scheduled so that
    ``_validate_status()`` in the service does not permanently block
    subsequent attempts with a ``ResourceLockedError``.
    """
    logger.info("discover_sources_task started for campaign %s (run_id=%s)", campaign_id, run_id)
    _mark_campaign_phase_started(
        campaign_id,
        status=CampaignStatus.DISCOVERING_SOURCES,
        run_id=run_id,
    )
    _publish_progress(campaign_id, "source_discovery", 0, 1, run_id)

    try:

        async def run() -> dict:
            async_redis = _make_async_redis_client()
            try:
                async with AsyncSessionLocal() as db:
                    service = CampaignSourceDiscoveryService(db, async_redis)
                    return await service.discover_all(UUID(campaign_id))
            finally:
                await async_redis.aclose()

        summary = syncify(run)()

        total = summary.get("total", 1)
        _publish_progress(campaign_id, "source_discovery", total, total, run_id)

        retry_unverified_sources_task.apply_async(
            args=[campaign_id, run_id],
            countdown=86400,  # 24 hours
        )
        logger.info(
            "Scheduled source verification retry for campaign %s in 24 hours.",
            campaign_id,
        )
        return {"status": "completed", "summary": summary}

    except SoftTimeLimitExceeded as e:
        logger.warning(
            "discover_sources_task soft time limit exceeded for campaign %s. "
            "Resetting status and scheduling retry.",
            campaign_id,
        )
        _reset_campaign_for_discovery_retry(campaign_id)
        raise self.retry(exc=e, countdown=120)

    except Exception as e:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return {"status": "retrying", "campaign_id": campaign_id}
        logger.error("discover_sources_task failed: %s", e, exc_info=True)
        if _is_non_retryable_billing_error(e):
            logger.error(
                "discover_sources_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        raise self.retry(exc=e)


@celery_app.task(bind=True, queue="processing", max_retries=3, default_retry_delay=60)
def dispatch_campaign_scrapes_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Task to enqueue scrape jobs for all campaign jurisdictions."""
    logger.info(
        "dispatch_campaign_scrapes_task started for campaign %s (run_id=%s)",
        campaign_id,
        run_id,
    )
    _publish_progress(campaign_id, "scraping_dispatch", 0, 1, run_id)

    try:
        with SyncSessionLocal() as db:
            campaign = db.exec(
                select(Campaign)
                .options(selectinload(Campaign.jurisdictions))
                .where(Campaign.id == UUID(campaign_id))
            ).first()

            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            eligible_jurisdictions = [
                j
                for j in campaign.jurisdictions
                if j.discovery_status == DiscoveryStatus.DISCOVERED
            ]

            if not eligible_jurisdictions:
                logger.error(
                    "No jurisdictions with discovered sources for campaign %s.",
                    campaign_id,
                )
                raise ProcessingError(
                    message=(
                        "Scraping dispatching failed: no jurisdictions have sources "
                        "to scrape. Please review source discovery results."
                    )
                )

            dispatched_count = 0
            for jurisdiction in eligible_jurisdictions:
                try:
                    celery_app.send_task(
                        "app.api.modules.v1.scraping.service.tasks."
                        "dispatch_single_jurisdiction_scrape",
                        args=[str(jurisdiction.id)],
                        queue="processing",
                    )
                    dispatched_count += 1
                except Exception as ex:
                    logger.warning(
                        "Failed to enqueue scrape dispatch for jurisdiction %s: %s",
                        jurisdiction.id,
                        ex,
                    )

            if dispatched_count == 0:
                logger.error(
                    "Failed to dispatch any scraping jobs for campaign %s despite %d eligible.",
                    campaign_id,
                    len(eligible_jurisdictions),
                )
                raise ProcessingError(
                    message=(
                        "Scraping dispatching failed: could not enqueue any scrape "
                        "jobs. Please check jurisdiction scraping service."
                    )
                )

            # Only transition to SCRAPING after dispatch succeeds
            campaign.status = CampaignStatus.SCRAPING
            campaign.updated_at = datetime.now(timezone.utc)
            db.add(campaign)
            db.commit()

        _publish_progress(
            campaign_id,
            "scraping_dispatch",
            dispatched_count,
            len(eligible_jurisdictions),
            run_id,
        )
        return {
            "status": "completed",
            "dispatched": dispatched_count,
            "eligible_jurisdictions": len(eligible_jurisdictions),
        }
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return {"status": "retrying", "campaign_id": campaign_id}
        raise
    except Exception as e:
        logger.error("dispatch_campaign_scrapes_task failed: %s", e, exc_info=True)
        if _is_non_retryable_billing_error(e):
            logger.error(
                "dispatch_campaign_scrapes_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        raise self.retry(exc=e)


@celery_app.task(bind=True, queue="processing", max_retries=120, default_retry_delay=30)
def publish_campaign_blogs_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Wait for jurisdiction scrapes to complete, then finalize campaign state."""
    logger.info(
        "publish_campaign_blogs_task started for campaign %s (run_id=%s)", campaign_id, run_id
    )

    try:
        from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignStatus
        from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
        from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
            JurisdictionScrapeJob,
            JurisdictionScrapeJobStatus,
        )

        with SyncSessionLocal() as db:
            campaign = db.exec(
                select(Campaign)
                .options(selectinload(Campaign.jurisdictions))
                .where(Campaign.id == UUID(campaign_id))
            ).first()

            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")

            db.expire_all()

            active_jobs = db.exec(
                select(JurisdictionScrapeJob)
                .join(Jurisdiction, Jurisdiction.id == JurisdictionScrapeJob.jurisdiction_id)
                .where(Jurisdiction.campaign_id == UUID(campaign_id))
                .where(
                    JurisdictionScrapeJob.status.notin_(
                        [
                            JurisdictionScrapeJobStatus.COMPLETED,
                            JurisdictionScrapeJobStatus.FAILED,
                        ]
                    )
                )
            ).all()

            if active_jobs:
                statuses = sorted({job.status.value for job in active_jobs})
                logger.info(
                    "Campaign %s: %d active scrape jobs (statuses: %s). Retrying in 30s.",
                    campaign_id,
                    len(active_jobs),
                    statuses,
                )
                if self.request.retries >= FORCE_FAIL_AFTER_RETRIES:
                    now = datetime.now(timezone.utc)
                    logger.warning(
                        "Campaign %s exceeded retry threshold (%d). Force-failing %d jobs.",
                        campaign_id,
                        FORCE_FAIL_AFTER_RETRIES,
                        len(active_jobs),
                    )
                    for stuck_job in active_jobs:
                        stuck_job.status = JurisdictionScrapeJobStatus.FAILED
                        stuck_job.error_message = (
                            "Force-failed: exceeded campaign completion timeout"
                        )
                        stuck_job.completed_at = now
                        db.add(stuck_job)
                    db.commit()
                else:
                    raise self.retry(countdown=30)

            logger.info("All scrape jobs completed for campaign %s. Finalizing.", campaign_id)

            all_scrape_jobs = db.exec(
                select(JurisdictionScrapeJob)
                .join(Jurisdiction, Jurisdiction.id == JurisdictionScrapeJob.jurisdiction_id)
                .where(Jurisdiction.campaign_id == UUID(campaign_id))
            ).all()

            if not all_scrape_jobs:
                logger.error(
                    "No scrape jobs were created for campaign %s. Cannot mark as MONITORING.",
                    campaign_id,
                )
                raise ProcessingError(
                    message=(
                        "Campaign finalization failed: no scrape jobs were created. "
                        "This indicates a failure in earlier pipeline phases."
                    )
                )

            failed_jobs = [
                job for job in all_scrape_jobs if job.status == JurisdictionScrapeJobStatus.FAILED
            ]
            if failed_jobs:
                logger.warning(
                    "Campaign %s completed pipelines but %d jurisdictions FAILED.",
                    campaign_id,
                    len(failed_jobs),
                )
                exec_log = CampaignExecutionLog(
                    campaign_id=campaign.id,
                    phase="pipeline_completed_with_errors",
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    error_log={
                        "run_id": run_id,
                        "failed_jurisdiction_count": len(failed_jobs),
                        "message": "Some jurisdiction tasks failed during extraction.",
                        "failed_job_ids": [str(job.id) for job in failed_jobs],
                    },
                )
                db.add(exec_log)

            campaign.status = CampaignStatus.MONITORING
            campaign.updated_at = datetime.now(timezone.utc)
            db.add(campaign)
            db.commit()

            _enqueue_sitemap_rebuild()

        return {"status": "completed", "message": "Campaign advanced to MONITORING"}
    except OperationalError:
        if retry_on_db_exhaustion(self, initial_delay=15, max_retries=3):
            return {"status": "retrying", "campaign_id": campaign_id}
        raise
    except Exception as e:
        if type(e).__name__ == "Retry":
            raise
        logger.error("publish_campaign_blogs_task failed: %s", e, exc_info=True)
        if _is_non_retryable_billing_error(e):
            logger.error(
                "publish_campaign_blogs_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True)
def campaign_pipeline_error_handler(
    self,
    str_campaign_id: str,
    run_id: str | None,
    task_id: str,
) -> None:
    """Shared on-error callback for campaign pipeline tasks."""
    result = AsyncResult(task_id)
    exc = result.result if result.failed() else None
    tb = result.traceback if result.failed() else None

    if not str_campaign_id:
        logger.error(
            (
                "campaign_pipeline_error_handler called without campaign_id. "
                "Task: %s, Error: %s, run_id=%s"
            ),
            task_id,
            exc,
            run_id,
        )
        return

    logger.error(
        "Campaign pipeline failed for %s. Task: %s, Error: %s, run_id=%s",
        str_campaign_id,
        task_id,
        exc,
        run_id,
    )

    failure = _classify_failure(exc if isinstance(exc, Exception) else Exception(str(exc)))

    try:
        with SyncSessionLocal() as db:
            campaign = db.get(Campaign, UUID(str_campaign_id))
            if campaign:
                campaign.status = CampaignStatus.FAILED
                campaign.updated_at = datetime.now(timezone.utc)

                stats = dict(campaign.stats) if isinstance(campaign.stats, dict) else {}
                pipeline_control = dict(stats.get("pipeline_control") or {})
                pipeline_control["failure"] = failure
                if run_id:
                    pipeline_control["run_id"] = run_id
                pipeline_control["updated_at"] = datetime.now(timezone.utc).isoformat()
                stats["pipeline_control"] = pipeline_control
                campaign.stats = stats
                db.add(campaign)

                exec_log = CampaignExecutionLog(
                    campaign_id=campaign.id,
                    phase="pipeline_error",
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    error_log={
                        "run_id": run_id,
                        "task_id": task_id,
                        "failure": failure,
                        "exception": str(exc),
                        "traceback": str(tb),
                    },
                )
                db.add(exec_log)
                db.commit()
    except Exception as db_e:
        logger.error(
            "Failed to update campaign status in error handler for %s: %s",
            str_campaign_id,
            db_e,
        )


@celery_app.task(bind=True, queue="processing", max_retries=3, default_retry_delay=60)
def retry_unverified_sources_task(self, campaign_id: str, run_id: str | None = None) -> dict:
    """Retry verification of sources that failed due to retryable errors.

    Scheduled 24 hours after discovery completes. Finds sources with retryable
    verification failures and attempts re-verification with fresh user-agents.
    """
    from app.api.modules.v1.campaigns.models.campaign_model import Campaign
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.scraping.service.source_verification_service import VerificationStatus

    try:
        campaign_uuid = UUID(campaign_id)
    except (ValueError, TypeError):
        logger.error("Invalid campaign_id format: %s", campaign_id)
        raise

    try:
        # Phase 1: load source IDs synchronously — do NOT pass ORM objects
        # across session boundaries; extract primitives only.
        with SyncSessionLocal() as db:
            campaign = db.exec(select(Campaign).where(Campaign.id == campaign_uuid)).first()
            if not campaign:
                logger.error("Campaign not found: %s", campaign_id)
                raise ProcessingError(message=f"Campaign {campaign_id} not found")

            retryable_statuses = [
                VerificationStatus.BLOCKED_BY_BOT_PROTECTION.value,
                VerificationStatus.TIMEOUT.value,
                VerificationStatus.UNVERIFIED_RETRYABLE.value,
            ]
            unverified_sources = db.exec(
                select(Source)
                .join(Jurisdiction, Source.jurisdiction_id == Jurisdiction.id)
                .where(
                    Jurisdiction.campaign_id == campaign_uuid,
                    Source.verification_status.in_(retryable_statuses),
                    Source.verification_attempts < 3,
                )
            ).all()

            if not unverified_sources:
                logger.info("No unverified sources to retry for campaign %s", campaign_id)
                return {"retried_count": 0, "success_count": 0, "failure_count": 0}

            # Extract IDs only — never pass live ORM objects out of a sync session
            # into an async session; they're detached and will raise on attribute access.
            source_ids = [s.id for s in unverified_sources]

        logger.info(
            "Retrying verification for %d sources in campaign %s (run_id=%s)",
            len(source_ids),
            campaign_id,
            run_id,
        )

        # Phase 2: async re-verification in its own properly scoped session.
        async def run_retry() -> dict:
            async with AsyncSessionLocal() as db:
                return await _retry_sources_async(db, source_ids, campaign_uuid)

        results = syncify(run_retry)()
        logger.info("Retry completed for campaign %s (run_id=%s): %s", campaign_id, run_id, results)
        return results

    except Exception as e:
        logger.error(
            "Retry verification task failed for campaign %s: %s",
            campaign_id,
            e,
            exc_info=True,
        )
        if _is_non_retryable_billing_error(e):
            logger.error(
                "retry_unverified_sources_task encountered non-retryable billing failure "
                "for campaign %s (run_id=%s).",
                campaign_id,
                run_id,
            )
            raise
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=300)
        raise


async def _retry_sources_async(
    db_session,
    source_ids: list,
    campaign_id: UUID,
) -> dict:
    """Async helper: re-verify a batch of sources by ID within a fresh session.

    Receives primitive IDs (not ORM objects) so there are no detached-instance
    issues when crossing the sync/async session boundary.

    Args:
        db_session: Async database session (owned by this coroutine).
        source_ids: List of source UUIDs to reload and re-verify.
        campaign_id: Campaign UUID for logging context.

    Returns:
        dict: ``{retried_count, success_count, failure_count}``
    """
    from sqlmodel import select

    from app.api.modules.v1.scraping.service.source_verification_service import (
        VerificationStatus,
    )

    if not source_ids:
        return {"retried_count": 0, "success_count": 0, "failure_count": 0}

    verification_svc = SourceVerificationService()
    success_count = 0
    failure_count = 0

    # Single batch load — objects bound to THIS async session, no detachment issues.
    result = await db_session.execute(select(Source).where(Source.id.in_(source_ids)))
    sources = result.scalars().all()

    for source in sources:
        try:
            verification_result = await verification_svc.verify_single(
                url=source.url,
                attempt_count=source.verification_attempts + 1,
            )
            source.verification_status = verification_result.status.value
            source.verification_attempts += 1
            source.last_verification_at = datetime.now(timezone.utc)
            db_session.add(source)

            if verification_result.status == VerificationStatus.VERIFIED:
                success_count += 1
                logger.info(
                    "Source %s verified successfully after retry (campaign %s)",
                    source.url,
                    campaign_id,
                )
            else:
                logger.debug(
                    "Source %s still failed verification: %s (campaign %s)",
                    source.url,
                    verification_result.status.value,
                    campaign_id,
                )
                failure_count += 1

        except Exception as e:
            logger.error(
                "Failed to retry verification for source %s (campaign %s): %s",
                source.id,
                campaign_id,
                e,
                exc_info=True,
            )
            failure_count += 1

    try:
        await db_session.commit()
    except Exception as e:
        logger.error(
            "Commit failed for retry verification (campaign %s): %s",
            campaign_id,
            e,
            exc_info=True,
        )
        await db_session.rollback()
        raise

    return {
        "retried_count": len(sources),
        "success_count": success_count,
        "failure_count": failure_count,
    }


@celery_app.task(bind=True)
def detect_zombie_campaigns(self) -> str:
    """Find campaigns stuck in transitional states beyond the expected timeout.

    Celery Beat task that runs periodically to recover campaigns that may have
    been abandoned due to worker crashes, soft-time-limit resets that fired
    before retry enqueue, or other infrastructure failures.

    Returns:
        str: Status message with count of recovered campaigns.
    """
    try:
        with SyncSessionLocal() as db:
            threshold_seconds = settings.CAMPAIGN_ZOMBIE_DETECTION_THRESHOLD_SECONDS
            threshold = datetime.now(timezone.utc) - timedelta(seconds=threshold_seconds)

            transitional_statuses = [
                CampaignStatus.GENERATING_TAXONOMY.value,
                CampaignStatus.HYDRATING.value,
                CampaignStatus.DISCOVERING_SOURCES.value,
                CampaignStatus.SCRAPING.value,
                CampaignStatus.PUBLISHING.value,
            ]

            zombies = db.exec(
                select(Campaign).where(
                    Campaign.status.in_(transitional_statuses),
                    Campaign.updated_at <= threshold,
                )
            ).all()

            recovered = 0
            for campaign in zombies:
                original_status = campaign.status.value
                logger.warning(
                    "Zombie campaign detected: %s (status=%s, last_updated=%s). "
                    "Preserving phase for phase-aware recovery.",
                    campaign.id,
                    original_status,
                    campaign.updated_at,
                )
                # Keep the current status so resume starts from the right phase.
                # Clear pipeline_control so stale task IDs and run history
                # don't block a new pipeline launch.
                campaign.updated_at = datetime.now(timezone.utc)

                if isinstance(campaign.stats, dict):
                    stats = dict(campaign.stats)
                    stats.pop("pipeline_control", None)
                    campaign.stats = stats

                db.add(campaign)
                recovered += 1

            if recovered:
                db.commit()
                logger.info("Recovered %d zombie campaign(s)", recovered)
            else:
                logger.debug("No zombie campaigns detected")

            return f"Zombie detection: {recovered} campaign(s) recovered."

    except Exception as e:
        logger.error(f"Zombie campaign detection failed: {e}", exc_info=True)
        return "Zombie detection: error occurred."
