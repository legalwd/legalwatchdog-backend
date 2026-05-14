import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import (
    SpecialistHireRequest,
    SpecialistHireResponse,
)
from app.api.modules.v1.hire_specialists.service.specialists_service import SpecialistHireService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.specialist_routes_docs import (
    deactivate_hire_custom_errors,
    deactivate_hire_custom_success,
    deactivate_hire_responses,
    get_hire_status_custom_errors,
    get_hire_status_custom_success,
    get_hire_status_responses,
    hire_specialist_custom_errors,
    hire_specialist_custom_success,
    hire_specialist_responses,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organizations/{organization_id}/projects/{project_id}/specialists",
    tags=["Specialists"],
)


@router.post(
    "/hire-requests",
    response_model=SpecialistHireResponse,
    status_code=status.HTTP_201_CREATED,
    responses=hire_specialist_responses,
)
async def hire_specialist(
    request: SpecialistHireRequest,
    organization_id: UUID,
    project_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new specialist hire request.

    Accepts company information and specialist requirements,
    stores them in the database, sends notifications, and returns a success confirmation.

    Args:
        request: Specialist hire request data containing:
            - company_name (str): Name of the company
            - company_email (str): Contact email for the company
            - industry (str): Industry sector
            - brief_description (str): Brief description of specialist requirements
        organization_id: UUID of the organization
        project_id: UUID of the project
        background_tasks: FastAPI background tasks handler
        current_user: Currently authenticated user
        db: Database session dependency

    Returns:
        SpecialistHireResponse with success message and hire details

    Raises:
        HTTPException:
            - 403 Forbidden if user doesn't have access to the organization
            - 500 Internal Server Error if hire request creation fails
    """
    logger.info(
        f"Received hire request for company: {request.company_name}, "
        f"project: {project_id}, org: {organization_id}"
    )

    service = SpecialistHireService(db)
    hire_record = await service.create_hire_request(
        request_data=request,
        user_id=current_user.id,
        project_id=project_id,
        organization_id=organization_id,
        background_tasks=background_tasks,
    )

    logger.info(
        f"Hire request processed successfully: id={hire_record.id}, "
        f"company={hire_record.company_name}"
    )

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message="Specialist hired successfully. A specialist will be sent to you shortly",
        data={
            "id": hire_record.id,
            "company_name": hire_record.company_name,
            "company_email": hire_record.company_email,
            "industry": hire_record.industry,
            "brief_description": hire_record.brief_description,
            "created_at": hire_record.created_at.isoformat(),
        },
    )


hire_specialist._custom_errors = hire_specialist_custom_errors
hire_specialist._custom_success = hire_specialist_custom_success


@router.get(
    "/hire-status",
    response_model=SpecialistHireResponse,
    status_code=status.HTTP_200_OK,
    responses=get_hire_status_responses,
)
async def get_project_hire_status(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the active specialist hire status for a specific project.

    Returns the hire details if an active specialist hire exists for the project,
    or a message indicating no active hire exists.

    Args:
        project_id: UUID of the project to check
        organization_id: UUID of the organization
        current_user: Currently authenticated user
        db: Database session dependency

    Returns:
        SpecialistHireResponse with hire details or null data if no active hire

    Raises:
        HTTPException:
            - 403 Forbidden if user doesn't have access to the organization
            - 500 Internal Server Error if status check fails
    """
    logger.info(f"Checking hire status for project: {project_id}, org: {organization_id}")

    service = SpecialistHireService(db)
    hire = await service.get_project_hire_status(
        project_id=project_id,
        user_id=current_user.id,
        organization_id=organization_id,
    )

    if hire:
        logger.info(f"Active hire found for project {project_id}: {hire.id}")
        return success_response(
            status_code=status.HTTP_200_OK,
            message="Active specialist hire found",
            data={
                "id": hire.id,
                "company_name": hire.company_name,
                "company_email": hire.company_email,
                "industry": hire.industry,
                "brief_description": hire.brief_description,
                "created_at": hire.created_at.isoformat(),
                "is_active": hire.is_active,
            },
        )
    else:
        logger.info(f"No active hire found for project {project_id}")
        return success_response(
            status_code=status.HTTP_200_OK,
            message="No active specialist hire for this project",
            data=None,
        )


get_project_hire_status._custom_errors = get_hire_status_custom_errors
get_project_hire_status._custom_success = get_hire_status_custom_success


@router.patch(
    "/deactivate",
    response_model=SpecialistHireResponse,
    status_code=status.HTTP_200_OK,
    responses=deactivate_hire_responses,
)
async def deactivate_specialist_hire(
    project_id: UUID,
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate an active specialist hire for a project.

    Marks the specialist hire as inactive and records the deactivation timestamp.

    Args:
        project_id: UUID of the project
        organization_id: UUID of the organization
        current_user: Currently authenticated user
        db: Database session dependency

    Returns:
        SpecialistHireResponse with deactivation confirmation

    Raises:
        HTTPException:
            - 403 Forbidden if user doesn't have access to the organization
            - 404 Not Found if no active hire exists for the project
            - 500 Internal Server Error if deactivation fails
    """
    logger.info(f"Deactivating specialist hire for project: {project_id}, org: {organization_id}")

    service = SpecialistHireService(db)
    hire = await service.deactivate_hire(
        project_id=project_id,
        user_id=current_user.id,
        organization_id=organization_id,
    )

    logger.info(f"Specialist hire deactivated successfully: id={hire.id}, project={project_id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Specialist hire deactivated successfully",
        data={
            "id": hire.id,
            "company_name": hire.company_name,
            "is_active": hire.is_active,
            "deactivated_at": hire.deactivated_at.isoformat() if hire.deactivated_at else None,
        },
    )


deactivate_specialist_hire._custom_errors = deactivate_hire_custom_errors
deactivate_specialist_hire._custom_success = deactivate_hire_custom_success
