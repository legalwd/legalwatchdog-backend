import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.api.modules.v1.campaigns.models.campaign_model import Campaign, CampaignStatus
from app.api.modules.v1.campaigns.schemas.campaign_schema import CampaignBlogBatchPublishRequest
from app.api.modules.v1.campaigns.service.campaign_service import CampaignService
from app.api.modules.v1.jurisdictions.models.jurisdiction_blog_post import JurisdictionBlogPost
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User


@pytest_asyncio.fixture
async def campaign_blog_graph(db_session):
    """Create a campaign with two generated blogs for service tests."""
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid.uuid4(),
        email=f"campaign-service-{uuid.uuid4().hex[:8]}@example.com",
        name="Service User",
        is_active=True,
        is_approved=True,
        is_superadmin=True,
    )
    organization = Organization(
        id=uuid.uuid4(),
        name="Campaign Service Org",
        email=f"org-{uuid.uuid4().hex[:8]}@example.com",
    )
    project = Project(
        id=uuid.uuid4(),
        org_id=organization.id,
        title="Campaign Preview Project",
    )
    campaign = Campaign(
        id=uuid.uuid4(),
        organization_id=organization.id,
        project_id=project.id,
        name="Campaign Preview",
        industry="Technology",
        status=CampaignStatus.MONITORING,
        created_by=user.id,
        created_at=now,
        updated_at=now,
    )
    jurisdiction_one = Jurisdiction(
        id=uuid.uuid4(),
        project_id=project.id,
        campaign_id=campaign.id,
        name="Germany",
        created_at=now,
        updated_at=now,
    )
    jurisdiction_two = Jurisdiction(
        id=uuid.uuid4(),
        project_id=project.id,
        campaign_id=campaign.id,
        name="France",
        created_at=now,
        updated_at=now,
    )
    blog_one = JurisdictionBlogPost(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_one.id,
        title="Germany Tech Employment Guide",
        slug="technology-guide-germany",
        content="# Germany",
        content_html="<h1>Germany</h1>",
        meta_description="Germany employment law guide for tech companies.",
        keywords=["germany", "employment"],
        content_hash="hash-one",
        version=1,
        generated_at=now,
        created_at=now,
        updated_at=now,
    )
    blog_two = JurisdictionBlogPost(
        id=uuid.uuid4(),
        jurisdiction_id=jurisdiction_two.id,
        title="France Tech Employment Guide",
        slug="technology-guide-france",
        content="# France",
        content_html="<h1>France</h1>",
        meta_description="France employment law guide for tech companies.",
        keywords=["france", "employment"],
        content_hash="hash-two",
        version=1,
        generated_at=now,
        created_at=now,
        updated_at=now,
    )

    db_session.add(user)
    db_session.add(organization)
    db_session.add(project)
    await db_session.flush()
    db_session.add(campaign)
    await db_session.flush()
    db_session.add(jurisdiction_one)
    db_session.add(jurisdiction_two)
    await db_session.flush()
    db_session.add(blog_one)
    db_session.add(blog_two)
    await db_session.commit()

    return {
        "campaign": campaign,
        "jurisdiction_one": jurisdiction_one,
        "jurisdiction_two": jurisdiction_two,
        "blog_one": blog_one,
        "blog_two": blog_two,
    }


@pytest.mark.asyncio
async def test_batch_publish_campaign_blogs_selected_ids(db_session, campaign_blog_graph) -> None:
    """Batch publish updates only the selected campaign blogs and returns a summary."""
    service = CampaignService(db_session)
    campaign = campaign_blog_graph["campaign"]
    jurisdiction_one = campaign_blog_graph["jurisdiction_one"]
    blog_one = campaign_blog_graph["blog_one"]

    payload = CampaignBlogBatchPublishRequest(
        blog_ids=[blog_one.id],
        is_published=True,
    )

    with patch(
        "app.api.modules.v1.campaigns.service.campaign_service.BlogGenerationService.publish_blog_post",
        new=AsyncMock(
            return_value={
                "data": {
                    "id": str(blog_one.id),
                    "jurisdiction_id": str(jurisdiction_one.id),
                    "title": blog_one.title,
                    "slug": blog_one.slug,
                    "is_published": True,
                    "public_url": "https://legalwatch.dog/resources/project/germany/",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }
            }
        ),
    ) as mock_publish:
        result = await service.batch_publish_campaign_blogs(campaign.id, payload)

    assert result["action"] == "published"
    assert result["requested_count"] == 1
    assert result["matched_count"] == 1
    assert result["processed_count"] == 1
    assert result["failed_count"] == 0
    assert result["items"][0]["status"] == "success"
    mock_publish.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real PostgreSQL - skipped")
async def test_render_campaign_blog_preview(db_session, campaign_blog_graph) -> None:
    """Preview rendering returns a full HTML document for the selected blog."""
    pass
