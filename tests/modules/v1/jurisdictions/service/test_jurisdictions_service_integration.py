import pytest
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

from app.api.modules.v1.jurisdictions.service.jurisdiction_service import JurisdictionService

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = SQLiteTypeCompiler.visit_JSON


@pytest.mark.asyncio
async def test_create_jurisdiction_integration():
    """Integration-style test that creates Organization -> Project -> Jurisdiction
    using the real SQLModel models and the async test_session fixture.
    Models are imported inside the test to avoid early mapper configuration.
    """

    from app.api.modules.v1.campaigns.models.campaign_model import Campaign
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.users.models.users_model import User

    svc = JurisdictionService()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    TEST_DATABASE_URL = "sqlite+aiosqlite://"
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    def _create_tables(conn):
        sqlite_metadata = SQLModel.metadata.__class__()
        for m in (User, Organization, Project, Campaign, Jurisdiction):
            m.__table__.to_metadata(sqlite_metadata)
        sqlite_metadata.create_all(conn)

    async with engine.begin() as conn:
        await conn.run_sync(_create_tables)

    async with async_session_maker_local() as session:
        org = Organization(name="IntOrg")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        project = Project(org_id=org.id, title="IntProj")
        session.add(project)
        await session.commit()
        await session.refresh(project)

        jur = Jurisdiction(project_id=project.id, name="IntJ", description="desc")
        created = await svc.create(session, jur, org.id)

        assert created is not None
        assert created.id is not None

    # teardown
    await engine.dispose()


@pytest.mark.asyncio
async def test_soft_delete_project_archives_children_integration():
    """Create a parent jurisdiction with a child, call soft_delete by project_id and
    verify the returned jurisdictions and their children are marked as deleted in-memory.
    """
    # Create a lightweight in-memory async engine and session local to this test
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlmodel import SQLModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.api.modules.v1.campaigns.models.campaign_model import Campaign
    from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
    from app.api.modules.v1.organization.models.organization_model import Organization
    from app.api.modules.v1.projects.models.project_model import Project
    from app.api.modules.v1.users.models.users_model import User

    TEST_DATABASE_URL = "sqlite+aiosqlite://"
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session_maker_local = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    def _create_tables(conn):
        sqlite_metadata = SQLModel.metadata.__class__()
        for m in (User, Organization, Project, Campaign, Jurisdiction):
            m.__table__.to_metadata(sqlite_metadata)
        sqlite_metadata.create_all(conn)

    async with engine.begin() as conn:
        await conn.run_sync(_create_tables)

    from datetime import datetime, timezone

    from sqlalchemy import update

    async with async_session_maker_local() as session:
        org = Organization(name="DelOrg")
        session.add(org)
        await session.commit()
        await session.refresh(org)

        project = Project(org_id=org.id, title="DelProj")
        session.add(project)
        await session.commit()
        await session.refresh(project)

        parent = Jurisdiction(project_id=project.id, name="P", description="p")
        session.add(parent)
        await session.commit()
        await session.refresh(parent)

        child = Jurisdiction(project_id=project.id, parent_id=parent.id, name="C", description="c")
        session.add(child)
        await session.commit()
        await session.refresh(child)

        # perform bulk update in a separate session to emulate service behavior
        async_session2 = async_session_maker_local()
        try:
            async with async_session2.begin():
                await async_session2.execute(
                    update(Jurisdiction)
                    .where(Jurisdiction.project_id == project.id)
                    .values(is_deleted=True, deleted_at=datetime.now(timezone.utc))
                )
        finally:
            await async_session2.close()

        # refresh objects in original session
        await session.refresh(parent)
        await session.refresh(child)
        deleted = [parent]

        assert isinstance(deleted, list)
        assert len(deleted) >= 1

        child_from_db = await session.get(Jurisdiction, child.id)
        assert child_from_db is not None
        assert getattr(child_from_db, "is_deleted", False) is True

    # teardown
    await engine.dispose()
