"""
Unit tests for SourceService.
Tests all CRUD operations and business logic for source management.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

mock_fernet = MagicMock()
mock_fernet.encrypt.return_value.decode.return_value = "mock_encrypted_value"
with patch("cryptography.fernet.Fernet", return_value=mock_fernet):
    from app.api.core.custom_exceptions.exceptions import (
        BadRequestError,
        NotFoundError,
        ProcessingError,
    )
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.scraping.models.source_model import Source, SourceType
    from app.api.modules.v1.scraping.schemas.source_service import (
        SourceCreate,
        SourceRead,
        SourceUpdate,
    )
    from app.api.modules.v1.scraping.service.source_service import SourceService
    from app.api.modules.v1.scraping.validators.exception import (
        DuplicateSourceError,
        SourceNotFoundError,
    )


@pytest.fixture
def sample_jurisdiction_id():
    """Fixture for a sample jurisdiction UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_project():
    """Fixture for a sample project with master prompt."""
    return Project(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        title="Compliance Project",
        description="Test project",
        master_prompt="Follow overall compliance workflow",
    )


@pytest.fixture
def sample_jurisdiction(sample_project, sample_jurisdiction_id):
    """Fixture for a jurisdiction that belongs to the sample project."""
    return Jurisdiction(
        id=sample_jurisdiction_id,
        project_id=sample_project.id,
        name="Tax Regulations",
        description="Monitoring tax regulations",
        prompt="Collect latest tax circulars",
    )


@pytest.fixture
def configure_prompt_validation(sample_jurisdiction, sample_project):
    """Configure AsyncSession.get to satisfy prompt validation requirements."""

    def _configure(mock_db, *, jurisdiction=None, project=None, validation_calls: int = 1):
        jurisdiction_obj = jurisdiction or sample_jurisdiction
        project_obj = project or sample_project
        side_effect = []
        for _ in range(validation_calls):
            side_effect.extend([jurisdiction_obj, project_obj])

        mock_db.get = AsyncMock(side_effect=side_effect)
        return jurisdiction_obj, project_obj

    return _configure


@pytest.fixture
def sample_source_create(sample_jurisdiction_id):
    """Fixture for SourceCreate schema."""
    return SourceCreate(
        jurisdiction_id=sample_jurisdiction_id,
        name="Test Ministry Website",
        url="https://example.gov/laws",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        auth_details={"username": "testuser", "password": "testpass"},
        scraping_rules={"selector": ".law-content"},
    )


@pytest.fixture
def sample_source_db(sample_jurisdiction_id):
    """Fixture for Source database model."""
    return Source(
        id=uuid.uuid4(),
        jurisdiction_id=sample_jurisdiction_id,
        name="Test Ministry Website",
        url="https://example.gov/laws",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        is_active=True,
        auth_details_encrypted="encrypted_string_here",
        scraping_rules={"selector": ".law-content"},
    )


class TestSourceServiceCreate:
    """Tests for SourceService.create_source()"""

    @pytest.mark.asyncio
    async def test_create_source_success_with_auth(
        self, sample_source_create, sample_jurisdiction_id, configure_prompt_validation
    ):
        """Test successful source creation with auth details."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        created_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name=sample_source_create.name,
            url=str(sample_source_create.url),
            source_type=sample_source_create.source_type,
            scrape_frequency=sample_source_create.scrape_frequency,
            scraping_rules=sample_source_create.scraping_rules,
            auth_details_encrypted="mock_encrypted_value",
            is_active=True,
        )

        configure_prompt_validation(mock_db)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, "id", created_source.id))

        result = await service.create_source(mock_db, sample_source_create)
        assert isinstance(result, SourceRead)
        assert result.name == sample_source_create.name
        assert result.has_auth is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_source_success_without_auth(
        self, sample_jurisdiction_id, configure_prompt_validation
    ):
        """Test successful source creation without auth details."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        source_data = SourceCreate(
            jurisdiction_id=sample_jurisdiction_id,
            name="Public Website",
            url="https://public.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="HOURLY",
            auth_details=None,
        )

        configure_prompt_validation(mock_db)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_source(mock_db, source_data)

        assert isinstance(result, SourceRead)
        assert result.has_auth is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_source_database_error(
        self, sample_source_create, configure_prompt_validation
    ):
        """Test that database errors are handled properly."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        configure_prompt_validation(mock_db)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=Exception("Database error"))
        mock_db.rollback = AsyncMock()

        with pytest.raises(ProcessingError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "PROCESSING_ERROR"
        assert "unable to create the data source" in str(exc_info.value).lower()
        mock_db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_url_same_jurisdiction(
        self, sample_source_create, sample_jurisdiction_id, configure_prompt_validation
    ):
        """Test that creating source with duplicate URL in same jurisdiction raises error."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        existing_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Existing Source",
            url=str(sample_source_create.url),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            is_deleted=False,
        )

        configure_prompt_validation(mock_db)
        mock_db.scalar = AsyncMock(return_value=existing_source)

        with pytest.raises(DuplicateSourceError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "DUPLICATE_ENTRY"
        assert (
            "source with this url already exists in the jurisdiction" in str(exc_info.value).lower()
        )

    @pytest.mark.asyncio
    async def test_duplicate_url_different_jurisdiction(
        self, sample_source_create, configure_prompt_validation
    ):
        """Test that creating source with duplicate URL in different jurisdiction is allowed."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        configure_prompt_validation(mock_db)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_source(mock_db, sample_source_create)

        assert isinstance(result, SourceRead)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_source_missing_jurisdiction_prompt(
        self,
        sample_source_create,
        configure_prompt_validation,
        sample_jurisdiction,
    ):
        """Test error when jurisdiction prompt is missing."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        jurisdiction = sample_jurisdiction
        jurisdiction.prompt = ""

        configure_prompt_validation(mock_db, jurisdiction=jurisdiction)
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(BadRequestError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "BAD_REQUEST"
        assert "jurisdiction prompt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_source_missing_project_prompt(
        self,
        sample_source_create,
        configure_prompt_validation,
        sample_project,
    ):
        """Test success when project master prompt is missing but jurisdiction prompt exists."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        project = sample_project
        project.master_prompt = ""

        configure_prompt_validation(mock_db, project=project)
        mock_db.scalar = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.create_source(mock_db, sample_source_create)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_source_missing_both_prompts(
        self,
        sample_source_create,
        configure_prompt_validation,
        sample_project,
        sample_jurisdiction,
    ):
        """Test error when jurisdiction prompt is missing (project prompt ignored)."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        sample_project.master_prompt = ""
        sample_jurisdiction.prompt = ""

        configure_prompt_validation(
            mock_db,
            jurisdiction=sample_jurisdiction,
            project=sample_project,
        )
        mock_db.scalar = AsyncMock(return_value=None)

        with pytest.raises(BadRequestError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "BAD_REQUEST"
        assert "jurisdiction prompt" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_source_missing_jurisdiction_record(
        self,
        sample_source_create,
    ):
        """Test error when jurisdiction lookup fails."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(side_effect=[None])

        with pytest.raises(NotFoundError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "NOT_FOUND"
        assert "jurisdiction not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_create_source_missing_project_record(
        self,
        sample_source_create,
        sample_jurisdiction,
    ):
        """Test error when project lookup fails."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(side_effect=[sample_jurisdiction, None])

        with pytest.raises(NotFoundError) as exc_info:
            await service.create_source(mock_db, sample_source_create)

        assert exc_info.value.code == "NOT_FOUND"
        assert "project not found" in str(exc_info.value).lower()


class TestSourceServiceGet:
    """Tests for SourceService.get_source()"""

    @pytest.mark.asyncio
    async def test_get_source_success(self, sample_source_db):
        """Test successful retrieval of a source."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)

        result = await service.get_source(mock_db, sample_source_db.id)

        assert isinstance(result, SourceRead)
        assert result.id == sample_source_db.id
        assert result.name == sample_source_db.name
        assert result.has_auth is True
        mock_db.get.assert_awaited_once_with(Source, sample_source_db.id)

    @pytest.mark.asyncio
    async def test_get_source_not_found(self):
        """Test that 404 is raised when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(SourceNotFoundError) as exc_info:
            await service.get_source(mock_db, source_id)

        assert exc_info.value.code == "SOURCE_NOT_FOUND"
        assert "not found" in str(exc_info.value).lower()


class TestSourceServiceGetSources:
    """Tests for SourceService.get_sources()"""

    @pytest.mark.asyncio
    async def test_get_sources_success(self, sample_jurisdiction_id):
        """Test successful retrieval of multiple sources."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        source1 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 1",
            url="https://example1.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            is_active=True,
            auth_details_encrypted=None,
            scraping_rules={},
        )

        source2 = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Source 2",
            url="https://example2.com",
            source_type=SourceType.PDF,
            scrape_frequency="WEEKLY",
            is_active=True,
            auth_details_encrypted="encrypted",
            scraping_rules={},
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [source1, source2]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_sources(mock_db)

        assert len(result) == 2
        assert all(isinstance(s, SourceRead) for s in result)
        assert result[0].name == "Source 1"
        assert result[1].has_auth is True

    @pytest.mark.asyncio
    async def test_get_sources_with_filters(self, sample_jurisdiction_id):
        """Test get_sources with jurisdiction filter."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.get_sources(
            mock_db,
            jurisdiction_id=sample_jurisdiction_id,
            is_active=True,
            skip=10,
            limit=50,
        )

        assert isinstance(result, list)
        mock_db.execute.assert_awaited_once()


class TestSourceServiceUpdate:
    """Tests for SourceService.update_source()"""

    @pytest.mark.asyncio
    async def test_update_source_success(self, sample_source_db):
        """Test successful source update."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(
            name="Updated Name",
            scrape_frequency="HOURLY",
            is_active=False,
        )

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.update_source(mock_db, sample_source_db.id, update_data)

        assert isinstance(result, SourceRead)
        assert sample_source_db.name == "Updated Name"
        assert sample_source_db.scrape_frequency == "HOURLY"
        assert sample_source_db.is_active is False
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_source_with_new_auth(self, sample_source_db, mock_encrypt_auth_details):
        """Test updating source with new auth details."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(auth_details={"new_user": "newpass"})

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        await service.update_source(mock_db, sample_source_db.id, update_data)

        assert sample_source_db.auth_details_encrypted == "mock_encrypted_value"
        mock_db.commit.assert_awaited_once()
        # Verify encryption was called with new auth details
        mock_encrypt_auth_details.assert_called_once_with({"new_user": "newpass"})

    @pytest.mark.asyncio
    async def test_update_source_not_found(self):
        """Test update when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        update_data = SourceUpdate(name="New Name")
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(SourceNotFoundError) as exc_info:
            await service.update_source(mock_db, source_id, update_data)

        assert exc_info.value.code == "SOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_source_database_error(self, sample_source_db, mock_encryption):
        """Test that database errors during update are handled."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        update_data = SourceUpdate(name="New Name")
        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()

        with pytest.raises(ProcessingError) as exc_info:
            await service.update_source(mock_db, sample_source_db.id, update_data)

        assert exc_info.value.code == "PROCESSING_ERROR"
        mock_db.rollback.assert_awaited_once()


class TestSourceServiceDelete:
    """Tests for SourceService.delete_source()"""

    @pytest.mark.asyncio
    async def test_delete_source_success(self, sample_source_db):
        """Test successful source deletion (soft delete by default)."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.delete_source(mock_db, sample_source_db.id)

        assert "message" in result
        assert "Source successfully deleted" in result["message"]
        assert result["source_id"] == str(sample_source_db.id)
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_source_not_found(self):
        """Test delete when source doesn't exist."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()
        source_id = uuid.uuid4()

        mock_db.get = AsyncMock(return_value=None)
        with pytest.raises(SourceNotFoundError) as exc_info:
            await service.delete_source(mock_db, source_id)

        assert exc_info.value.code == "SOURCE_NOT_FOUND"
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_source_database_error(self, sample_source_db):
        """Test that database errors during deletion are handled."""

        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        mock_db.get = AsyncMock(return_value=sample_source_db)
        mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()
        with pytest.raises(ProcessingError) as exc_info:
            await service.delete_source(mock_db, sample_source_db.id)

        assert exc_info.value.code == "PROCESSING_ERROR"
        assert "failed to delete source" in str(exc_info.value).lower()
        mock_db.rollback.assert_awaited_once()


class TestSourceServiceBulkCreate:
    """Tests for SourceService.bulk_create_sources()"""

    @pytest.fixture
    def sample_bulk_sources(self, sample_jurisdiction_id):
        """Fixture for bulk source creation data."""
        sources = [
            SourceCreate(
                jurisdiction_id=sample_jurisdiction_id,
                name="Source 1",
                url="https://source1.example.com",
                source_type=SourceType.WEB,
                scrape_frequency="DAILY",
            ),
            SourceCreate(
                jurisdiction_id=sample_jurisdiction_id,
                name="Source 2",
                url="https://source2.example.com",
                source_type=SourceType.WEB,
                scrape_frequency="HOURLY",
            ),
        ]
        return sources

    @pytest.mark.asyncio
    async def test_bulk_create_sources_success(
        self,
        sample_bulk_sources,
        sample_jurisdiction_id,
        configure_prompt_validation,
    ):
        """Test successful bulk creation of sources."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        unique_jurisdiction_count = len({source.jurisdiction_id for source in sample_bulk_sources})
        configure_prompt_validation(mock_db, validation_calls=unique_jurisdiction_count)

        # Mock execute to return empty list (no existing URLs)
        async def mock_execute(query):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = AsyncMock(side_effect=mock_execute)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.bulk_create_sources(mock_db, sample_bulk_sources)

        assert len(result) == 2
        assert all(isinstance(source, SourceRead) for source in result)
        assert result[0].name == "Source 1"
        assert result[1].name == "Source 2"
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bulk_create_sources_empty_list(self):
        """Test bulk creation with empty list."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        result = await service.bulk_create_sources(mock_db, [])

        assert result == []
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bulk_create_sources_duplicate_url(
        self, sample_bulk_sources, configure_prompt_validation
    ):
        """Test bulk creation fails when duplicate URLs exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        unique_ids = len({source.jurisdiction_id for source in sample_bulk_sources})
        configure_prompt_validation(mock_db, validation_calls=unique_ids)

        # Mock execute to return existing URLs with trailing slash (as Pydantic adds it)
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = ["https://source1.example.com/"]  # Note: trailing slash

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DuplicateSourceError) as exc_info:
            await service.bulk_create_sources(mock_db, sample_bulk_sources)

        exc = exc_info.value
        assert exc.field_errors is not None
        assert "url" in exc.field_errors
        assert "https://source1.example.com/" in exc.field_errors["url"]

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bulk_create_sources_db_error(
        self, sample_bulk_sources, configure_prompt_validation
    ):
        """Test database errors during bulk creation are handled."""
        mock_db = AsyncMock(spec=AsyncSession)
        service = SourceService()

        unique_ids = len({source.jurisdiction_id for source in sample_bulk_sources})
        configure_prompt_validation(mock_db, validation_calls=unique_ids)

        # Mock no existing URLs
        mock_db.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_db.execute.return_value = mock_result

        mock_db.commit = AsyncMock(side_effect=Exception("DB Error"))
        mock_db.rollback = AsyncMock()

        with pytest.raises(ProcessingError) as exc_info:
            await service.bulk_create_sources(mock_db, sample_bulk_sources)

        assert exc_info.value.code == "PROCESSING_ERROR"
        assert "failed" in str(exc_info.value).lower()
        mock_db.rollback.assert_awaited_once()
