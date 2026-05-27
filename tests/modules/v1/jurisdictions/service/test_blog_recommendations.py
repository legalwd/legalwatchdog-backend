"""Tests for BlogRecommendationEngine and accordion tree hierarchy."""

import pytest
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.jurisdictions.service.blog_recommendation_service import BlogRecommendationEngine
from app.api.modules.v1.jurisdictions.service.guides_service import GuidesService
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project


@pytest.mark.asyncio
async def test_blog_recommendations_and_tree(db_session):
    """Test subdivisions, physical neighbors, reference frameworks, similar topics, and tree JSON structure."""
    # 1. Create Organization
    org = Organization(
        name="Test Org Recommendations",
        industry="EOR",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # 2. Create Project
    project = Project(
        org_id=org.id,
        title="Test Project Recommendations",
        master_prompt="Standard Prompt",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    # 3. Create parent Country jurisdictions
    us = Jurisdiction(
        project_id=project.id,
        parent_id=None,
        name="United States",
        description="US Root",
    )
    armenia = Jurisdiction(
        project_id=project.id,
        parent_id=None,
        name="Armenia",
        description="Armenia Root",
    )
    georgia = Jurisdiction(
        project_id=project.id,
        parent_id=None,
        name="Georgia",
        description="Georgia Root",
    )
    db_session.add(us)
    db_session.add(armenia)
    db_session.add(georgia)
    await db_session.commit()
    await db_session.refresh(us)
    await db_session.refresh(armenia)
    await db_session.refresh(georgia)

    # 4. Create child subdivisions
    california = Jurisdiction(
        project_id=project.id,
        parent_id=us.id,
        name="California",
        description="California subdivision",
    )
    new_york = Jurisdiction(
        project_id=project.id,
        parent_id=us.id,
        name="New York",
        description="New York subdivision",
    )
    db_session.add(california)
    db_session.add(new_york)
    await db_session.commit()
    await db_session.refresh(california)
    await db_session.refresh(new_york)

    # 5. Create blog posts
    post_us = JurisdictionBlogPost(
        jurisdiction_id=us.id,
        title="US Federal Compliance Guide",
        slug="eor-guide-united-states",
        content="US compliance content",
        meta_description="US EOR Compliance Guide",
        keywords=["EOR", "Compliance"],
        is_published=True,
        content_hash="hash1",
    )
    post_california = JurisdictionBlogPost(
        jurisdiction_id=california.id,
        title="California Compliance Guide",
        slug="eor-guide-california",
        content="California compliance content",
        meta_description="California EOR Compliance Guide",
        keywords=["EOR", "Payroll"],
        is_published=True,
        content_hash="hash2",
    )
    post_ny = JurisdictionBlogPost(
        jurisdiction_id=new_york.id,
        title="New York Compliance Guide",
        slug="eor-guide-new-york",
        content="New York compliance content",
        meta_description="New York EOR Compliance Guide",
        keywords=["EOR", "Tax"],
        is_published=True,
        content_hash="hash3",
    )
    post_armenia = JurisdictionBlogPost(
        jurisdiction_id=armenia.id,
        title="Armenia Compliance Guide",
        slug="eor-guide-armenia",
        content="Armenia compliance content",
        meta_description="Armenia EOR Compliance Guide",
        keywords=["EOR", "Compliance"],
        is_published=True,
        content_hash="hash4",
    )
    post_georgia = JurisdictionBlogPost(
        jurisdiction_id=georgia.id,
        title="Georgia Compliance Guide",
        slug="eor-guide-georgia",
        content="Georgia compliance content",
        meta_description="Georgia EOR Compliance Guide",
        keywords=["EOR", "Tax"],
        is_published=True,
        content_hash="hash5",
    )
    db_session.add(post_us)
    db_session.add(post_california)
    db_session.add(post_ny)
    db_session.add(post_armenia)
    db_session.add(post_georgia)
    await db_session.commit()

    # 6. Test Recommendations for California
    engine = BlogRecommendationEngine(db_session)
    recs_ca = await engine.get_recommendations(post_california)

    assert len(recs_ca) > 0
    types = [r.type for r in recs_ca]
    names = [r.name for r in recs_ca]

    # California should have New York as a Subdivision sibling, and US/others as Reference Framework or Similar Framework
    assert "Subdivision" in types
    assert "New York" in names

    # 7. Test Recommendations for Armenia
    # Georgia should be a Neighboring Country (both Western Asia subregion in countries.csv)
    recs_am = await engine.get_recommendations(post_armenia)
    assert len(recs_am) > 0
    am_types = [r.type for r in recs_am]
    am_names = [r.name for r in recs_am]
    assert "Neighboring Country" in am_types
    assert "Georgia" in am_names

    # 8. Test Hierarchy Tree
    guides_service = GuidesService(db_session)
    tree = await guides_service.build_hierarchy_tree()

    assert len(tree) > 0
    root_names = [t["name"] for t in tree]
    assert "United States" in root_names
    assert "Armenia" in root_names
    assert "Georgia" in root_names

    us_node = next(t for t in tree if t["name"] == "United States")
    child_names = [c["name"] for c in us_node["children"]]
    assert "California" in child_names
    assert "New York" in child_names
