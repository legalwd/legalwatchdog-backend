"""Celery tasks for sitemap generation and debounced rebuilds."""

import redis

from app.api.core.config import settings
from app.api.core.logger import logger
from app.api.utils.celery_utils import syncify
from app.api.utils.sitemap_service import SitemapService
from app.celery_app import celery_app


@celery_app.task(name="sitemap_rebuild_debounced")
def sitemap_rebuild_debounced() -> dict:
    """Rebuild sitemap files with Redis-based debouncing.

    Uses lock key ``sitemap_rebuild_lock`` with TTL 300s.
    If lock is already held, the task exits silently.

        Debounce semantics:
        - By default (`SITEMAP_RELEASE_LOCK_AFTER_RUN=False`) the lock TTL acts as
            a rate-limit window: once a rebuild starts, no further rebuilds will run
            for the remainder of the TTL (prevents frequent rebuilds).
        - If `SITEMAP_RELEASE_LOCK_AFTER_RUN=True`, the task will delete the lock
            after a successful run which allows subsequent triggers to schedule
            another rebuild immediately. Use this to "coalesce" triggers in a
            different way (keep lock only for the duration of the running task).
    """
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    lock_key = "sitemap_rebuild_lock"

    try:
        acquired = redis_client.set(lock_key, "1", nx=True, ex=300)
        if not acquired:
            logger.info("Sitemap rebuild skipped: lock already held")
            return {"status": "skipped", "reason": "lock_held"}

        syncify(SitemapService().write_all)()
        logger.info("Sitemap rebuild completed")

        try:
            if getattr(settings, "SITEMAP_RELEASE_LOCK_AFTER_RUN", False):
                redis_client.delete(lock_key)
                logger.debug("Sitemap rebuild lock released after successful run")
        except Exception:
            logger.warning("Failed to release sitemap rebuild lock", exc_info=True)
        return {"status": "rebuilt"}
    finally:
        redis_client.close()
