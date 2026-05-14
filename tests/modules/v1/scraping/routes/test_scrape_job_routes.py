"""Tests for scrape job routes (manual scrape trigger and job status endpoints)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.plan_limits import PlanLimits
from app.api.db.database import get_db
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.scraping.models.scrape_job import ScrapeJob, ScrapeJobStatus
from app.api.modules.v1.scraping.models.source_model import Source, SourceType
from app.api.modules.v1.users.models.users_model import User
from main import app


@pytest.fixture(autouse=True)
def allow_billing_and_unlimited_scans(monkeypatch):
    """
    By default, allow billing & remove scan limits so existing tests behave
    as before. Individual tests can override this monkeypatch if needed.
    """
    from app.api.core.dependencies import plan_limits as plan_limits_mod

    async def fake_get_plan_limits_for_org(org_id, db):
        return PlanLimits(
            max_projects=None,
            max_jurisdictions=None,
            monthly_scans=None,
        )

    async def fake_count_monthly_scans_for_org(org_id, db):
        return 0

    async def fake_require_billing_access(organization_id, db):
        return None

    monkeypatch.setattr(
        plan_limits_mod,
        "get_plan_limits_for_org",
        fake_get_plan_limits_for_org,
    )
    monkeypatch.setattr(
        plan_limits_mod,
        "_count_monthly_scans_for_org",
        fake_count_monthly_scans_for_org,
    )
    monkeypatch.setattr(
        plan_limits_mod,
        "require_billing_access",
        fake_require_billing_access,
    )


@pytest.fixture
def sample_user() -> User:
    """Fixture providing a sample authenticated user."""
    return User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_approved=True,
    )


@pytest_asyncio.fixture
async def sample_jurisdiction_id(pg_async_session) -> uuid.UUID:
    """Fixture providing a sample jurisdiction UUID with required parent entities."""
    organization = Organization(name="Test Organization", is_active=True)
    pg_async_session.add(organization)
    await pg_async_session.commit()
    await pg_async_session.refresh(organization)

    project = Project(org_id=organization.id, title="Test Project", description="Test description")
    pg_async_session.add(project)
    await pg_async_session.commit()
    await pg_async_session.refresh(project)

    jurisdiction = Jurisdiction(
        project_id=project.id,
        name="Test Jurisdiction",
        description="Test description",
    )
    pg_async_session.add(jurisdiction)
    await pg_async_session.commit()
    await pg_async_session.refresh(jurisdiction)

    return jurisdiction.id


@pytest_asyncio.fixture
async def client():
    """Fixture providing async HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """Fixture providing authorization headers."""
    return {"Authorization": "Bearer test-token"}


@pytest_asyncio.fixture
async def sample_source(pg_async_session, sample_jurisdiction_id) -> Source:
    """Fixture providing a sample active source."""
    source = Source(
        id=uuid.uuid4(),
        jurisdiction_id=sample_jurisdiction_id,
        name="Test Source",
        url="https://test.example.com",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        is_active=True,
    )
    pg_async_session.add(source)
    await pg_async_session.commit()
    await pg_async_session.refresh(source)
    return source


@pytest_asyncio.fixture
async def inactive_source(pg_async_session, sample_jurisdiction_id) -> Source:
    """Fixture providing a sample inactive source."""
    source = Source(
        id=uuid.uuid4(),
        jurisdiction_id=sample_jurisdiction_id,
        name="Inactive Source",
        url="https://inactive.example.com",
        source_type=SourceType.WEB,
        scrape_frequency="DAILY",
        is_active=False,
    )
    pg_async_session.add(source)
    await pg_async_session.commit()
    await pg_async_session.refresh(source)
    return source


class TestManualScrapeTrigger:
    """Tests for POST /sources/{source_id}/scrapes endpoint."""

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_success(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test successful scrape job creation returns 202 Accepted."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch(
            "app.api.modules.v1.scraping.service.scrape_job_service.ScrapeJobService.queue_scrape_job",
        ):
            response = await client.post(
                f"/api/v1/sources/{sample_source.id}/scrapes",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_202_ACCEPTED, (
            f"Expected 202, got {response.status_code}: {response.json()}"
        )
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Scrape job queued successfully"
        assert "job_id" in data["data"]
        assert data["data"]["source_id"] == str(sample_source.id)
        assert data["data"]["status"] == ScrapeJobStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test 404 when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            f"/api/v1/sources/{non_existent_id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_source_inactive(
        self, client, pg_async_session, auth_headers, inactive_source, sample_user
    ):
        """Test 400 when source is inactive."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            f"/api/v1/sources/{inactive_source.id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "inactive" in data["message"].lower()
        assert data["error_code"] == "SOURCE_INACTIVE"

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_concurrent_job_conflict(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 409 when a scrape is already in progress for the source."""
        existing_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(existing_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            f"/api/v1/sources/{sample_source.id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already in progress" in data["message"].lower()
        assert data["error_code"] == "SCRAPE_IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_pending_job_conflict(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 409 when a pending scrape exists for the source."""
        existing_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(existing_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.post(
            f"/api/v1/sources/{sample_source.id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_after_completed_job(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 202 when a previous job is completed (no conflict)."""
        completed_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(completed_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch(
            "app.api.modules.v1.scraping.service.scrape_job_service.ScrapeJobService.queue_scrape_job",
        ):
            response = await client.post(
                f"/api/v1/sources/{sample_source.id}/scrapes",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_after_failed_job(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 202 when a previous job failed (no conflict)."""
        failed_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.FAILED,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_message="Previous failure",
        )
        pg_async_session.add(failed_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch(
            "app.api.modules.v1.scraping.service.scrape_job_service.ScrapeJobService.queue_scrape_job",
        ):
            response = await client.post(
                f"/api/v1/sources/{sample_source.id}/scrapes",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.asyncio
    async def test_manual_scrape_trigger_unauthorized(
        self, client, pg_async_session, sample_source
    ):
        """Test that unauthenticated requests are rejected."""
        app.dependency_overrides.clear()

        response = await client.post(
            f"/api/v1/sources/{sample_source.id}/scrapes",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestGetScrapeJobStatus:
    """Tests for GET /sources/{source_id}/scrapes/{job_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_pending(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test getting status of a pending job."""
        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["id"] == str(job.id)
        assert data["data"]["source_id"] == str(sample_source.id)
        assert data["data"]["status"] == ScrapeJobStatus.PENDING.value
        assert data["data"]["result"] is None
        assert data["data"]["error_message"] is None

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_in_progress(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test getting status of an in-progress job."""
        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["status"] == ScrapeJobStatus.IN_PROGRESS.value
        assert data["data"]["started_at"] is not None

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_completed(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test getting status of a completed job with result."""
        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result={"content": "scraped data", "items_found": 10},
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["status"] == ScrapeJobStatus.COMPLETED.value
        assert data["data"]["result"] == {"content": "scraped data", "items_found": 10}
        assert data["data"]["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_failed(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test getting status of a failed job with error message."""
        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.FAILED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_message="Scrape execution failed. Please try again.",
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["status"] == ScrapeJobStatus.FAILED.value
        assert data["data"]["error_message"] == "Scrape execution failed. Please try again."

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_not_found(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 404 when job doesn't exist."""
        non_existent_job_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{non_existent_job_id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["message"] == "Scrape job not found"
        assert data["error_code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_wrong_source(
        self,
        client,
        pg_async_session,
        auth_headers,
        sample_source,
        sample_jurisdiction_id,
        sample_user,
    ):
        """Test 404 when job belongs to a different source."""
        other_source = Source(
            id=uuid.uuid4(),
            jurisdiction_id=sample_jurisdiction_id,
            name="Other Source",
            url="https://other.example.com",
            source_type=SourceType.WEB,
            scrape_frequency="DAILY",
            is_active=True,
        )
        pg_async_session.add(other_source)
        await pg_async_session.commit()

        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=other_source.id,
            status=ScrapeJobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_unauthorized(
        self, client, pg_async_session, sample_source
    ):
        """Test that unauthenticated requests are rejected."""
        app.dependency_overrides.clear()

        job_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job_id}",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_scrape_job_status_response_structure(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test that response contains all expected fields."""
        job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result={"data": "test"},
        )
        pg_async_session.add(job)
        await pg_async_session.commit()
        await pg_async_session.refresh(job)

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/{job.id}",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        assert "id" in data
        assert "source_id" in data
        assert "status" in data
        assert "result" in data
        assert "error_message" in data
        assert "data_revision_id" in data
        assert "created_at" in data
        assert "started_at" in data
        assert "completed_at" in data


class TestGetActiveScrapeJob:
    """Tests for GET /sources/{source_id}/scrapes/active endpoint."""

    @pytest.mark.asyncio
    async def test_get_active_scrape_job_found(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test successful retrieval of active scrape job returns 200 OK."""
        active_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(active_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/active",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Active scrape job found for this source"
        assert data["data"]["id"] == str(active_job.id)
        assert data["data"]["source_id"] == str(sample_source.id)
        assert data["data"]["status"] == ScrapeJobStatus.IN_PROGRESS.value

    @pytest.mark.asyncio
    async def test_get_active_scrape_job_pending_status(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test retrieval of pending scrape job returns 200 OK."""
        pending_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(pending_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/active",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["data"]["status"] == ScrapeJobStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_active_scrape_job_no_active_job(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test 204 when no active scrape job exists."""
        # Add a completed job (should not be returned)
        completed_job = ScrapeJob(
            id=uuid.uuid4(),
            source_id=sample_source.id,
            status=ScrapeJobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        pg_async_session.add(completed_job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes/active",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "No active scrape job found for this source"

    @pytest.mark.asyncio
    async def test_get_active_scrape_job_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test 404 when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{non_existent_id}/scrapes/active",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["message"].lower()
        assert data["error_code"] == "SOURCE_NOT_FOUND"


class TestListScrapeJobs:
    """Tests for GET /sources/{source_id}/scrapes endpoint."""

    @pytest.mark.asyncio
    async def test_list_scrape_jobs_success(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test successful listing of scrape jobs returns 200 OK."""
        # Create multiple jobs with different statuses
        jobs = [
            ScrapeJob(
                id=uuid.uuid4(),
                source_id=sample_source.id,
                status=ScrapeJobStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                result={"status": "success", "change_detected": True},
            ),
            ScrapeJob(
                id=uuid.uuid4(),
                source_id=sample_source.id,
                status=ScrapeJobStatus.FAILED,
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
                started_at=datetime.now(timezone.utc) - timedelta(hours=1),
                completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
                error_message="Network timeout",
            ),
        ]

        for job in jobs:
            pg_async_session.add(job)
        await pg_async_session.commit()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["message"] == "Scrape jobs retrieved successfully"
        assert len(data["data"]["items"]) == 2
        assert data["data"]["pagination"]["total"] == 2
        assert data["data"]["pagination"]["page"] == 1

        # Check ordering (newest first)
        first_job = data["data"]["items"][0]
        second_job = data["data"]["items"][1]
        assert first_job["status"] == ScrapeJobStatus.COMPLETED.value
        assert second_job["status"] == ScrapeJobStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_list_scrape_jobs_empty_list(
        self, client, pg_async_session, auth_headers, sample_source, sample_user
    ):
        """Test empty list when no jobs exist for source."""

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{sample_source.id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert len(data["data"]["items"]) == 0
        assert data["data"]["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_scrape_jobs_source_not_found(
        self, client, pg_async_session, auth_headers, sample_user
    ):
        """Test 404 when source doesn't exist."""
        non_existent_id = uuid.uuid4()

        async def override_get_db():
            yield pg_async_session

        async def override_get_current_user():
            return sample_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        response = await client.get(
            f"/api/v1/sources/{non_existent_id}/scrapes",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["message"].lower()
        assert data["error_code"] == "SOURCE_NOT_FOUND"
