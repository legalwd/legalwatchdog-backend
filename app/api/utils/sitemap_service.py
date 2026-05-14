import re
from datetime import date
from pathlib import Path
from typing import Tuple

from sitemapy import Sitemap, URLEntry
from sqlalchemy import select

from app.api.core.config import settings
from app.api.db.database import CeleryAsyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.blog_generation_service import BlogGenerationService
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project


class SitemapService:
    """Service for generating XML sitemaps and robots.txt files.

    This class writes sitemap files to `settings.BLOG_STATIC_DIR` and creates a
    sitemap index and `robots.txt` that reference the generated sitemaps.
    """

    MAX_URLS_PER_SITEMAP = settings.MAX_URLS_PER_SITEMAP
    _active_industry: str = "general"
    _active_urls: list[Tuple[str, str]] = []

    @staticmethod
    def _slugify_industry(industry: str) -> str:
        if not industry:
            return "general"

        s = industry.lower()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[-\s]+", "-", s).strip("-")
        return s or "general"

    async def generate_sitemap(self, offset: int, limit: int) -> str:
        """Generate a single sitemap file for the active industry.

        Args:
            offset: Pagination offset into active URL list.
            limit: Maximum items per sitemap file.

        Returns:
            str: Path to the written sitemap file.
        """
        urls_chunk = self._active_urls[offset : offset + limit]

        sitemap = Sitemap()
        for loc, lastmod in urls_chunk:
            sitemap.add_url(URLEntry(loc=loc, lastmod=lastmod, changefreq="weekly", priority=0.8))

        page_index = (offset // limit) + 1
        if page_index == 1:
            filename = f"sitemap-{self._active_industry}.xml"
        else:
            filename = f"sitemap-{self._active_industry}-{page_index}.xml"
        out_path = Path(settings.BLOG_STATIC_DIR) / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        sitemap.write_to_file(str(out_path))

        return str(out_path)

    async def generate_sitemap_index(self) -> str:
        """Generate a sitemap index file referencing all sitemap-*.xml files.

        Returns:
            str: Path to the written sitemap index file.
        """
        static_dir = Path(settings.BLOG_STATIC_DIR)
        static_dir.mkdir(parents=True, exist_ok=True)

        sitemap_files = sorted(static_dir.glob("sitemap-*.xml"))

        root_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]

        today = date.today().isoformat()
        for p in sitemap_files:
            base = (settings.BLOG_SITE_URL or "https://legalwatch.dog").rstrip("/")
            loc = f"{base}/{p.name}"
            root_lines.append("  <sitemap>")
            root_lines.append(f"    <loc>{loc}</loc>")
            root_lines.append(f"    <lastmod>{today}</lastmod>")
            root_lines.append("  </sitemap>")

        root_lines.append("</sitemapindex>")

        index_path = static_dir / "sitemap.xml"
        index_path.write_text("\n".join(root_lines), encoding="utf-8")

        return str(index_path)

    async def write_all(self) -> None:
        """Query published blogs and write industry sitemaps to BLOG_STATIC_DIR."""
        async with CeleryAsyncSessionLocal() as db:
            stmt = (
                select(JurisdictionBlogPost, Jurisdiction, Project, Organization)
                .join(Jurisdiction, Jurisdiction.id == JurisdictionBlogPost.jurisdiction_id)
                .join(Project, Project.id == Jurisdiction.project_id)
                .join(Organization, Organization.id == Project.org_id)
                .where(JurisdictionBlogPost.is_published.is_(True))
            )
            result = await db.execute(stmt)
            rows = result.all()
            jur_lookup = {}
            try:
                all_jurs = await db.execute(select(Jurisdiction))
                for j in all_jurs.scalars().all():
                    jur_lookup[j.id] = j
            except Exception:
                jur_lookup = {}

            industry_urls: dict[str, list[Tuple[str, str]]] = {}

            def _resolve_hierarchy_in_memory(jur_id):
                chain = []
                visited = set()
                current = jur_lookup.get(jur_id)
                while current and current.id not in visited:
                    visited.add(current.id)
                    chain.append(current)
                    current = jur_lookup.get(current.parent_id)
                chain.reverse()
                return chain

            for post, jurisdiction, _project, organization in rows:
                industry_slug = self._slugify_industry(organization.industry or "general")

                # Build resource path in-memory using preloaded jurisdictions
                project_segment = BlogGenerationService._slugify_segment(
                    _project.title if _project else "project"
                )
                hierarchy_nodes = _resolve_hierarchy_in_memory(jurisdiction.id)
                hierarchy_segments = [
                    BlogGenerationService._slugify_segment(n.name) for n in hierarchy_nodes
                ]
                post_segment = BlogGenerationService._slugify_segment(post.slug)
                resource_path = "/".join(
                    [
                        BlogGenerationService.RESOURCE_ROOT_SEGMENT,
                        project_segment,
                        *hierarchy_segments,
                        post_segment,
                    ]
                )

                loc = BlogGenerationService._build_public_resource_url(resource_path)
                lastmod = post.updated_at.date().isoformat()
                industry_urls.setdefault(industry_slug, []).append((loc, lastmod))

        for industry_slug, url_list in industry_urls.items():
            self._active_industry = industry_slug
            self._active_urls = url_list
            for offset in range(0, len(url_list), self.MAX_URLS_PER_SITEMAP):
                await self.generate_sitemap(offset, self.MAX_URLS_PER_SITEMAP)

        await self.generate_sitemap_index()
        await self.write_robots_txt()

    async def write_robots_txt(self) -> None:
        """Write a simple robots.txt that allows all and points to sitemap index."""
        static_dir = Path(settings.BLOG_STATIC_DIR)
        static_dir.mkdir(parents=True, exist_ok=True)

        sitemap_url = (
            f"{(settings.BLOG_SITE_URL or 'https://legalwatch.dog').rstrip('/')}/sitemap.xml"
        )
        content = (
            """User-agent: *
Allow: /
Sitemap: %s
"""
            % sitemap_url
        )

        robots_path = static_dir / "robots.txt"
        robots_path.write_text(content, encoding="utf-8")
