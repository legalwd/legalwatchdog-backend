import pytest
from sqlalchemy import text

from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.search.schemas.search_schema import SearchRequest
from app.api.modules.v1.search.service.search_service import SearchService


@pytest.mark.asyncio
async def test_search_basic(pg_async_session):
    """Test basic search functionality returns results ordered by relevance."""
    db = pg_async_session

    org = Organization(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Org",
        description="Test organization",
    )
    db.add(org)
    await db.flush()

    project = Project(
        id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-000000000001",
        title="Test Project",
        description="Test project for search",
    )
    db.add(project)
    await db.flush()

    jurisdiction1 = Jurisdiction(
        id="00000000-0000-0000-0000-000000000001",
        name="US Federal",
        description="Federal laws",
        project_id="00000000-0000-0000-0000-000000000001",
    )
    db.add(jurisdiction1)
    await db.flush()

    source1 = Source(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Source 1",
        url="http://example.com/source1",
        jurisdiction_id=jurisdiction1.id,
        source_type="WEB",
        scrape_frequency="DAILY",
    )
    db.add(source1)
    await db.flush()

    revision = DataRevision(
        ai_summary="test summary",
        source_id=source1.id,
        minio_object_key="test_key.pdf",
    )
    db.add(revision)
    await db.flush()

    await db.execute(
        text("""
            UPDATE data_revisions
            SET search_vector = to_tsvector('english',
                COALESCE(minio_object_key, '') || ' ' ||
                COALESCE(ai_summary, '')
            )
            WHERE id = :id
        """),
        {"id": str(revision.id)},
    )
    await db.commit()
    await db.refresh(revision)

    search_request = SearchRequest(query="test", operator="AND", page=1, limit=10, min_rank=0.0)
    service = SearchService(db)
    response = await service.search(search_request)

    assert response.total >= 1
    assert response.page == 1
    assert response.limit == 10
    assert response.total_pages >= 1
    assert any(
        "test" in (r.title or r.content or r.summary or "").lower() for r in response.results
    )


@pytest.mark.asyncio
async def test_search_with_filters(pg_async_session):
    """Test search with source_id and extracted_data filters."""
    db = pg_async_session

    org = Organization(
        id="00000000-0000-0000-0000-000000000001",
        name="Test Org",
        description="Test organization",
    )
    db.add(org)
    await db.flush()

    project = Project(
        id="00000000-0000-0000-0000-000000000001",
        org_id="00000000-0000-0000-0000-000000000001",
        title="Test Project",
        description="Test project for search",
    )
    db.add(project)
    await db.flush()

    jurisdiction2 = Jurisdiction(
        id="00000000-0000-0000-0000-000000000002",
        name="US State",
        description="State laws",
        project_id="00000000-0000-0000-0000-000000000001",
    )
    jurisdiction3 = Jurisdiction(
        id="00000000-0000-0000-0000-000000000003",
        name="EU",
        description="European laws",
        project_id="00000000-0000-0000-0000-000000000001",
    )
    db.add(jurisdiction2)
    db.add(jurisdiction3)
    await db.flush()

    source2 = Source(
        id="00000000-0000-0000-0000-000000000002",
        name="Test Source 2",
        url="http://example.com/source2",
        jurisdiction_id=jurisdiction2.id,
        source_type="WEB",
        scrape_frequency="DAILY",
    )
    source3 = Source(
        id="00000000-0000-0000-0000-000000000003",
        name="Test Source 3",
        url="http://example.com/source3",
        jurisdiction_id=jurisdiction3.id,
        source_type="WEB",
        scrape_frequency="DAILY",
    )
    db.add(source2)
    db.add(source3)
    await db.flush()

    revision1 = DataRevision(
        ai_summary="US federal legal document",
        source_id=source2.id,
        minio_object_key="federal_law.pdf",
    )

    revision2 = DataRevision(
        ai_summary="California legal document",
        source_id=source3.id,
        minio_object_key="state_law.pdf",
    )

    db.add(revision1)
    db.add(revision2)
    await db.flush()

    await db.execute(
        text("""
            UPDATE data_revisions
            SET search_vector = to_tsvector('english',
                COALESCE(minio_object_key, '') || ' ' ||
                COALESCE(ai_summary, '')
            )
            WHERE id IN (:id1, :id2)
        """),
        {"id1": str(revision1.id), "id2": str(revision2.id)},
    )
    await db.commit()

    search_request = SearchRequest(query="legal", page=1, limit=10, min_rank=0.0)
    service = SearchService(db)
    response = await service.search(search_request)

    assert response.total >= 1
    assert response.page == 1
    assert response.total_pages >= 1


@pytest.mark.asyncio
async def test_empty_search(pg_async_session):
    """Test search with empty or non-existent query returns no results."""
    db = pg_async_session
    search_request = SearchRequest(query="nonexistentterm", page=1, limit=10, min_rank=0.0)
    service = SearchService(db)
    response = await service.search(search_request)

    assert response.total == 0
    assert response.total_pages == 0
    assert len(response.results) == 0
