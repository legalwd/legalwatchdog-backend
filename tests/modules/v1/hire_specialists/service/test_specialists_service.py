"""Unit tests for SpecialistHireService."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
    UserNotInOrganizationError,
)
from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import SpecialistHireRequest
from app.api.modules.v1.hire_specialists.service.specialists_service import SpecialistHireService
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "testuser@example.com"
    user.name = "Test User"
    return user


@pytest.fixture
def mock_project(mock_user):
    """Create a mock project object."""
    org_id = uuid4()
    project = MagicMock(spec=Project)
    project.id = uuid4()
    project.org_id = org_id
    project.name = "Test Project"
    return project, org_id


@pytest.fixture
def mock_background_tasks():
    """Create a mock background tasks handler."""
    return MagicMock()


@pytest.fixture
def valid_hire_request():
    """Create a valid specialist hire request."""
    return SpecialistHireRequest(
        company_name="Acme Corporation",
        company_email="hr@acme.com",
        industry="Technology",
        brief_description="We need a specialist for immigration matters.",
        jurisdiction_id=uuid4(),
    )


@pytest.fixture
def minimal_hire_request():
    """Create a minimal specialist hire request without optional fields."""
    return SpecialistHireRequest(
        company_name="Small Business LLC",
        company_email="contact@smallbiz.com",
        industry="Retail",
        brief_description="Need help with work permits.",
    )


def _setup_db_execute_mock(mock_db, user, project):
    """Helper to setup mock_db.execute to return user and project."""
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project

    mock_db.execute = AsyncMock(side_effect=[user_result, project_result])


def _setup_db_execute_for_hire(mock_db, user, project, hire=None):
    """Helper to setup mock_db.execute for hire status/deactivate operations."""
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project

    hire_result = MagicMock()
    hire_result.scalar_one_or_none.return_value = hire

    mock_db.execute = AsyncMock(side_effect=[user_result, project_result, hire_result])


class TestSpecialistHireService:
    """Test suite for SpecialistHireService."""

    @pytest.mark.asyncio
    async def test_create_hire_request_success(
        self, mock_db, mock_user, mock_project, mock_background_tasks, valid_hire_request
    ):
        """Test successful creation of a hire request."""
        project, org_id = mock_project
        _setup_db_execute_mock(mock_db, mock_user, project)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            with patch(
                "app.api.modules.v1.hire_specialists.service.specialists_service.SpecialistHireService._handle_notifications",
                new_callable=AsyncMock,
            ):
                service = SpecialistHireService(db=mock_db)
                result = await service.create_hire_request(
                    request_data=valid_hire_request,
                    user_id=mock_user.id,
                    project_id=project.id,
                    organization_id=org_id,
                    background_tasks=mock_background_tasks,
                )

                mock_db.add.assert_called_once()
                mock_db.commit.assert_awaited_once()
                mock_db.refresh.assert_awaited_once()

                added_hire = mock_db.add.call_args[0][0]
                assert isinstance(added_hire, SpecialistHire)
                assert added_hire.company_name == valid_hire_request.company_name
                assert added_hire.company_email == valid_hire_request.company_email
                assert added_hire.industry == valid_hire_request.industry
                assert added_hire.brief_description == valid_hire_request.brief_description
                assert added_hire.project_id == project.id
                assert added_hire.jurisdiction_id == valid_hire_request.jurisdiction_id
                assert added_hire.user_id == mock_user.id

                assert result == added_hire

                mock_tenant_guard.assert_called_once_with(mock_db, mock_user)
                mock_tenant_instance.get_membership.assert_called_once_with(org_id)

    @pytest.mark.asyncio
    async def test_create_hire_request_user_not_found(
        self, mock_db, mock_project, mock_background_tasks, valid_hire_request
    ):
        """Test that NotFoundError is raised when user is not found."""
        project, org_id = mock_project
        user_id = uuid4()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=user_result)

        service = SpecialistHireService(db=mock_db)

        with pytest.raises(NotFoundError) as exc_info:
            await service.create_hire_request(
                request_data=valid_hire_request,
                user_id=user_id,
                project_id=project.id,
                organization_id=org_id,
                background_tasks=mock_background_tasks,
            )

        assert "User not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_create_hire_request_user_not_in_organization(
        self, mock_db, mock_user, mock_project, mock_background_tasks, valid_hire_request
    ):
        """Test that UserNotInOrganizationError is raised when user is not in org."""
        project, org_id = mock_project

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=user_result)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock(
                side_effect=UserNotInOrganizationError(message="User not in organization")
            )

            service = SpecialistHireService(db=mock_db)

            with pytest.raises(UserNotInOrganizationError):
                await service.create_hire_request(
                    request_data=valid_hire_request,
                    user_id=mock_user.id,
                    project_id=project.id,
                    organization_id=org_id,
                    background_tasks=mock_background_tasks,
                )

    @pytest.mark.asyncio
    async def test_create_hire_request_project_not_found(
        self, mock_db, mock_user, mock_background_tasks, valid_hire_request
    ):
        """Test that NotFoundError is raised when project is not found."""
        org_id = uuid4()
        project_id = uuid4()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = mock_user

        project_result = MagicMock()
        project_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[user_result, project_result])

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)

            with pytest.raises(NotFoundError) as exc_info:
                await service.create_hire_request(
                    request_data=valid_hire_request,
                    user_id=mock_user.id,
                    project_id=project_id,
                    organization_id=org_id,
                    background_tasks=mock_background_tasks,
                )

            assert "Project not found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_create_hire_request_project_org_mismatch(
        self, mock_db, mock_user, mock_project, mock_background_tasks, valid_hire_request
    ):
        """Test that PermissionDeniedError is raised when project doesn't belong to org."""
        project, _ = mock_project
        different_org_id = uuid4()

        _setup_db_execute_mock(mock_db, mock_user, project)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)

            with pytest.raises(PermissionDeniedError) as exc_info:
                await service.create_hire_request(
                    request_data=valid_hire_request,
                    user_id=mock_user.id,
                    project_id=project.id,
                    organization_id=different_org_id,
                    background_tasks=mock_background_tasks,
                )

            assert "doesn't belong to the specified organization" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_create_hire_request_db_commit_failure(
        self, mock_db, mock_user, mock_project, mock_background_tasks, valid_hire_request
    ):
        """Test handling of database commit failure."""
        project, org_id = mock_project
        _setup_db_execute_mock(mock_db, mock_user, project)
        mock_db.commit.side_effect = Exception("Database connection lost")

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)

            with pytest.raises(ProcessingError) as exc_info:
                await service.create_hire_request(
                    request_data=valid_hire_request,
                    user_id=mock_user.id,
                    project_id=project.id,
                    organization_id=org_id,
                    background_tasks=mock_background_tasks,
                )

            mock_db.rollback.assert_awaited_once()
            assert "couldn't process your hire request" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_db):
        """Test service initialization with database session."""
        service = SpecialistHireService(db=mock_db)
        assert service.db == mock_db

    @pytest.mark.asyncio
    async def test_get_project_hire_status_success(self, mock_db, mock_user, mock_project):
        """Test successful retrieval of project hire status."""
        project, org_id = mock_project

        mock_hire = MagicMock(spec=SpecialistHire)
        mock_hire.id = uuid4()
        mock_hire.project_id = project.id
        mock_hire.is_active = True

        _setup_db_execute_for_hire(mock_db, mock_user, project, mock_hire)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)
            result = await service.get_project_hire_status(
                project_id=project.id,
                user_id=mock_user.id,
                organization_id=org_id,
            )

            assert result == mock_hire

    @pytest.mark.asyncio
    async def test_get_project_hire_status_not_found(self, mock_db, mock_user, mock_project):
        """Test retrieval when no active hire exists."""
        project, org_id = mock_project

        _setup_db_execute_for_hire(mock_db, mock_user, project, None)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)
            result = await service.get_project_hire_status(
                project_id=project.id,
                user_id=mock_user.id,
                organization_id=org_id,
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_deactivate_hire_success(self, mock_db, mock_user, mock_project):
        """Test successful deactivation of a specialist hire."""
        project, org_id = mock_project

        mock_hire = MagicMock(spec=SpecialistHire)
        mock_hire.id = uuid4()
        mock_hire.project_id = project.id
        mock_hire.is_active = True

        _setup_db_execute_for_hire(mock_db, mock_user, project, mock_hire)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)
            result = await service.deactivate_hire(
                project_id=project.id,
                user_id=mock_user.id,
                organization_id=org_id,
            )

            assert result == mock_hire
            assert mock_hire.is_active is False
            assert mock_hire.deactivated_at is not None
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deactivate_hire_not_found(self, mock_db, mock_user, mock_project):
        """Test deactivation when no active hire exists."""
        project, org_id = mock_project

        _setup_db_execute_for_hire(mock_db, mock_user, project, None)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            service = SpecialistHireService(db=mock_db)

            with pytest.raises(NotFoundError) as exc_info:
                await service.deactivate_hire(
                    project_id=project.id,
                    user_id=mock_user.id,
                    organization_id=org_id,
                )

            assert "No active specialist hire found" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_create_hire_request_preserves_email_format(
        self, mock_db, mock_user, mock_project, mock_background_tasks
    ):
        """Test that email addresses are preserved correctly."""
        project, org_id = mock_project
        request = SpecialistHireRequest(
            company_name="Test Corp",
            company_email="Test.User+tag@Example.COM",
            industry="Finance",
            brief_description="Test description",
        )

        _setup_db_execute_mock(mock_db, mock_user, project)

        with patch(
            "app.api.modules.v1.hire_specialists.service.specialists_service.TenantGuard"
        ) as mock_tenant_guard:
            mock_tenant_instance = mock_tenant_guard.return_value
            mock_tenant_instance.get_membership = AsyncMock()

            with patch(
                "app.api.modules.v1.hire_specialists.service.specialists_service.SpecialistHireService._handle_notifications",
                new_callable=AsyncMock,
            ):
                service = SpecialistHireService(db=mock_db)
                await service.create_hire_request(
                    request_data=request,
                    user_id=mock_user.id,
                    project_id=project.id,
                    organization_id=org_id,
                    background_tasks=mock_background_tasks,
                )

                added_hire = mock_db.add.call_args[0][0]
                assert "example.com" in added_hire.company_email.lower()
