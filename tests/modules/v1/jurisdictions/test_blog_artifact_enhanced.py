import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.api.modules.v1.jurisdictions.service import blog_artifact_service


def _make_post(slug: str = "enhanced-seo"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        title="Enhanced SEO Post",
        meta_description="Enhanced SEO metadata description.",
        keywords=["seo", "jurisdiction"],
        content_html="<p>Body</p>",
        published_at=now,
        updated_at=now,
    )


def _artifact_html(tmp_path, resource_path: str) -> str:
    artifact_file = tmp_path / resource_path / "index.html"
    return artifact_file.read_text(encoding="utf-8")


def test_artifact_has_breadcrumb_jsonld(tmp_path):
    post = _make_post("breadcrumb-jsonld")
    resource_path = "resources/eor/nigeria/breadcrumb-jsonld"
    breadcrumb_json = (
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[]}'
        "</script>"
    )

    with (
        patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)),
        patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True),
        patch.object(
            blog_artifact_service, "_build_enhanced_seo_blocks", return_value=(breadcrumb_json, "")
        ),
    ):
        blog_artifact_service.write_artifact(post, resource_path)

    html = _artifact_html(tmp_path, resource_path)
    assert "BreadcrumbList" in html


def test_artifact_breadcrumb_depth_3(tmp_path):
    post = _make_post("breadcrumb-depth")
    resource_path = "resources/eor/africa/nigeria/breadcrumb-depth"
    breadcrumbs = [
        ("Africa", "https://legalwatch.dog/resources/eor/africa/"),
        ("Nigeria", "https://legalwatch.dog/resources/eor/africa/nigeria/"),
        (
            "Breadcrumb Depth",
            "https://legalwatch.dog/resources/eor/africa/nigeria/breadcrumb-depth/",
        ),
    ]
    breadcrumb_json = blog_artifact_service._build_breadcrumb_jsonld(
        "https://legalwatch.dog/resources/eor/africa/nigeria/breadcrumb-depth/",
        breadcrumbs,
    )

    with (
        patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)),
        patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True),
        patch.object(
            blog_artifact_service, "_build_enhanced_seo_blocks", return_value=(breadcrumb_json, "")
        ),
    ):
        blog_artifact_service.write_artifact(post, resource_path)

    html = _artifact_html(tmp_path, resource_path)
    assert html.count('"@type": "ListItem"') == 3


def test_artifact_has_cross_links(tmp_path):
    post = _make_post("cross-links")
    resource_path = "resources/eor/nigeria/cross-links"
    related_html = (
        '<nav class="related-jurisdictions" aria-label="Related jurisdictions">'
        '<a href="https://legalwatch.dog/resources/eor/nigeria/lagos/">Lagos</a>'
        '<a href="https://legalwatch.dog/resources/eor/nigeria/abuja/">Abuja</a>'
        "</nav>"
    )

    with (
        patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)),
        patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True),
        patch.object(
            blog_artifact_service, "_build_enhanced_seo_blocks", return_value=("", related_html)
        ),
    ):
        blog_artifact_service.write_artifact(post, resource_path)

    html = _artifact_html(tmp_path, resource_path)
    assert "related-jurisdictions" in html
    assert "Lagos" in html
    assert "Abuja" in html


def test_artifact_has_date_modified(tmp_path):
    post = _make_post("date-modified")
    updated_at = datetime(2026, 1, 10, 8, 30, tzinfo=timezone.utc)
    post.updated_at = updated_at
    resource_path = "resources/eor/nigeria/date-modified"

    with (
        patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)),
        patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True),
        patch.object(blog_artifact_service, "_build_enhanced_seo_blocks", return_value=("", "")),
    ):
        blog_artifact_service.write_artifact(post, resource_path)

    html = _artifact_html(tmp_path, resource_path)
    assert '"dateModified": "2026-01-10T08:30:00+00:00"' in html


def test_artifact_has_hreflang(tmp_path):
    post = _make_post("hreflang")
    resource_path = "resources/eor/nigeria/hreflang"

    with (
        patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)),
        patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True),
        patch.object(blog_artifact_service.settings, "BLOG_SITE_URL", "https://legalwatch.dog"),
        patch.object(blog_artifact_service, "_build_enhanced_seo_blocks", return_value=("", "")),
    ):
        blog_artifact_service.write_artifact(post, resource_path)

    html = _artifact_html(tmp_path, resource_path)
    assert '<link rel="alternate" hreflang="en"' in html
    assert "https://legalwatch.dog/resources/eor/nigeria/hreflang/" in html
