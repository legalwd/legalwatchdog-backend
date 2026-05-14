"""Tests for blog_artifact_service — render_html_body, write_artifact, delete_artifact."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ARTIFACT_MODULE = "app.api.modules.v1.jurisdictions.service.blog_artifact_service"


def _make_blog_post(
    slug="eor-guide-california",
    title="EOR Guide California",
    meta_description="A guide to EOR compliance in California.",
    keywords=None,
    content_html="<h1>Guide</h1><p>Body content here.</p>",
    published_at=None,
):
    """Build a minimal JurisdictionBlogPost stub for artifact tests."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        slug=slug,
        title=title,
        meta_description=meta_description,
        keywords=keywords or ["EOR", "California"],
        content_html=content_html,
        published_at=published_at or datetime.now(timezone.utc),
    )


# ──────────────────────────────────────────
# render_html_body
# ──────────────────────────────────────────


class TestRenderHtmlBody:
    """Tests for render_html_body."""

    def test_converts_heading(self):
        """Test markdown H1 heading converts to <h1> tag."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        result = render_html_body("# Hello World")

        assert "<h1" in result
        assert "Hello World" in result

    def test_converts_paragraph(self):
        """Test plain text converts to <p> tag."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        result = render_html_body("Some paragraph text.")

        assert "<p>" in result
        assert "Some paragraph text." in result

    def test_converts_fenced_code_block(self):
        """Test fenced code blocks convert to <code> elements."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        md = "```python\nprint('hello')\n```"
        result = render_html_body(md)

        assert "<code" in result
        assert "print" in result

    def test_converts_table(self):
        """Test markdown table converts to <table> element."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        md = "| Col1 | Col2 |\n|------|------|\n| A    | B    |"
        result = render_html_body(md)

        assert "<table>" in result
        assert "<td>" in result or "<th>" in result

    def test_empty_string_returns_empty(self):
        """Test empty markdown returns empty string."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        result = render_html_body("")

        assert result == ""

    def test_does_not_include_full_html_document(self):
        """Test output is a body fragment — no <html> or <head> tags."""
        from app.api.modules.v1.jurisdictions.service.blog_artifact_service import (
            render_html_body,
        )

        result = render_html_body("# Title\n\nBody text.")

        assert "<html" not in result
        assert "<head" not in result
        assert "<body" not in result


# ──────────────────────────────────────────
# write_artifact
# ──────────────────────────────────────────


class TestWriteArtifact:
    """Tests for write_artifact."""

    def test_writes_file_to_correct_path(self, tmp_path):
        """Test artifact is written at {BLOG_STATIC_DIR}/resources/{slug}/index.html."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="test-slug")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.write_artifact(post)

        artifact_path = tmp_path / "resources" / "test-slug" / "index.html"
        assert artifact_path.exists()

    def test_artifact_contains_content_html(self, tmp_path):
        """Test the written HTML file contains the post's content_html."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(
            slug="content-test",
            content_html="<p>Special content UNIQUE_MARKER</p>",
        )

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.write_artifact(post)

        artifact_path = tmp_path / "resources" / "content-test" / "index.html"
        html_content = artifact_path.read_text(encoding="utf-8")
        assert "UNIQUE_MARKER" in html_content

    def test_artifact_contains_title_in_head(self, tmp_path):
        """Test the written HTML file includes title in <title> tag."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="title-test", title="My Unique Blog Title")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.write_artifact(post)

        artifact_path = tmp_path / "resources" / "title-test" / "index.html"
        html_content = artifact_path.read_text(encoding="utf-8")
        assert "My Unique Blog Title" in html_content

    def test_noop_when_publish_artifacts_false(self, tmp_path):
        """Test no file is written when BLOG_PUBLISH_ARTIFACTS is False."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="noop-test")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", False):
                blog_artifact_service.write_artifact(post)

        artifact_path = tmp_path / "resources" / "noop-test" / "index.html"
        assert not artifact_path.exists()

    def test_atomic_write_uses_tmp_then_rename(self, tmp_path):
        """Test write is atomic — no partial file served during write."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="atomic-test")
        rename_calls = []
        original_replace = Path.replace

        def tracking_replace(self, target):
            rename_calls.append((str(self), str(target)))
            return original_replace(self, target)

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                with patch.object(Path, "replace", tracking_replace):
                    blog_artifact_service.write_artifact(post)

        assert len(rename_calls) == 1
        src, dst = rename_calls[0]
        assert src.endswith(".tmp")
        assert dst.endswith("index.html")

    def test_writes_file_to_custom_resource_path(self, tmp_path):
        """Test artifact writes to a canonical nested resource path."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="nested-test")
        resource_path = "resources/eor/nigeria/employment-rules/nested-test"

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.write_artifact(post, resource_path)

        artifact_path = tmp_path / "resources" / "eor" / "nigeria" / "employment-rules"
        artifact_path = artifact_path / "nested-test" / "index.html"
        assert artifact_path.exists()

    def test_artifact_contains_canonical_public_url(self, tmp_path):
        """Test canonical URL in HTML shell uses BLOG_SITE_URL and resource path."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="canonical-url")
        resource_path = "resources/eor/nigeria/labor-rules/canonical-url"

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                with patch.object(
                    blog_artifact_service.settings,
                    "BLOG_SITE_URL",
                    "https://staging.legalwatch.dog",
                ):
                    blog_artifact_service.write_artifact(post, resource_path)

        artifact_file = (
            tmp_path
            / "resources"
            / "eor"
            / "nigeria"
            / "labor-rules"
            / "canonical-url"
            / "index.html"
        )
        html_content = artifact_file.read_text(encoding="utf-8")
        assert (
            "https://staging.legalwatch.dog/resources/eor/nigeria/labor-rules/canonical-url/"
            in html_content
        )

    def test_writes_legacy_slug_redirect_for_canonical_path(self, tmp_path):
        """Test canonical artifact write also creates legacy slug redirect artifact."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        post = _make_blog_post(slug="legacy-redirect-slug")
        canonical_path = "resources/eor/nigeria/employment-rules/legacy-redirect-slug"

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                with patch.object(
                    blog_artifact_service.settings,
                    "BLOG_SITE_URL",
                    "https://staging.legalwatch.dog",
                ):
                    blog_artifact_service.write_artifact(post, canonical_path)

        legacy_file = tmp_path / "resources" / "legacy-redirect-slug" / "index.html"
        assert legacy_file.exists()

        redirect_html = legacy_file.read_text(encoding="utf-8")
        assert 'http-equiv="refresh"' in redirect_html
        assert (
            "https://staging.legalwatch.dog/resources/eor/nigeria/employment-rules/"
            "legacy-redirect-slug/" in redirect_html
        )


# ──────────────────────────────────────────
# delete_artifact
# ──────────────────────────────────────────


class TestDeleteArtifact:
    """Tests for delete_artifact."""

    def test_removes_artifact_file(self, tmp_path):
        """Test existing artifact file is removed on delete."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        slug = "delete-test"
        artifact_dir = tmp_path / "resources" / slug
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "index.html"
        artifact_file.write_text("<html>test</html>", encoding="utf-8")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.delete_artifact(slug)

        assert not artifact_file.exists()

    def test_silent_when_file_missing(self, tmp_path):
        """Test delete is silent when artifact file does not exist."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.delete_artifact("nonexistent-slug")

    def test_noop_when_publish_artifacts_false(self, tmp_path):
        """Test no deletion occurs when BLOG_PUBLISH_ARTIFACTS is False."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        slug = "noop-delete"
        artifact_dir = tmp_path / "resources" / slug
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "index.html"
        artifact_file.write_text("<html>test</html>", encoding="utf-8")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", False):
                blog_artifact_service.delete_artifact(slug)

        assert artifact_file.exists()

    def test_removes_nested_resource_artifact_file(self, tmp_path):
        """Test delete removes nested canonical resource path artifacts."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        resource_path = "resources/eor/nigeria/employment-rules/deep-path"
        artifact_dir = tmp_path / "resources" / "eor" / "nigeria" / "employment-rules" / "deep-path"
        artifact_dir.mkdir(parents=True)
        artifact_file = artifact_dir / "index.html"
        artifact_file.write_text("<html>test</html>", encoding="utf-8")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.delete_artifact(resource_path)

        assert not artifact_file.exists()

    def test_removes_legacy_and_canonical_artifacts_together(self, tmp_path):
        """Test delete removes canonical and legacy artifacts when legacy slug is provided."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        canonical_path = "resources/eor/nigeria/employment-rules/combined-delete"
        canonical_dir = (
            tmp_path / "resources" / "eor" / "nigeria" / "employment-rules" / "combined-delete"
        )
        canonical_dir.mkdir(parents=True)
        canonical_file = canonical_dir / "index.html"
        canonical_file.write_text("<html>canonical</html>", encoding="utf-8")

        legacy_dir = tmp_path / "resources" / "combined-delete"
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / "index.html"
        legacy_file.write_text("<html>legacy</html>", encoding="utf-8")

        with patch.object(blog_artifact_service.settings, "BLOG_STATIC_DIR", str(tmp_path)):
            with patch.object(blog_artifact_service.settings, "BLOG_PUBLISH_ARTIFACTS", True):
                blog_artifact_service.delete_artifact(canonical_path, "combined-delete")

        assert not canonical_file.exists()
        assert not legacy_file.exists()


class TestPublicResourceUrl:
    """Tests for build_public_resource_url helper."""

    def test_build_public_resource_url(self):
        """Test helper returns normalized absolute URL with trailing slash."""
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        with patch.object(
            blog_artifact_service.settings, "BLOG_SITE_URL", "https://staging.legalwatch.dog"
        ):
            result = blog_artifact_service.build_public_resource_url(
                "/resources/eor/nigeria/employment-rules/"
            )

        assert result == "https://staging.legalwatch.dog/resources/eor/nigeria/employment-rules/"


class TestSitemapDispatch:
    """Tests for non-blocking sitemap dispatch from artifact writes."""

    def test_dispatch_sitemap_rebuild_uses_daemon_thread(self):
        """
        Test sitemap dispatch is offloaded so artifact writes do not block on Celery broker IO.
        """
        from app.api.modules.v1.jurisdictions.service import blog_artifact_service

        started = {}

        class FakeThread:
            def __init__(self, *, target, name, daemon):
                started["target"] = target
                started["name"] = name
                started["daemon"] = daemon

            def start(self):
                started["started"] = True

        with patch.object(blog_artifact_service.threading, "Thread", FakeThread):
            blog_artifact_service._dispatch_sitemap_rebuild()

        assert started["started"] is True
        assert started["daemon"] is True
        assert started["name"] == "sitemap-rebuild-dispatch"
