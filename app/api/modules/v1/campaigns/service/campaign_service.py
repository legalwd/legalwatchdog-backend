"""Campaign business logic service."""

import logging
from copy import copy
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import and_, func, select

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    ProcessingError,
    ResourceLockedError,
)
from app.api.modules.v1.campaigns.models.campaign_model import (
    Campaign,
    CampaignStatus,
)
from app.api.modules.v1.campaigns.schemas.campaign_schema import (
    CampaignBlogBatchPublishRequest,
    CampaignCreateRequest,
    CampaignUpdateRequest,
)
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.blog_artifact_service import build_artifact_html
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService

logger = logging.getLogger("app")


class CampaignService:
    """
    Service class for Campaign CRUD business logic.

    Encapsulates create, read, list, update, and delete operations for
    Campaign resources. All mutating operations enforce the DRAFT-only
    invariant: campaigns that have progressed past DRAFT are locked from
    edits and deletes.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize CampaignService with a database session.

        Args:
            db (AsyncSession): Async SQLAlchemy session.
        """
        self.db = db

    async def create_campaign(
        self,
        payload: CampaignCreateRequest,
        organization_id: UUID,
        created_by: UUID,
    ) -> Campaign:
        """
        Create a new Campaign in DRAFT status.

        Args:
            payload (CampaignCreateRequest): Field values for the new campaign.
            organization_id (UUID): Owning organization UUID.
            created_by (UUID): UUID of the superadmin creating the campaign.

        Returns:
            Campaign: The newly persisted Campaign with execution_logs eagerly loaded.

        Raises:
            ProcessingError: If a database error occurs during creation.

        Examples:
            >>> service = CampaignService(db)
            >>> campaign = await service.create_campaign(payload, org_id, user_id)
            >>> campaign.status
            <CampaignStatus.DRAFT: 'DRAFT'>
        """
        try:
            campaign = Campaign(
                organization_id=organization_id,
                project_id=payload.project_id,
                name=payload.name,
                industry=payload.industry,
                domain_description=payload.domain_description,
                target_depth=payload.target_depth,
                monitor_backend=payload.monitor_backend,
                monitor_cadence=payload.monitor_cadence,
                sources_per_jurisdiction=payload.sources_per_jurisdiction,
                max_jurisdictions=payload.max_jurisdictions,
                target_countries=payload.target_countries,
                target_states=payload.target_states,
                status=CampaignStatus.DRAFT,
                created_by=created_by,
            )
            self.db.add(campaign)
            await self.db.commit()
            await self.db.refresh(campaign)

            loaded = await self._get_with_logs(campaign.id)
            return loaded
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to create campaign: {exc}", exc_info=True)
            raise ProcessingError("Failed to create campaign. Please try again.")

    async def get_campaign(self, campaign_id: UUID) -> Campaign:
        """
        Retrieve a Campaign with eagerly loaded execution logs.

        Args:
            campaign_id (UUID): The campaign's primary key.

        Returns:
            Campaign: The Campaign with execution_logs populated.

        Raises:
            NotFoundError: If no campaign with the given ID exists.

        Examples:
            >>> service = CampaignService(db)
            >>> campaign = await service.get_campaign(uuid)
        """
        campaign = await self._get_with_logs(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")
        return campaign

    async def list_campaigns(
        self,
        organization_id: Optional[UUID] = None,
        status_filter: Optional[CampaignStatus] = None,
        industry_filter: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """
        Return a paginated list of campaigns with optional filters.

        Args:
            organization_id (Optional[UUID]): Filter by organization.
            status_filter (Optional[CampaignStatus]): Filter by campaign status.
            industry_filter (Optional[str]): Case-insensitive partial industry filter.
            page (int): 1-based page number. Defaults to 1.
            limit (int): Page size (max 100). Defaults to 20.

        Returns:
            dict: Keys ``items``, ``total``, ``page``, ``limit``, ``total_pages``.

        Raises:
            ProcessingError: If the database query fails.

        Examples:
            >>> result = await service.list_campaigns(page=1, limit=20)
            >>> result["total"]
            0
        """
        try:
            conditions = []
            if organization_id:
                conditions.append(Campaign.organization_id == organization_id)
            if status_filter:
                conditions.append(Campaign.status == status_filter)
            if industry_filter:
                conditions.append(Campaign.industry.ilike(f"%{industry_filter}%"))

            count_stmt = select(func.count()).select_from(Campaign)
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))

            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0

            offset = (page - 1) * limit
            stmt = (
                select(Campaign)
                .options(selectinload(Campaign.execution_logs))
                .order_by(Campaign.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await self.db.execute(stmt)
            campaigns: List[Campaign] = result.scalars().all()

            total_pages = (total + limit - 1) // limit if total > 0 else 0

            return {
                "items": campaigns,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
            }
        except Exception as exc:
            logger.error(f"Failed to list campaigns: {exc}", exc_info=True)
            raise ProcessingError("Failed to retrieve campaigns. Please try again.")

    async def update_campaign(
        self,
        campaign_id: UUID,
        payload: CampaignUpdateRequest,
    ) -> Campaign:
        """
        Apply a partial update to a Campaign, enforcing DRAFT-only constraint.

        Args:
            campaign_id (UUID): Target campaign primary key.
            payload (CampaignUpdateRequest): Fields to update (all optional).

        Returns:
            Campaign: Updated Campaign with execution_logs eagerly loaded.

        Raises:
            NotFoundError: If no campaign matches ``campaign_id``.
            ResourceLockedError: If campaign status is not DRAFT.
            ProcessingError: If the database update fails.

        Examples:
            >>> updated = await service.update_campaign(campaign_id, payload)
        """
        campaign = await self._get_plain(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")

        if campaign.status != CampaignStatus.DRAFT:
            raise ResourceLockedError(
                "Campaign can only be updated while in DRAFT status. "
                f"Current status: {campaign.status.value}"
            )

        try:
            update_data = payload.model_dump(exclude_none=True, exclude_unset=True)
            for field, value in update_data.items():
                setattr(campaign, field, value)
            campaign.updated_at = datetime.now(timezone.utc)

            self.db.add(campaign)
            await self.db.commit()
            await self.db.refresh(campaign)

            return await self._get_with_logs(campaign_id)
        except (NotFoundError, ResourceLockedError):
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to update campaign {campaign_id}: {exc}", exc_info=True)
            raise ProcessingError("Failed to update campaign. Please try again.")

    async def delete_campaign(self, campaign_id: UUID) -> None:
        """
        Delete a Campaign, enforcing DRAFT-only constraint.

        Args:
            campaign_id (UUID): Target campaign primary key.

        Returns:
            None

        Raises:
            NotFoundError: If no campaign matches ``campaign_id``.
            ResourceLockedError: If campaign status is not DRAFT.
            ProcessingError: If the database delete fails.

        Examples:
            >>> await service.delete_campaign(campaign_id)
        """
        campaign = await self._get_plain(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")

        if campaign.status != CampaignStatus.DRAFT:
            raise ResourceLockedError(
                "Campaign can only be deleted while in DRAFT status. "
                f"Current status: {campaign.status.value}"
            )

        try:
            await self.db.delete(campaign)
            await self.db.commit()
        except (NotFoundError, ResourceLockedError):
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to delete campaign {campaign_id}: {exc}", exc_info=True)
            raise ProcessingError("Failed to delete campaign. Please try again.")

    async def list_campaign_blogs(self, campaign_id: UUID) -> list:
        """
        List all blog posts generated for a specific campaign.

        Args:
            campaign_id: Target campaign primary key.

        Returns:
            List of JurisdictionBlogPost instances.

        Raises:
            NotFoundError: If no campaign matches `campaign_id`.
        """
        campaign = await self._get_plain(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")

        stmt = (
            select(JurisdictionBlogPost)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(Jurisdiction.campaign_id == campaign_id)
            .order_by(JurisdictionBlogPost.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def batch_publish_campaign_blogs(
        self,
        campaign_id: UUID,
        payload: CampaignBlogBatchPublishRequest,
    ) -> dict:
        """Publish or unpublish campaign blogs in batch with per-item results."""
        campaign = await self._get_plain(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")

        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(Jurisdiction.campaign_id == campaign_id)
            .order_by(JurisdictionBlogPost.created_at.desc())
        )
        if payload.blog_ids:
            stmt = stmt.where(JurisdictionBlogPost.id.in_(payload.blog_ids))

        result = await self.db.execute(stmt)
        blog_rows = result.all()

        requested_count = len(payload.blog_ids or [])
        if payload.publish_all:
            requested_count = len(blog_rows)

        items = []
        success_count = 0
        failed_count = 0

        for blog_post, jurisdiction in blog_rows:
            try:
                publish_result = await BlogGenerationService.publish_blog_post(
                    self.db,
                    campaign.organization_id,
                    jurisdiction.id,
                    payload.is_published,
                )
                item = publish_result["data"]
                item["status"] = "success"
                items.append(item)
                success_count += 1
            except Exception as exc:
                logger.error(
                    "Failed to update campaign blog %s during batch publish: %s",
                    blog_post.id,
                    exc,
                    exc_info=True,
                )
                items.append(
                    {
                        "id": str(blog_post.id),
                        "jurisdiction_id": str(jurisdiction.id),
                        "title": blog_post.title,
                        "slug": blog_post.slug,
                        "is_published": blog_post.is_published,
                        "public_url": None,
                        "published_at": (
                            blog_post.published_at.isoformat() if blog_post.published_at else None
                        ),
                        "status": "failed",
                        "message": str(exc),
                    }
                )
                failed_count += 1

        action = "published" if payload.is_published else "unpublished"
        return {
            "campaign_id": str(campaign_id),
            "action": action,
            "requested_count": requested_count,
            "matched_count": len(blog_rows),
            "processed_count": success_count,
            "failed_count": failed_count,
            "items": items,
        }

    async def render_campaign_blog_preview(self, campaign_id: UUID, blog_id: UUID) -> str:
        """Render the full HTML preview for an unpublished or published campaign blog."""
        campaign = await self._get_plain(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found.")

        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(
                Jurisdiction.campaign_id == campaign_id,
                JurisdictionBlogPost.id == blog_id,
            )
        )
        result = await self.db.execute(stmt)
        row = result.first()
        if not row:
            raise NotFoundError("Campaign blog post not found.")

        blog_post, jurisdiction = row
        resource_path = await BlogGenerationService._build_public_resource_path(
            self.db,
            jurisdiction,
            blog_post,
        )

        preview_post = copy(blog_post)
        if not preview_post.published_at:
            preview_post.published_at = (
                preview_post.generated_at or preview_post.updated_at or preview_post.created_at
            )

        return build_artifact_html(
            preview_post,
            resource_path=resource_path,
            robots_content="noindex, nofollow",
        )

    async def _get_with_logs(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Load a Campaign with execution_logs eagerly loaded.

        Args:
            campaign_id (UUID): Primary key of the campaign.

        Returns:
            Optional[Campaign]: Campaign instance or None if not found.

        Examples:
            >>> campaign = await service._get_with_logs(uuid)
        """
        stmt = (
            select(Campaign)
            .options(selectinload(Campaign.execution_logs))
            .where(Campaign.id == campaign_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_plain(self, campaign_id: UUID) -> Optional[Campaign]:
        """
        Load a Campaign without any relationship loading.

        Args:
            campaign_id (UUID): Primary key of the campaign.

        Returns:
            Optional[Campaign]: Campaign instance or None if not found.

        Examples:
            >>> campaign = await service._get_plain(uuid)
        """
        result = await self.db.execute(select(Campaign).where(Campaign.id == campaign_id))
        return result.scalar_one_or_none()
