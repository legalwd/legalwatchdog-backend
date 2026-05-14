import logging
from datetime import datetime, timedelta, timezone
from typing import List, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.core.custom_exceptions.exceptions import (
    ClosedTicketError,
    ForbiddenError,
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
    UserNotInOrganizationError,
)
from app.api.core.dependencies.auth import TenantGuard
from app.api.core.dependencies.billing_guard import require_billing_access
from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.notifications.service.participant_notification_task import (
    send_external_participant_notification_task,
    send_internal_user_notification_task,
)
from app.api.modules.v1.organization.models.user_organization_model import UserOrganization
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    InternalParticipant,
    Ticket,
    TicketStatus,
)
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    ExternalParticipantDetail,
    ExternalParticipantResponse,
    InternalParticipantDetail,
    InternalUserInvitationResponse,
    InviteParticipantsResponse,
    TicketParticipantsResponse,
)
from app.api.modules.v1.tickets.utils.guest_token import (
    create_guest_token,
    hash_token,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.frontend_client import add_client_query, resolve_frontend_url
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class ParticipantService:
    """Service for handling ticket participant invitations (internal users + external guests)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def invite_participants(
        self,
        ticket_id: UUID,
        emails: List[str],
        current_user_id: UUID,
        client: str | None = None,
    ) -> InviteParticipantsResponse:
        """
        Invite participants to a ticket (BOTH internal users AND external participants).

        UNIFIED INVITATION SYSTEM:
        - Checks if email exists in users table
        - If YES (internal user):
          → MUST be a member of the ticket's project
          → If not in project: Added to not_in_project list with message to add to project first
          → If in project: Send notification email with regular ticket link
          → They log in normally to view ticket
        - If NO (external participant):
          → Create ExternalParticipant record with "Guest" role
          → Generate JWT magic link (expires in 2 days)
          → Send guest access email

        Args:
            ticket_id: The UUID of the ticket
            emails: List of email addresses (internal or external)
            current_user_id: The UUID of the current user making the request
            client: Optional client identifier for frontend URL resolution

        Returns:
            InviteParticipantsResponse with:
            - internal_users: Successfully invited internal users
            - external_participants: Successfully invited external participants
            - already_invited: Emails already invited
            - not_in_project: Internal users not in project (cannot invite)

        Raises:
            NotFoundError: If ticket or user not found
            PermissionDeniedError: If user lacks permission or ticket is closed
            ProcessingError: For any other processing errors
        """
        role = "Guest"
        expiry_days = 2

        try:
            statement = (
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .options(
                    selectinload(Ticket.external_participants),
                    selectinload(Ticket.internal_participants),
                    selectinload(Ticket.organization),
                    selectinload(Ticket.project),
                )
            )
            result = await self.db.execute(statement)
            ticket = result.scalar_one_or_none()

            if not ticket:
                logger.warning(
                    f"Ticket not found for participant invitation: ticket_id={ticket_id}"
                )
                raise NotFoundError(
                    message="The ticket you're trying to add participants to doesn't exist."
                )

            if ticket.status == TicketStatus.CLOSED:
                logger.warning(
                    f"Attempt to invite participants to closed ticket: ticket_id={ticket_id}"
                )
                raise ClosedTicketError(message="Cannot invite participants to a closed ticket")

            organization_id = ticket.organization_id

            try:
                await require_billing_access(organization_id=organization_id, db=self.db)
            except HTTPException as billing_error:
                logger.warning(
                    f"Billing check failed for org {organization_id} when inviting "
                    f"participants: {billing_error.detail}"
                )
                raise PermissionDeniedError(message=billing_error.detail)

            current_user_result = await self.db.execute(
                select(User).where(User.id == current_user_id)
            )
            current_user = current_user_result.scalar_one_or_none()

            if not current_user:
                logger.warning(f"Current user not found: user_id={current_user_id}")
                raise NotFoundError(message="User not found")

            tenant = TenantGuard(self.db, current_user)
            await tenant.get_membership(organization_id)

            has_permission = await check_user_permission(
                self.db,
                current_user_id,
                organization_id,
                "invite_participants",
            )
            if not has_permission:
                logger.warning(
                    f"User lacks permission to invite participants: user_id={current_user_id}, "
                    f"org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message=(
                        "You don't have permission to invite participants. "
                        "Please contact your organization administrator."
                    )
                )

            existing_external_emails = {p.email.lower() for p in ticket.external_participants}
            existing_internal_user_ids = {p.user_id for p in ticket.internal_participants}

            normalized_emails = [email.strip().lower() for email in emails]

            user_statement = (
                select(User)
                .join(
                    UserOrganization,
                    and_(
                        UserOrganization.user_id == User.id,
                        UserOrganization.organization_id == organization_id,
                        UserOrganization.is_active,
                        UserOrganization.is_deleted.is_(False),
                    ),
                )
                .where(
                    and_(
                        User.email.in_(normalized_emails),
                        User.is_active,
                        User.is_verified,
                    )
                )
            )
            user_result = await self.db.execute(user_statement)
            found_users = user_result.scalars().all()

            users_by_email = {user.email.lower(): user for user in found_users}

            internal_users: List[InternalUserInvitationResponse] = []
            external_participants: List[ExternalParticipantResponse] = []
            already_invited: List[str] = []
            not_in_project: List[str] = []

            for email in normalized_emails:
                if email in existing_external_emails:
                    already_invited.append(email)
                    continue

                user = users_by_email.get(email)

                if user:
                    if user.id in existing_internal_user_ids:
                        already_invited.append(email)
                        continue

                    project_membership_stmt = select(ProjectUser).where(
                        and_(
                            ProjectUser.user_id == user.id,
                            ProjectUser.project_id == ticket.project_id,
                        )
                    )
                    project_membership_result = await self.db.execute(project_membership_stmt)
                    is_in_project = project_membership_result.scalar_one_or_none() is not None

                    if not is_in_project:
                        not_in_project.append(email)
                        logger.warning(
                            f"Cannot invite user {user.id} ({user.email}) to ticket {ticket_id} - "
                            f"not a member of project {ticket.project_id}"
                        )
                        continue

                    internal_participant = InternalParticipant(
                        ticket_id=ticket_id,
                        user_id=user.id,
                        invited_by_user_id=current_user_id,
                        invited_at=datetime.now(timezone.utc),
                        is_active=True,
                    )
                    self.db.add(internal_participant)
                    await self.db.flush()
                    await self.db.refresh(internal_participant)

                    frontend_url = resolve_frontend_url(client)
                    ticket_link = add_client_query(
                        f"{frontend_url}/tickets/{ticket_id}",
                        client,
                    )

                    send_internal_user_notification_task.delay(
                        str(ticket_id),
                        str(user.id),
                        str(current_user_id),
                        ticket_link,
                    )

                    internal_users.append(
                        InternalUserInvitationResponse(
                            user_id=str(user.id),
                            email=user.email,
                            name=user.name or None,
                            is_internal=True,
                            invited_at=datetime.now(timezone.utc),
                        )
                    )

                    logger.info(
                        f"Internal user {user.id} ({user.email}) notified about ticket {ticket_id}"
                    )

                else:
                    expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

                    participant = ExternalParticipant(
                        ticket_id=ticket_id,
                        email=email,
                        role=role,
                        invited_by_user_id=current_user_id,
                        invited_at=datetime.now(timezone.utc),
                        is_active=True,
                        expires_at=expires_at,
                    )
                    self.db.add(participant)
                    await self.db.flush()
                    await self.db.refresh(participant)

                    token = create_guest_token(
                        participant_id=participant.id,
                        ticket_id=ticket_id,
                        expiry_days=expiry_days,
                    )

                    participant.token_hash = hash_token(token)
                    self.db.add(participant)

                    frontend_url = resolve_frontend_url(client)
                    magic_link = add_client_query(
                        f"{frontend_url}/guest/access?token={token}",
                        client,
                    )

                    send_external_participant_notification_task.delay(
                        str(ticket_id),
                        str(participant.id),
                        str(current_user_id),
                        magic_link,
                    )

                    external_participants.append(
                        ExternalParticipantResponse(
                            participant_id=str(participant.id),
                            email=email,
                            role=role,
                            is_internal=False,
                            invited_at=participant.invited_at,
                            expires_at=expires_at,
                            magic_link=magic_link,
                        )
                    )

                    logger.info(
                        f"External participant {email} invited to ticket {ticket_id} (guest access)"
                    )

            if internal_users or external_participants:
                await self.db.commit()

            return InviteParticipantsResponse(
                internal_users=internal_users,
                external_participants=external_participants,
                already_invited=already_invited,
                not_in_project=not_in_project,
            )
        except (
            NotFoundError,
            PermissionDeniedError,
            ClosedTicketError,
            UserNotInOrganizationError,
        ) as e:
            await self.db.rollback()
            logger.error(f"Known error in invite_participants: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error inviting participants: {str(e)}")
            raise ProcessingError(message="Failed to invite participants. Please try again.")

    async def get_ticket_participants(
        self,
        ticket_id: UUID,
        user_or_guest: Union[User, GuestContext],
    ) -> TicketParticipantsResponse:
        """
        Get all participants (internal users + external guests) for a ticket.

        Access Control:
        - External participants (guests): Already validated by token, can view
        - Users with VIEW_TICKETS permission (admins/managers/owners): Can view all participants
        - Regular users: Must be either:
          1. Member of the project, OR
          2. Internal participant of the ticket
        - Users in org but not in project/participants/permission: Permission Denied
        - Users not in org: Forbidden

        Args:
            ticket_id: The UUID of the ticket
            user_or_guest: Either a User object or GuestContext

        Returns:
            TicketParticipantsResponse with internal and external participants

        Raises:
            NotFoundError: If ticket or user not found
            PermissionDeniedError: If user lacks permission to view participants
            ForbiddenError: If user not in organization
            ProcessingError: For any other processing errors
        """
        try:
            statement = (
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .options(
                    selectinload(Ticket.external_participants),
                    selectinload(Ticket.internal_participants).selectinload(
                        InternalParticipant.user
                    ),
                    selectinload(Ticket.organization),
                    selectinload(Ticket.project),
                )
            )
            result = await self.db.execute(statement)
            ticket = result.scalar_one_or_none()

            if not ticket:
                logger.warning(f"Ticket not found: ticket_id={ticket_id}")
                raise NotFoundError(message="The ticket you're trying to view doesn't exist.")

            organization_id = ticket.organization_id
            project_id = ticket.project_id

            if isinstance(user_or_guest, GuestContext):
                if user_or_guest.ticket_id != ticket_id:
                    logger.warning(
                        f"Guest ticket mismatch expected {ticket_id}, got {user_or_guest.ticket_id}"
                    )
                    raise PermissionDeniedError(
                        message="You don't have permission to view these participants."
                    )

                logger.info(
                    f"Guest {user_or_guest.email} accessing participants for ticket {ticket_id}"
                )

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

                if not has_view_tickets_permission:
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
                    internal_participant = await self.db.execute(internal_participant_stmt)
                    is_internal_participant = internal_participant.scalar_one_or_none() is not None

                    if not is_in_project and not is_internal_participant:
                        logger.warning(
                            f"User {current_user_id} in org but not in project {project_id} "
                            f"and not a participant of ticket {ticket_id}"
                        )
                        raise PermissionDeniedError(
                            message=(
                                "You don't have permission to view these participants. "
                                "Only project members and ticket participants can view this info"
                            )
                        )

                    logger.info(
                        f"User {current_user_id} accessing participants for ticket {ticket_id} "
                        f"(in_project={is_in_project}, is_participant={is_internal_participant})"
                    )
                else:
                    logger.info(
                        f"User {current_user_id} accessing participants for ticket {ticket_id} "
                        f"(has view_tickets permission)"
                    )

            now = datetime.now(timezone.utc)
            online_threshold = timedelta(minutes=5)

            internal_participants_list: List[InternalParticipantDetail] = []
            for internal_participant in ticket.internal_participants:
                user = internal_participant.user
                if not user:
                    continue

                is_online = user.last_active and (now - user.last_active) <= online_threshold
                status = "online" if is_online else "offline"

                internal_participants_list.append(
                    InternalParticipantDetail(
                        user_id=str(user.id),
                        name=user.name or "",
                        email=user.email,
                        profile_picture_url=user.profile_picture_url,
                        avatar_url=user.avatar_url,
                        status=status,
                        invited_at=internal_participant.invited_at,
                    )
                )

            external_participants_list: List[ExternalParticipantDetail] = []
            for external_participant in ticket.external_participants:
                is_guest_online = (
                    external_participant.last_accessed_at
                    and (now - external_participant.last_accessed_at) <= online_threshold
                )
                guest_status = "online" if is_guest_online else "offline"

                external_participants_list.append(
                    ExternalParticipantDetail(
                        participant_id=str(external_participant.id),
                        name="Guest",
                        email=external_participant.email,
                        role=external_participant.role,
                        status=guest_status,
                        invited_at=external_participant.invited_at,
                        expires_at=external_participant.expires_at,
                    )
                )

            logger.info(
                f"Retrieved {len(internal_participants_list)} internal and "
                f"{len(external_participants_list)} external participants for ticket {ticket_id}"
            )

            return TicketParticipantsResponse(
                internal_participants=internal_participants_list,
                external_participants=external_participants_list,
            )
        except (
            NotFoundError,
            PermissionDeniedError,
            ForbiddenError,
            UserNotInOrganizationError,
        ) as e:
            logger.error(f"Known error in get_ticket_participants: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Error getting ticket participants: {str(e)}")
            raise ProcessingError(
                message="Failed to retrieve ticket participants. Please try again."
            )
