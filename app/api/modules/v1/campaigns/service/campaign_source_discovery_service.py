"""Campaign source discovery service.

Batch discovers and creates sources for campaign jurisdictions.
"""

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

import redis.asyncio as redis
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ProcessingError,
    ResourceLockedError,
)
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignExecutionLog,
    CampaignStatus,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
    DiscoveryStatus,
    Jurisdiction,
)
from app.api.modules.v1.scraping.schemas.source_service import SourceCreate
from app.api.modules.v1.scraping.service.source_discovery_service import SourceDiscoveryService
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.scraping.validators.exception import DuplicateSourceError

logger = logging.getLogger("app")

_PROGRESS_COMMIT_INTERVAL = 10
_RATE_LIMIT_WINDOW_SECONDS = 60
_INTER_JURISDICTION_DELAY_DEFAULT = 0.5
_MAX_RATE_LIMIT_RETRIES = 3  # Default max retries for rate limit backoff

# Allow override via settings for production use
INTER_JURISDICTION_DELAY_SECONDS = (
    settings.CAMPAIGN_SOURCE_DISCOVERY_INTER_JURISDICTION_DELAY_SECONDS
    or _INTER_JURISDICTION_DELAY_DEFAULT
)

# Expose rate limit max retries for tests
RATE_LIMIT_MAX_RETRIES = (
    settings.CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_RETRIES or _MAX_RATE_LIMIT_RETRIES
)
_RATE_LIMIT_ACQUIRE_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = redis.call('GET', key)

if not current then
    redis.call('SET', key, 1, 'EX', window)
    return 1
end

current = tonumber(current)
if current < limit then
    redis.call('INCR', key)
    return 1
end

return 0
"""


class CampaignSourceDiscoveryService:
    """Discovers and auto-accepts sources for all jurisdictions in a campaign.

    Wraps ``SourceDiscoveryService.suggest_sources()`` in a batch driver with
    Redis-backed sliding-window rate limiting and per-jurisdiction failure
    isolation.

    Root cause of the previous greenlet error
    ------------------------------------------
    After ``await self.db.flush()`` (or any DB write), SQLAlchemy marks all
    ORM objects in the session as *expired*.  When code later accesses an
    attribute on one of those objects (e.g. ``jurisdiction.discovery_status``),
    SQLAlchemy tries to issue a lazy SELECT to refresh it.  In an async session
    that lazy load requires the greenlet context established by
    ``AsyncSession``'s internal machinery — if the access happens outside that
    context (which can occur when objects are held in plain Python dicts and
    accessed after an intervening flush), the
    ``greenlet_spawn has not been called; can't call await_only() here`` error
    is raised.

    The fix is two-pronged:
    1. Store only *primitive* snapshots (IDs, names, strings) in the batch
       loop's dict — never raw ORM objects that might be expired mid-loop.
    2. Re-fetch the jurisdiction ORM object from the session immediately before
       writing to it, so we always operate on a live, in-session instance.

    Attributes:
        db: Async database session.
        redis_client: Async Redis client for rate limiting.
    """

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis_client = redis_client

    @staticmethod
    def _checkpoint_key(campaign_id: UUID) -> str:
        return f"campaign:discovery:{campaign_id}"

    async def _load_checkpoints(self, campaign_id: UUID) -> set[str]:
        members = await self.redis_client.smembers(self._checkpoint_key(campaign_id))
        return {m.decode() if isinstance(m, bytes) else m for m in members}

    async def _save_checkpoint(self, campaign_id: UUID, jurisdiction_id: UUID) -> None:
        key = self._checkpoint_key(campaign_id)
        await self.redis_client.sadd(key, str(jurisdiction_id))
        await self.redis_client.expire(key, 86400 * 7)

    async def _clear_checkpoints(self, campaign_id: UUID) -> None:
        await self.redis_client.delete(self._checkpoint_key(campaign_id))

    @staticmethod
    def _normalize_concurrency_value(value: int) -> int:
        """Normalize configured concurrency to a safe positive integer.

        Args:
            value: Configured concurrency value.

        Returns:
            int: Normalized concurrency, minimum of ``1``.

        Raises:
            ValueError: If ``value`` is not an integer.

        Examples:
            >>> CampaignSourceDiscoveryService._normalize_concurrency_value(5)
            5
        """
        if not isinstance(value, int):
            raise ValueError("Concurrency value must be an integer.")
        return max(1, value)

    async def discover_all(self, campaign_id: UUID) -> dict:
        """Batch-discover sources for every jurisdiction in a campaign.

        Uses Redis checkpointing to resume interrupted runs without
        re-discovering already-processed jurisdictions.

        Args:
            campaign_id: Primary key of the campaign.

        Returns:
            dict: Summary ``{total, discovered, failed, sources_created, skipped_duplicate}``.

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in an eligible status.
            ProcessingError: Fatal error; campaign set to ``FAILED``.
        """
        campaign = await self._load_campaign_with_jurisdictions(campaign_id)
        self._validate_status(campaign)

        now = datetime.now(timezone.utc)
        campaign.status = CampaignStatus.DISCOVERING_SOURCES
        campaign.updated_at = now
        self.db.add(campaign)
        await self.db.flush()

        jurisdictions = campaign.jurisdictions
        eligible_statuses = {
            DiscoveryStatus.PENDING,
            DiscoveryStatus.DISCOVERY_FAILED,
        }
        eligible_jurisdictions = [
            jurisdiction
            for jurisdiction in jurisdictions
            if jurisdiction.discovery_status in eligible_statuses
        ]
        skipped_already_processed = len(jurisdictions) - len(eligible_jurisdictions)

        # ── KEY FIX ──────────────────────────────────────────────────────────
        # Extract primitives from campaign BEFORE the loop to prevent accessing
        # expired ORM objects later. After flush() or rollback(), the campaign
        # object expires in the session. Accessing campaign.sources_per_jurisdiction
        # would trigger lazy load outside greenlet context → greenlet error.
        # ─────────────────────────────────────────────────────────────────────
        sources_per_jurisdiction = campaign.sources_per_jurisdiction
        campaign_name = campaign.name

        # Store only primitive values from ORM objects BEFORE the first flush.
        # After flush(), SQLAlchemy expires all in-session objects.  Accessing
        # any attribute on an expired ORM object from a plain dict triggers a
        # lazy load, which fails in async context with the greenlet error.
        # We keep the jurisdiction UUID so we can re-fetch the live ORM object
        # later when we need to write back to it.
        jurisdiction_snapshots = [
            {
                "id": j.id,  # UUID — primitive, safe to hold
                "id_str": str(j.id),
                "name": j.name,  # str — copied, not a lazy attr
                "description": j.description,  # str
                "prompt": j.prompt,  # str
                "campaign_name": campaign_name,  # Use extracted primitive
            }
            for j in eligible_jurisdictions
        ]

        if skipped_already_processed > 0:
            logger.info(
                "Skipping %d already-processed jurisdictions for campaign %s.",
                skipped_already_processed,
                campaign_id,
            )

        # Checkpoint: load previously completed jurisdictions from Redis so
        # an interrupted run can resume without re-discovering them.
        checkpointed = await self._load_checkpoints(campaign_id)
        jurisdiction_snapshots = [
            snap for snap in jurisdiction_snapshots if snap["id_str"] not in checkpointed
        ]
        skipped_checkpointed = len(checkpointed)
        if skipped_checkpointed > 0:
            logger.info(
                "Resuming campaign %s: %d jurisdictions already checkpointed.",
                campaign_id,
                skipped_checkpointed,
            )

        exec_log = CampaignExecutionLog(
            campaign_id=campaign_id,
            phase="source_discovery",
            started_at=now,
            total_items=len(jurisdiction_snapshots),
            completed_items=0,
            failed_items=0,
            error_log={},
        )
        self.db.add(exec_log)
        await self.db.flush()

        # Commit the phase transition and initial execution log immediately so
        # status is not left as HYDRATING if the worker is terminated mid-run.
        await self.db.commit()
        await self.db.refresh(campaign)
        await self.db.refresh(exec_log)

        total_sources_created = 0
        skipped_duplicate = 0
        completed = 0
        failed = 0
        error_details: Dict[str, Any] = {}

        try:
            concurrency = self._normalize_concurrency_value(
                settings.CAMPAIGN_SOURCE_DISCOVERY_CONCURRENCY
            )
            semaphore = asyncio.Semaphore(concurrency)

            search_results = await self._discover_sources_parallel(
                jurisdiction_snapshots=jurisdiction_snapshots,
                campaign_id=campaign_id,
                sources_per_jurisdiction=sources_per_jurisdiction,
                semaphore=semaphore,
            )

            source_svc = SourceService()

            for idx, jur_snap in enumerate(jurisdiction_snapshots):
                jur_id_str = jur_snap["id_str"]
                jur_name = jur_snap["name"]
                discovered = search_results.get(jur_id_str)

                if discovered is None:
                    failed += 1
                    error_details[jur_id_str] = {
                        "name": jur_name,
                        "error": "No discovery result returned.",
                    }
                    await self._mark_jurisdiction_failed(jurisdiction_id=jur_snap["id"])
                elif discovered["error"] is not None:
                    failed += 1
                    error_details[jur_id_str] = {
                        "name": jur_name,
                        "error": str(discovered["error"])[:500],
                    }
                    logger.warning(
                        "Source discovery failed for jurisdiction %s (%s): %s",
                        jur_id_str,
                        jur_name,
                        discovered["error"],
                    )
                    await self._mark_jurisdiction_failed(jurisdiction_id=jur_snap["id"])
                else:
                    try:
                        created, dupes, discovery_status = await self._persist_discovered_sources(
                            jurisdiction_snap=jur_snap,
                            suggested_sources=discovered["suggested_sources"],
                            source_svc=source_svc,
                        )
                        total_sources_created += created
                        skipped_duplicate += dupes
                        if discovery_status in (
                            DiscoveryStatus.DISCOVERED,
                            DiscoveryStatus.REQUIRES_MANUAL_SOURCES,
                        ):
                            completed += 1
                            await self._save_checkpoint(campaign_id, jur_snap["id"])
                        else:
                            failed += 1
                            error_details[jur_id_str] = {
                                "name": jur_name,
                                "error": "No sources found after fallback queries.",
                            }
                    except Exception as exc:
                        failed += 1
                        error_details[jur_id_str] = {
                            "name": jur_name,
                            "error": str(exc)[:500],
                        }
                        logger.warning(
                            "Source persistence failed for jurisdiction %s (%s): %s",
                            jur_id_str,
                            jur_name,
                            exc,
                        )
                        await self._mark_jurisdiction_failed(jurisdiction_id=jur_snap["id"])

                exec_log.completed_items = completed
                exec_log.failed_items = failed
                exec_log.error_log = error_details if error_details else None
                self.db.add(exec_log)
                await self.db.flush()

                # Persist incremental progress periodically so retries can resume
                # from already-processed jurisdictions after interruptions.
                if (idx + 1) % _PROGRESS_COMMIT_INTERVAL == 0:
                    await self.db.commit()
                    await self.db.refresh(exec_log)

            completed_at = datetime.now(timezone.utc)
            exec_log.completed_at = completed_at
            self.db.add(exec_log)

            # Re-fetch campaign to avoid stale/expired state after many flushes
            await self.db.refresh(campaign)
            campaign_stats = campaign.stats or {}
            campaign.stats = {
                **campaign_stats,
                "source_discovery_completed_at": completed_at.isoformat(),
                "total_sources_created": total_sources_created,
                "source_discovery_failed": failed,
            }
            campaign.updated_at = completed_at
            self.db.add(campaign)

            await self.db.commit()

            # All jurisdictions processed — clear Redis checkpoints.
            await self._clear_checkpoints(campaign_id)

            summary = {
                "total": len(jurisdictions),
                "eligible_for_discovery": len(eligible_jurisdictions),
                "skipped_already_processed": skipped_already_processed,
                "skipped_checkpointed": skipped_checkpointed,
                "discovered": completed,
                "failed": failed,
                "sources_created": total_sources_created,
                "skipped_duplicate": skipped_duplicate,
            }

            if jurisdiction_snapshots and failed == len(jurisdiction_snapshots):
                logger.error(
                    "Source discovery failed for ALL jurisdictions in campaign %s.",
                    campaign_id,
                )
                raise ProcessingError(
                    message=(
                        "Source discovery failed for all jurisdictions. "
                        "Campaign cannot proceed to scraping phase."
                    )
                )

            logger.info(
                "Source discovery complete for campaign %s: %s",
                campaign_id,
                summary,
            )
            return summary

        except (ResourceLockedError, NotFoundError):
            raise
        except Exception as exc:
            logger.exception(
                "Source discovery failed fatally for campaign %s: %s",
                campaign_id,
                exc,
            )
            try:
                campaign.status = CampaignStatus.FAILED
                campaign.updated_at = datetime.now(timezone.utc)
                self.db.add(campaign)
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            await self._clear_checkpoints(campaign_id)
            raise ProcessingError(f"Source discovery failed. {exc}")

    async def discover_for_jurisdiction(
        self,
        jurisdiction_id: UUID,
        campaign_id: UUID,
    ) -> List[UUID]:
        """Discover and create sources for a single jurisdiction.

        Args:
            jurisdiction_id: Target jurisdiction primary key.
            campaign_id: Owning campaign primary key.

        Returns:
            List[UUID]: IDs of sources created (excludes duplicates).
        """
        campaign = await self._load_campaign(campaign_id)
        jurisdiction = await self._load_jurisdiction(jurisdiction_id, campaign_id)

        source_discovery_svc = SourceDiscoveryService(db_session=None)
        source_svc = SourceService()

        try:
            suggested = await self._suggest_sources_with_fallback(
                jurisdiction=jurisdiction,
                campaign_name=campaign.name,
                campaign_id=campaign_id,
                max_results=campaign.sources_per_jurisdiction,
                source_discovery_svc=source_discovery_svc,
            )

            source_ids: List[UUID] = []
            duplicate_count = 0
            for source in suggested:
                try:
                    created = await source_svc.create_source(
                        db=self.db,
                        source_data=SourceCreate(
                            jurisdiction_id=jurisdiction_id,
                            name=source.title,
                            url=source.url,
                        ),
                        strict_validation=False,
                    )
                    source_ids.append(created.id)
                except DuplicateSourceError:
                    duplicate_count += 1
                    logger.debug(
                        "Skipped duplicate source: %s for jurisdiction %s",
                        source.url,
                        jurisdiction_id,
                    )
                except HTTPException:
                    logger.debug(
                        "Skipped invalid source: %s for jurisdiction %s",
                        source.url,
                        jurisdiction_id,
                    )

            # Re-fetch fresh from database, bypassing identity map cache
            # which may contain stale/expired objects after rollbacks from SourceService
            result = await self.db.execute(
                select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            )
            live_jurisdiction = result.scalar_one_or_none()
            if live_jurisdiction:
                live_jurisdiction.discovery_status = self._resolve_discovery_status(
                    created_count=len(source_ids),
                    duplicate_count=duplicate_count,
                )
                self.db.add(live_jurisdiction)
            await self.db.commit()

            return source_ids

        except Exception:
            result = await self.db.execute(
                select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
            )
            live_jurisdiction = result.scalar_one_or_none()
            if live_jurisdiction:
                live_jurisdiction.discovery_status = DiscoveryStatus.DISCOVERY_FAILED
                self.db.add(live_jurisdiction)
                await self.db.commit()
            raise

        finally:
            await source_discovery_svc.close()

    async def _discover_sources_parallel(
        self,
        jurisdiction_snapshots: List[dict],
        campaign_id: UUID,
        sources_per_jurisdiction: int,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Dict[str, Optional[Any]]]:
        """Discover suggested sources concurrently for multiple jurisdictions.

        Args:
            jurisdiction_snapshots: Jurisdiction primitive snapshots.
            campaign_id: Owning campaign ID.
            sources_per_jurisdiction: Maximum number of sources per jurisdiction.
            semaphore: Concurrency guard for external search requests.

        Returns:
            Dict[str, Dict[str, Optional[Any]]]: Per-jurisdiction discovery results.

        Raises:
            ProcessingError: If creating the discovery service fails.

        Examples:
            >>> service = CampaignSourceDiscoveryService(db, redis_client)
            >>> sem = asyncio.Semaphore(2)
            >>> results = await service._discover_sources_parallel(
            ...     jurisdiction_snapshots=[],
            ...     campaign_id=UUID("00000000-0000-0000-0000-000000000000"),
            ...     sources_per_jurisdiction=3,
            ...     semaphore=sem,
            ... )
        """
        try:
            source_discovery_svc = SourceDiscoveryService(db_session=None)
        except Exception as exc:
            raise ProcessingError(f"Failed to initialize source discovery service: {exc}") from exc

        async def _run_single(
            jurisdiction_snap: dict,
        ) -> Tuple[str, Optional[Sequence[Any]], Optional[Exception]]:
            jurisdiction_id = jurisdiction_snap["id_str"]
            try:
                async with semaphore:
                    suggested_sources = await self._suggest_sources_with_fallback(
                        jurisdiction=jurisdiction_snap,
                        campaign_name=str(jurisdiction_snap.get("campaign_name", "") or ""),
                        campaign_id=campaign_id,
                        max_results=sources_per_jurisdiction,
                        source_discovery_svc=source_discovery_svc,
                    )
                return jurisdiction_id, suggested_sources, None
            except Exception as exc:
                return jurisdiction_id, None, exc

        try:
            tasks = [_run_single(jurisdiction_snap=snap) for snap in jurisdiction_snapshots]
            results = await asyncio.gather(*tasks)
            return {
                jurisdiction_id: {
                    "suggested_sources": suggested_sources,
                    "error": error,
                }
                for jurisdiction_id, suggested_sources, error in results
            }
        finally:
            await source_discovery_svc.close()

    async def _persist_discovered_sources(
        self,
        jurisdiction_snap: dict,
        suggested_sources: Sequence[Any],
        source_svc: SourceService,
    ) -> Tuple[int, int, DiscoveryStatus]:
        """Persist discovered sources for one jurisdiction sequentially.

        Args:
            jurisdiction_snap: Jurisdiction primitive snapshot.
            suggested_sources: Suggested sources from external search.
            source_svc: Source service for persistence operations.

        Returns:
            Tuple[int, int, DiscoveryStatus]: Created count, duplicate count, discovery status.

        Raises:
            ProcessingError: If persistence fails unexpectedly.

        Examples:
            >>> await service._persist_discovered_sources(
            ...     jurisdiction_snap={"id": some_uuid, "id_str": "..."},
            ...     suggested_sources=[],
            ...     source_svc=SourceService(),
            ... )
        """
        created_count = 0
        duplicate_count = 0
        jurisdiction_uuid: UUID = jurisdiction_snap["id"]

        for source in suggested_sources:
            try:
                async with await self._begin_nested_context():
                    await source_svc.create_source(
                        db=self.db,
                        source_data=SourceCreate(
                            jurisdiction_id=jurisdiction_uuid,
                            name=source.title,
                            url=source.url,
                        ),
                        strict_validation=False,
                        auto_commit=False,
                    )
                created_count += 1
            except DuplicateSourceError:
                duplicate_count += 1
                logger.debug(
                    "Duplicate source skipped: %s for jurisdiction %s",
                    source.url,
                    jurisdiction_snap["id_str"],
                )
            except HTTPException as exc:
                logger.debug(
                    "Source creation skipped (HTTP %s): %s for jurisdiction %s",
                    exc.status_code,
                    source.url,
                    jurisdiction_snap["id_str"],
                )

        resolved_status = self._resolve_discovery_status(
            created_count=created_count,
            duplicate_count=duplicate_count,
        )

        result = await self.db.execute(
            select(Jurisdiction).where(Jurisdiction.id == jurisdiction_uuid)
        )
        live_jurisdiction = result.scalar_one_or_none()
        if live_jurisdiction and hasattr(live_jurisdiction, "discovery_status"):
            live_jurisdiction.discovery_status = resolved_status
            self.db.add(live_jurisdiction)

        return created_count, duplicate_count, resolved_status

    async def _mark_jurisdiction_failed(self, jurisdiction_id: UUID) -> None:
        """Mark a jurisdiction as discovery failed.

        Args:
            jurisdiction_id: Jurisdiction ID to mark failed.

        Returns:
            None

        Raises:
            ProcessingError: If lookup fails unexpectedly.

        Examples:
            >>> await service._mark_jurisdiction_failed(some_uuid)
        """
        result = await self.db.execute(
            select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
        )
        live_jurisdiction = result.scalar_one_or_none()
        if live_jurisdiction and hasattr(live_jurisdiction, "discovery_status"):
            live_jurisdiction.discovery_status = DiscoveryStatus.DISCOVERY_FAILED
            self.db.add(live_jurisdiction)

    async def _begin_nested_context(self):
        """Create a nested transaction context compatible with async test doubles.

        Args:
            None

        Returns:
            Any: Async context manager for nested transaction scope.

        Raises:
            ProcessingError: If the nested transaction context is invalid.

        Examples:
            >>> ctx = await service._begin_nested_context()
            >>> async with ctx:
            ...     pass
        """
        nested = self.db.begin_nested()
        if inspect.isawaitable(nested):
            nested = await nested
        return nested

    async def _acquire_rate_limit_token(self, key: str, limit: int) -> bool:
        """Acquire a rate-limit token using Lua and fallback for legacy mocks.

        Args:
            key: Redis key for campaign rate limiting.
            limit: Max requests in the configured window.

        Returns:
            bool: True when request can proceed, otherwise False.

        Raises:
            Exception: Propagates Redis client errors.

        Examples:
            >>> allowed = await service._acquire_rate_limit_token("k", 25)
            >>> isinstance(allowed, bool)
            True
        """
        eval_method = getattr(self.redis_client, "eval", None)
        if eval_method is not None:
            acquired = await eval_method(
                _RATE_LIMIT_ACQUIRE_LUA,
                1,
                key,
                limit,
                _RATE_LIMIT_WINDOW_SECONDS,
            )
            if isinstance(acquired, (int, str, bytes)):
                try:
                    return int(acquired) == 1
                except (TypeError, ValueError):
                    pass

        current = await self.redis_client.incr(key)
        if current == 1:
            await self.redis_client.expire(key, _RATE_LIMIT_WINDOW_SECONDS)
        return current <= limit

    async def _wait_for_rate_limit(self, campaign_id: UUID) -> None:
        """Block until the Redis sliding window allows the next request."""
        key = f"campaign_search_rate_limit:{campaign_id}"
        limit = settings.CAMPAIGN_SEARCH_RATE_LIMIT
        max_retries = max(0, settings.CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_RETRIES)
        max_backoff_seconds = max(
            1, settings.CAMPAIGN_SOURCE_DISCOVERY_RATE_LIMIT_MAX_BACKOFF_SECONDS
        )

        for attempt in range(max_retries + 1):
            if await self._acquire_rate_limit_token(key=key, limit=limit):
                return

            if attempt >= max_retries:
                raise ProcessingError(
                    f"Rate limit exceeded after {max_retries} retries for campaign {campaign_id}"
                )

            backoff = min(2**attempt, max_backoff_seconds)
            logger.info(
                "Rate-limited for campaign %s (attempt %d/%d). Backing off %ds.",
                campaign_id,
                attempt + 1,
                max_retries,
                backoff,
            )
            await asyncio.sleep(backoff)

    @staticmethod
    def _build_search_query(jurisdiction: Any) -> str:
        """Build a search query string from jurisdiction data."""
        if isinstance(jurisdiction, dict):
            name = str(jurisdiction.get("name", "")).strip()
            prompt = str(jurisdiction.get("prompt", "") or "")
        else:
            name = str(getattr(jurisdiction, "name", "")).strip()
            prompt = str(getattr(jurisdiction, "prompt", "") or "")

        prompt_fragment = prompt[:200].strip()
        if prompt_fragment:
            return f"{name} {prompt_fragment}"
        return name

    @classmethod
    def _generate_fallback_queries(cls, jurisdiction: Any, campaign_name: str = "") -> List[str]:
        """Generate progressively broader fallback queries for source discovery."""
        if isinstance(jurisdiction, dict):
            name = str(jurisdiction.get("name", "")).strip()
            prompt = str(jurisdiction.get("prompt", "") or "")
        else:
            name = str(getattr(jurisdiction, "name", "")).strip()
            prompt = str(getattr(jurisdiction, "prompt", "") or "")

        prompt_fragment = prompt[:200].strip()
        candidates = [
            f"{name} {prompt_fragment}".strip() if prompt_fragment else name,
            f"{name} {campaign_name.strip()}".strip() if campaign_name else name,
            name,
        ]

        queries: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in queries:
                queries.append(candidate)
        return queries

    async def _suggest_sources_with_fallback(
        self,
        *,
        jurisdiction: Any,
        campaign_name: str,
        campaign_id: UUID,
        max_results: int,
        source_discovery_svc: SourceDiscoveryService,
    ) -> Sequence[Any]:
        """Try progressively broader queries until sources are suggested."""
        queries = self._generate_fallback_queries(jurisdiction, campaign_name=campaign_name)
        max_fallback_queries = max(1, settings.CAMPAIGN_SOURCE_DISCOVERY_MAX_FALLBACK_QUERIES)
        queries = queries[:max_fallback_queries]
        jurisdiction_name = (
            jurisdiction["name"] if isinstance(jurisdiction, dict) else jurisdiction.name
        )

        for search_query in queries:
            await self._wait_for_rate_limit(campaign_id)
            suggested = await source_discovery_svc.suggest_sources(
                search_query=search_query,
                jurisdiction_name=jurisdiction_name,
                max_results=max_results,
            )
            if suggested:
                return suggested

            logger.info(
                "No sources found for jurisdiction %s using query '%s'. Trying fallback.",
                jurisdiction_name,
                search_query,
            )

        return []

    @staticmethod
    def _resolve_discovery_status(created_count: int, duplicate_count: int) -> DiscoveryStatus:
        """Map source creation outcome to a discovery status."""
        if created_count > 0 or duplicate_count > 0:
            return DiscoveryStatus.DISCOVERED
        return DiscoveryStatus.REQUIRES_MANUAL_SOURCES

    async def _load_campaign_with_jurisdictions(self, campaign_id: UUID) -> Campaign:
        """Load campaign with jurisdictions eagerly loaded (prevents N+1)."""
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.jurisdictions))
            .where(Campaign.id == campaign_id)
        )
        result = await self.db.execute(stmt)
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found.")
        return campaign

    async def _load_campaign(self, campaign_id: UUID) -> Campaign:
        """Load a campaign without relationship loading."""
        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found.")
        return campaign

    async def _load_jurisdiction(self, jurisdiction_id: UUID, campaign_id: UUID) -> Any:
        """Load a jurisdiction belonging to a specific campaign."""
        result = await self.db.execute(
            select(Jurisdiction).where(
                Jurisdiction.id == jurisdiction_id,
                Jurisdiction.campaign_id == campaign_id,
            )
        )
        jurisdiction = result.scalar_one_or_none()
        if jurisdiction is None:
            raise NotFoundError(
                f"Jurisdiction {jurisdiction_id} not found for campaign {campaign_id}."
            )
        return jurisdiction

    @staticmethod
    def _validate_status(campaign: Campaign) -> None:
        """Ensure the campaign is in a valid status for source discovery.

        Allowed: ``HYDRATING`` (first run after hydration) or
        ``DISCOVERING_SOURCES`` (resume after partial failure / time limit).

        Raises:
            ResourceLockedError: Campaign status is not eligible.
        """
        allowed = {CampaignStatus.HYDRATING, CampaignStatus.DISCOVERING_SOURCES}
        if campaign.status not in allowed:
            raise ResourceLockedError(
                f"Source discovery requires HYDRATING or DISCOVERING_SOURCES status. "
                f"Current status: {campaign.status.value}"
            )
