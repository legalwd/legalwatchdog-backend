from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.core.config import settings
from app.api.modules.v1.jurisdictions.service.sitemap_tasks import sitemap_rebuild_debounced
from app.api.utils.sitemap_service import SitemapService


@pytest.mark.asyncio
async def test_generate_sitemap_xml_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BLOG_STATIC_DIR", str(tmp_path))

    service = SitemapService()
    service._active_industry = "eor"
    service._active_urls = [
        (
            "https://legalwatch.dog/resources/project/california/eor-guide-california/",
            "2026-03-09",
        )
    ]

    path = await service.generate_sitemap(offset=0, limit=50_000)
    content = (tmp_path / "sitemap-eor.xml").read_text(encoding="utf-8")

    assert path.endswith("sitemap-eor.xml")
    assert "<urlset" in content
    assert (
        "<loc>https://legalwatch.dog/resources/project/california/"
        "eor-guide-california/</loc>" in content
    )
    assert "<lastmod>2026-03-09</lastmod>" in content
    assert "<changefreq>weekly</changefreq>" in content
    assert "<priority>0.8</priority>" in content


@pytest.mark.asyncio
async def test_generate_sitemap_index(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BLOG_STATIC_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BLOG_SITE_URL", "https://www.legalwatch.dog/blogs")

    (tmp_path / "sitemap-eor.xml").write_text("<urlset/>", encoding="utf-8")
    (tmp_path / "sitemap-data-privacy-2.xml").write_text("<urlset/>", encoding="utf-8")

    service = SitemapService()
    index_path = await service.generate_sitemap_index()
    index_content = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")

    assert index_path.endswith("sitemap.xml")
    assert "<sitemapindex" in index_content
    assert "https://www.legalwatch.dog/blogs/sitemap-eor.xml" in index_content
    assert "https://www.legalwatch.dog/blogs/sitemap-data-privacy-2.xml" in index_content


@pytest.mark.asyncio
async def test_sitemap_respects_50k_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BLOG_STATIC_DIR", str(tmp_path))

    service = SitemapService()
    service._active_industry = "eor"
    service._active_urls = [
        (f"https://legalwatch.dog/resources/eor/post-{idx}/", "2026-03-09") for idx in range(50_001)
    ]

    for offset in range(0, len(service._active_urls), service.MAX_URLS_PER_SITEMAP):
        await service.generate_sitemap(offset, service.MAX_URLS_PER_SITEMAP)

    assert (tmp_path / "sitemap-eor.xml").exists()
    assert (tmp_path / "sitemap-eor-2.xml").exists()


@pytest.mark.asyncio
async def test_write_robots_txt(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BLOG_STATIC_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BLOG_SITE_URL", "https://www.legalwatch.dog/blogs")

    service = SitemapService()
    await service.write_robots_txt()

    robots_content = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots_content
    assert "Allow: /" in robots_content
    assert "Sitemap: https://www.legalwatch.dog/blogs/sitemap.xml" in robots_content


def test_sitemap_rebuild_debounced_skips_if_lock_held():
    redis_client = MagicMock()
    redis_client.set.return_value = False
    redis_client.close = MagicMock()

    with (
        patch(
            "app.api.modules.v1.jurisdictions.service.sitemap_tasks.redis.Redis.from_url",
            return_value=redis_client,
        ),
        patch(
            "app.api.modules.v1.jurisdictions.service.sitemap_tasks.SitemapService.write_all",
            new=AsyncMock(),
        ) as mock_write_all,
    ):
        result = sitemap_rebuild_debounced()

    assert result["status"] == "skipped"
    assert result["reason"] == "lock_held"
    mock_write_all.assert_not_awaited()
