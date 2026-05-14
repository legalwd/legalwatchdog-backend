from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.modules.v1.jurisdictions.service.blog_search_service import (
    BlogSearchService,
)


class TestBlogSearchServiceGetAll:
    @pytest.mark.asyncio
    async def test_get_all_blog_posts_service_success(self):
        svc = BlogSearchService()

        org_id = uuid4()

        # Create a minimal post stub that will be returned by ranking
        post = SimpleNamespace(id=uuid4(), updated_at=datetime.now(timezone.utc))

        mock_db = AsyncMock()

        # Patch crud.get_all_blog_post to return our posts
        with (
            patch(
                "app.api.modules.v1.jurisdictions.service.blog_search_service.crud.get_all_blog_post",
                new=AsyncMock(return_value=[post]),
            ),
            patch(
                "app.api.modules.v1.jurisdictions.service.blog_search_service.BlogSearchService.rank_n_sort_posts",
                new=AsyncMock(return_value=[post]),
            ),
            patch(
                "app.api.modules.v1.jurisdictions.service.blog_search_service.BlogPostResponse.model_validate",
                new=MagicMock(
                    return_value=SimpleNamespace(model_dump=lambda mode=None: {"id": str(post.id)})
                ),
            ),
        ):
            result = await svc.get_all_blog_posts_service(
                db=mock_db, query_terms="test query", organization_id=org_id, page=1, limit=10
            )

        assert result["status_code"] == 200
        assert "data" in result
        assert isinstance(result["data"], dict)
        assert "items" in result["data"]
        assert len(result["data"]["items"]) == 1
