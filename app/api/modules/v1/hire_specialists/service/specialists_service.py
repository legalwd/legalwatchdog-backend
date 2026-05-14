import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
    UserNotInOrganizationError,
)
from app.api.core.dependencies.auth import TenantGuard
from app.api.modules.v1.hire_specialists.models.specialist_models import SpecialistHire
from app.api.modules.v1.hire_specialists.schemas.specialist_schemas import SpecialistHireRequest
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.users.models.users_model import User

logger = logging.getLogger(__name__)


class SpecialistHireService:
    """
    Service class for specialist hire-related business logic operations.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the SpecialistHireService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def _validate_user_and_project(
        self, user_id: UUID, project_id: UUID, organization_id: UUID
    ) -> tuple[User, Project]:
        """
        Validate user exists, is member of organization, and project exists and belongs to org.

        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            organization_id: UUID of the organization

        Returns:
            Tuple of (User, Project)

        Raises:
            NotFoundError: If user or project not found
            UserNotInOrganizationError: If user is not a member of the organization
            PermissionDeniedError: If project doesn't belong to the organization
        """
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        current_user = user_result.scalar_one_or_none()

        if not current_user:
            logger.warning(f"User not found: user_id={user_id}")
            raise NotFoundError(message="User not found.")

        tenant = TenantGuard(self.db, current_user)
        await tenant.get_membership(organization_id)

        project_result = await self.db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        if not project:
            logger.warning(f"Project not found: project_id={project_id}")
            raise NotFoundError(message="Project not found.")

        if project.org_id != organization_id:
            logger.warning(
                f"Project organization mismatch: project_id={project_id}, "
                f"project_org_id={project.org_id}, expected_org_id={organization_id}"
            )
            raise PermissionDeniedError(
                message="This project doesn't belong to the specified organization."
            )

        return current_user, project

    async def create_hire_request(
        self,
        request_data: SpecialistHireRequest,
        user_id: UUID,
        project_id: UUID,
        organization_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> SpecialistHire:
        """
        Create a new specialist hire request.

        Args:
            request_data: Specialist hire request data containing company information
                and specialist requirements
            user_id: ID of the current authenticated user
            project_id: ID of the project
            organization_id: ID of the organization
            background_tasks: FastAPI background tasks handler

        Returns:
            Created SpecialistHire object

        Raises:
            NotFoundError: If user or project is not found
            UserNotInOrganizationError: If user is not a member of the organization
            PermissionDeniedError: If project doesn't belong to the organization
            ProcessingError: If hire request creation fails
        """
        try:
            logger.info(f"Processing hire request for company: {request_data.company_name}")

            current_user, project = await self._validate_user_and_project(
                user_id, project_id, organization_id
            )

            new_hire = SpecialistHire(
                company_name=request_data.company_name,
                company_email=request_data.company_email,
                industry=request_data.industry,
                brief_description=request_data.brief_description,
                project_id=project.id,
                jurisdiction_id=request_data.jurisdiction_id,
                user_id=current_user.id,
            )

            self.db.add(new_hire)
            await self.db.commit()
            await self.db.refresh(new_hire)

            logger.info(
                f"Specialist hire request successfully created: "
                f"id={new_hire.id}, company={new_hire.company_name}"
            )

            await self._handle_notifications(new_hire, current_user, project, background_tasks)

            return new_hire

        except (NotFoundError, UserNotInOrganizationError, PermissionDeniedError, ProcessingError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Failed to create hire request: {str(e)}")
            raise ProcessingError(
                message=(
                    "We couldn't process your hire request at the moment. "
                    "Please try again or contact support if the problem persists."
                )
            )

    async def _handle_notifications(
        self,
        hire: SpecialistHire,
        user: User,
        project: Project,
        background_tasks: BackgroundTasks,
    ) -> None:
        """
        Handle all notifications for the specialist hire request.

        Args:
            hire: Created SpecialistHire object
            user: User who made the request
            project: Project associated with the hire
            background_tasks: FastAPI background tasks handler

        Raises:
            ProcessingError: If notification handling fails critically
        """
        from app.api.modules.v1.notifications.service.specialist_notification_task import (
            create_specialist_hire_notification,
            send_specialist_request_notifications_background,
        )

        try:
            await create_specialist_hire_notification(
                db_session=self.db,
                hire_id=hire.id,
                company_name=hire.company_name,
                user_id=user.id,
                project_id=project.id,
                org_id=project.org_id,
            )

            background_tasks.add_task(
                send_specialist_request_notifications_background,
                hire_id=str(hire.id),
                company_name=hire.company_name,
                company_email=hire.company_email,
                industry=hire.industry,
                brief_description=hire.brief_description,
                user_email=user.email,
                created_at=hire.created_at,
            )
            logger.info(f"Notifications handled for hire {hire.id}")

        except ProcessingError:
            raise
        except Exception as e:
            logger.exception(f"Failed to handle notifications for hire {hire.id}: {str(e)}")
            raise ProcessingError(message="Hire request created but notification setup failed.")

    async def get_project_hire_status(
        self, project_id: UUID, user_id: UUID, organization_id: UUID
    ) -> Optional[SpecialistHire]:
        """
        Get active specialist hire for a project.

        Args:
            project_id: UUID of the project
            user_id: ID of the current authenticated user
            organization_id: ID of the organization

        Returns:
            SpecialistHire object if active hire exists, None otherwise

        Raises:
            NotFoundError: If user or project is not found
            UserNotInOrganizationError: If user is not a member of the organization
            PermissionDeniedError: If project doesn't belong to the organization
            ProcessingError: If fetching hire status fails
        """
        try:
            logger.info(f"Fetching specialist hire status for project: {project_id}")

            await self._validate_user_and_project(user_id, project_id, organization_id)

            query = select(SpecialistHire).where(
                SpecialistHire.project_id == project_id, SpecialistHire.is_active
            )
            result = await self.db.execute(query)
            hire = result.scalar_one_or_none()

            if hire:
                logger.info(f"Active specialist hire found for project {project_id}: {hire.id}")
            else:
                logger.info(f"No active specialist hire found for project {project_id}")

            return hire

        except (NotFoundError, UserNotInOrganizationError, PermissionDeniedError):
            raise
        except Exception as e:
            logger.exception(f"Failed to fetch hire status for project {project_id}: {str(e)}")
            raise ProcessingError(
                message="We couldn't fetch the specialist hire status. Please try again."
            )

    async def deactivate_hire(
        self, project_id: UUID, user_id: UUID, organization_id: UUID
    ) -> SpecialistHire:
        """
        Deactivate an active specialist hire for a project.

        Args:
            project_id: UUID of the project
            user_id: ID of the current authenticated user
            organization_id: ID of the organization

        Returns:
            Deactivated SpecialistHire object

        Raises:
            NotFoundError: If user, project, or active hire is not found
            UserNotInOrganizationError: If user is not a member of the organization
            PermissionDeniedError: If project doesn't belong to the organization
            ProcessingError: If deactivation fails
        """
        try:
            logger.info(f"Deactivating specialist hire for project: {project_id}")

            await self._validate_user_and_project(user_id, project_id, organization_id)

            query = select(SpecialistHire).where(
                SpecialistHire.project_id == project_id, SpecialistHire.is_active
            )
            result = await self.db.execute(query)
            hire = result.scalar_one_or_none()

            if not hire:
                logger.warning(f"No active specialist hire found for project {project_id}")
                raise NotFoundError(message="No active specialist hire found for this project.")

            hire.is_active = False
            hire.deactivated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            await self.db.commit()
            await self.db.refresh(hire)

            logger.info(
                f"Specialist hire deactivated successfully: id={hire.id}, project={project_id}"
            )

            return hire

        except (NotFoundError, UserNotInOrganizationError, PermissionDeniedError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Failed to deactivate hire for project {project_id}: {str(e)}")
            raise ProcessingError(
                message="We couldn't deactivate the specialist hire. Please try again."
            )
