"""Tests for BlogGenerationService."""

import hashlib
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.jurisdictions.models.blog_generation_job import (
    ProjectBulkBlogJob,
    ProjectBulkBlogJobStatus,
)
from app.api.modules.v1.jurisdictions.schemas.blog_schema import BlogLLMOutput
from app.api.modules.v1.jurisdictions.service.blog_generation_service import (
    BlogGenerationService,
)
from app.api.modules.v1.projects.models.project_model import Project

SERVICE_MODULE = "app.api.modules.v1.jurisdictions.service.blog_generation_service"


def _make_organization(industry="EOR", name="Acme Corp"):
    """Build a minimal Organization stub."""
    return SimpleNamespace(industry=industry, name=name)


def _make_project(org=None, master_prompt="Monitor EOR regulations"):
    """Build a minimal Project stub with an organization."""
    if org is None:
        org = _make_organization()
    return SimpleNamespace(
        id=uuid.uuid4(),
        title="EOR Regulations",
        organization=org,
        master_prompt=master_prompt,
        org_id=uuid.uuid4(),
    )


def _make_jurisdiction(
    name="California",
    prompt="Track labor law changes",
    project=None,
):
    """Build a minimal Jurisdiction stub with project chain."""
    if project is None:
        project = _make_project()
    jur_id = uuid.uuid4()
    project_id = getattr(project, "id", uuid.uuid4())
    jur = SimpleNamespace(
        id=jur_id,
        project_id=project_id,
        parent_id=None,
        name=name,
        prompt=prompt,
        project=project,
    )
    return jur


def _make_state_map(fields=None):
    """Build a state_map dict with SimpleNamespace values."""
    if fields is None:
        fields = {
            "min_wage": "$15/hr",
            "overtime_rate": "1.5x",
        }
    state_map = {}
    for key, value in fields.items():
        state_map[key] = SimpleNamespace(value=value, source_evidence=["source1.gov"])
    return state_map


def _make_blog_llm_output():
    """Build a valid BlogLLMOutput instance."""
    return BlogLLMOutput(
        title="California EOR Compliance Guide 2026",
        meta_description=(
            "A comprehensive guide to California EOR compliance "
            "requirements covering minimum wage, overtime, "
            "payroll, benefits, and regulatory standards "
            "for 2026."
        ),
        keywords=["EOR", "California", "compliance"],
        content="# California EOR Compliance\n\n" + "x" * 100,
    )


def _make_existing_blog(jurisdiction_id=None, version=1, content_hash="oldhash"):
    """Build a minimal JurisdictionBlogPost stub."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_id or uuid.uuid4(),
        version=version,
        content_hash=content_hash,
        title="Old Title",
        slug="eor-guide-california",
        content="old content",
        content_html="<p>old content</p>",
        meta_description="old desc",
        keywords=["old"],
        is_published=False,
        generation_model=None,
        generated_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class MockScalarsResult:
    """Mock for result.scalar_one_or_none() chain."""

    def __init__(self, item=None):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class MockAllResult:
    """Mock for result.all() chain."""

    def __init__(self, items=None):
        self._items = items or []

    def all(self):
        return self._items


def _make_history_rows(n=2):
    """Build a list of SimpleNamespace history row stubs."""
    base = datetime(2024, 7, 1, tzinfo=timezone.utc)
    return [
        SimpleNamespace(
            field_key=f"field_{i}",
            previous_value=f"old_val_{i}" if i % 2 == 0 else None,
            new_value=f"new_val_{i}",
            changed_at=base.replace(day=i + 1),
            change_reason="Accepted via review",
        )
        for i in range(n)
    ]


# ──────────────────────────────────────────
# _resolve_domain_context
# ──────────────────────────────────────────


class TestResolveDomainContext:
    """Tests for _resolve_domain_context."""

    def test_domain_context_eor(self):
        """Test EOR industry context is extracted correctly."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        jur = _make_jurisdiction()

        ctx = service._resolve_domain_context(jur)

        assert ctx["industry"] == "EOR"
        assert ctx["jurisdiction_name"] == "California"
        assert "Monitor EOR" in ctx["project_prompt"]

    def test_domain_context_fintech(self):
        """Test fintech industry context adapts correctly."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        org = _make_organization(industry="Financial Services", name="FinCo")
        project = _make_project(org=org, master_prompt="Track banking regs")
        jur = _make_jurisdiction(name="New York", prompt="Monitor fintech", project=project)

        ctx = service._resolve_domain_context(jur)

        assert ctx["industry"] == "Financial Services"
        assert ctx["project_prompt"] == "Track banking regs"
        assert ctx["jurisdiction_prompt"] == "Monitor fintech"

    def test_domain_context_no_organization(self):
        """Test graceful defaults when organization is None."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        project = SimpleNamespace(organization=None, master_prompt=None, org_id=uuid.uuid4())
        jur = _make_jurisdiction(name="Texas", prompt=None, project=project)

        ctx = service._resolve_domain_context(jur)

        assert ctx["industry"] == "General Compliance"
        assert ctx["project_prompt"] == "Regulatory monitoring"
        assert ctx["jurisdiction_prompt"] == "Monitor regulations"

    def test_domain_context_none_org_fields(self):
        """Test org with None fields passes through None values."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        org = _make_organization(industry=None, name=None)
        project = _make_project(org=org, master_prompt=None)
        jur = _make_jurisdiction(name="Texas", prompt=None, project=project)

        ctx = service._resolve_domain_context(jur)

        assert ctx["industry"] is None
        assert ctx["project_prompt"] == "Regulatory monitoring"
        assert ctx["jurisdiction_prompt"] == "Monitor regulations"

    def test_resolve_domain_context_traversal(self):
        """Test the Jurisdiction -> Project -> Organization traversal."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        org = _make_organization(industry="Healthcare", name="HealthOrg")
        project = _make_project(org=org, master_prompt="HIPAA monitoring")
        jur = _make_jurisdiction(
            name="Florida",
            prompt="Track patient data laws",
            project=project,
        )

        ctx = service._resolve_domain_context(jur)

        assert ctx["industry"] == "Healthcare"
        assert ctx["project_prompt"] == "HIPAA monitoring"
        assert ctx["jurisdiction_prompt"] == "Track patient data laws"
        assert ctx["jurisdiction_name"] == "Florida"


# ──────────────────────────────────────────
# _build_state_context
# ──────────────────────────────────────────


class TestBuildStateContext:
    """Tests for _build_state_context."""

    def test_builds_formatted_string_and_hash(self):
        """Test state map is formatted with hash."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        state_map = _make_state_map()

        formatted, content_hash = service._build_state_context(state_map)

        assert "min_wage" in formatted
        assert "$15/hr" in formatted
        assert "Sources:" in formatted
        expected_hash = hashlib.sha256(formatted.encode("utf-8")).hexdigest()
        assert content_hash == expected_hash

    def test_empty_state_map(self):
        """Test empty state map produces empty formatted string."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        formatted, content_hash = service._build_state_context({})

        assert formatted == ""
        assert isinstance(content_hash, str)


# ──────────────────────────────────────────
# _slugify
# ──────────────────────────────────────────


class TestSlugify:
    """Tests for _slugify."""

    def test_slug_generation(self):
        """Test basic slug generation from jurisdiction name and industry."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        slug = service._slugify("California", "EOR")
        assert slug == "eor-guide-california"

    def test_slug_special_characters(self):
        """Test slug strips special characters."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        slug = service._slugify("São Paulo (City)", "Financial Services")
        assert "guide" in slug
        assert "(" not in slug
        assert ")" not in slug

    def test_slug_max_length(self):
        """Test slug is truncated to 100 characters."""
        service = BlogGenerationService.__new__(BlogGenerationService)
        long_name = "A" * 200
        slug = service._slugify(long_name, "EOR")
        assert len(slug) <= 100


# ──────────────────────────────────────────
# generate_blog_post_sync — success path
# ──────────────────────────────────────────


class TestGenerateBlogPostSync:
    """Tests for generate_blog_post_sync."""

    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_success(self, mock_state_svc_cls, mock_llm_cls):
        """Test successful blog generation returns status=success."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=None),
            MockAllResult(items=[]),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = _make_state_map()
        mock_state_svc_cls.return_value = mock_state_svc

        llm_output = _make_blog_llm_output()
        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = llm_output.model_dump_json()
        mock_response.model = "openai/gpt-4o-mini"
        mock_llm_instance.generate_with_tracking_sync.return_value = mock_response
        mock_llm_cls.return_value = mock_llm_instance

        with patch(f"{SERVICE_MODULE}.blog_crud") as mock_blog_crud:
            mock_blog_crud.update_post_tokens = MagicMock()
            result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "success"
        assert result["jurisdiction_id"] == str(jur_id)
        assert result["version"] is not None
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_no_state_returns_placeholder(self, mock_state_svc_cls):
        """Test empty state returns placeholder blog post."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=None),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = {}
        mock_state_svc_cls.return_value = mock_state_svc

        with patch(f"{SERVICE_MODULE}.blog_crud") as mock_blog_crud:
            mock_blog_crud.update_post_tokens = MagicMock()
            result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "placeholder"
        assert "no state data" in result["message"].lower()

    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_unchanged_hash_skips(self, mock_state_svc_cls):
        """Test content hash unchanged returns status=skipped."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id
        state_map = _make_state_map()

        svc_proto = BlogGenerationService.__new__(BlogGenerationService)
        _, expected_hash = svc_proto._build_state_context(state_map)

        existing_blog = _make_existing_blog(
            jurisdiction_id=jur_id, content_hash=expected_hash, version=3
        )

        mock_db = MagicMock()

        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=existing_blog),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = state_map
        mock_state_svc_cls.return_value = mock_state_svc

        result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "skipped"
        assert result["version"] == 3

    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_llm_failure(self, mock_state_svc_cls, mock_llm_cls):
        """Test LLM failure preserves existing version and returns failed."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id
        existing_blog = _make_existing_blog(jurisdiction_id=jur_id, version=2)

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=existing_blog),
            MockAllResult(items=[]),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = _make_state_map()
        mock_state_svc_cls.return_value = mock_state_svc

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_with_tracking_sync.side_effect = Exception("LLM timeout")
        mock_llm_cls.return_value = mock_llm_instance

        result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "failed"
        assert result["version"] == 2
        assert result["message"] == "Blog generation encountered an error. Please try again."

    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_invalid_llm_output(self, mock_state_svc_cls, mock_llm_cls):
        """Test LLM returning bad JSON is treated as failure."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=None),
            MockAllResult(items=[]),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = _make_state_map()
        mock_state_svc_cls.return_value = mock_state_svc

        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "not valid json {"
        mock_llm_instance.generate_with_tracking_sync.return_value = mock_response
        mock_llm_cls.return_value = mock_llm_instance

        result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "failed"

    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.JurisdictionStateService")
    def test_generate_blog_post_updates_version(self, mock_state_svc_cls, mock_llm_cls):
        """Test existing post gets version incremented on regeneration."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id
        existing_blog = _make_existing_blog(
            jurisdiction_id=jur_id, version=2, content_hash="oldhash"
        )

        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            MockScalarsResult(item=jur),
            MockScalarsResult(item=existing_blog),
            MockAllResult(items=[]),
        ]
        mock_db.get.return_value = SimpleNamespace(title="EOR Regulations")

        service = BlogGenerationService(mock_db)

        mock_state_svc = MagicMock()
        mock_state_svc.get_jurisdiction_state.return_value = _make_state_map()
        mock_state_svc_cls.return_value = mock_state_svc

        llm_output = _make_blog_llm_output()
        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = llm_output.model_dump_json()
        mock_response.model = "openai/gpt-4o"
        mock_llm_instance.generate_with_tracking_sync.return_value = mock_response
        mock_llm_cls.return_value = mock_llm_instance

        with patch(f"{SERVICE_MODULE}.blog_crud") as mock_blog_crud:
            mock_blog_crud.update_post_tokens = MagicMock()
            result = service.generate_blog_post_sync(jur_id)

        assert result["status"] == "success"
        assert existing_blog.version == 3
        assert existing_blog.generation_model == "openai/gpt-4o"
        assert existing_blog.generated_at is not None

    def test_generate_blog_post_jurisdiction_not_found(self):
        """Test missing jurisdiction raises ProcessingError."""
        jur_id = uuid.uuid4()

        mock_db = MagicMock()
        mock_db.execute.return_value = MockScalarsResult(item=None)

        service = BlogGenerationService(mock_db)

        with pytest.raises(ProcessingError):
            service.generate_blog_post_sync(jur_id)


# ──────────────────────────────────────────
# generate_blog_post_async
# ──────────────────────────────────────────


class TestGenerateBlogPostAsync:
    """Tests for generate_blog_post_async."""

    @pytest.mark.asyncio
    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.AsyncJurisdictionStateService")
    async def test_async_generate_success(self, mock_state_svc_cls, mock_llm_cls):
        """Test async blog generation returns status=success."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=None),
                MockAllResult(items=[]),
            ]
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.get = AsyncMock(return_value=SimpleNamespace(title="EOR Regulations"))

        service = BlogGenerationService(mock_db)

        mock_state_svc = AsyncMock()
        mock_state_svc.get_jurisdiction_state = AsyncMock(return_value=_make_state_map())
        mock_state_svc_cls.return_value = mock_state_svc

        llm_output = _make_blog_llm_output()
        mock_llm_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.content = llm_output.model_dump_json()
        mock_response.model = "anthropic/claude-3.5-sonnet"
        mock_llm_instance.generate_with_tracking = AsyncMock(return_value=mock_response)
        mock_llm_cls.return_value = mock_llm_instance

        result = await service.generate_blog_post_async(jur_id)

        assert result["status"] == "success"
        assert result["jurisdiction_id"] == str(jur_id)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_MODULE}.AsyncJurisdictionStateService")
    async def test_async_generate_no_state_placeholder(self, mock_state_svc_cls):
        """Test async path returns placeholder when no state exists."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=None),
            ]
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.get = AsyncMock(return_value=SimpleNamespace(title="EOR Regulations"))

        service = BlogGenerationService(mock_db)

        mock_state_svc = AsyncMock()
        mock_state_svc.get_jurisdiction_state = AsyncMock(return_value={})
        mock_state_svc_cls.return_value = mock_state_svc

        result = await service.generate_blog_post_async(jur_id)

        assert result["status"] == "placeholder"

    @pytest.mark.asyncio
    async def test_async_generate_jurisdiction_not_found(self):
        """Test async path raises ProcessingError for missing jurisdiction."""
        jur_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=None))

        service = BlogGenerationService(mock_db)

        with pytest.raises(ProcessingError):
            await service.generate_blog_post_async(jur_id)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_MODULE}.LLMManager")
    @patch(f"{SERVICE_MODULE}.AsyncJurisdictionStateService")
    async def test_async_generate_llm_failure(self, mock_state_svc_cls, mock_llm_cls):
        """Test async LLM failure preserves previous version."""
        jur_id = uuid.uuid4()
        jur = _make_jurisdiction()
        jur.id = jur_id
        existing_blog = _make_existing_blog(jurisdiction_id=jur_id, version=4)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                MockScalarsResult(item=jur),
                MockScalarsResult(item=existing_blog),
                MockAllResult(items=[]),
            ]
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.rollback = AsyncMock()

        service = BlogGenerationService(mock_db)

        mock_state_svc = AsyncMock()
        mock_state_svc.get_jurisdiction_state = AsyncMock(return_value=_make_state_map())
        mock_state_svc_cls.return_value = mock_state_svc

        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_with_tracking = AsyncMock(
            side_effect=Exception("API rate limit")
        )
        mock_llm_cls.return_value = mock_llm_instance

        result = await service.generate_blog_post_async(jur_id)

        assert result["status"] == "failed"
        assert result["version"] == 4
        assert result["message"] == "Blog generation encountered an error. Please try again."


# ──────────────────────────────────────────
# Slug collision handling
# ──────────────────────────────────────────


class TestSlugCollisionHandling:
    """Tests for slug collision handling in upsert methods."""

    def test_slug_collision_appends_uuid_suffix(self):
        """Test IntegrityError on commit triggers slug with UUID suffix."""
        mock_db = MagicMock()
        mock_db.commit.side_effect = [
            IntegrityError("dupe", {}, Exception()),
            None,
        ]

        service = BlogGenerationService(mock_db)

        with patch(f"{SERVICE_MODULE}.blog_crud") as mock_blog_crud:
            mock_blog_crud.update_post_tokens = MagicMock()

            blog = service._upsert_blog_post_sync(
                jurisdiction_id=uuid.uuid4(),
                title="Test Title",
                slug="eor-guide-california",
                content="test content " * 20,
                meta_description="test desc that is long enough",
                keywords=["test"],
                content_hash="abc123",
                generation_model="openai/gpt-4o",
            )
            assert blog.slug.startswith("eor-guide-california-")
            assert len(blog.slug) > len("eor-guide-california-")
            assert mock_db.rollback.called


# ──────────────────────────────────────────
# _format_history_context
# ──────────────────────────────────────────


class TestFormatHistoryContext:
    """Tests for _format_history_context."""

    def test_empty_rows_returns_sentinel(self):
        """Test empty list returns 'No changes recorded.' sentinel."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        result = svc._format_history_context([])
        assert result == "No changes recorded."

    def test_populated_rows_returns_markdown_table(self):
        """Test populated rows produce a Markdown table with header and data rows."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = _make_history_rows(2)
        result = svc._format_history_context(rows)
        assert "| Field | Previous Value | New Value | Date Changed | Change Reason |" in result
        assert "|---|---|---|---|---|"
        assert "Field 0" in result
        assert "new_val_0" in result
        assert "new_val_1" in result
        assert "Accepted via review" in result

    def test_null_previous_value_renders_dash(self):
        """Test None previous_value is rendered as em-dash."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = _make_history_rows(2)
        result = svc._format_history_context(rows)
        assert "\u2014" in result

    def test_date_formatting(self):
        """Test changed_at is formatted as YYYY-MM-DD."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = _make_history_rows(1)
        result = svc._format_history_context(rows)
        assert "2024-07" in result

    def test_row_count_determines_table_length(self):
        """Test that one row per history entry is produced."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = _make_history_rows(5)
        lines = svc._format_history_context(rows).splitlines()
        assert len(lines) == 5 + 2

    def test_history_field_label_preserves_known_acronyms(self):
        """Test known field acronyms are preserved in display labels."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = [
            SimpleNamespace(
                field_key="paye_tax_bands",
                previous_value="old",
                new_value="new",
                changed_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
                change_reason="Accepted via review",
            ),
            SimpleNamespace(
                field_key="nhf_employee_rate",
                previous_value="old",
                new_value="new",
                changed_at=datetime(2024, 7, 2, tzinfo=timezone.utc),
                change_reason="Accepted via review",
            ),
        ]
        result = svc._format_history_context(rows)
        assert "PAYE Tax Bands" in result
        assert "NHF Employee Rate" in result

    def test_markdown_cell_characters_are_escaped(self):
        """Test pipe and newline characters are escaped for Markdown table safety."""
        svc = BlogGenerationService.__new__(BlogGenerationService)
        rows = [
            SimpleNamespace(
                field_key="paye_tax_bands",
                previous_value="legacy|rate",
                new_value='{"tier":"A|B"}\nnext-line',
                changed_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
                change_reason="Accepted|review",
            )
        ]
        result = svc._format_history_context(rows)
        assert "legacy\\|rate" in result
        assert '{"tier":"A\\|B"}<br>next-line' in result
        assert "Accepted\\|review" in result


# ──────────────────────────────────────────
# _load_history_context_sync / async
# ──────────────────────────────────────────


class TestLoadHistoryContextSync:
    """Tests for _load_history_context_sync."""

    def test_returns_formatted_table_when_rows_present(self):
        """Test returns Markdown table when history rows exist."""
        jur_id = uuid.uuid4()
        rows = _make_history_rows(3)
        mock_db = MagicMock()
        mock_db.execute.return_value = MockAllResult(items=rows)

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = svc._load_history_context_sync(jur_id)
        assert "| Field |" in result
        assert "Field 0" in result
        mock_db.execute.assert_called_once()

    def test_filters_initial_state_initialization_rows(self):
        """Test initialization rows are excluded from formatted history output."""
        jur_id = uuid.uuid4()
        rows = [
            SimpleNamespace(
                field_key="minimum_wage",
                previous_value=None,
                new_value="Exempt",
                changed_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
                change_reason="Initial State Initialization",
            ),
            SimpleNamespace(
                field_key="minimum_wage",
                previous_value="Exempt",
                new_value="50000",
                changed_at=datetime(2024, 7, 2, tzinfo=timezone.utc),
                change_reason="Accepted via review",
            ),
        ]
        mock_db = MagicMock()
        mock_db.execute.return_value = MockAllResult(items=rows)

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = svc._load_history_context_sync(jur_id)
        assert "Initial State Initialization" not in result
        assert "Accepted via review" in result

    def test_returns_sentinel_when_no_rows(self):
        """Test returns 'No changes recorded.' when history table is empty."""
        jur_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.execute.return_value = MockAllResult(items=[])

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = svc._load_history_context_sync(jur_id)
        assert result == "No changes recorded."

    def test_db_error_returns_sentinel(self):
        """Test exception from DB returns sentinel instead of propagating."""
        jur_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB connection lost")

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = svc._load_history_context_sync(jur_id)
        assert result == "No changes recorded."


class TestLoadHistoryContextAsync:
    """Tests for _load_history_context_async."""

    @pytest.mark.asyncio
    async def test_returns_formatted_table_when_rows_present(self):
        """Test async path returns Markdown table when history rows exist."""
        jur_id = uuid.uuid4()
        rows = _make_history_rows(2)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockAllResult(items=rows))

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = await svc._load_history_context_async(jur_id)
        assert "| Field |" in result
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filters_initialization_rows_in_async_loader(self):
        """Test async loader excludes initial state initialization history rows."""
        jur_id = uuid.uuid4()
        rows = [
            SimpleNamespace(
                field_key="paye_tax_bands",
                previous_value=None,
                new_value="specified in schedule",
                changed_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
                change_reason="Initial State Initialization",
            ),
            SimpleNamespace(
                field_key="paye_tax_bands",
                previous_value="specified in schedule",
                new_value='[{"min":0,"max":800000,"rate":"0%"}]',
                changed_at=datetime(2024, 7, 2, tzinfo=timezone.utc),
                change_reason="Accepted via review",
            ),
        ]
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockAllResult(items=rows))

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = await svc._load_history_context_async(jur_id)
        assert "Initial State Initialization" not in result
        assert "Accepted via review" in result

    @pytest.mark.asyncio
    async def test_db_error_returns_sentinel(self):
        """Test async DB failure returns sentinel gracefully."""
        jur_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("timeout"))

        svc = BlogGenerationService.__new__(BlogGenerationService)
        svc.db = mock_db

        result = await svc._load_history_context_async(jur_id)
        assert result == "No changes recorded."

    @pytest.mark.asyncio
    async def test_async_slug_collision_appends_uuid_suffix(self):
        """Test async IntegrityError triggers slug with UUID suffix."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock(
            side_effect=[
                IntegrityError("dupe", {}, Exception()),
                None,
            ]
        )
        mock_db.add = MagicMock()
        mock_db.refresh = AsyncMock()
        mock_db.rollback = AsyncMock()

        service = BlogGenerationService(mock_db)
        with patch(f"{SERVICE_MODULE}.blog_crud") as mock_blog_crud:
            mock_blog_crud.update_post_tokens = MagicMock()

            blog = await service._upsert_blog_post_async(
                jurisdiction_id=uuid.uuid4(),
                title="Test Title",
                slug="eor-guide-california",
                content="test content " * 20,
                meta_description="test desc that is long enough",
                keywords=["test"],
                content_hash="abc123",
                generation_model="openai/gpt-4o",
            )

            assert blog.slug.startswith("eor-guide-california-")
            mock_db.rollback.assert_called_once()


# ──────────────────────────────────────────
# Bulk generation methods
# ──────────────────────────────────────────


class TestBulkBlogGeneration:
    """Tests for project-level bulk blog generation."""

    @pytest.mark.asyncio
    async def test_start_bulk_generation_async(self):
        """Test starting a bulk job creates a PENDING job."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        service = BlogGenerationService(mock_db)

        project_id = uuid.uuid4()
        user_id = uuid.uuid4()

        job = await service.start_bulk_generation_async(
            project_id=project_id,
            user_id=user_id,
            publish_after_generate=True,
        )

        assert job.project_id == project_id
        assert job.status == ProjectBulkBlogJobStatus.PENDING
        assert job.publish_requested is True
        mock_db.add.assert_called_once_with(job)
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_get_bulk_generation_status(self):
        """Test fetching the status of a bulk generation job."""
        mock_db = AsyncMock()
        service = BlogGenerationService(mock_db)

        project_id = uuid.uuid4()
        job_id = uuid.uuid4()
        job = ProjectBulkBlogJob(
            id=job_id,
            project_id=project_id,
            status=ProjectBulkBlogJobStatus.IN_PROGRESS,
            totals=10,
            processed=4,
            failed=1,
            skipped=0,
            publish_requested=False,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_bulk_generation_status(mock_db, project_id, job_id)

        assert str(result["data"]["id"]) == str(job_id)
        assert result["data"]["status"] == ProjectBulkBlogJobStatus.IN_PROGRESS
        assert result["data"]["totals"] == 10
        assert result["data"]["processed"] == 4

    @pytest.mark.asyncio
    async def test_get_bulk_generation_status_not_found(self):
        """Test fetching a non-existent job returns 404."""
        from app.api.core.custom_exceptions.exceptions import CustomDomainException

        mock_db = AsyncMock()
        service = BlogGenerationService(mock_db)

        project_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(CustomDomainException) as exc:
            await service.get_bulk_generation_status(mock_db, project_id, job_id)

        assert exc.value.code == "RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    @patch(f"{SERVICE_MODULE}.AsyncJurisdictionStateService")
    @patch(f"{SERVICE_MODULE}.BlogGenerationService.generate_blog_post_async")
    @patch(f"{SERVICE_MODULE}.BlogGenerationService.publish_blog_post")
    async def test_execute_bulk_generation_bg_success(
        self, mock_publish, mock_generate, mock_state_svc_cls
    ):
        """Test executing bulk background job properly coordinates processing."""
        mock_db = AsyncMock()
        service = BlogGenerationService(mock_db)

        project_id = uuid.uuid4()
        org_id = uuid.uuid4()
        bulk_job_id = uuid.uuid4()

        job = ProjectBulkBlogJob(
            id=bulk_job_id,
            project_id=project_id,
            status=ProjectBulkBlogJobStatus.PENDING,
            publish_requested=True,
        )

        jur1 = _make_jurisdiction(name="Jur1")
        jur2 = _make_jurisdiction(name="Jur2")
        jurisdictions = [jur1, jur2]

        project = Project(id=project_id, org_id=org_id, title="Test", description="Test")

        def mock_execute_side_effect(stmt):
            stmt_str = str(stmt).lower()
            mock_res = MagicMock()
            if "project_bulk_blog_jobs" in stmt_str:
                mock_res.scalar_one_or_none.return_value = job
            elif "jurisdictions" in stmt_str:
                mock_res.scalars.return_value.all.return_value = jurisdictions
            elif "projects" in stmt_str:
                mock_res.scalar_one.return_value = project
            return mock_res

        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)

        # Pre-flight ledger check must return non-empty state so jurisdictions
        # are not skipped by the empty-ledger guard.
        mock_state_svc = AsyncMock()
        mock_state_svc.get_jurisdiction_state = AsyncMock(
            return_value={"minimum_wage": MagicMock()}
        )
        mock_state_svc_cls.return_value = mock_state_svc

        mock_generate.side_effect = [{"status": "success"}, {"status": "skipped"}]
        mock_publish.return_value = {"status": "success"}

        await service._execute_bulk_generation_bg(bulk_job_id)

        assert mock_db.commit.call_count >= 2

        assert mock_generate.call_count == 2
        mock_publish.assert_called_once_with(mock_db, org_id, jur1.id, True)

        assert job.processed == 1
        assert job.skipped == 1
        assert job.failed == 0
        assert job.status == ProjectBulkBlogJobStatus.COMPLETED


class TestGetBlogPostPublicUrl:
    """Tests for get_blog_post canonical public URL metadata."""

    @pytest.mark.asyncio
    async def test_returns_public_url_and_resource_path_when_published(self):
        """Test get_blog_post returns canonical URL fields for published posts."""
        organization_id = uuid.uuid4()
        jurisdiction_id = uuid.uuid4()
        blog_post = _make_existing_blog(jurisdiction_id=jurisdiction_id)
        blog_post.is_published = True
        blog_post.published_at = datetime.now(timezone.utc)

        jurisdiction = SimpleNamespace(
            id=jurisdiction_id,
            name="California",
            parent_id=None,
            project=SimpleNamespace(title="Law Regulation Compliance Guide"),
        )
        expected_resource_path = (
            "resources/law-regulation-compliance-guide/california/eor-guide-california"
        )
        expected_public_url = (
            "https://staging.legalwatch.dog/resources/law-regulation-compliance-guide/"
            "california/eor-guide-california/"
        )

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=blog_post))
        mock_db.rollback = AsyncMock()

        with patch.object(
            BlogGenerationService,
            "_get_jurisdiction",
            AsyncMock(return_value=jurisdiction),
        ):
            with patch.object(
                BlogGenerationService,
                "_build_public_resource_path",
                AsyncMock(return_value=expected_resource_path),
            ):
                with patch.object(
                    BlogGenerationService,
                    "_build_public_resource_url",
                    return_value=expected_public_url,
                ):
                    result = await BlogGenerationService.get_blog_post(
                        mock_db,
                        organization_id,
                        jurisdiction_id,
                    )

        assert result["status_code"] == 200
        assert result["data"]["resource_path"] == expected_resource_path
        assert result["data"]["public_url"] == expected_public_url

    @pytest.mark.asyncio
    async def test_returns_null_public_fields_when_unpublished(self):
        """Test get_blog_post returns null URL metadata for unpublished posts."""
        organization_id = uuid.uuid4()
        jurisdiction_id = uuid.uuid4()
        blog_post = _make_existing_blog(jurisdiction_id=jurisdiction_id)
        blog_post.is_published = False
        blog_post.published_at = None

        jurisdiction = SimpleNamespace(
            id=jurisdiction_id,
            name="California",
            parent_id=None,
            project=SimpleNamespace(title="Law Regulation Compliance Guide"),
        )

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MockScalarsResult(item=blog_post))
        mock_db.rollback = AsyncMock()

        with patch.object(
            BlogGenerationService,
            "_get_jurisdiction",
            AsyncMock(return_value=jurisdiction),
        ):
            with patch.object(
                BlogGenerationService,
                "_build_public_resource_path",
                AsyncMock(),
            ) as mock_build_path:
                result = await BlogGenerationService.get_blog_post(
                    mock_db,
                    organization_id,
                    jurisdiction_id,
                )

        mock_build_path.assert_not_called()
        assert result["status_code"] == 200
        assert result["data"]["resource_path"] is None
        assert result["data"]["public_url"] is None
