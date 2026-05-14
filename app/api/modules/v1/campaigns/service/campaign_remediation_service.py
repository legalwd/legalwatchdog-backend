"""Campaign remediation services for failed source discovery jurisdictions."""

import logging
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import BadRequestError, NotFoundError
from app.api.modules.v1.campaigns.models.campaign_model import Campaign
from app.api.modules.v1.campaigns.schemas.campaign_schema import (
    FailedDiscoveryJurisdictionListResponse,
    FailedDiscoveryJurisdictionResponse,
    JurisdictionManualSourcesRequest,
    JurisdictionRemediationResponse,
)
from app.api.modules.v1.campaigns.service.campaign_source_discovery_service import (
    CampaignSourceDiscoveryService,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import (
    DiscoveryStatus,
    Jurisdiction,
)
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import (
    JurisdictionScrapeJob,
    JurisdictionScrapeJobStatus,
)
from app.api.modules.v1.scraping.schemas.source_service import SourceCreate
from app.api.modules.v1.scraping.service.source_service import SourceService
from app.api.modules.v1.scraping.validators.exception import DuplicateSourceError
from app.celery_app import celery_app

logger = logging.getLogger("app")


class CampaignRemediationService:
    """Administrative remediation workflows for campaign discovery failures."""

    def __init__(self, db: AsyncSession):
        """Initialize service with injected database session."""
        self.db = db

    async def get_failed_discovery_nodes(
        self,
        campaign_id: UUID,
    ) -> FailedDiscoveryJurisdictionListResponse:
        """Return campaign jurisdictions that still require manual sources."""
        campaign = await self.db.get(Campaign, campaign_id)
        if campaign is None:
            raise NotFoundError("Campaign not found.")

        result = await self.db.execute(
            select(Jurisdiction).where(
                Jurisdiction.campaign_id == campaign_id,
                Jurisdiction.discovery_status == DiscoveryStatus.REQUIRES_MANUAL_SOURCES,
            )
        )
        jurisdictions = result.scalars().all()
        return FailedDiscoveryJurisdictionListResponse(
            jurisdictions=[
                FailedDiscoveryJurisdictionResponse.model_validate(jurisdiction)
                for jurisdiction in jurisdictions
            ],
            total=len(jurisdictions),
        )

    async def add_manual_sources(
        self,
        jurisdiction_id: UUID,
        payload: JurisdictionManualSourcesRequest,
    ) -> JurisdictionRemediationResponse:
        """Create manual sources for a jurisdiction and dispatch a catch-up scrape."""
        jurisdiction = await self._load_jurisdiction(jurisdiction_id)

        source_service = SourceService()
        created_count = 0
        duplicate_count = 0

        for url in payload.urls:
            try:
                await source_service.create_source(
                    db=self.db,
                    source_data=SourceCreate(
                        jurisdiction_id=jurisdiction.id,
                        name=url.host or str(url),
                        url=url,
                    ),
                )
                created_count += 1
            except DuplicateSourceError:
                duplicate_count += 1
                logger.info(
                    "Duplicate manual source ignored for jurisdiction %s: %s",
                    jurisdiction_id,
                    url,
                )

        if created_count == 0 and duplicate_count == 0:
            raise BadRequestError("No usable sources were provided for this jurisdiction.")

        jurisdiction.discovery_status = DiscoveryStatus.DISCOVERED
        self.db.add(jurisdiction)
        await self.db.commit()
        await self.db.refresh(jurisdiction)

        task = self._dispatch_single_jurisdiction_scrape(jurisdiction.id)
        return JurisdictionRemediationResponse(
            jurisdiction_id=jurisdiction.id,
            discovery_status=jurisdiction.discovery_status,
            sources_created=created_count,
            scrape_dispatch_task_id=task.id,
        )

    async def retry_discovery(self, jurisdiction_id: UUID) -> JurisdictionRemediationResponse:
        """Re-run source discovery for a single jurisdiction and dispatch scrape on success."""
        jurisdiction = await self._load_jurisdiction(jurisdiction_id)
        if jurisdiction.campaign_id is None:
            raise BadRequestError("Jurisdiction is not attached to a campaign.")

        jurisdiction.discovery_status = DiscoveryStatus.PENDING
        self.db.add(jurisdiction)
        await self.db.commit()
        await self.db.refresh(jurisdiction)

        redis_client = self._make_async_redis_client()
        try:
            discovery_service = CampaignSourceDiscoveryService(self.db, redis_client)
            source_ids = await discovery_service.discover_for_jurisdiction(
                jurisdiction.id,
                jurisdiction.campaign_id,
            )
        finally:
            await redis_client.aclose()

        await self.db.refresh(jurisdiction)
        task_id = None
        if jurisdiction.discovery_status == DiscoveryStatus.DISCOVERED:
            task = self._dispatch_single_jurisdiction_scrape(jurisdiction.id)
            task_id = task.id

        return JurisdictionRemediationResponse(
            jurisdiction_id=jurisdiction.id,
            discovery_status=jurisdiction.discovery_status,
            sources_created=len(source_ids),
            scrape_dispatch_task_id=task_id,
        )

    async def retry_failed_jurisdiction_scrapes(self, campaign_id: UUID) -> dict:
        """Retry all failed jurisdiction scrapes for a campaign."""
        result = await self.db.execute(
            select(JurisdictionScrapeJob)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionScrapeJob.jurisdiction_id)
            .where(
                Jurisdiction.campaign_id == campaign_id,
                JurisdictionScrapeJob.status == JurisdictionScrapeJobStatus.FAILED,
            )
        )
        failed_jobs = result.scalars().all()

        if not failed_jobs:
            return {"retried_count": 0, "message": "No failed jurisdiction jobs found."}

        retried_count = 0
        from app.api.modules.v1.campaigns.models.campaign_model import CampaignStatus

        for job in failed_jobs:
            job.status = JurisdictionScrapeJobStatus.PENDING
            job.error_message = None
            self.db.add(job)
            self._dispatch_single_jurisdiction_scrape(job.jurisdiction_id)
            retried_count += 1

        await self.db.commit()

        campaign = await self.db.get(Campaign, campaign_id)
        if campaign and campaign.status == CampaignStatus.MONITORING:
            campaign.status = CampaignStatus.SCRAPING
            self.db.add(campaign)
            await self.db.commit()

            celery_app.send_task(
                "app.api.modules.v1.campaigns.tasks.campaign_tasks.publish_campaign_blogs_task",
                args=[str(campaign_id)],
                queue="processing",
            )

        return {
            "retried_count": retried_count,
            "message": f"Successfully queued {retried_count} failed jobs for retry.",
        }

    async def _load_jurisdiction(self, jurisdiction_id: UUID) -> Jurisdiction:
        """Load a jurisdiction for remediation workflows."""
        jurisdiction = await self.db.get(Jurisdiction, jurisdiction_id)
        if jurisdiction is None or jurisdiction.is_deleted:
            raise NotFoundError("Jurisdiction not found.")
        return jurisdiction

    @staticmethod
    def _dispatch_single_jurisdiction_scrape(jurisdiction_id: UUID):
        """Send a single-jurisdiction dispatch task back into the live pipeline."""
        return celery_app.send_task(
            "app.api.modules.v1.scraping.service.tasks.dispatch_single_jurisdiction_scrape",
            args=[str(jurisdiction_id)],
            queue="processing",
        )

    @staticmethod
    def _make_async_redis_client() -> aioredis.Redis:
        """Build an async Redis client configured for campaign discovery rate limiting."""
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
