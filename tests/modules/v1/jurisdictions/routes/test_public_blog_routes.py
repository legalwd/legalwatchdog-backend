"""Tests for public (unauthenticated) blog post API endpoints."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.core.custom_exceptions.exceptions import ResourceNotFoundError
from app.api.modules.v1.jurisdictions.routes.public_blog_routes import (
    get_published_blog_post_by_resource_path,
    get_published_blog_post_by_slug,
    list_published_blog_posts,
)

PUBLIC_ROUTE_MODULE = "app.api.modules.v1.jurisdictions.routes.public_blog_routes"


class MockScalarsResult:
    """Mock for result.scalar_one_or_none() chain."""

    def __init__(self, item=None):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class MockScalarResult:
    """Mock for result.scalar() chain (used for count queries)."""

    def __init__(self, value=0):
        self._value = value

    def scalar(self):
        return self._value


class MockScalarsAllResult:
    """Mock for result.scalars().all() chain (used for list queries)."""

    def __init__(self, items=None):
        self._items = items or []

    def scalars(self):
        return self

    def all(self):
        return self._items


def _make_published_post(
    slug="eor-guide-california",
    title="EOR Guide California",
    jurisdiction_id=None,
    published_at=None,
):
    """Build a minimal published blog post stub."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_id or uuid.uuid4(),
        slug=slug,
        title=title,
        content_html="<h1>EOR Guide</h1><p>Content here.</p>",
        meta_description="California EOR compliance guide.",
        keywords=["EOR", "California"],
        is_published=True,
        published_at=published_at or datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_jurisdiction(jurisdiction_id):
    """Build a minimal jurisdiction stub for canonical path building."""
    return SimpleNamespace(
        id=jurisdiction_id,
        name="Nigeria Employment Rules",
        parent_id=None,
        project_id=uuid.uuid4(),
        project=SimpleNamespace(title="Law Regulation Compliance Guide"),
    )


# ──────────────────────────────────────────
# GET /blog/posts
# ──────────────────────────────────────────


class TestListPublishedBlogPosts:
    """Tests for list_published_blog_posts endpoint."""

    @pytest.mark.asyncio
    async def test_returns_200_with_items_and_pagination(self):
        """Test returns paginated list of published posts."""
        post1 = _make_published_post(slug="post-one")
        post2 = _make_published_post(slug="post-two")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarResult(value=2),
                MockScalarsAllResult(items=[post1, post2]),
                MockScalarsResult(item=_make_jurisdiction(post1.jurisdiction_id)),
                MockScalarsResult(item=_make_jurisdiction(post2.jurisdiction_id)),
            ]
        )

        response = await list_published_blog_posts(page=1, limit=20, db=mock_db)

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["status"] == "SUCCESS"
        assert len(body["data"]["items"]) == 2
        assert "public_url" in body["data"]["items"][0]
        assert "resource_path" in body["data"]["items"][0]
        assert body["data"]["pagination"]["total"] == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_published_posts(self):
        """Test returns empty items list when no posts are published."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarResult(value=0),
                MockScalarsAllResult(items=[]),
            ]
        )

        response = await list_published_blog_posts(page=1, limit=20, db=mock_db)

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["items"] == []
        assert body["data"]["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_response_items_contain_slug_and_content_html(self):
        """Test each returned item includes slug and content_html fields."""
        post = _make_published_post(slug="test-slug")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarResult(value=1),
                MockScalarsAllResult(items=[post]),
                MockScalarsResult(item=_make_jurisdiction(post.jurisdiction_id)),
            ]
        )

        response = await list_published_blog_posts(page=1, limit=20, db=mock_db)

        body = json.loads(response.body)
        item = body["data"]["items"][0]
        assert item["slug"] == "test-slug"
        assert "content_html" in item
        assert "title" in item
        assert "meta_description" in item
        assert "keywords" in item
        assert item["public_url"].startswith("https://")
        assert item["resource_path"].startswith("resources/")

    @pytest.mark.asyncio
    async def test_pagination_second_page(self):
        """Test pagination metadata is correct for non-first pages."""
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarResult(value=25),
                MockScalarsAllResult(items=[_make_published_post()]),
                MockScalarsResult(item=_make_jurisdiction(uuid.uuid4())),
            ]
        )

        response = await list_published_blog_posts(page=2, limit=20, db=mock_db)

        body = json.loads(response.body)
        assert body["data"]["pagination"]["total"] == 25
        assert len(body["data"]["items"]) == 1


# ──────────────────────────────────────────
# GET /blog/posts/{slug}
# ──────────────────────────────────────────


class TestGetPublishedBlogPostBySlug:
    """Tests for get_published_blog_post_by_slug endpoint."""

    @pytest.mark.asyncio
    async def test_returns_200_with_full_post(self):
        """Test returns full post data for a valid published slug."""
        slug = "eor-guide-california"
        post = _make_published_post(slug=slug)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=_make_jurisdiction(post.jurisdiction_id)),
            ]
        )

        response = await get_published_blog_post_by_slug(
            slug=slug,
            redirect_to_public_url=False,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["status"] == "SUCCESS"
        assert body["data"]["slug"] == slug
        assert body["data"]["content_html"] == post.content_html
        assert body["data"]["public_url"].startswith("https://")

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_slug(self):
        """Test raises ResourceNotFoundError when slug does not exist."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        with pytest.raises(ResourceNotFoundError):
            await get_published_blog_post_by_slug(slug="unknown-slug", db=mock_db)

    @pytest.mark.asyncio
    async def test_response_includes_seo_fields(self):
        """Test returned post includes meta_description and keywords."""
        post = _make_published_post(slug="seo-test")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=_make_jurisdiction(post.jurisdiction_id)),
            ]
        )

        response = await get_published_blog_post_by_slug(
            slug="seo-test",
            redirect_to_public_url=False,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert "meta_description" in body["data"]
        assert "keywords" in body["data"]
        assert "published_at" in body["data"]

    @pytest.mark.asyncio
    async def test_response_does_not_include_internal_fields(self):
        """Test internal fields like content_hash are not exposed in public response."""
        post = _make_published_post(slug="internal-test")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=_make_jurisdiction(post.jurisdiction_id)),
            ]
        )

        response = await get_published_blog_post_by_slug(
            slug="internal-test",
            redirect_to_public_url=False,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert "content_hash" not in body["data"]
        assert "generation_model" not in body["data"]
        assert "version" not in body["data"]

    @pytest.mark.asyncio
    async def test_can_redirect_to_public_url(self):
        """Test slug endpoint can redirect to canonical public URL."""
        post = _make_published_post(slug="redirect-test")

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=_make_jurisdiction(post.jurisdiction_id)),
            ]
        )

        response = await get_published_blog_post_by_slug(
            slug="redirect-test",
            redirect_to_public_url=True,
            db=mock_db,
        )

        assert response.status_code == 307
        assert response.headers["location"].startswith("https://")


class TestGetPublishedBlogPostByResourcePath:
    """Tests for get_published_blog_post_by_resource_path endpoint."""

    @pytest.mark.asyncio
    async def test_returns_post_for_matching_resource_path(self):
        """Test canonical path endpoint returns post when path matches."""
        post = _make_published_post(slug="employment-rules-guide")
        jurisdiction = _make_jurisdiction(post.jurisdiction_id)
        resource_path = "resources/law-regulation-compliance-guide/nigeria-employment-rules"
        resource_path = f"{resource_path}/employment-rules-guide"

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=jurisdiction),
            ]
        )

        response = await get_published_blog_post_by_resource_path(
            resource_path=resource_path,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["resource_path"] == resource_path

    @pytest.mark.asyncio
    async def test_raises_404_for_mismatched_resource_path(self):
        """Test canonical path endpoint raises when resolved path does not match."""
        post = _make_published_post(slug="employment-rules-guide")
        jurisdiction = _make_jurisdiction(post.jurisdiction_id)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=post),
                MockScalarsResult(item=jurisdiction),
            ]
        )

        with pytest.raises(ResourceNotFoundError):
            await get_published_blog_post_by_resource_path(
                resource_path="resources/other/path/employment-rules-guide",
                db=mock_db,
            )
