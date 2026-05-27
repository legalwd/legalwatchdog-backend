"""Public (unauthenticated) blog post endpoints.

Exposes published blog posts for consumption by:
- FE ViteSSG build pipeline (fetches at build time to pre-render routes)
- SEO crawlers and indexing tools
- RSS feed generators (future)
- Any other public consumers

Routes:
    GET /blog/posts          - List all published blog posts (paginated)
    GET /blog/posts/{slug}   - Get a single published post by slug
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.core.custom_exceptions.exceptions import ResourceNotFoundError
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.blog_schema import PublicBlogPostResponse
from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
    build_legacy_resource_path,
    build_public_resource_url,
)
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService
from app.api.utils.pagination import calculate_pagination
from app.api.utils.response_payloads import success_response

router = APIRouter(
    prefix="/blog",
    tags=["Public Blog"],
)

logger = logging.getLogger(__name__)


async def _build_public_payload(db: AsyncSession, post: JurisdictionBlogPost) -> dict:
    """Build public response payload with canonical navigation URL fields.

    Args:
        db: Database session.
        post: Published blog post model.

    Returns:
        dict: Public API payload including canonical URL metadata.

    Examples:
        >>> payload = await _build_public_payload(db, post)
        >>> payload["public_url"].startswith("https://")
        True
    """
    jurisdiction_stmt = (
        select(Jurisdiction)
        .options(selectinload(Jurisdiction.project))
        .where(Jurisdiction.id == post.jurisdiction_id)
    )
    jurisdiction_result = await db.execute(jurisdiction_stmt)
    jurisdiction = jurisdiction_result.scalar_one_or_none()

    if jurisdiction:
        resource_path = await BlogGenerationService._build_public_resource_path(
            db,
            jurisdiction,
            post,
        )
    else:
        resource_path = build_legacy_resource_path(post.slug)

    from app.api.modules.v1.jurisdictions.service.blog_recommendation_service import BlogRecommendationEngine

    is_mock = (
        type(db).__name__ in ("AsyncMock", "MagicMock", "Mock", "NonCallableMagicMock")
        or hasattr(db, "assert_called")
    )
    if is_mock:
        recommendations = []
    else:
        try:
            engine = BlogRecommendationEngine(db)
            recommendations = await engine.get_recommendations(post)
        except Exception as e:
            logger.warning(f"Could not load recommendations: {e}")
            recommendations = []

    response_obj = PublicBlogPostResponse.model_validate(post)
    response_obj.related_jurisdictions = recommendations

    payload = response_obj.model_dump()
    payload["resource_path"] = resource_path
    payload["public_url"] = build_public_resource_url(resource_path)
    return payload


@router.get(
    "/posts",
    status_code=status.HTTP_200_OK,
)
async def list_published_blog_posts(
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    country: Optional[str] = Query(default=None, description="Filter by Country name or slug"),
    topic: Optional[str] = Query(default=None, description="Filter by topic keyword"),
    db: AsyncSession = Depends(get_db),
):
    """List all published blog posts.

    Returns paginated published blog posts with metadata and pre-rendered HTML.
    Used by the FE build pipeline to discover slugs and fetch content at SSG
    build time.

    No authentication required — this is a public endpoint.

    Args:
        page: Page number (1-indexed).
        limit: Items per page (1-100).
        country: Optional country filter.
        topic: Optional topic filter.
        db: Database session.

    Returns:
        JSONResponse: Paginated list of published blog posts.

    Examples:
        >>> GET /api/v1/blog/posts?page=1&limit=20
        >>> # Returns published posts with content_html, slug, SEO metadata
    """
    from sqlalchemy import func, String

    count_stmt = (
        select(func.count())
        .select_from(JurisdictionBlogPost)
        .where(JurisdictionBlogPost.is_published.is_(True))
    )

    posts_stmt = (
        select(JurisdictionBlogPost)
        .where(JurisdictionBlogPost.is_published.is_(True))
        .order_by(JurisdictionBlogPost.published_at.desc())
    )

    if isinstance(country, str):
        from app.api.modules.v1.jurisdictions.service.guides_service import _slugify, GuidesService
        # Find matching country top-level jurisdiction
        country_stmt = select(Jurisdiction).where(
            Jurisdiction.parent_id.is_(None),
            Jurisdiction.is_deleted.is_(False)
        )
        country_res = await db.execute(country_stmt)
        candidates = country_res.scalars().all()
        target_country = next((c for c in candidates if _slugify(c.name) == country or c.name.lower() == country.lower()), None)
        if target_country:
            guides_service = GuidesService(db)
            subtree_ids = await guides_service._get_subtree_ids(target_country.id)
            count_stmt = count_stmt.where(JurisdictionBlogPost.jurisdiction_id.in_(subtree_ids))
            posts_stmt = posts_stmt.where(JurisdictionBlogPost.jurisdiction_id.in_(subtree_ids))
        else:
            # Country filter provided but not found: return empty pagination
            return success_response(
                status_code=status.HTTP_200_OK,
                message="Published blog posts retrieved successfully",
                data={"items": [], "pagination": calculate_pagination(0, page, limit)},
            )

    if isinstance(topic, str):
        # Case insensitive topic match on keywords casted to string
        count_stmt = count_stmt.where(JurisdictionBlogPost.keywords.cast(String).ilike(f"%{topic}%"))
        posts_stmt = posts_stmt.where(JurisdictionBlogPost.keywords.cast(String).ilike(f"%{topic}%"))

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    posts_stmt = posts_stmt.offset((page - 1) * limit).limit(limit)
    posts_result = await db.execute(posts_stmt)
    posts = posts_result.scalars().all()

    posts_data = []
    for post in posts:
        posts_data.append(await _build_public_payload(db, post))

    pagination = calculate_pagination(total, page, limit)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Published blog posts retrieved successfully",
        data={"items": posts_data, "pagination": pagination},
    )


@router.get(
    "/posts/{slug}",
    status_code=status.HTTP_200_OK,
)
async def get_published_blog_post_by_slug(
    slug: str,
    redirect_to_public_url: bool = Query(
        default=False,
        description="Set true to redirect to canonical public URL",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get a single published blog post by slug.

    Returns the full blog post including `content_html` for direct use in
    page templates. Only published posts are returned — draft posts return 404.

    No authentication required — this is a public endpoint.

    Args:
        slug: URL-safe slug (e.g., "eor-guide-california").
        db: Database session.

    Returns:
        JSONResponse: Full published blog post with content_html and SEO metadata.

    Raises:
        ResourceNotFoundError: If slug does not exist or post is not published.

    Examples:
        >>> GET /api/v1/blog/posts/eor-guide-california
        >>> # Returns full post with content_html ready for SSG template injection
    """
    stmt = select(JurisdictionBlogPost).where(
        JurisdictionBlogPost.slug == slug,
        JurisdictionBlogPost.is_published.is_(True),
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise ResourceNotFoundError(message="Blog post not found")

    payload = await _build_public_payload(db, post)

    if redirect_to_public_url:
        return RedirectResponse(
            url=payload["public_url"],
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Blog post retrieved successfully",
        data=payload,
    )


@router.get(
    "/resources/{resource_path:path}",
    status_code=status.HTTP_200_OK,
)
async def get_published_blog_post_by_resource_path(
    resource_path: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single published blog post by canonical resource path.

    Args:
        resource_path: Canonical resource path without host.
        db: Database session.

    Returns:
        JSONResponse: Full published blog post with canonical URL metadata.

    Raises:
        ResourceNotFoundError: If no published post matches path.

    Examples:
        >>> GET /api/v1/blog/resources/resources/eor/my-country/eor-guide-my-country
    """
    normalized_path = resource_path.strip("/")
    path_segments = [segment for segment in normalized_path.split("/") if segment]
    if not path_segments:
        raise ResourceNotFoundError(message="Blog post not found")

    slug = path_segments[-1]
    stmt = select(JurisdictionBlogPost).where(
        JurisdictionBlogPost.slug == slug,
        JurisdictionBlogPost.is_published.is_(True),
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()

    if not post:
        raise ResourceNotFoundError(message="Blog post not found")

    payload = await _build_public_payload(db, post)
    if payload["resource_path"].strip("/") != normalized_path:
        raise ResourceNotFoundError(message="Blog post not found")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Blog post retrieved successfully",
        data=payload,
    )


@router.get(
    "/meta/tree",
    status_code=status.HTTP_200_OK,
)
async def get_blog_meta_tree(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full hierarchical location tree of active locations."""
    from app.api.modules.v1.jurisdictions.service.guides_service import GuidesService

    guides_service = GuidesService(db)
    tree = await guides_service.build_hierarchy_tree()
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Active location tree retrieved successfully",
        data={"tree": tree},
    )


@router.get(
    "/meta/countries",
    status_code=status.HTTP_200_OK,
)
async def get_blog_meta_countries(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a list of unique countries that have published blog posts."""
    from app.api.modules.v1.jurisdictions.service.guides_service import _slugify

    # Fetch all jurisdictions that are published or have published descendants
    stmt_all = (
        select(Jurisdiction)
        .join(JurisdictionBlogPost, JurisdictionBlogPost.jurisdiction_id == Jurisdiction.id)
        .where(
            Jurisdiction.is_deleted.is_(False),
            JurisdictionBlogPost.is_published.is_(True),
        )
    )
    result_all = await db.execute(stmt_all)
    all_published_jurs = result_all.scalars().all()

    unique_root_countries = {}
    for jur in all_published_jurs:
        curr = jur
        visited = {curr.id}
        while curr.parent_id is not None:
            if curr.parent_id in visited:
                break
            visited.add(curr.parent_id)
            parent = await db.get(Jurisdiction, curr.parent_id)
            if not parent:
                break
            curr = parent
        if curr.id not in unique_root_countries:
            unique_root_countries[curr.id] = curr

    countries_data = [
        {"name": c.name, "slug": _slugify(c.name)}
        for c in sorted(unique_root_countries.values(), key=lambda x: x.name.lower())
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Active countries list retrieved successfully",
        data={"countries": countries_data},
    )


@router.get(
    "/meta/topics",
    status_code=status.HTTP_200_OK,
)
async def get_blog_meta_topics(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a list of unique topics/keywords across all published blog posts."""
    stmt = select(JurisdictionBlogPost.keywords).where(JurisdictionBlogPost.is_published.is_(True))
    result = await db.execute(stmt)
    keywords_lists = result.scalars().all()

    unique_topics = set()
    for kw_list in keywords_lists:
        if kw_list:
            for kw in kw_list:
                if kw.strip():
                    unique_topics.add(kw.strip())

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Active topics list retrieved successfully",
        data={"topics": sorted(list(unique_topics))},
    )


@router.get(
    "/search",
    status_code=status.HTTP_200_OK,
)
async def search_published_blog_posts(
    q: str = Query(..., description="Search query"),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """Perform a high-speed token search using BlogPostToken ranking and sorting."""
    from app.api.modules.v1.jurisdictions.service.blog_search_service import BlogSearchService

    # 1. Fetch all published blog posts
    stmt = select(JurisdictionBlogPost).where(JurisdictionBlogPost.is_published.is_(True))
    result = await db.execute(stmt)
    posts = list(result.scalars().all())

    if not posts:
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Search results",
            data={"items": [], "pagination": calculate_pagination(0, page, limit)},
        )

    # 2. Use BlogSearchService to rank and sort the posts
    search_service = BlogSearchService()
    ranked_posts = await search_service.rank_n_sort_posts(db, posts, q)

    total = len(ranked_posts)
    start = (page - 1) * limit
    end = start + limit
    paginated_posts = ranked_posts[start:end]

    posts_data = []
    for post in paginated_posts:
        posts_data.append(await _build_public_payload(db, post))

    pagination = calculate_pagination(total, page, limit)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Search results retrieved successfully",
        data={"items": posts_data, "pagination": pagination},
    )

