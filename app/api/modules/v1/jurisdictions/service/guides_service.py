"""Service for public-facing Guides listing API.

Provides industry-level and region-level listing data for SEO guide pages.
All queries are scoped to *published* blog posts only.

URL hierarchy served:
    /guides/{industry}/                   → industry listing (regions + counts)
    /guides/{industry}/{region-slug}/     → region listing (paginated jurisdictions)
    /guides/{industry}/{region}/{jur}/    → individual post (from blog_generation_service)

Two-tier pagination strategy:
    Tier 1 (industry): returns regions with aggregate counts, no jurisdiction list.
    Tier 2 (region):   returns paginated jurisdictions with rich SEO data.
"""

import logging
import re
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import ResourceNotFoundError
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.guides_schema import (
    IndustryListingResponse,
    JurisdictionDetailResponse,
    JurisdictionSummary,
    PaginationInfo,
    RegionListingResponse,
    RegionSummary,
    SortOrder,
)
from app.api.modules.v1.jurisdictions.service.blog_artifact_service import build_public_resource_url
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project

logger = logging.getLogger(__name__)

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


def _slugify(value: str) -> str:
    """Convert a string to a URL-safe slug.

    Args:
        value: Raw string value.

    Returns:
        str: Lowercase URL-safe slug.

    Examples:
        >>> _slugify("Employer of Record")
        'employer-of-record'
    """
    normalized = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    return re.sub(r"[-\s]+", "-", normalized) or "item"


def _industry_slug(industry: str) -> str:
    """Normalize an industry name to a URL slug.

    Args:
        industry: Raw industry string from Organization.industry.

    Returns:
        str: URL-safe industry slug.

    Examples:
        >>> _industry_slug("EOR")
        'eor'
    """
    return _slugify(industry)


class GuidesService:
    """Service for public-facing Guides listing pages.

    Queries published blog posts and their jurisdiction hierarchy to power
    industry/region/jurisdiction listing pages.

    Attributes:
        db: Async database session.

    Examples:
        >>> service = GuidesService(db)
        >>> result = await service.list_industry(industry_slug="eor", page=1)
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize GuidesService.

        Args:
            db: Async database session.
        """
        self.db = db

    async def list_industry(
        self,
        industry_slug: str,
        page: int = 1,
        per_page: int = _DEFAULT_PAGE_SIZE,
        sort: SortOrder = SortOrder.NAME_ASC,
    ) -> IndustryListingResponse:
        """Return industry-level listing: paginated top-level regions with counts.

        Fetches all *parent* jurisdictions (parent_id IS NULL) that have at
        least one published blog post under their subtree, for the given
        industry slug. Returns aggregate counts only — individual jurisdictions
        are deferred to :meth:`list_region`.

        Args:
            industry_slug: URL slug of the industry (e.g., "eor").
            page: Current page number (1-indexed).
            per_page: Items per page (max 100).
            sort: Sort order for regions.

        Returns:
            IndustryListingResponse: Paginated list of regions with counts.

        Raises:
            ResourceNotFoundError: If no published posts exist for this industry.

        Examples:
            >>> result = await service.list_industry("eor", page=1)
            >>> len(result.regions) > 0
            True
        """
        per_page = min(per_page, _MAX_PAGE_SIZE)
        offset = (page - 1) * per_page
        base_url = (settings.BLOG_SITE_URL or "https://legalwatch.dog").rstrip("/")

        # Resolve all projects whose org matches the industry slug
        project_ids = await self._resolve_project_ids_for_industry(industry_slug)
        if not project_ids:
            raise ResourceNotFoundError(
                message=f"No published guides found for industry: {industry_slug}"
            )

        # Fetch all published posts joined with their jurisdiction + project + org
        published_stmt = (
            select(JurisdictionBlogPost, Jurisdiction, Project, Organization)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .join(Project, Project.id == Jurisdiction.project_id)
            .join(Organization, Organization.id == Project.org_id)
            .where(
                JurisdictionBlogPost.is_published.is_(True),
                Project.id.in_(project_ids),
            )
        )
        result = await self.db.execute(published_stmt)
        rows = result.all()

        if not rows:
            raise ResourceNotFoundError(
                message=f"No published guides found for industry: {industry_slug}"
            )

        # Industry display name from first org
        industry_display_name = rows[0][3].industry if rows else industry_slug.upper()

        # Build region map: top-level jurisdiction → {count, latest_update, jur_obj}
        all_jurisdictions = {row[1].id: row[1] for row in rows}
        post_update_by_jur: dict[UUID, object] = {row[1].id: row[0].updated_at for row in rows}

        region_map: dict[UUID, dict] = {}
        for _post, jurisdiction, _project, _org in rows:
            root = await self._find_root_ancestor(jurisdiction, all_jurisdictions)
            root_id = root.id
            if root_id not in region_map:
                region_map[root_id] = {
                    "jurisdiction": root,
                    "count": 0,
                    "latest_update": None,
                }
            region_map[root_id]["count"] += 1
            jur_updated = post_update_by_jur.get(jurisdiction.id)
            if jur_updated and (
                region_map[root_id]["latest_update"] is None
                or jur_updated > region_map[root_id]["latest_update"]
            ):
                region_map[root_id]["latest_update"] = jur_updated

        # Build RegionSummary list
        region_list = []
        for region_id, data in region_map.items():
            jur: Jurisdiction = data["jurisdiction"]
            slug = _slugify(jur.name)
            url = f"{base_url}/guides/{industry_slug}/{slug}/"
            region_list.append(
                RegionSummary(
                    id=region_id,
                    name=jur.name,
                    slug=slug,
                    jurisdiction_count=data["count"],
                    latest_update=data["latest_update"],
                    url=url,
                )
            )

        # Apply sort
        region_list = self._sort_regions(region_list, sort)

        total = len(region_list)
        paginated = region_list[offset : offset + per_page]
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        # Overall counts
        total_jurisdictions = sum(r.jurisdiction_count for r in region_list)
        all_updates = [r.latest_update for r in region_list if r.latest_update]
        last_updated = max(all_updates) if all_updates else None

        return IndustryListingResponse(
            industry=industry_slug,
            industry_display_name=industry_display_name,
            total_jurisdictions=total_jurisdictions,
            last_updated=last_updated,
            regions=paginated,
            pagination=PaginationInfo(
                page=page,
                per_page=per_page,
                total_pages=total_pages,
                total_items=total,
            ),
        )

    async def list_region(
        self,
        industry_slug: str,
        region_slug: str,
        page: int = 1,
        per_page: int = _DEFAULT_PAGE_SIZE,
        sort: SortOrder = SortOrder.NAME_ASC,
    ) -> RegionListingResponse:
        """Return region-level listing: paginated jurisdictions under a region.

        Returns rich SEO data per jurisdiction including summary, topics, and URL.

        Args:
            industry_slug: URL slug of the industry.
            region_slug: URL slug of the region (top-level jurisdiction).
            page: Current page number (1-indexed).
            per_page: Items per page (max 100).
            sort: Sort order for jurisdictions.

        Returns:
            RegionListingResponse: Paginated list of jurisdictions with SEO data.

        Raises:
            ResourceNotFoundError: If region or industry not found.

        Examples:
            >>> result = await service.list_region("eor", "united-states", page=1)
            >>> len(result.jurisdictions) > 0
            True
        """
        per_page = min(per_page, _MAX_PAGE_SIZE)
        offset = (page - 1) * per_page

        project_ids = await self._resolve_project_ids_for_industry(industry_slug)
        if not project_ids:
            raise ResourceNotFoundError(
                message=f"No published guides found for industry: {industry_slug}"
            )

        # Resolve region (top-level jurisdiction matching slug)
        region = await self._find_region_by_slug(region_slug, project_ids)
        if not region:
            raise ResourceNotFoundError(
                message=f"Region '{region_slug}' not found for industry: {industry_slug}"
            )

        # Fetch all published posts for jurisdictions in this region's subtree
        subtree_ids = await self._get_subtree_ids(region.id)

        published_stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(
                JurisdictionBlogPost.is_published.is_(True),
                Jurisdiction.id.in_(subtree_ids),
                Jurisdiction.project_id.in_(project_ids),
            )
        )
        result = await self.db.execute(published_stmt)
        rows = result.all()

        # Build JurisdictionSummary list
        jurisdictions: list[JurisdictionSummary] = []
        for post, jurisdiction in rows:
            resource_path = await BlogGenerationService._build_public_resource_path(
                self.db, jurisdiction, post
            )
            post_url = build_public_resource_url(resource_path)
            jurisdictions.append(
                JurisdictionSummary(
                    id=jurisdiction.id,
                    name=jurisdiction.name,
                    slug=_slugify(jurisdiction.name),
                    post_url=post_url,
                    summary=post.meta_description,
                    updated_at=post.updated_at,
                    key_topics=post.keywords[:5] if post.keywords else [],
                )
            )

        # Sort
        jurisdictions = self._sort_jurisdictions(jurisdictions, sort)

        total = len(jurisdictions)
        paginated = jurisdictions[offset : offset + per_page]
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return RegionListingResponse(
            industry=industry_slug,
            region_id=region.id,
            region_name=region.name,
            region_slug=region_slug,
            jurisdictions=paginated,
            pagination=PaginationInfo(
                page=page,
                per_page=per_page,
                total_pages=total_pages,
                total_items=total,
            ),
        )

    async def get_jurisdiction_detail(
        self,
        industry_slug: str,
        region_slug: str,
        jurisdiction_slug: str,
    ) -> JurisdictionDetailResponse:
        """Return jurisdiction detail metadata for schema.org markup and SEO pre-rendering.

        Args:
            industry_slug: URL slug of the industry.
            region_slug: URL slug of the region.
            jurisdiction_slug: URL slug of the jurisdiction.

        Returns:
            JurisdictionDetailResponse: Jurisdiction metadata including breadcrumbs.

        Raises:
            ResourceNotFoundError: If jurisdiction or blog post not found.

        Examples:
            >>> result = await service.get_jurisdiction_detail("eor", "united-states", "california")
        """
        project_ids = await self._resolve_project_ids_for_industry(industry_slug)
        if not project_ids:
            raise ResourceNotFoundError(
                message=f"No published guides found for industry: {industry_slug}"
            )

        region = await self._find_region_by_slug(region_slug, project_ids)
        if not region:
            raise ResourceNotFoundError(
                message=f"Region '{region_slug}' not found for industry: {industry_slug}"
            )

        subtree_ids = await self._get_subtree_ids(region.id)

        # Find jurisdiction by slug match
        jur_stmt = select(Jurisdiction).where(
            Jurisdiction.id.in_(subtree_ids),
            Jurisdiction.project_id.in_(project_ids),
        )
        jur_result = await self.db.execute(jur_stmt)
        candidates = jur_result.scalars().all()
        jurisdiction = next((j for j in candidates if _slugify(j.name) == jurisdiction_slug), None)
        if not jurisdiction:
            raise ResourceNotFoundError(message=f"Jurisdiction '{jurisdiction_slug}' not found.")

        # Fetch published blog post
        post_stmt = select(JurisdictionBlogPost).where(
            JurisdictionBlogPost.jurisdiction_id == jurisdiction.id,
            JurisdictionBlogPost.is_published.is_(True),
        )
        post_result = await self.db.execute(post_stmt)
        post = post_result.scalar_one_or_none()
        if not post:
            raise ResourceNotFoundError(
                message=f"No published blog post for jurisdiction '{jurisdiction_slug}'."
            )

        resource_path = await BlogGenerationService._build_public_resource_path(
            self.db, jurisdiction, post
        )
        post_url = build_public_resource_url(resource_path)

        return JurisdictionDetailResponse(
            id=jurisdiction.id,
            name=jurisdiction.name,
            slug=jurisdiction_slug,
            industry=industry_slug,
            post_url=post_url,
            breadcrumbs=post.breadcrumbs or [],
            title=post.title,
            meta_description=post.meta_description,
            keywords=post.keywords,
            published_at=post.published_at,
            updated_at=post.updated_at,
        )

    # ─────────────────────────────────── helpers ────────────────────────────────

    async def _resolve_project_ids_for_industry(self, industry_slug: str) -> list[UUID]:
        """Return project IDs whose organization OR campaign matches the industry slug.

        Checks both Organization.industry and Campaign.industry to support
        multiple campaigns with different industries under one organization.

        Args:
            industry_slug: URL slug of the industry.

        Returns:
            list[UUID]: Matching project IDs.
        """
        from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignStatus

        all_project_ids: list[UUID] = []

        # Approach 1: Find projects via Organization.industry (single query)
        org_stmt = (
            select(Project.id)
            .join(Organization, Organization.id == Project.org_id)
            .where(
                Organization.industry.isnot(None),
                func.lower(func.replace(Organization.industry, " ", "-")) == industry_slug.lower(),
            )
        )
        org_result = await self.db.execute(org_stmt)
        org_project_ids = [row[0] for row in org_result.all()]
        all_project_ids.extend(org_project_ids)

        # Approach 2: Find projects via Campaign.industry (single query)
        campaign_stmt = (
            select(Project.id)
            .join(Campaign, Campaign.project_id == Project.id)
            .where(
                Campaign.industry.isnot(None),
                Campaign.status.notin_([CampaignStatus.FAILED, CampaignStatus.DRAFT]),
                func.lower(func.replace(Campaign.industry, " ", "-")) == industry_slug.lower(),
            )
        )
        campaign_result = await self.db.execute(campaign_stmt)
        campaign_project_ids = [row[0] for row in campaign_result.all()]

        # Combine and deduplicate
        seen = set(all_project_ids)
        for pid in campaign_project_ids:
            if pid not in seen:
                all_project_ids.append(pid)
                seen.add(pid)

        return all_project_ids

    async def _find_region_by_slug(
        self, region_slug: str, project_ids: list[UUID]
    ) -> Optional[Jurisdiction]:
        """Find the top-level (root) jurisdiction matching a slug within project scope.

        Args:
            region_slug: URL slug of the region.
            project_ids: List of project IDs to scope the search.

        Returns:
            Jurisdiction or None if not found.

        Examples:
            >>> region = await service._find_region_by_slug("united-states", project_ids)
        """
        stmt = select(Jurisdiction).where(
            Jurisdiction.project_id.in_(project_ids),
            Jurisdiction.parent_id.is_(None),
            Jurisdiction.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()
        return next((j for j in candidates if _slugify(j.name) == region_slug), None)

    async def _get_subtree_ids(self, root_id: UUID) -> list[UUID]:
        """Collect all jurisdiction IDs in the subtree rooted at root_id.

        Traverses children iteratively to avoid recursive SQL queries.

        Args:
            root_id: Root jurisdiction UUID.

        Returns:
            list[UUID]: All jurisdiction IDs including the root.

        Examples:
            >>> ids = await service._get_subtree_ids(root_id)
            >>> root_id in ids
            True
        """
        all_ids: list[UUID] = [root_id]
        frontier: list[UUID] = [root_id]
        visited: set[UUID] = {root_id}

        while frontier:
            child_stmt = select(Jurisdiction.id).where(
                Jurisdiction.parent_id.in_(frontier),
                Jurisdiction.is_deleted.is_(False),
            )
            child_result = await self.db.execute(child_stmt)
            child_ids = [row[0] for row in child_result.all() if row[0] not in visited]
            all_ids.extend(child_ids)
            visited.update(child_ids)
            frontier = child_ids

        return all_ids

    async def _find_root_ancestor(
        self,
        jurisdiction: Jurisdiction,
        preload_map: dict[UUID, Jurisdiction],
    ) -> Jurisdiction:
        """Traverse parent chain to find the root ancestor of a jurisdiction.

        Args:
            jurisdiction: Starting jurisdiction.
            preload_map: In-memory cache of loaded jurisdictions.

        Returns:
            Jurisdiction: Root ancestor (parent_id is None).

        Examples:
            >>> root = await service._find_root_ancestor(jurisdiction, preload_map)
            >>> root.parent_id is None
            True
        """
        current = jurisdiction
        visited: set[UUID] = {current.id}

        while current.parent_id is not None:
            if current.parent_id in visited:
                break
            visited.add(current.parent_id)
            parent = preload_map.get(current.parent_id)
            if not parent:
                parent = await self.db.get(Jurisdiction, current.parent_id)
                if not parent:
                    break
                preload_map[parent.id] = parent
            current = parent

        return current

    @staticmethod
    def _sort_regions(regions: list[RegionSummary], sort: SortOrder) -> list[RegionSummary]:
        """Sort a list of RegionSummary objects.

        Args:
            regions: List to sort.
            sort: Sort order.

        Returns:
            list[RegionSummary]: Sorted list.
        """
        if sort == SortOrder.NAME_ASC:
            return sorted(regions, key=lambda r: r.name.lower())
        if sort == SortOrder.NAME_DESC:
            return sorted(regions, key=lambda r: r.name.lower(), reverse=True)
        if sort == SortOrder.UPDATED_DESC:
            return sorted(
                regions,
                key=lambda r: r.latest_update or "",
                reverse=True,
            )
        if sort == SortOrder.UPDATED_ASC:
            return sorted(regions, key=lambda r: r.latest_update or "")
        return regions

    @staticmethod
    def _sort_jurisdictions(
        jurisdictions: list[JurisdictionSummary], sort: SortOrder
    ) -> list[JurisdictionSummary]:
        """Sort a list of JurisdictionSummary objects.

        Args:
            jurisdictions: List to sort.
            sort: Sort order.

        Returns:
            list[JurisdictionSummary]: Sorted list.
        """
        if sort == SortOrder.NAME_ASC:
            return sorted(jurisdictions, key=lambda j: j.name.lower())
        if sort == SortOrder.NAME_DESC:
            return sorted(jurisdictions, key=lambda j: j.name.lower(), reverse=True)
        if sort == SortOrder.UPDATED_DESC:
            return sorted(jurisdictions, key=lambda j: j.updated_at, reverse=True)
        if sort == SortOrder.UPDATED_ASC:
            return sorted(jurisdictions, key=lambda j: j.updated_at)
        return jurisdictions

    async def build_hierarchy_tree(self) -> list[dict]:
        """Build the full hierarchical accordion tree of active locations.

        Preloads the active location tree in memory in a single step to avoid
        recursive N+1 DB calls, and structures a nested JSON tree.
        """
        # 1. Fetch all published blog posts
        stmt = (
            select(JurisdictionBlogPost, Jurisdiction)
            .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
            .where(JurisdictionBlogPost.is_published.is_(True))
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # Map to keep track of published posts
        published_posts = {row[1].id: row[0] for row in rows}
        active_jurs = {row[1].id: row[1] for row in rows}

        # 2. Collect all ancestor IDs to form a complete tree
        all_jur_ids = set(active_jurs.keys())

        # Traverse parent_ids that are not loaded yet
        to_check = [j.parent_id for j in active_jurs.values() if j.parent_id is not None]
        while to_check:
            next_check = []
            jurs_to_fetch = [pid for pid in to_check if pid not in all_jur_ids]
            if jurs_to_fetch:
                ancestor_stmt = select(Jurisdiction).where(
                    Jurisdiction.id.in_(jurs_to_fetch),
                    Jurisdiction.is_deleted.is_(False),
                )
                ancestor_result = await self.db.execute(ancestor_stmt)
                ancestors = ancestor_result.scalars().all()
                for ancestor in ancestors:
                    active_jurs[ancestor.id] = ancestor
                    all_jur_ids.add(ancestor.id)
                    if ancestor.parent_id is not None and ancestor.parent_id not in all_jur_ids:
                        next_check.append(ancestor.parent_id)
            to_check = next_check

        # 3. Construct the nested tree nodes
        nodes = {}
        for jur_id, jur in active_jurs.items():
            post = published_posts.get(jur_id)
            url = None
            if post:
                resource_path = await BlogGenerationService._build_public_resource_path(
                    self.db, jur, post
                )
                url = build_public_resource_url(resource_path)

            nodes[jur_id] = {
                "id": str(jur.id),
                "name": jur.name,
                "slug": _slugify(jur.name),
                "url": url,
                "children": [],
            }

        # 4. Link children to parents
        roots = []
        # Sort nodes by name so that siblings are in alphabetical order
        sorted_jurs = sorted(active_jurs.values(), key=lambda j: j.name.lower())

        for jur in sorted_jurs:
            node = nodes[jur.id]
            if jur.parent_id is None:
                roots.append(node)
            else:
                parent_node = nodes.get(jur.parent_id)
                if parent_node:
                    parent_node["children"].append(node)
                else:
                    # Fallback to root if parent was not found
                    roots.append(node)

        return roots
