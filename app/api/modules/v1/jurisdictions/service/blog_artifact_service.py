"""Service for rendering and publishing blog post HTML artifacts.

Converts stored Markdown to an HTML body fragment, then writes a complete
self-contained HTML page to the static artifact directory on publish.
The artifact is served directly by Nginx without touching the FastAPI process
at request time.

Design decisions:
- Markdown → HTML conversion happens at generation time (_render_html_body).
  The result is stored in `content_html` in the database.
- Artifact writing (full page shell + content_html → file on disk) happens at
  publish time (_write_artifact / _delete_artifact).
- The HTML shell is intentionally minimal: no SPA bundles, no Vite-hashed assets.
  It references a stable versioned CSS URL owned by the FE team (BLOG_CSS_URL).
"""

import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.api.core.config import settings
from app.api.core.logger import logger
from app.api.db.database import SyncSessionLocal
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.projects.models.project_model import Project

_HTML_SHELL = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | {site_name}</title>
  <meta name="description" content="{meta_description}">
  <meta name="keywords" content="{keywords}">
  <meta name="robots" content="{robots_content}">

  <!-- Open Graph -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:site_name" content="{site_name}">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{meta_description}">

  <link rel="canonical" href="{canonical_url}">
  <link rel="alternate" hreflang="en" href="{canonical_url}">
  <link rel="stylesheet" href="{css_url}">

  <!-- Article structured data -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{title}",
    "description": "{meta_description}",
    "datePublished": "{published_at}",
    "dateModified": "{date_modified}",
    "publisher": {{
      "@type": "Organization",
      "name": "{site_name}"
    }}
  }}
  </script>
  {breadcrumb_jsonld}
</head>
<body class="lwd-blog">
  <main class="blog-post-container">
    {breadcrumb_nav_html}
    <article class="blog-post" itemscope itemtype="https://schema.org/Article">
      <header class="blog-post__header">
        <h1 class="blog-post__title" itemprop="headline">{title}</h1>
        <div class="blog-post__meta">
          <time class="blog-post__date" datetime="{published_at_iso}"
                itemprop="datePublished">{published_at_human}</time>
          <span class="blog-post__update-label">
            Last updated: <time datetime="{date_modified}">{date_modified_human}</time>
          </span>
        </div>
      </header>
      <div class="blog-post__content" itemprop="articleBody">
        {content_html}
      </div>
      {related_jurisdictions_html}
    </article>
  </main>
</body>
</html>
"""

_LEGACY_REDIRECT_SHELL = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0;url={canonical_url}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical_url}">
    <title>Redirecting…</title>
    <script>
        window.location.replace("{canonical_url}");
    </script>
</head>
<body>
    <p>Redirecting to <a href="{canonical_url}">{canonical_url}</a></p>
</body>
</html>
"""


def _normalize_resource_path(resource_path: str) -> str:
    """Normalize a resource path to a clean relative path.

    Args:
        resource_path (str): Resource path or slug.

    Returns:
        str: Normalized relative path without leading/trailing slashes.

    Examples:
        >>> _normalize_resource_path("/resources/post/")
        'resources/post'
    """
    stripped = resource_path.strip("/")
    parts = [part for part in stripped.split("/") if part]
    return "/".join(parts)


def build_legacy_resource_path(slug: str) -> str:
    """Build the legacy resource path from a post slug.

    Args:
        slug (str): Blog post slug.

    Returns:
        str: Legacy resource path under the resources directory.

    Examples:
        >>> build_legacy_resource_path("eor-guide-california")
        'resources/eor-guide-california'
    """
    return f"resources/{slug.strip('/')}"


def build_public_resource_url(resource_path: str) -> str:
    """Build an absolute public URL for a blog resource path.

    Args:
        resource_path (str): Relative resource path.

    Returns:
        str: Absolute public URL with a trailing slash.

    Examples:
        >>> build_public_resource_url("resources/eor-guide-california")
        'https://legalwatch.dog/resources/eor-guide-california/'
    """
    normalized_path = _normalize_resource_path(resource_path)
    base = (settings.BLOG_SITE_URL or "https://legalwatch.dog").rstrip("/")
    return f"{base}/{normalized_path}/"


def _write_file_atomic(file_path: Path, content: str) -> None:
    """Write a file atomically using a temporary file and rename.

    Args:
        file_path (Path): Destination file path.
        content (str): File content.

    Returns:
        None: This function does not return a value.

    Examples:
        >>> _write_file_atomic(Path("index.html"), "<html></html>")
    """
    tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(file_path)


def _slugify_segment(value: Optional[str]) -> str:
    if not value:
        return "item"

    normalized = re.sub(r"[^\w\s-]", "", value.lower()).strip()
    normalized = re.sub(r"[-\s]+", "-", normalized)
    return normalized or "item"


def _build_jurisdiction_hierarchy_sync(
    db, jurisdiction: Jurisdiction, preload: Optional[dict] = None
) -> list[Jurisdiction]:
    """Build the parent chain for a jurisdiction.

    This function supports an optional `preload` mapping of id -> Jurisdiction
    so callers can resolve the chain in-memory and avoid repeated DB calls.
    """
    chain: list[Jurisdiction] = [jurisdiction]
    current_parent_id = jurisdiction.parent_id
    visited = set()

    while current_parent_id and current_parent_id not in visited:
        visited.add(current_parent_id)
        if preload is not None:
            parent = preload.get(current_parent_id)
        else:
            parent = db.get(Jurisdiction, current_parent_id)

        if not parent:
            break
        chain.append(parent)
        current_parent_id = parent.parent_id

    chain.reverse()
    return chain


def _build_resource_path_for_post(
    db,
    jurisdiction: Jurisdiction,
    post: JurisdictionBlogPost,
    preload: Optional[dict] = None,
    project: Optional[Project] = None,
) -> str:
    if project is None:
        project = db.get(Project, jurisdiction.project_id)
    project_segment = _slugify_segment(project.title if project else "project")
    hierarchy = _build_jurisdiction_hierarchy_sync(db, jurisdiction, preload=preload)
    hierarchy_segments = [_slugify_segment(node.name) for node in hierarchy]
    post_segment = _slugify_segment(post.slug)
    return "/".join(["resources", project_segment, *hierarchy_segments, post_segment])


def _load_published_post_for_jurisdiction(db, jurisdiction_id) -> Optional[JurisdictionBlogPost]:
    stmt = select(JurisdictionBlogPost).where(
        JurisdictionBlogPost.jurisdiction_id == jurisdiction_id,
        JurisdictionBlogPost.is_published.is_(True),
    )
    result = db.execute(stmt)
    return result.scalar_one_or_none()


def _build_breadcrumb_nav_html(breadcrumbs: list[dict]) -> str:
    """Build a visible HTML breadcrumb navigation bar from precomputed breadcrumbs.

    Uses schema.org microdata attributes so the visual nav doubles as
    structured data for search engines.

    Args:
        breadcrumbs: List of {"name": str, "url": str} dicts from blog post.

    Returns:
        str: HTML <nav> breadcrumb block, or empty string if no breadcrumbs.

    Examples:
        >>> crumbs = [{"name": "United States", "url": "https://..."}]
        >>> html = _build_breadcrumb_nav_html(crumbs)
        >>> '<nav' in html
        True
    """
    if not breadcrumbs:
        return ""

    items = []
    for idx, crumb in enumerate(breadcrumbs):
        name = _escape_attr(crumb.get("name", ""))
        url = _escape_attr(crumb.get("url", ""))
        is_last = idx == len(breadcrumbs) - 1
        if is_last:
            items.append(
                f'<li class="breadcrumb__item breadcrumb__item--current" '
                f'itemprop="itemListElement" itemscope '
                f'itemtype="https://schema.org/ListItem">'
                f'<span itemprop="name">{name}</span>'
                f'<meta itemprop="position" content="{idx + 1}">'
                f"</li>"
            )
        else:
            items.append(
                f'<li class="breadcrumb__item" '
                f'itemprop="itemListElement" itemscope '
                f'itemtype="https://schema.org/ListItem">'
                f'<a class="breadcrumb__link" href="{url}" itemprop="item">'
                f'<span itemprop="name">{name}</span>'
                f"</a>"
                f'<meta itemprop="position" content="{idx + 1}">'
                f'<span class="breadcrumb__separator" aria-hidden="true">/</span>'
                f"</li>"
            )

    items_html = "\n        ".join(items)
    return (
        '<nav class="breadcrumb" aria-label="Breadcrumb" '
        'itemscope itemtype="https://schema.org/BreadcrumbList">\n'
        '  <ol class="breadcrumb__list">\n'
        f"        {items_html}\n"
        "  </ol>\n"
        "</nav>"
    )


def _build_breadcrumb_jsonld(canonical_url: str, breadcrumbs: list[tuple[str, str]]) -> str:
    if not breadcrumbs:
        return ""

    items = []
    for idx, (name, url) in enumerate(breadcrumbs, start=1):
        items.append(
            {
                "@type": "ListItem",
                "position": idx,
                "name": name,
                "item": url,
            }
        )

    payload = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(payload, ensure_ascii=False)
        + "\n</script>"
    )


def _build_related_jurisdictions_html(
    parent_link: Optional[tuple[str, str]],
    sibling_links: list[tuple[str, str]],
    child_links: list[tuple[str, str]],
) -> str:
    if not parent_link and not sibling_links and not child_links:
        return ""

    lines = ['<nav class="related-jurisdictions" aria-label="Related jurisdictions">']

    if parent_link:
        lines.append('<section class="related-jurisdictions__parent">')
        lines.append("<h2>Parent Jurisdiction</h2>")
        lines.append(f'<a href="{_escape_attr(parent_link[1])}">{_escape_attr(parent_link[0])}</a>')
        lines.append("</section>")

    if sibling_links:
        lines.append('<section class="related-jurisdictions__siblings">')
        lines.append("<h2>Related Jurisdictions</h2>")
        lines.append("<ul>")
        for name, url in sibling_links:
            lines.append(f'<li><a href="{_escape_attr(url)}">{_escape_attr(name)}</a></li>')
        lines.append("</ul>")
        lines.append("</section>")

    if child_links:
        lines.append('<section class="related-jurisdictions__children">')
        lines.append("<h2>Sub-Jurisdictions</h2>")
        lines.append("<ul>")
        for name, url in child_links:
            lines.append(f'<li><a href="{_escape_attr(url)}">{_escape_attr(name)}</a></li>')
        lines.append("</ul>")
        lines.append("</section>")

    lines.append("</nav>")
    return "\n".join(lines)


def _build_enhanced_seo_blocks(
    blog_post: JurisdictionBlogPost, canonical_url: str, db=None
) -> tuple[str, str]:
    """Build breadcrumb JSON-LD and related-jurisdictions HTML.

    Accepts an optional `db` session to allow callers to reuse a session
    (avoids opening a new connection per artifact write). If `db` is not
    provided this function will create and close a `SyncSessionLocal()`.
    This implementation batch-loads published posts and preloads
    jurisdictions for the current project to eliminate N+1 queries.
    """
    jurisdiction_id = getattr(blog_post, "jurisdiction_id", None)
    if not jurisdiction_id:
        return "", ""

    close_db = False
    if db is None:
        db = SyncSessionLocal()
        close_db = True

    try:
        jurisdiction = db.get(Jurisdiction, jurisdiction_id)
        if not jurisdiction:
            return "", ""
        preload_map = {}
        try:
            stmt_all = select(Jurisdiction).where(
                Jurisdiction.project_id == jurisdiction.project_id
            )
            all_result = db.execute(stmt_all)
            for j in all_result.scalars().all():
                preload_map[j.id] = j
        except Exception:
            preload_map = {}

        try:
            project_main = db.get(Project, jurisdiction.project_id)
        except Exception:
            project_main = None

        hierarchy = _build_jurisdiction_hierarchy_sync(db, jurisdiction, preload=preload_map)

        sibling_stmt = (
            select(Jurisdiction)
            .where(
                Jurisdiction.project_id == jurisdiction.project_id,
                Jurisdiction.parent_id == jurisdiction.parent_id,
                Jurisdiction.id != jurisdiction.id,
            )
            .limit(10)
        )
        sibling_result = db.execute(sibling_stmt)
        siblings = sibling_result.scalars().all()

        child_stmt = select(Jurisdiction).where(Jurisdiction.parent_id == jurisdiction.id).limit(20)
        child_result = db.execute(child_stmt)
        children = child_result.scalars().all()

        all_ids = [n.id for n in hierarchy]
        all_ids += [s.id for s in siblings]
        all_ids += [c.id for c in children]
        posts_by_jid: dict = {}
        if all_ids:
            try:
                posts_stmt = select(JurisdictionBlogPost).where(
                    JurisdictionBlogPost.jurisdiction_id.in_(all_ids),
                    JurisdictionBlogPost.is_published.is_(True),
                )
                posts_result = db.execute(posts_stmt)
                posts_by_jid = {p.jurisdiction_id: p for p in posts_result.scalars().all()}
            except Exception:
                posts_by_jid = {}

        breadcrumb_items: list[tuple[str, str]] = []
        for node in hierarchy:
            node_post = posts_by_jid.get(node.id)
            if not node_post:
                continue
            path = _build_resource_path_for_post(
                db, node, node_post, preload=preload_map, project=project_main
            )
            breadcrumb_items.append((node.name, build_public_resource_url(path)))

        if not breadcrumb_items:
            breadcrumb_items.append((blog_post.title, canonical_url))

        parent_link: Optional[tuple[str, str]] = None
        if jurisdiction.parent_id:
            parent = (
                preload_map.get(jurisdiction.parent_id)
                if preload_map
                else db.get(Jurisdiction, jurisdiction.parent_id)
            )
            if parent:
                parent_post = posts_by_jid.get(parent.id)
                if parent_post:
                    parent_path = _build_resource_path_for_post(
                        db, parent, parent_post, preload=preload_map, project=project_main
                    )
                    parent_link = (parent.name, build_public_resource_url(parent_path))

        sibling_links: list[tuple[str, str]] = []
        for sibling in siblings:
            sibling_post = posts_by_jid.get(sibling.id)
            if not sibling_post:
                continue
            sibling_path = _build_resource_path_for_post(
                db, sibling, sibling_post, preload=preload_map, project=project_main
            )
            sibling_links.append((sibling.name, build_public_resource_url(sibling_path)))

        child_links: list[tuple[str, str]] = []
        for child in children:
            child_post = posts_by_jid.get(child.id)
            if not child_post:
                continue
            child_path = _build_resource_path_for_post(
                db, child, child_post, preload=preload_map, project=project_main
            )
            child_links.append((child.name, build_public_resource_url(child_path)))
    finally:
        if close_db:
            try:
                db.close()
            except Exception:
                pass

    breadcrumb_jsonld = _build_breadcrumb_jsonld(canonical_url, breadcrumb_items)
    related_html = _build_related_jurisdictions_html(parent_link, sibling_links, child_links)
    return breadcrumb_jsonld, related_html


def _remove_artifact_file(normalized_resource_path: str) -> None:
    """Remove an artifact index file for a normalized resource path.

    Args:
        normalized_resource_path (str): Normalized path under blog static root.

    Returns:
        None: This function does not return a value.

    Examples:
        >>> _remove_artifact_file("resources/eor-guide-california")
    """
    artifact_path = Path(settings.BLOG_STATIC_DIR) / normalized_resource_path / "index.html"

    if not artifact_path.exists():
        logger.info("Artifact not found (already deleted or never written): %s", artifact_path)
        return

    artifact_path.unlink()
    logger.info("Blog artifact deleted: %s", artifact_path)

    parent = artifact_path.parent
    try:
        parent.rmdir()
    except OSError:
        pass


def _dispatch_sitemap_rebuild() -> None:
    """Trigger a sitemap rebuild without blocking artifact writes on broker IO.

    Artifact publication is user-facing and disk-bound. It should not wait on
    Celery broker connectivity, especially in tests or degraded environments.
    The task publish is therefore offloaded to a daemon thread and treated as
    best-effort.
    """

    def _publish() -> None:
        try:
            from app.api.modules.v1.jurisdictions.service.sitemap_tasks import (
                sitemap_rebuild_debounced,
            )

            sitemap_rebuild_debounced.delay()
        except Exception:
            logger.warning("Failed to dispatch sitemap rebuild task", exc_info=True)

    threading.Thread(target=_publish, name="sitemap-rebuild-dispatch", daemon=True).start()


def render_html_body(markdown_content: str) -> str:
    """Convert Markdown content to an HTML body fragment.

    Converts the blog post Markdown to HTML using the Python `markdown`
    library with a standard set of extensions. The result is the article
    body only — not a full page. No `<html>`, `<head>`, or `<body>` tags.

    Args:
        markdown_content (str): Raw Markdown text from the LLM.

    Returns:
        str: HTML fragment suitable for embedding in the page shell.

    Raises:
        ImportError: If the `markdown` package is not installed.
        Exception: If conversion fails for any other reason.

    Examples:
        >>> html = render_html_body("# Hello\\n\\nWorld")
        >>> "<h1>Hello</h1>" in html
        True
    """
    try:
        import markdown as md_lib

        converter = md_lib.Markdown(
            extensions=[
                "fenced_code",
                "tables",
                "toc",
                "nl2br",
                "sane_lists",
                "attr_list",
            ]
        )
        return converter.convert(markdown_content)
    except ImportError as exc:
        logger.error("markdown package not installed. Run: uv add markdown")
        raise ImportError(
            "markdown package is required for HTML conversion. Run: uv add markdown"
        ) from exc
    except Exception as exc:
        logger.error("Markdown → HTML conversion failed: %s", exc, exc_info=True)
        raise


def build_artifact_html(
    blog_post: JurisdictionBlogPost,
    resource_path: Optional[str] = None,
    db=None,
    robots_content: str = "index, follow",
) -> str:
    """Build the full HTML page for a blog artifact or preview.

    Uses precomputed breadcrumbs from the blog post when available for
    both the visible nav and schema.org BreadcrumbList JSON-LD.
    Falls back to dynamically built breadcrumbs when the field is empty.

    Args:
        blog_post: Published blog post with content_html and metadata.
        resource_path: Canonical relative resource path for URL building.
        db: Database session for dynamic breadcrumb fallback.
        robots_content: robots meta tag value.

    Returns:
        str: Complete HTML page string.
    """
    normalized_resource_path = _normalize_resource_path(
        resource_path or build_legacy_resource_path(blog_post.slug)
    )
    canonical_url = build_public_resource_url(normalized_resource_path)

    published_source = blog_post.published_at or getattr(blog_post, "generated_at", None)
    published_source = published_source or getattr(blog_post, "updated_at", None)
    published_at_iso = published_source.isoformat() if published_source else ""
    published_at_human = published_source.strftime("%B %d, %Y") if published_source else ""

    updated_at = getattr(blog_post, "updated_at", None)
    date_modified_iso = updated_at.isoformat() if updated_at else published_at_iso
    date_modified_human = updated_at.strftime("%B %d, %Y") if updated_at else published_at_human

    keywords_str = ", ".join(blog_post.keywords) if blog_post.keywords else ""

    # Use precomputed breadcrumbs when available (O(1) — no DB hit needed)
    precomputed = getattr(blog_post, "breadcrumbs", None) or []

    if precomputed:
        # Build both visual nav and JSON-LD from the precomputed list
        breadcrumb_nav_html = _build_breadcrumb_nav_html(precomputed)
        breadcrumb_items_for_jsonld = [(c["name"], c["url"]) for c in precomputed]
        breadcrumb_jsonld = _build_breadcrumb_jsonld(canonical_url, breadcrumb_items_for_jsonld)
        _, related_jurisdictions_html = _build_enhanced_seo_blocks(blog_post, canonical_url, db=db)
    else:
        # Fallback: dynamic computation (older posts without precomputed breadcrumbs)
        breadcrumb_jsonld, related_jurisdictions_html = _build_enhanced_seo_blocks(
            blog_post, canonical_url, db=db
        )
        breadcrumb_nav_html = ""

    return _HTML_SHELL.format(
        title=_escape_attr(blog_post.title),
        site_name=_escape_attr(settings.BLOG_SITE_NAME),
        meta_description=_escape_attr(blog_post.meta_description),
        keywords=_escape_attr(keywords_str),
        robots_content=_escape_attr(robots_content),
        canonical_url=canonical_url,
        css_url=settings.BLOG_CSS_URL,
        published_at=published_at_iso,
        date_modified=date_modified_iso,
        date_modified_human=date_modified_human,
        published_at_iso=published_at_iso,
        published_at_human=published_at_human,
        breadcrumb_jsonld=breadcrumb_jsonld,
        breadcrumb_nav_html=breadcrumb_nav_html,
        content_html=blog_post.content_html,
        related_jurisdictions_html=related_jurisdictions_html,
    )


def write_artifact(
    blog_post: JurisdictionBlogPost, resource_path: Optional[str] = None, db=None
) -> None:
    """Write a complete HTML artifact file for a published blog post.

    Creates `/var/www/blog-static/{resource_path}/index.html` (path is
    configurable via BLOG_STATIC_DIR). If `resource_path` is not provided,
    it falls back to `resources/{slug}` for backward compatibility.
    If the file already exists it is overwritten atomically.
    The directory is created if it does not exist.

    The HTML shell references:
    - BLOG_CSS_URL (stable versioned CSS from the FE team)
    - BLOG_SITE_URL / BLOG_SITE_NAME (set in config / .env)

    This function is a no-op when BLOG_PUBLISH_ARTIFACTS=False (e.g., in CI).

    Args:
        blog_post (JurisdictionBlogPost): The published blog post. Must have
            `content_html`, `slug`, `title`, `meta_description`, `keywords`,
            and `published_at` populated.
        resource_path (Optional[str]): Canonical relative resource path.

    Raises:
        OSError: If the directory cannot be created or the file cannot be written.

    Examples:
        >>> write_artifact(blog_post)
        # Creates /var/www/blog-static/resources/eor-guide-california/index.html
    """
    if not settings.BLOG_PUBLISH_ARTIFACTS:
        logger.info("BLOG_PUBLISH_ARTIFACTS=False, skipping artifact write for %s", blog_post.slug)
        return

    try:
        normalized_resource_path = _normalize_resource_path(
            resource_path or build_legacy_resource_path(blog_post.slug)
        )
        legacy_resource_path = _normalize_resource_path(build_legacy_resource_path(blog_post.slug))
        artifact_dir = Path(settings.BLOG_STATIC_DIR) / normalized_resource_path
        artifact_dir.mkdir(parents=True, exist_ok=True)

        html_page = build_artifact_html(
            blog_post,
            resource_path=normalized_resource_path,
            db=db,
            robots_content="index, follow",
        )
        canonical_url = build_public_resource_url(normalized_resource_path)

        artifact_path = artifact_dir / "index.html"
        _write_file_atomic(artifact_path, html_page)

        os.chmod(artifact_path, 0o644)
        os.chmod(artifact_dir, 0o755)

        if legacy_resource_path != normalized_resource_path:
            legacy_dir = Path(settings.BLOG_STATIC_DIR) / legacy_resource_path
            legacy_dir.mkdir(parents=True, exist_ok=True)

            redirect_html = _LEGACY_REDIRECT_SHELL.format(canonical_url=canonical_url)
            legacy_artifact_path = legacy_dir / "index.html"
            _write_file_atomic(legacy_artifact_path, redirect_html)

            os.chmod(legacy_artifact_path, 0o644)
            os.chmod(legacy_dir, 0o755)

        logger.info("Blog artifact written: %s", artifact_path)

        _dispatch_sitemap_rebuild()

    except Exception as exc:
        logger.error(
            "Failed to write blog artifact for slug '%s': %s", blog_post.slug, exc, exc_info=True
        )
        raise


def delete_artifact(resource_path: str, legacy_slug: Optional[str] = None) -> None:
    """Delete the HTML artifact for a blog post on unpublish.

    Removes `/var/www/blog-static/{resource_path}/index.html`.
    For backward compatibility, when a plain slug is provided, it is resolved
    to `resources/{slug}`.
    If the file does not exist the call is silently ignored.
    The parent directory is removed only if it becomes empty after deletion.

    This function is a no-op when BLOG_PUBLISH_ARTIFACTS=False (e.g., in CI).

    Args:
        resource_path (str): Canonical relative resource path or legacy slug.
        legacy_slug (Optional[str]): Optional legacy slug path to delete as
            `resources/{legacy_slug}`.

    Examples:
        >>> delete_artifact("eor-guide-california")
        # Removes /var/www/blog-static/resources/eor-guide-california/index.html
    """
    if not settings.BLOG_PUBLISH_ARTIFACTS:
        logger.info("BLOG_PUBLISH_ARTIFACTS=False, skipping artifact delete for %s", resource_path)
        return

    try:
        normalized_path = _normalize_resource_path(resource_path)
        if "/" not in normalized_path:
            normalized_path = build_legacy_resource_path(normalized_path)

        _remove_artifact_file(normalized_path)

        if legacy_slug:
            legacy_path = _normalize_resource_path(build_legacy_resource_path(legacy_slug))
            if legacy_path != normalized_path:
                _remove_artifact_file(legacy_path)

    except Exception:
        logger.error(
            "Failed to delete blog artifact for resource_path '%s'",
            resource_path,
            exc_info=True,
        )
        raise


def _escape_attr(value: Optional[str]) -> str:
    """Escape a string for safe use in HTML attributes and text nodes.

    Args:
        value (Optional[str]): String to escape. None is treated as empty.

    Returns:
        str: HTML-escaped string.

    Examples:
        >>> _escape_attr('Hello & "World"')
        'Hello &amp; &quot;World&quot;'
    """
    if not value:
        return ""
    return (
        value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )
