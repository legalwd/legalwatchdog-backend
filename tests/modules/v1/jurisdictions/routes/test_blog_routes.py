"""Tests for blog route handlers."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.custom_exceptions.exceptions import (
    BlogGenerationInProgressError,
    ResourceNotFoundError,
)
from app.api.modules.v1.jurisdictions.models.blog_generation_job import (
    BlogGenerationJobStatus,
)
from app.api.modules.v1.jurisdictions.routes.blog_routes import (
    _generate_blog_in_background,
    generate_blog_post,
    get_blog_post,
    get_generation_status,
    list_generation_jobs,
    publish_blog_post,
)
from app.api.modules.v1.jurisdictions.schemas.blog_schema import (
    BlogPublishRequest,
)

ROUTE_MODULE = "app.api.modules.v1.jurisdictions.routes.blog_routes"
SERVICE_MODULE = "app.api.modules.v1.jurisdictions.service.blog_generation_service"


class TestGetAllBlogPosts:
    """Tests for get_all_blog_posts endpoint (GET /blog/posts)."""

    @pytest.mark.asyncio
    async def test_get_all_blog_posts_success(self):
        org_id = uuid.uuid4()

        mock_db = AsyncMock()

        fake_response = {
            "status_code": 200,
            "message": "Blog posts retrieved successfully",
            "data": {
                "items": [{"id": "1", "title": "Test"}],
                "pagination": {"total": 1, "page": 1, "limit": 10},
            },
        }

        with patch(
            f"{ROUTE_MODULE}.blog_search_service.get_all_blog_posts_service",
            new=AsyncMock(return_value=fake_response),
        ):
            response = await __import__(
                "app.api.modules.v1.jurisdictions.routes.blog_routes",
                fromlist=["get_all_blog_posts"],
            ).get_all_blog_posts(
                organization_id=org_id,
                db=mock_db,
                query_terms="test",
                page=1,
                limit=10,
            )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["items"][0]["title"] == "Test"

    @pytest.mark.asyncio
    async def test_get_all_blog_posts_no_query_terms(self):
        """Ensure endpoint works when no query_terms provided."""
        org_id = uuid.uuid4()

        mock_db = AsyncMock()

        fake_response = {
            "status_code": 200,
            "message": "Blog posts retrieved successfully",
            "data": {
                "items": [{"id": "1", "title": "Test"}],
                "pagination": {"total": 1, "page": 1, "limit": 10},
            },
        }

        with patch(
            f"{ROUTE_MODULE}.blog_search_service.get_all_blog_posts_service",
            new=AsyncMock(return_value=fake_response),
        ):
            response = await __import__(
                "app.api.modules.v1.jurisdictions.routes.blog_routes",
                fromlist=["get_all_blog_posts"],
            ).get_all_blog_posts(
                organization_id=org_id,
                db=mock_db,
                page=1,
                limit=10,
            )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["items"][0]["title"] == "Test"


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


def _make_blog_post_stub(
    jurisdiction_id=None,
    is_published=False,
    published_at=None,
):
    """Build a minimal blog post stub for route tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_id or uuid.uuid4(),
        title="EOR Compliance Guide — California",
        slug="eor-guide-california",
        content="# California EOR\n\nContent here.",
        content_html="<h1>California EOR</h1>\n<p>Content here.</p>",
        meta_description="California EOR compliance guide.",
        keywords=["EOR", "California", "compliance"],
        is_published=is_published,
        version=1,
        content_hash="abc123",
        generation_model="openai/gpt-4o-mini",
        generated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        published_at=published_at,
    )


def _make_jurisdiction_stub(jur_id=None):
    """Build a minimal jurisdiction stub."""
    return SimpleNamespace(
        id=jur_id or uuid.uuid4(),
        name="California",
        parent_id=None,
        project_id=uuid.uuid4(),
        project=SimpleNamespace(title="Law Regulation Compliance Guide"),
    )


def _make_job_stub(jurisdiction_id=None, status=BlogGenerationJobStatus.PENDING):
    """Build a minimal BlogGenerationJob stub."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_id or uuid.uuid4(),
        status=status,
        error_message=None,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        triggered_by=None,
    )


# ──────────────────────────────────────────
# GET /{jurisdiction_id}/blog
# ──────────────────────────────────────────


class TestGetBlogPost:
    """Tests for get_blog_post endpoint."""

    @pytest.mark.asyncio
    async def test_get_blog_post_success(self):
        """Test successful blog post retrieval returns 200."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        blog = _make_blog_post_stub(jurisdiction_id=jur_id)
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=blog),
            ]
        )

        response = await get_blog_post(
            organization_id=org_id,
            jurisdiction_id=jur_id,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["status"] == "SUCCESS"
        assert body["data"]["title"] == blog.title

    @pytest.mark.asyncio
    async def test_get_blog_post_jurisdiction_not_found(self):
        """Test 404 when jurisdiction not in organization."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        with pytest.raises(ResourceNotFoundError):
            await get_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_get_blog_post_blog_not_found(self):
        """Test 404 when jurisdiction exists but no blog post."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=None),
            ]
        )

        with pytest.raises(ResourceNotFoundError):
            await get_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                db=mock_db,
            )


# ──────────────────────────────────────────
# POST /{jurisdiction_id}/blog/generate
# ──────────────────────────────────────────


class TestGenerateBlogPost:
    """Tests for generate_blog_post endpoint."""

    @pytest.mark.asyncio
    async def test_generate_blog_creates_job_and_dispatches_background_task(self):
        """Test 202 returned with job_id and background task dispatched."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)
        job = _make_job_stub(jurisdiction_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=jur))
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        # db.refresh populates the job's id
        async def _refresh_side_effect(obj):
            pass

        mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

        mock_bg_tasks = MagicMock()

        with patch(f"{SERVICE_MODULE}.BlogGenerationJob", return_value=job):
            response = await generate_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                background_tasks=mock_bg_tasks,
                db=mock_db,
            )

        body = json.loads(response.body)
        assert body["status_code"] == 202
        assert body["data"]["job_id"] == str(job.id)
        assert body["data"]["status"] == "PENDING"
        mock_bg_tasks.add_task.assert_called_once_with(_generate_blog_in_background, jur_id, job.id)

    @pytest.mark.asyncio
    async def test_generate_blog_jurisdiction_not_found(self):
        """Test 404 when jurisdiction not in organization."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        mock_bg_tasks = MagicMock()

        with pytest.raises(ResourceNotFoundError):
            await generate_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                background_tasks=mock_bg_tasks,
                db=mock_db,
            )

        mock_bg_tasks.add_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_blog_duplicate_raises_processing_error(self):
        """Test ProcessingError when active job already exists (IntegrityError)."""
        from sqlalchemy.exc import IntegrityError

        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=jur))
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("dup", {}, Exception("unique violation"))
        )
        mock_db.rollback = AsyncMock()

        mock_bg_tasks = MagicMock()

        with pytest.raises(BlogGenerationInProgressError):
            await generate_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                background_tasks=mock_bg_tasks,
                db=mock_db,
            )


# ──────────────────────────────────────────
# GET /{jurisdiction_id}/blog/generations/{job_id}
# ──────────────────────────────────────────


class TestGetGenerationStatus:
    """Tests for get_generation_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_generation_status_success(self):
        """Test successful job status retrieval returns 200."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)
        job = _make_job_stub(jurisdiction_id=jur_id, status=BlogGenerationJobStatus.COMPLETED)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=job),
            ]
        )

        response = await get_generation_status(
            organization_id=org_id,
            jurisdiction_id=jur_id,
            job_id=job.id,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["id"] == str(job.id)
        assert body["data"]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_get_generation_status_jurisdiction_not_found(self):
        """Test 404 when jurisdiction not in organization."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        with pytest.raises(ResourceNotFoundError):
            await get_generation_status(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                job_id=job_id,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_get_generation_status_job_not_found(self):
        """Test 404 when job does not exist."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        job_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=None),
            ]
        )

        with pytest.raises(ResourceNotFoundError):
            await get_generation_status(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                job_id=job_id,
                db=mock_db,
            )


# ──────────────────────────────────────────
# GET /{jurisdiction_id}/blog/generations
# ──────────────────────────────────────────


class TestListGenerationJobs:
    """Tests for list_generation_jobs endpoint."""

    @pytest.mark.asyncio
    async def test_list_generation_jobs_success(self):
        """Test paginated list returns 200 with items and pagination."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)
        job1 = _make_job_stub(jurisdiction_id=jur_id, status=BlogGenerationJobStatus.COMPLETED)
        job2 = _make_job_stub(jurisdiction_id=jur_id, status=BlogGenerationJobStatus.PENDING)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarResult(value=2),
                MockScalarsAllResult(items=[job1, job2]),
            ]
        )

        response = await list_generation_jobs(
            organization_id=org_id,
            jurisdiction_id=jur_id,
            page=1,
            limit=10,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert len(body["data"]["items"]) == 2
        assert body["data"]["pagination"]["total"] == 2

    @pytest.mark.asyncio
    async def test_list_generation_jobs_empty(self):
        """Test empty list returns 200 with zero items."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarResult(value=0),
                MockScalarsAllResult(items=[]),
            ]
        )

        response = await list_generation_jobs(
            organization_id=org_id,
            jurisdiction_id=jur_id,
            page=1,
            limit=10,
            db=mock_db,
        )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["items"] == []
        assert body["data"]["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_generation_jobs_jurisdiction_not_found(self):
        """Test 404 when jurisdiction not in organization."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        with pytest.raises(ResourceNotFoundError):
            await list_generation_jobs(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                page=1,
                limit=10,
                db=mock_db,
            )


# ──────────────────────────────────────────
# PATCH /{jurisdiction_id}/blog/publish
# ──────────────────────────────────────────


class TestPublishBlogPost:
    """Tests for publish_blog_post endpoint."""

    @pytest.mark.asyncio
    async def test_publish_blog_post_success(self):
        """Test publishing sets is_published and published_at."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)
        blog = _make_blog_post_stub(jurisdiction_id=jur_id, is_published=False)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=blog),
            ]
        )
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        payload = BlogPublishRequest(is_published=True)

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            response = await publish_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                payload=payload,
                db=mock_db,
            )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["is_published"] is True
        assert body["data"]["public_url"].startswith("https://")
        assert body["data"]["public_url"].endswith("/")
        assert blog.is_published is True
        assert blog.published_at is not None
        mock_db.commit.assert_called_once()
        mock_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unpublish_blog_post_clears_published_at(self):
        """Test unpublishing clears published_at."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)
        blog = _make_blog_post_stub(
            jurisdiction_id=jur_id,
            is_published=True,
            published_at=datetime.now(timezone.utc),
        )

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=blog),
            ]
        )
        mock_db.get = AsyncMock(
            return_value=SimpleNamespace(title="Law Regulation Compliance Guide")
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        payload = BlogPublishRequest(is_published=False)

        with patch("asyncio.to_thread", new_callable=AsyncMock):
            response = await publish_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                payload=payload,
                db=mock_db,
            )

        body = json.loads(response.body)
        assert body["status_code"] == 200
        assert body["data"]["is_published"] is False
        assert body["data"]["public_url"] is None
        assert blog.is_published is False
        assert blog.published_at is None

    @pytest.mark.asyncio
    async def test_publish_blog_post_not_found(self):
        """Test 404 when blog post does not exist."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction_stub(jur_id=jur_id)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=None),
            ]
        )

        payload = BlogPublishRequest(is_published=True)

        with pytest.raises(ResourceNotFoundError):
            await publish_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                payload=payload,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_publish_blog_jurisdiction_not_found(self):
        """Test 404 when jurisdiction not in organization."""
        org_id = uuid.uuid4()
        jur_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        payload = BlogPublishRequest(is_published=True)

        with pytest.raises(ResourceNotFoundError):
            await publish_blog_post(
                organization_id=org_id,
                jurisdiction_id=jur_id,
                payload=payload,
                db=mock_db,
            )


# ──────────────────────────────────────────
# _generate_blog_in_background
# ──────────────────────────────────────────


class TestGenerateBlogInBackground:
    """Tests for _generate_blog_in_background helper."""

    @pytest.mark.asyncio
    @patch(f"{ROUTE_MODULE}.BlogGenerationService")
    @patch(f"{ROUTE_MODULE}.SyncSessionLocal")
    async def test_background_gen_calls_sync_service_with_job_id(
        self, mock_session_cls, mock_svc_cls
    ):
        """Test background task creates sync session and calls service with job_id."""
        jur_id = uuid.uuid4()
        job_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_svc = MagicMock()
        mock_svc.generate_blog_post_sync.return_value = {
            "status": "success",
            "jurisdiction_id": str(jur_id),
            "message": "Blog generated",
            "version": 1,
        }
        mock_svc_cls.return_value = mock_svc

        await _generate_blog_in_background(jur_id, job_id)

        mock_session_cls.assert_called_once()
        mock_svc_cls.assert_called_once_with(mock_session)
        mock_svc.generate_blog_post_sync.assert_called_once_with(jur_id, job_id=job_id)
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{ROUTE_MODULE}.BlogGenerationService")
    @patch(f"{ROUTE_MODULE}.SyncSessionLocal")
    async def test_background_gen_closes_session_on_error(self, mock_session_cls, mock_svc_cls):
        """Test session is closed even when service raises."""
        jur_id = uuid.uuid4()
        job_id = uuid.uuid4()
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_svc = MagicMock()
        mock_svc.generate_blog_post_sync.side_effect = Exception("boom")
        mock_svc_cls.return_value = mock_svc

        await _generate_blog_in_background(jur_id, job_id)

        mock_session.close.assert_called_once()
