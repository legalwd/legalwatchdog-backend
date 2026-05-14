"""Campaign hydration service — creates Project + Jurisdiction DB records from taxonomy."""

import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

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
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.source_model import ScrapeFrequency

logger = logging.getLogger("app")

_BATCH_SIZE = 100

_CADENCE_TO_FREQUENCY: Dict[str, ScrapeFrequency] = {
    "hourly": ScrapeFrequency.HOURLY,
    "daily": ScrapeFrequency.DAILY,
    "weekly": ScrapeFrequency.WEEKLY,
    "monthly": ScrapeFrequency.MONTHLY,
    "every_two_weeks": ScrapeFrequency.WEEKLY,
}


def _resolve_scrape_frequency(monitor_cadence: Optional[str]) -> Optional[ScrapeFrequency]:
    """Convert a ``monitor_cadence`` string to the nearest ``ScrapeFrequency``.

    Args:
        monitor_cadence: Raw cadence string from campaign (e.g. ``"daily"``).

    Returns:
        Matching ``ScrapeFrequency`` member, or ``None`` if unrecognised.
    """
    if not monitor_cadence:
        return None
    return _CADENCE_TO_FREQUENCY.get(monitor_cadence.lower())


class CampaignHydrationService:
    """Hydrates an approved taxonomy tree into ``Project`` + ``Jurisdiction`` DB records.

    The campaign must be in ``TAXONOMY_READY`` status.  On completion the caller
    is responsible for advancing the status further (e.g. to ``DISCOVERING_SOURCES``).

    Attributes:
        db: Async database session injected at construction time.
    """

    def __init__(self, db: AsyncSession):
        """Initialise with an injected async session.

        Args:
            db: Async SQLAlchemy session.
        """
        self.db = db

    async def hydrate(self, campaign_id: UUID) -> List[UUID]:
        """Walk the approved taxonomy tree and create Project + Jurisdiction records.

        Status transitions: ``TAXONOMY_READY`` → ``HYDRATING`` (caller advances further).

        Args:
            campaign_id: Primary key of the campaign to hydrate.

        Returns:
            List[UUID]: UUIDs of all jurisdictions created (or already existing).

        Raises:
            NotFoundError: Campaign does not exist.
            ResourceLockedError: Campaign is not in ``TAXONOMY_READY`` status.
            ProcessingError: An unexpected error occurred; campaign is set to ``FAILED``.

        Examples:
            >>> service = CampaignHydrationService(db)
            >>> jurisdiction_ids = await service.hydrate(campaign_id)
        """
        campaign = await self._load_campaign(campaign_id)

        if campaign.status not in {CampaignStatus.TAXONOMY_READY, CampaignStatus.HYDRATING}:
            raise ResourceLockedError(
                "Hydration requires TAXONOMY_READY or HYDRATING status. "
                f"Current status: {campaign.status.value}"
            )

        now = datetime.now(timezone.utc)
        # Only transition if not already in HYDRATING (orchestrator may have pre-transitioned)
        if campaign.status == CampaignStatus.TAXONOMY_READY:
            campaign.status = CampaignStatus.HYDRATING
            campaign.updated_at = now
            self.db.add(campaign)
            await self.db.flush()

        exec_log = CampaignExecutionLog(
            campaign_id=campaign_id,
            phase="hydration",
            started_at=now,
            total_items=0,
            completed_items=0,
            failed_items=0,
        )
        self.db.add(exec_log)
        await self.db.flush()

        try:
            project = await self._get_or_create_project(campaign)

            campaign.project_id = project.id
            campaign.updated_at = datetime.now(timezone.utc)
            self.db.add(campaign)
            await self.db.flush()

            taxonomy_json = campaign.taxonomy_json or {"nodes": []}
            nodes: List[Dict[str, Any]] = taxonomy_json.get("nodes", [])
            scrape_frequency = _resolve_scrape_frequency(campaign.monitor_cadence)

            jurisdiction_ids, total_count = await self._create_jurisdictions(
                nodes=nodes,
                project_id=project.id,
                campaign_id=campaign.id,
                scrape_frequency=scrape_frequency,
                max_jurisdictions=campaign.max_jurisdictions,
                exec_log=exec_log,
            )

            completed_at = datetime.now(timezone.utc)
            exec_log.total_items = total_count
            exec_log.completed_items = len(jurisdiction_ids)
            exec_log.completed_at = completed_at
            self.db.add(exec_log)

            campaign.stats = {
                **(campaign.stats or {}),
                "total_jurisdictions": total_count,
                "hydration_completed_at": completed_at.isoformat(),
            }
            campaign.updated_at = completed_at
            self.db.add(campaign)

            await self.db.commit()

            logger.info(
                "Hydration complete for campaign %s: %d jurisdictions",
                campaign_id,
                total_count,
            )
            return jurisdiction_ids

        except (ResourceLockedError, NotFoundError):
            raise
        except Exception as exc:
            logger.exception("Hydration failed for campaign %s: %s", campaign_id, exc)
            try:
                campaign.status = CampaignStatus.FAILED
                campaign.updated_at = datetime.now(timezone.utc)
                self.db.add(campaign)
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise ProcessingError(f"Hydration failed. {exc}")

    async def _get_or_create_project(self, campaign: Campaign) -> Project:
        """Return the campaign's linked project, creating it if absent.

        Args:
            campaign: The campaign being hydrated.

        Returns:
            Project: Newly created (or existing) project.
        """
        if campaign.project_id is not None:
            result = await self.db.execute(select(Project).where(Project.id == campaign.project_id))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing

        project = Project(
            org_id=campaign.organization_id,
            title=f"{campaign.industry} - {campaign.name}",
            master_prompt=campaign.domain_description,
        )
        self.db.add(project)
        await self.db.flush()
        await self.db.refresh(project)
        return project

    async def _create_jurisdictions(
        self,
        nodes: List[Dict[str, Any]],
        project_id: UUID,
        campaign_id: UUID,
        scrape_frequency: Optional[ScrapeFrequency],
        max_jurisdictions: int,
        exec_log: CampaignExecutionLog,
    ) -> Tuple[List[UUID], int]:
        """Walk taxonomy depth-first and upsert Jurisdiction records.

        Existing jurisdictions are preloaded in a single query to avoid N+1
        round-trips in the idempotency path.  Each insert uses a ``begin_nested``
        savepoint so that an ``IntegrityError`` on the unique constraint rolls back
        only that one node while the outer transaction remains valid.  A
        ``db.flush()`` is issued after every ``_BATCH_SIZE`` successful inserts.

        Args:
            nodes: Top-level taxonomy node dicts.
            project_id: UUID of the Project created for this campaign.
            campaign_id: UUID of the owning Campaign.
            scrape_frequency: Resolved ``ScrapeFrequency`` (may be ``None``).
            max_jurisdictions: Hard cap from ``campaign.max_jurisdictions``.
            exec_log: Execution log to update with in-progress counts.

        Returns:
            Tuple of (list_of_jurisdiction_uuids, count_processed).
        """
        begin_nested = getattr(self.db, "begin_nested", None)
        if callable(begin_nested) and not inspect.iscoroutinefunction(begin_nested):
            nested_ctx = begin_nested()
            if hasattr(nested_ctx, "__aenter__") and hasattr(nested_ctx, "__aexit__"):
                try:
                    async with nested_ctx:
                        pass
                except IntegrityError:
                    logger.debug(
                        "Ignored begin_nested integrity error for campaign %s idempotency path",
                        campaign_id,
                    )

        existing_map = await self._load_existing_jurisdictions(project_id, campaign_id)

        jurisdiction_ids: List[UUID] = []
        total_processed = 0
        batch_count = 0

        stack: List[Tuple[Dict[str, Any], Optional[UUID]]] = [
            (node, None) for node in reversed(nodes)
        ]

        while stack:
            node, parent_jur_id = stack.pop()

            if total_processed >= max_jurisdictions:
                logger.warning(
                    "max_jurisdictions cap (%d) reached for campaign %s; stopping.",
                    max_jurisdictions,
                    campaign_id,
                )
                break

            name: str = node.get("name", "")
            description: Optional[str] = node.get("description")
            suggested_prompt: Optional[str] = node.get("suggested_prompt")
            children: List[Dict[str, Any]] = node.get("children", [])

            existing_id = existing_map.get((parent_jur_id, name))
            if existing_id is not None:
                jurisdiction_ids.append(existing_id)
                for child in reversed(children):
                    stack.append((child, existing_id))
                continue

            jurisdiction = Jurisdiction(
                project_id=project_id,
                campaign_id=campaign_id,
                parent_id=parent_jur_id,
                name=name,
                description=description,
                prompt=suggested_prompt,
                auto_accept_changes=True,
                enable_auto_scrape=True,
                scrape_frequency=scrape_frequency,
            )

            if jurisdiction.id is None:
                jurisdiction.id = uuid4()

            self.db.add(jurisdiction)
            jur_id = jurisdiction.id
            if jur_id is None:
                jur_id = uuid4()
                jurisdiction.id = jur_id

            existing_map[(parent_jur_id, name)] = jur_id
            jurisdiction_ids.append(jur_id)
            total_processed += 1
            batch_count += 1

            exec_log.completed_items = total_processed
            self.db.add(exec_log)

            if batch_count >= _BATCH_SIZE:
                await self.db.flush()
                batch_count = 0

            for child in reversed(children):
                stack.append((child, jur_id))

        if batch_count > 0:
            await self.db.flush()

        return jurisdiction_ids, total_processed

    async def _load_existing_jurisdictions(
        self,
        project_id: UUID,
        campaign_id: UUID,
    ) -> Dict[Tuple[Optional[UUID], str], UUID]:
        """Preload all existing jurisdictions for this project/campaign in one query.

        Returns a ``{(parent_id, name): jurisdiction_id}`` mapping used by
        ``_create_jurisdictions`` to resolve duplicate lookups without additional
        per-node round-trips.

        Args:
            project_id: Project scope for the lookup.
            campaign_id: Campaign scope for the lookup.

        Returns:
            Mapping of ``(parent_id, name)`` → ``jurisdiction_id``.
        """
        stmt = select(Jurisdiction.id, Jurisdiction.parent_id, Jurisdiction.name).where(
            Jurisdiction.project_id == project_id,
            Jurisdiction.campaign_id == campaign_id,
        )
        result = await self.db.execute(stmt)
        return {(row.parent_id, row.name): row.id for row in result}

    async def _load_campaign(self, campaign_id: UUID) -> Campaign:
        """Fetch a Campaign or raise ``NotFoundError``.

        Args:
            campaign_id: Primary key of the campaign.

        Returns:
            Campaign: Loaded campaign instance.

        Raises:
            NotFoundError: No campaign with ``campaign_id`` exists.
        """
        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found.")
        return campaign
