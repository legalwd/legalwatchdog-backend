"""Comprehensive tests for optional fields requirements."""

import uuid

import pytest
import pytest_asyncio
from pydantic import HttpUrl

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.schemas.jurisdiction_schema import (
    JurisdictionCreateSchema,
    JurisdictionUpdateSchema,
)
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.source_model import Source, SourceType
from app.api.modules.v1.scraping.schemas.source_service import SourceCreate


@pytest_asyncio.fixture
async def setup_test_data(pg_async_session):
    """Create test organization, project, and jurisdiction."""
    org = Organization(name="Test Org", is_active=True)
    pg_async_session.add(org)
    await pg_async_session.commit()
    await pg_async_session.refresh(org)

    project = Project(org_id=org.id, title="Test Project", description="Test description")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test jurisdiction description",
        prompt="Extract data",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    return {
        "org": org,
        "project": project,
        "jurisdiction": jurisdiction,
    }


class TestSourceCreationWithoutName:
    """Test that sources can be created without a name field."""

    @pytest.mark.asyncio
    async def test_create_source_without_name_field(self, setup_test_data):
        """Test creating source without providing name."""
        test_data = setup_test_data
        jurisdiction_id = test_data["jurisdiction"].id

        source_create = SourceCreate(
            jurisdiction_id=jurisdiction_id,
            url=HttpUrl("https://example.com/source"),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )

        assert source_create.name is None
        assert source_create.url is not None

    @pytest.mark.asyncio
    async def test_create_source_with_optional_name(self, setup_test_data):
        """Test creating source with optional name."""
        test_data = setup_test_data
        jurisdiction_id = test_data["jurisdiction"].id

        source_create = SourceCreate(
            jurisdiction_id=jurisdiction_id,
            name="Optional Source Name",
            url=HttpUrl("https://example.com/source2"),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )

        assert source_create.name == "Optional Source Name"

    @pytest.mark.asyncio
    async def test_create_source_name_field_accepts_none(self):
        """Test SourceCreate schema accepts None for name."""
        jurisdiction_id = uuid.uuid4()

        source_create = SourceCreate(
            jurisdiction_id=jurisdiction_id,
            name=None,
            url=HttpUrl("https://example.com/source3"),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )

        assert source_create.name is None

    @pytest.mark.asyncio
    async def test_source_model_name_is_optional(self, setup_test_data):
        """Test Source model allows None for name field."""
        test_data = setup_test_data
        jurisdiction_id = test_data["jurisdiction"].id

        source = Source(
            jurisdiction_id=jurisdiction_id,
            name=None,
            url="https://example.com/test",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )

        assert source.name is None
        assert source.url == "https://example.com/test"


class TestJurisdictionWithoutDescription:
    """Test jurisdictions can be created without description."""

    @pytest.mark.asyncio
    async def test_create_jurisdiction_without_description(self, setup_test_data):
        """Test creating jurisdiction without description."""
        test_data = setup_test_data
        project_id = test_data["project"].id

        jurisdiction_create = JurisdictionCreateSchema(
            project_id=project_id,
            name="Jurisdiction Without Description",
            parent_id=None,
        )

        assert jurisdiction_create.description is None
        assert jurisdiction_create.name is not None

    @pytest.mark.asyncio
    async def test_create_jurisdiction_with_optional_description(self, setup_test_data):
        """Test creating jurisdiction with optional description."""
        test_data = setup_test_data
        project_id = test_data["project"].id

        jurisdiction_create = JurisdictionCreateSchema(
            project_id=project_id,
            name="Jurisdiction With Description",
            description="Optional description",
            parent_id=None,
        )

        assert jurisdiction_create.description == "Optional description"

    @pytest.mark.asyncio
    async def test_update_jurisdiction_without_description(self):
        """Test updating jurisdiction without modifying description."""
        jurisdiction_update = JurisdictionUpdateSchema(
            name="Updated Jurisdiction",
            parent_id=None,
        )

        assert jurisdiction_update.description is None

    @pytest.mark.asyncio
    async def test_jurisdiction_model_description_is_optional(self, setup_test_data):
        """Test Jurisdiction model allows None for description field."""
        test_data = setup_test_data
        project_id = test_data["project"].id

        jurisdiction = Jurisdiction(
            project_id=project_id,
            name="Test Jurisdiction No Description",
            description=None,
            prompt="Extract rules",
        )

        assert jurisdiction.description is None
        assert jurisdiction.name is not None

    @pytest.mark.asyncio
    async def test_create_jurisdiction_description_none(self, setup_test_data):
        """Test creating jurisdiction with explicit None description."""
        test_data = setup_test_data
        project_id = test_data["project"].id

        jurisdiction_create = JurisdictionCreateSchema(
            project_id=project_id,
            name="Test Jurisdiction",
            description=None,
            parent_id=None,
        )

        assert jurisdiction_create.description is None


class TestIntegration:
    """Integration tests combining multiple optional fields."""

    @pytest.mark.asyncio
    async def test_create_source_without_name_full_flow(self, setup_test_data):
        """Test full flow with optional fields."""
        test_data = setup_test_data

        jurisdiction_schema = JurisdictionCreateSchema(
            project_id=test_data["project"].id,
            name="No Desc Jurisdiction",
            description=None,
        )

        assert jurisdiction_schema.description is None

        source_schema = SourceCreate(
            jurisdiction_id=test_data["jurisdiction"].id,
            name=None,
            url=HttpUrl("https://example.com/integrated"),
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
        )

        assert source_schema.name is None
        assert jurisdiction_schema.description is None


class TestSchemaValidation:
    """Test schemas properly validate optional fields."""

    @pytest.mark.asyncio
    async def test_source_create_schema_validation(self):
        """Test SourceCreate schema validation with optional name."""
        schema1 = SourceCreate(
            jurisdiction_id=uuid.uuid4(),
            name="Test Source",
            url=HttpUrl("https://example.com"),
            scrape_frequency="DAILY",
        )
        assert schema1.name == "Test Source"

        schema2 = SourceCreate(
            jurisdiction_id=uuid.uuid4(),
            url=HttpUrl("https://example.com"),
            scrape_frequency="DAILY",
        )
        assert schema2.name is None

        schema3 = SourceCreate(
            jurisdiction_id=uuid.uuid4(),
            name=None,
            url=HttpUrl("https://example.com"),
            scrape_frequency="DAILY",
        )
        assert schema3.name is None

    @pytest.mark.asyncio
    async def test_jurisdiction_create_schema_validation(self):
        """Test JurisdictionCreateSchema validation with optional description."""
        project_id = uuid.uuid4()

        schema1 = JurisdictionCreateSchema(
            project_id=project_id,
            name="Test",
            description="Test description",
        )
        assert schema1.description == "Test description"

        schema2 = JurisdictionCreateSchema(
            project_id=project_id,
            name="Test",
        )
        assert schema2.description is None

        schema3 = JurisdictionCreateSchema(
            project_id=project_id,
            name="Test",
            description=None,
        )
        assert schema3.description is None
