import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.hire_specialists.routes.specialist_routes import (
    deactivate_specialist_hire,
    get_project_hire_status,
    hire_specialist,
)
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import SpecialistHireRequest
from app.api.modules.v1.users.models.users_model import User


@pytest.mark.asyncio
async def test_hire_specialist_success():
    """
    Test the successful creation of a specialist hire request.

    Creates a mock SpecialistHireRequest and a mocked service,
    then calls the hire_specialist endpoint and asserts that the response
    contains the correct success status and data.
    """
    request_data = SpecialistHireRequest(
        company_name="TechCorp Solutions",
        company_email="contact@techcorp.com",
        industry="Immigration & Global Mobility",
        brief_description="We need assistance with EU travel compliance monitoring",
    )

    mock_db = AsyncMock()
    mock_user = User(id=UUID("123e4567-e89b-12d3-a456-426614174001"), email="test@example.com")
    organization_id = UUID("123e4567-e89b-12d3-a456-426614174002")
    project_id = UUID("123e4567-e89b-12d3-a456-426614174003")
    mock_background_tasks = MagicMock()

    mock_hire_instance = SpecialistHire(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        company_name=request_data.company_name,
        company_email=request_data.company_email,
        industry=request_data.industry,
        brief_description=request_data.brief_description,
        user_id=mock_user.id,
        project_id=project_id,
    )
    from datetime import datetime

    mock_hire_instance.created_at = datetime.fromisoformat("2025-01-15T10:30:00")

    with patch(
        "app.api.modules.v1.hire_specialists.routes.specialist_routes.SpecialistHireService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.create_hire_request = AsyncMock(return_value=mock_hire_instance)

        response = await hire_specialist(
            request=request_data,
            organization_id=organization_id,
            project_id=project_id,
            background_tasks=mock_background_tasks,
            current_user=mock_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())

        assert response_data["status"] == "SUCCESS"
        assert "Specialist hired successfully" in response_data["message"]
        assert response_data["data"]["company_name"] == request_data.company_name
        assert response_data["data"]["company_email"] == request_data.company_email
        assert response_data["data"]["industry"] == request_data.industry
        assert "id" in response_data["data"]
        assert "created_at" in response_data["data"]

        mock_service_class.assert_called_once_with(mock_db)

        mock_service.create_hire_request.assert_called_once_with(
            request_data=request_data,
            user_id=mock_user.id,
            project_id=project_id,
            organization_id=organization_id,
            background_tasks=mock_background_tasks,
        )


@pytest.mark.asyncio
async def test_hire_specialist_failure():
    """
    Test the failure case when the service raises a ProcessingError.

    Uses a mock SpecialistHireRequest and a mocked service that
    raises ProcessingError. Asserts that the ProcessingError is raised
    (which will be caught by a global exception handler in production).
    """
    request_data = SpecialistHireRequest(
        company_name="FailCorp",
        company_email="fail@corp.com",
        industry="Test Industry",
        brief_description="This will fail",
    )

    mock_db = AsyncMock()
    mock_user = User(id=UUID("123e4567-e89b-12d3-a456-426614174001"), email="test@example.com")
    organization_id = UUID("123e4567-e89b-12d3-a456-426614174002")
    project_id = UUID("123e4567-e89b-12d3-a456-426614174003")
    mock_background_tasks = MagicMock()

    with patch(
        "app.api.modules.v1.hire_specialists.routes.specialist_routes.SpecialistHireService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.create_hire_request = AsyncMock(
            side_effect=ProcessingError(
                message="We couldn't process your hire request at the moment."
            )
        )

        with pytest.raises(ProcessingError) as exc_info:
            await hire_specialist(
                request=request_data,
                organization_id=organization_id,
                project_id=project_id,
                background_tasks=mock_background_tasks,
                current_user=mock_user,
                db=mock_db,
            )

        assert "hire request" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_project_hire_status_found():
    """
    Test getting hire status when an active hire exists.
    """
    from datetime import datetime

    mock_db = AsyncMock()
    mock_user = User(id=UUID("123e4567-e89b-12d3-a456-426614174001"), email="test@example.com")
    organization_id = UUID("123e4567-e89b-12d3-a456-426614174002")
    project_id = UUID("123e4567-e89b-12d3-a456-426614174003")

    mock_hire = SpecialistHire(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        company_name="Test Corp",
        company_email="test@corp.com",
        industry="Tech",
        brief_description="Test",
        user_id=mock_user.id,
        project_id=project_id,
        is_active=True,
    )
    mock_hire.created_at = datetime.fromisoformat("2025-01-15T10:30:00")

    with patch(
        "app.api.modules.v1.hire_specialists.routes.specialist_routes.SpecialistHireService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.get_project_hire_status = AsyncMock(return_value=mock_hire)

        response = await get_project_hire_status(
            project_id=project_id,
            organization_id=organization_id,
            current_user=mock_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())

        assert response_data["status"] == "SUCCESS"
        assert "Active specialist hire found" in response_data["message"]
        assert response_data["data"]["company_name"] == "Test Corp"
        assert response_data["data"]["is_active"] is True

        mock_service.get_project_hire_status.assert_called_once_with(
            project_id=project_id,
            user_id=mock_user.id,
            organization_id=organization_id,
        )


@pytest.mark.asyncio
async def test_get_project_hire_status_not_found():
    """
    Test getting hire status when no active hire exists.
    """
    mock_db = AsyncMock()
    mock_user = User(id=UUID("123e4567-e89b-12d3-a456-426614174001"), email="test@example.com")
    organization_id = UUID("123e4567-e89b-12d3-a456-426614174002")
    project_id = UUID("123e4567-e89b-12d3-a456-426614174003")

    with patch(
        "app.api.modules.v1.hire_specialists.routes.specialist_routes.SpecialistHireService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.get_project_hire_status = AsyncMock(return_value=None)

        response = await get_project_hire_status(
            project_id=project_id,
            organization_id=organization_id,
            current_user=mock_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())

        assert response_data["status"] == "SUCCESS"
        assert "No active specialist hire" in response_data["message"]
        assert response_data["data"] == {}


@pytest.mark.asyncio
async def test_deactivate_specialist_hire_success():
    """
    Test successful deactivation of a specialist hire.
    """
    from datetime import datetime

    mock_db = AsyncMock()
    mock_user = User(id=UUID("123e4567-e89b-12d3-a456-426614174001"), email="test@example.com")
    organization_id = UUID("123e4567-e89b-12d3-a456-426614174002")
    project_id = UUID("123e4567-e89b-12d3-a456-426614174003")

    mock_hire = SpecialistHire(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        company_name="Test Corp",
        company_email="test@corp.com",
        industry="Tech",
        brief_description="Test",
        user_id=mock_user.id,
        project_id=project_id,
        is_active=False,
    )
    mock_hire.deactivated_at = datetime.fromisoformat("2025-01-15T12:00:00")

    with patch(
        "app.api.modules.v1.hire_specialists.routes.specialist_routes.SpecialistHireService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.deactivate_hire = AsyncMock(return_value=mock_hire)

        response = await deactivate_specialist_hire(
            project_id=project_id,
            organization_id=organization_id,
            current_user=mock_user,
            db=mock_db,
        )

        response_data = json.loads(response.body.decode())

        assert response_data["status"] == "SUCCESS"
        assert "deactivated successfully" in response_data["message"]
        assert response_data["data"]["is_active"] is False
        assert response_data["data"]["deactivated_at"] is not None

        mock_service.deactivate_hire.assert_called_once_with(
            project_id=project_id,
            user_id=mock_user.id,
            organization_id=organization_id,
        )
