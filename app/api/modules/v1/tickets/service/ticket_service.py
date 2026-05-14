import logging
from typing import Optional, Union
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import desc, select

from app.api.core.custom_exceptions.exceptions import (
    ChangeAlreadyHasTicketError,
    ForbiddenError,
    JurisdictionChangeNotFoundError,
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
    ValidationError,
)
from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.organization.models.organization_model import Organization
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_model import Project
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.projects.utils.project_utils import (
    check_project_user_exists,
)
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.jurisdiction_change import JurisdictionChange
from app.api.modules.v1.scraping.models.jurisdiction_scrape_job import JurisdictionScrapeJob
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.modules.v1.tickets.models.ticket_model import (
    InternalParticipant,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.api.modules.v1.tickets.schemas.comment_schemas import CommentResponse
from app.api.modules.v1.tickets.schemas.ticket_schema import TicketCreate
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class TicketService:
    """
    Service class for ticket-related business logic operations.

    This class encapsulates all ticket operations including creation,
    retrieval, updates, assignment, and user invitation.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    def _serialize_ticket_with_comments(self, ticket: Ticket, comments: list) -> dict:
        """
        Serialize a ticket with its comments into API response format.

        This method handles the transformation of SQLAlchemy models into
        a dictionary suitable for JSON serialization, including proper
        comment author resolution.

        Args:
            ticket: The Ticket object to serialize
            comments: List of Comment objects to include

        Returns:
            dict: Serialized ticket data with formatted comments
        """
        ticket_dict = jsonable_encoder(ticket)
        ticket_dict["comments"] = [
            jsonable_encoder(CommentResponse.from_comment(c)) for c in comments
        ]
        return ticket_dict

    def _infer_priority_from_confidence(self, confidence_score: Optional[float]) -> TicketPriority:
        """
        Infer ticket priority from AI confidence score.

        Priority mapping:
        - 0.85 - 1.0  → CRITICAL (very high confidence in significant change)
        - 0.6 - 0.85  → HIGH (high confidence)
        - 0.3 - 0.6   → MEDIUM (moderate confidence)
        - 0.0 - 0.3   → LOW (low confidence)
        - None        → MEDIUM (default fallback)

        Args:
            confidence_score: AI confidence score (0.0 to 1.0)

        Returns:
            TicketPriority enum value
        """
        if confidence_score is None:
            return TicketPriority.MEDIUM

        if confidence_score >= 0.85:
            return TicketPriority.CRITICAL
        elif confidence_score >= 0.6:
            return TicketPriority.HIGH
        elif confidence_score >= 0.3:
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.LOW

    async def create_manual_ticket(
        self,
        data: TicketCreate,
        user_id: UUID,
    ) -> Ticket:
        """
        Create a new manual ticket from source and revision data.

        Access Control:
        - Only users with CREATE_TICKETS permission (admins/managers/owners) can create tickets
        - Regular project members cannot create tickets

        Args:
            data: Ticket creation data (source_id, revision_id, priority)
            user_id: User UUID creating the ticket

        Returns:
            Created Ticket object with auto-populated title, description, and content

        Raises:
            NotFoundError: If source, revision, jurisdiction, or project not found
            PermissionDeniedError: If user lacks CREATE_TICKETS permission or not in organization
            ProcessingError: If an error occurs during ticket creation
        """
        try:
            is_source_level = data.source_id is not None and data.revision_id is not None
            is_jurisdiction_level = (
                data.jurisdiction_id is not None and data.jurisdiction_scrape_job_id is not None
            )

            if is_source_level and is_jurisdiction_level:
                raise ValidationError(
                    message=(
                        "Cannot create ticket with both source-level and "
                        "jurisdiction-level data. Please provide only one type."
                    )
                )

            if not is_source_level and not is_jurisdiction_level:
                raise ValidationError(
                    message=(
                        "Must provide either (source_id + revision_id) for source-level "
                        "tickets or (jurisdiction_id + jurisdiction_scrape_job_id) for "
                        "jurisdiction-level tickets."
                    )
                )

            if is_jurisdiction_level:
                return await self._create_jurisdiction_ticket(data, user_id)

            source_result = await self.db.execute(
                select(Source)
                .options(selectinload(Source.jurisdiction).selectinload(Jurisdiction.project))
                .where(Source.id == data.source_id)
            )
            source = source_result.scalar_one_or_none()

            if not source:
                logger.warning(f"Source not found: source_id={data.source_id}")
                raise NotFoundError(
                    message="The data source you're trying to reference doesn't exist. "
                    "Please select a valid source."
                )

            jurisdiction = source.jurisdiction
            if not jurisdiction:
                logger.warning(f"Jurisdiction not found for source: source_id={data.source_id}")
                raise NotFoundError(message="Jurisdiction not found for the given source")

            project = jurisdiction.project
            if not project:
                logger.warning(
                    f"Project not found for jurisdiction: jurisdiction_id={jurisdiction.id}"
                )
                raise NotFoundError(
                    message="The project you're trying to access doesn't exist or "
                    "doesn't belong to your organization."
                )

            organization_id = project.org_id
            project_id = project.id

            result = await self.db.execute(
                select(UserOrganization)
                .where(UserOrganization.user_id == user_id)
                .where(UserOrganization.organization_id == organization_id)
            )
            membership = result.scalars().first()
            if not membership:
                logger.warning(
                    f"User not in organization: user_id={user_id}, org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message=(
                        "You don't have access to this organization. "
                        "Please contact your administrator for access."
                    )
                )

            has_create_tickets_permission = await check_user_permission(
                self.db,
                user_id,
                organization_id,
                "create_tickets",
            )

            if not has_create_tickets_permission:
                logger.warning(
                    f"User lacks CREATE_TICKETS permit: user_id={user_id}, org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message=(
                        "You don't have permission to create tickets. "
                        "Only administrators, managers, and owners can create tickets. "
                        "Please contact your organization administrator."
                    )
                )

            revision_result = await self.db.execute(
                select(DataRevision).where(DataRevision.id == data.revision_id)
            )
            revision = revision_result.scalar_one_or_none()

            if not revision:
                logger.warning(f"Data revision not found: revision_id={data.revision_id}")
                raise NotFoundError(
                    message=(
                        "The data revision you're trying to reference doesn't exist. "
                        "Please select a valid revision."
                    )
                )

            if revision.source_id != source.id:
                logger.warning(
                    f"Revision source mismatch: revision_id={data.revision_id}, "
                    f"revision_source_id={revision.source_id}, expected_source_id={source.id}"
                )
                raise PermissionDeniedError(
                    message=(
                        "The revision you selected doesn't belong to the specified source. "
                        "Please ensure you're selecting the correct revision."
                    )
                )

            jurisdiction_name = jurisdiction.name if jurisdiction else "General"
            auto_title = f"[{jurisdiction_name}] {source.name} - Change Detected"
            auto_description = revision.ai_summary or "No summary available"

            auto_content = {
                "revision_summary": revision.ai_summary,
                "source_name": source.name,
                "source_url": source.url,
                "jurisdiction": jurisdiction_name,
                "scraped_at": revision.scraped_at.isoformat() if revision.scraped_at else None,
                "content_hash": revision.content_hash,
            }

            ticket_priority = data.priority
            confidence_for_priority = None
            change_diff = None

            change_diff_result = await self.db.execute(
                select(ChangeDiff).where(ChangeDiff.new_revision_id == revision.id).limit(1)
            )
            change_diff = change_diff_result.scalar_one_or_none()

            if change_diff:
                auto_content["diff_patch"] = change_diff.diff_patch
                auto_content["ai_confidence"] = change_diff.ai_confidence
                auto_content["change_diff_id"] = str(change_diff.diff_id)
                confidence_for_priority = change_diff.ai_confidence

            if ticket_priority is None:
                confidence_score = confidence_for_priority or revision.ai_confidence_score
                ticket_priority = self._infer_priority_from_confidence(confidence_score)
                auto_content["priority_inferred_from_ai"] = True
                auto_content["ai_confidence_used"] = confidence_score
                logger.info(
                    f"Priority inferred as {ticket_priority.value} "
                    f"from AI confidence: {confidence_score}"
                )
            else:
                auto_content["priority_inferred_from_ai"] = False

            logger.info(
                f"Creating ticket '{auto_title}' for user_id={user_id}, "
                f"organization_id={organization_id}, project_id={project_id}"
            )

            ticket_number_result = await self.db.execute(
                text("SELECT nextval('tickets_ticket_number_seq')")
            )
            next_ticket_number = ticket_number_result.scalar()

            ticket = Ticket(
                ticket_number=next_ticket_number,
                title=auto_title,
                description=auto_description,
                content=auto_content,
                priority=ticket_priority.value,
                status=TicketStatus.OPEN.value,
                is_manual=True,
                source_id=source.id,
                data_revision_id=revision.id,
                change_diff_id=change_diff.diff_id if change_diff else None,
                created_by_user_id=user_id,
                assigned_to_user_id=None,
                assigned_by_user_id=None,
                organization_id=organization_id,
                project_id=project_id,
            )

            self.db.add(ticket)
            await self.db.flush()
            await self.db.refresh(ticket)

            await self.db.execute(
                update(DataRevision)
                .where(DataRevision.id == revision.id)
                .values(ticket_created=True)
            )

            await self.db.commit()

            logger.info(
                f"Created ticket with id={ticket.id}, updated revision {revision.id} "
                f"ticket_created=True"
            )

            return ticket

        except (NotFoundError, PermissionDeniedError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating ticket: {str(e)}")
            raise ProcessingError(message="An error occurred while creating the ticket")

    async def get_tickets(
        self,
        user_id: UUID,
        source_id: UUID = None,
        jurisdiction_id: UUID = None,
        organization_id: UUID = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Ticket], int]:
        """
        Get paginated tickets with optional filters.

        Supports filtering by source_id, jurisdiction_id, and/or organization_id.
        At least one filter must be provided.

        Access Control:
        - Users with VIEW_TICKETS permission can view all tickets in their organization
        - Project members can view tickets in their projects
        - Others → Permission Denied

        Args:
            user_id: User UUID requesting the tickets
            source_id: Optional Source UUID to filter tickets
            jurisdiction_id: Optional Jurisdiction UUID to filter tickets
            organization_id: Optional Organization UUID to filter tickets
            page: Page number (default: 1)
            limit: Items per page (default: 20)

        Returns:
            Tuple of (List of Ticket objects, total count)

        Raises:
            NotFoundError: If referenced entities don't exist
            PermissionDeniedError: If user lacks permission
            ProcessingError: If an error occurs during ticket retrieval
        """
        try:
            if not any([source_id, jurisdiction_id, organization_id]):
                raise ValidationError(
                    message="At least one filter (source_id, jurisdiction_id, "
                    "or organization_id) must be provided"
                )

            conditions = []

            target_org_id = None
            target_project_id = None

            if source_id:
                source_result = await self.db.execute(select(Source).where(Source.id == source_id))
                source = source_result.scalar_one_or_none()

                if not source:
                    raise NotFoundError(message="Source not found")

                conditions.append(Ticket.source_id == source_id)

                jurisdiction_result = await self.db.execute(
                    select(Jurisdiction).where(Jurisdiction.id == source.jurisdiction_id)
                )
                jurisdiction = jurisdiction_result.scalar_one_or_none()

                if not jurisdiction:
                    raise NotFoundError(message="Jurisdiction not found")

                target_project_id = jurisdiction.project_id

                project_result = await self.db.execute(
                    select(Project).where(Project.id == target_project_id)
                )
                project = project_result.scalar_one_or_none()

                if not project:
                    raise NotFoundError(message="Project not found")

                target_org_id = project.org_id

            if jurisdiction_id:
                jurisdiction_result = await self.db.execute(
                    select(Jurisdiction).where(Jurisdiction.id == jurisdiction_id)
                )
                jurisdiction = jurisdiction_result.scalar_one_or_none()

                if not jurisdiction:
                    raise NotFoundError(message="Jurisdiction not found")

                source_subquery = select(Source.id).where(Source.jurisdiction_id == jurisdiction_id)
                change_subquery = (
                    select(JurisdictionChange.id)
                    .join(
                        JurisdictionScrapeJob,
                        JurisdictionChange.jurisdiction_scrape_job_id == JurisdictionScrapeJob.id,
                    )
                    .where(JurisdictionScrapeJob.jurisdiction_id == jurisdiction_id)
                )

                conditions.append(
                    or_(
                        Ticket.source_id.in_(source_subquery),
                        Ticket.jurisdiction_change_id.in_(change_subquery),
                    )
                )

                if not target_org_id:
                    target_project_id = jurisdiction.project_id

                    project_result = await self.db.execute(
                        select(Project).where(Project.id == target_project_id)
                    )
                    project = project_result.scalar_one_or_none()

                    if not project:
                        raise NotFoundError(message="Project not found")

                    target_org_id = project.org_id

            if organization_id:
                org_result = await self.db.execute(
                    select(Organization).where(Organization.id == organization_id)
                )
                organization = org_result.scalar_one_or_none()

                if not organization:
                    raise NotFoundError(message="Organization not found")

                conditions.append(Ticket.organization_id == organization_id)

                if not target_org_id:
                    target_org_id = organization_id

            has_view_tickets_permission = await check_user_permission(
                self.db,
                user_id,
                target_org_id,
                "view_tickets",
            )

            if not has_view_tickets_permission:
                if target_project_id:
                    is_project_member = await check_project_user_exists(
                        self.db, target_project_id, user_id
                    )
                    if not is_project_member:
                        raise PermissionDeniedError(
                            message="You don't have permission to view these tickets"
                        )
                else:
                    org_membership_result = await self.db.execute(
                        select(UserOrganization).where(
                            and_(
                                UserOrganization.user_id == user_id,
                                UserOrganization.organization_id == target_org_id,
                            )
                        )
                    )
                    if not org_membership_result.scalar_one_or_none():
                        raise PermissionDeniedError(
                            message="You don't have permission to view these tickets"
                        )

                    user_projects_result = await self.db.execute(
                        select(Project.id)
                        .join(ProjectUser, ProjectUser.project_id == Project.id)
                        .where(
                            and_(
                                ProjectUser.user_id == user_id,
                                Project.org_id == target_org_id,
                            )
                        )
                    )
                    user_project_ids = [p[0] for p in user_projects_result.all()]

                    if not user_project_ids:
                        return [], 0

                    conditions.append(Ticket.project_id.in_(user_project_ids))

            count_statement = select(func.count()).select_from(Ticket).where(and_(*conditions))
            count_result = await self.db.execute(count_statement)
            total = count_result.scalar()

            offset = (page - 1) * limit

            statement = (
                select(Ticket)
                .where(and_(*conditions))
                .options(
                    selectinload(Ticket.created_by_user),
                    selectinload(Ticket.assigned_by_user),
                    selectinload(Ticket.assigned_to_user),
                    selectinload(Ticket.external_participants),
                )
                .order_by(desc(Ticket.created_at))
                .offset(offset)
                .limit(limit)
            )

            result = await self.db.execute(statement)
            tickets = result.scalars().all()

            return tickets, total

        except (NotFoundError, PermissionDeniedError, ValidationError):
            raise
        except Exception as e:
            logger.exception(f"Error fetching tickets: {str(e)}")
            raise ProcessingError(message="An error occurred while fetching tickets")

    async def get_ticket_by_id(
        self,
        ticket_id: UUID,
        user_or_guest: Union[User, GuestContext],
    ) -> dict:
        """
        Get detailed ticket information by ID.

        Access Control:
        - External participants (guests): Already validated by token, can view their ticket
        - Regular users with VIEW_TICKETS permission (admins/managers/owners): Can view all tickets
        - Regular users: Must be either:
          1. Member of the project, OR
          2. Internal participant of the ticket
        - Users in org but not in project/participants/permission: Permission Denied
        - Users not in org: Forbidden

        Args:
            ticket_id: Ticket UUID
            user_or_guest: Either a User object or GuestContext

        Returns:
            dict: Serialized ticket data with formatted comments

        Raises:
            NotFoundError: If ticket not found
            PermissionDeniedError: If user lacks access
            ForbiddenError: If user not in organization
            ProcessingError: If an error occurs during ticket retrieval
        """
        try:
            statement = (
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .options(
                    selectinload(Ticket.created_by_user),
                    selectinload(Ticket.assigned_by_user),
                    selectinload(Ticket.assigned_to_user),
                    selectinload(Ticket.external_participants),
                    selectinload(Ticket.internal_participants),
                    selectinload(Ticket.source),
                    selectinload(Ticket.data_revision),
                    selectinload(Ticket.change_diff),
                    selectinload(Ticket.organization),
                    selectinload(Ticket.project),
                    selectinload(Ticket.comments),
                )
            )

            result = await self.db.execute(statement)
            ticket = result.scalar_one_or_none()

            if not ticket:
                logger.warning(f"Ticket not found: ticket_id={ticket_id}")
                raise NotFoundError(message="Ticket not found")

            all_comments = ticket.comments or []
            sorted_comments = sorted(
                [c for c in all_comments if c.deleted_at is None],
                key=lambda c: c.created_at,
                reverse=True,
            )[:20]

            organization_id = ticket.organization_id
            project_id = ticket.project_id

            if isinstance(user_or_guest, GuestContext):
                if user_or_guest.ticket_id != ticket_id:
                    logger.warning(
                        f"Guest ticket mismatch expected {ticket_id}, got {user_or_guest.ticket_id}"
                    )
                    raise PermissionDeniedError(
                        message="You don't have permission to view this ticket."
                    )

                logger.info(f"Guest {user_or_guest.email} accessing ticket {ticket_id}")
                return self._serialize_ticket_with_comments(ticket, sorted_comments)

            else:
                current_user = user_or_guest
                current_user_id = current_user.id

                org_membership_stmt = select(UserOrganization).where(
                    and_(
                        UserOrganization.user_id == current_user_id,
                        UserOrganization.organization_id == organization_id,
                        UserOrganization.is_active,
                        UserOrganization.is_deleted.is_(False),
                    )
                )
                org_membership_result = await self.db.execute(org_membership_stmt)
                org_membership = org_membership_result.scalar_one_or_none()

                if not org_membership:
                    logger.warning(f"User {current_user_id} not in organization {organization_id}")
                    raise ForbiddenError(message="You don't have access to this organization.")

                has_view_tickets_permission = await check_user_permission(
                    self.db,
                    current_user_id,
                    organization_id,
                    "view_tickets",
                )

                if has_view_tickets_permission:
                    logger.info(
                        f"User {current_user_id} accessing ticket {ticket_id} "
                        f"(has view_tickets permission)"
                    )
                    return self._serialize_ticket_with_comments(ticket, sorted_comments)

                project_membership_stmt = select(ProjectUser).where(
                    and_(
                        ProjectUser.user_id == current_user_id,
                        ProjectUser.project_id == project_id,
                    )
                )
                project_membership_result = await self.db.execute(project_membership_stmt)
                is_in_project = project_membership_result.scalar_one_or_none() is not None

                internal_participant_stmt = select(InternalParticipant).where(
                    and_(
                        InternalParticipant.user_id == current_user_id,
                        InternalParticipant.ticket_id == ticket_id,
                        InternalParticipant.is_active,
                    )
                )
                internal_participant_result = await self.db.execute(internal_participant_stmt)
                is_internal_participant = (
                    internal_participant_result.scalar_one_or_none() is not None
                )

                if not is_in_project and not is_internal_participant:
                    logger.warning(
                        f"User {current_user_id} in org but not in project {project_id} "
                        f"and not a participant of ticket {ticket_id}"
                    )
                    raise PermissionDeniedError(
                        message=(
                            "You don't have permission to view this ticket. "
                            "Only project members and ticket participants can view this information"
                        )
                    )

                logger.info(
                    f"User {current_user_id} accessing ticket {ticket_id} "
                    f"(in_project={is_in_project}, "
                    f"is_internal_participant={is_internal_participant})"
                )
                return self._serialize_ticket_with_comments(ticket, sorted_comments)

        except (NotFoundError, PermissionDeniedError, ForbiddenError):
            raise
        except Exception as e:
            logger.exception(f"Error fetching ticket: {str(e)}")
            raise ProcessingError(message="An error occurred while fetching the ticket")

    async def _create_jurisdiction_ticket(
        self,
        data: TicketCreate,
        user_id: UUID,
    ) -> Ticket:
        """Create a manual ticket for jurisdiction-level changes.

        This method handles ticket creation when users review consolidated
        jurisdiction changes and decide to create a ticket.

        Args:
            data: Ticket creation data (jurisdiction_id, jurisdiction_scrape_job_id, priority)
            user_id: User UUID creating the ticket

        Returns:
            Created Ticket object

        Raises:
            NotFoundError: If jurisdiction, job, or project not found
            PermissionDeniedError: If user lacks CREATE_TICKETS permission
            ProcessingError: If an error occurs during ticket creation
        """
        try:
            jurisdiction_result = await self.db.execute(
                select(Jurisdiction)
                .options(selectinload(Jurisdiction.project))
                .where(Jurisdiction.id == data.jurisdiction_id)
            )
            jurisdiction = jurisdiction_result.scalar_one_or_none()

            if not jurisdiction:
                logger.warning(f"Jurisdiction not found: jurisdiction_id={data.jurisdiction_id}")
                raise NotFoundError(message="Jurisdiction not found")

            project = jurisdiction.project
            if not project:
                logger.warning(
                    f"Project not found for jurisdiction: jurisdiction_id={jurisdiction.id}"
                )
                raise NotFoundError(message="Project not found for the jurisdiction")

            organization_id = project.org_id
            project_id = project.id

            org_membership_result = await self.db.execute(
                select(UserOrganization).where(
                    UserOrganization.user_id == user_id,
                    UserOrganization.organization_id == organization_id,
                )
            )
            if not org_membership_result.scalar_one_or_none():
                logger.warning(
                    f"User not in organization: user_id={user_id}, org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message="You don't have access to this organization. "
                    "Please contact your administrator for access."
                )

            has_create_tickets_permission = await check_user_permission(
                self.db, user_id, organization_id, "create_tickets"
            )
            if not has_create_tickets_permission:
                logger.warning(
                    f"User lacks CREATE_TICKETS: user_id={user_id}, org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message="You don't have permission to create tickets. "
                    "Only administrators, managers, and owners can create tickets. "
                    "Please contact your organization administrator."
                )

            job_result = await self.db.execute(
                select(JurisdictionScrapeJob).where(
                    JurisdictionScrapeJob.id == data.jurisdiction_scrape_job_id
                )
            )
            job = job_result.scalar_one_or_none()

            if not job:
                logger.warning(
                    f"Jurisdiction scrape job not found: job_id={data.jurisdiction_scrape_job_id}"
                )
                raise NotFoundError(message="Jurisdiction scrape job not found")

            if job.jurisdiction_id != jurisdiction.id:
                logger.warning(
                    f"Job jurisdiction mismatch: job_id={job.id}, "
                    f"job_jurisdiction_id={job.jurisdiction_id}, "
                    f"expected_jurisdiction_id={jurisdiction.id}"
                )
                raise PermissionDeniedError(
                    message="The scrape job doesn't belong to the specified jurisdiction"
                )

            jurisdiction_change = None
            if data.jurisdiction_change_id:
                jurisdiction_change = await self.db.get(
                    JurisdictionChange, data.jurisdiction_change_id
                )

                if not jurisdiction_change:
                    raise JurisdictionChangeNotFoundError()

                if jurisdiction_change.jurisdiction_scrape_job_id != job.id:
                    raise PermissionDeniedError(
                        message="This change doesn't belong to the specified job"
                    )
                if jurisdiction_change.ticket_created:
                    raise ChangeAlreadyHasTicketError()

                display_name = self._extract_display_name_from_description(
                    jurisdiction_change.change_description
                )

                auto_title = f"[{jurisdiction.name}] {display_name} Change"

                auto_description = jurisdiction_change.change_description

                auto_content = {
                    "jurisdiction_name": jurisdiction.name,
                    "jurisdiction_id": str(jurisdiction.id),
                    "job_id": str(job.id),
                    "change_id": str(jurisdiction_change.id),
                    "field_name": jurisdiction_change.field_name,
                    "display_name": display_name,
                    "old_value": jurisdiction_change.old_value,
                    "new_value": jurisdiction_change.new_value,
                    "change_description": jurisdiction_change.change_description,
                    "scraped_at": job.completed_at.isoformat() if job.completed_at else None,
                }
                changes = [auto_content]
            else:
                extracted_data = job.extracted_data or {}
                summary = extracted_data.get("summary", "Changes detected")
                markdown_summary = extracted_data.get("markdown_summary", "")
                changes = extracted_data.get("changes", [])

                auto_title = f"[{jurisdiction.name}] Jurisdiction Update - {len(changes)} Changes"
                auto_description = (
                    f"{summary}\n\n{markdown_summary}" if markdown_summary else summary
                )

                auto_content = {
                    "jurisdiction_name": jurisdiction.name,
                    "jurisdiction_id": str(jurisdiction.id),
                    "job_id": str(job.id),
                    "sources_scraped": job.total_sources,
                    "relevant_sources": job.filtered_sources,
                    "changes": changes,
                    "extracted_data": extracted_data,
                    "scraped_at": (job.completed_at.isoformat() if job.completed_at else None),
                }

            if data.priority is None:
                if len(changes) >= 10:
                    ticket_priority = TicketPriority.HIGH
                elif len(changes) >= 5:
                    ticket_priority = TicketPriority.MEDIUM
                else:
                    ticket_priority = TicketPriority.LOW
                auto_content["priority_inferred_from_changes"] = True
            else:
                ticket_priority = data.priority
                auto_content["priority_inferred_from_changes"] = False

            logger.info(
                f"Creating jurisdiction ticket '{auto_title}' for user_id={user_id}, "
                f"organization_id={organization_id}, project_id={project_id}"
            )

            ticket_number_result = await self.db.execute(
                text("SELECT nextval('tickets_ticket_number_seq')")
            )
            next_ticket_number = ticket_number_result.scalar()

            ticket = Ticket(
                ticket_number=next_ticket_number,
                title=auto_title,
                description=auto_description,
                content=auto_content,
                priority=ticket_priority.value,
                status=TicketStatus.OPEN.value,
                is_manual=True,
                source_id=None,
                data_revision_id=None,
                change_diff_id=None,
                created_by_user_id=user_id,
                assigned_to_user_id=None,
                assigned_by_user_id=None,
                organization_id=organization_id,
                project_id=project_id,
                jurisdiction_change_id=data.jurisdiction_change_id,
            )

            self.db.add(ticket)
            await self.db.flush()
            await self.db.refresh(ticket)

            if jurisdiction_change:
                jurisdiction_change.ticket_created = True
                self.db.add(jurisdiction_change)

            await self.db.commit()

            logger.info(
                f"Manual jurisdiction ticket created: ticket_id={ticket.id}, "
                f"ticket_number={ticket.ticket_number}, user_id={user_id}, "
                f"change_id={data.jurisdiction_change_id}"
            )

            return ticket

        except (
            NotFoundError,
            PermissionDeniedError,
            ChangeAlreadyHasTicketError,
            JurisdictionChangeNotFoundError,
        ):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating jurisdiction ticket: {str(e)}")
            raise ProcessingError(message="An error occurred while creating the ticket")

    @staticmethod
    def _extract_display_name_from_description(change_description: str) -> str:
        """Extract display name from LLM-generated change description.

        The LLM generates descriptions like:
        "Standard License Fee increased from $32,500 to $33,500"

        This extracts "Standard License Fee" for use in ticket titles.

        Args:
            change_description: Human-readable change description

        Returns:
            Display name extracted from description

        Examples:
            >>> _extract_display_name_from_description(
            ...     "Standard License Fee increased from $32,500 to $33,500"
            ... )
            'Standard License Fee'
            >>> _extract_display_name_from_description(
            ...     "Annual Audit Deadline changed from December 31st to January 15th"
            ... )
            'Annual Audit Deadline'
        """
        # Common verbs used in change descriptions
        verbs = [
            " increased",
            " decreased",
            " changed",
            " modified",
            " added",
            " removed",
            " updated",
        ]

        for verb in verbs:
            if verb in change_description:
                return change_description.split(verb)[0].strip()

        if ":" in change_description:
            return change_description.split(":")[0].strip()

        return (
            change_description[:50].strip()
            if len(change_description) > 50
            else change_description.strip()
        )
