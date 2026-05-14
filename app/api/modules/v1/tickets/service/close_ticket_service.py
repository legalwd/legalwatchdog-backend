import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.api.core.custom_exceptions.exceptions import (
    AlreadyExistsError,
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
    UserNotInOrganizationError,
)
from app.api.core.dependencies.auth import TenantGuard
from app.api.modules.v1.tickets.models.ticket_model import Ticket, TicketStatus
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import TicketCloseRequest
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.organization_validations import check_user_permission

logger = logging.getLogger("app")


class TicketService:
    """
    Service class for ticket-related business logic operations.

    This class encapsulates ticket operations including closing and
    other ticket state management.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the TicketService with a database session.

        Args:
            db (AsyncSession): The database session for executing queries.
        """
        self.db = db

    async def close_ticket(
        self,
        ticket_id: UUID,
        user_id: UUID,
        close_data: TicketCloseRequest,
    ) -> Ticket:
        """
        Close a ticket with provided data.

        Args:
            ticket_id: ID of the ticket to close
            user_id: ID of the user closing the ticket
            close_data: Closing request data with optional notes

        Returns:
            Updated Ticket object after closing

        Raises:
            NotFoundError: If ticket doesn't exist
            PermissionDeniedError: If user lacks permission or ticket ownership validation fails
            AlreadyExistsError: If ticket is already closed (using this for "already in state")
            ProcessingError: For unexpected processing errors
        """
        try:
            statement = select(Ticket).where(Ticket.id == ticket_id)
            result = await self.db.execute(statement)
            ticket = result.scalar_one_or_none()

            if not ticket:
                logger.warning(f"Ticket not found for closing: ticket_id={ticket_id}")
                raise NotFoundError(message="The ticket you're trying to close doesn't exist.")

            organization_id = ticket.organization_id
            project_id = ticket.project_id

            user_result = await self.db.execute(select(User).where(User.id == user_id))
            current_user = user_result.scalar_one_or_none()

            if not current_user:
                logger.warning(f"User not found: user_id={user_id}")
                raise NotFoundError(message="User not found.")

            tenant = TenantGuard(self.db, current_user)
            await tenant.get_membership(organization_id)

            has_permission = await check_user_permission(
                self.db, user_id, organization_id, "close_tickets"
            )

            if not has_permission:
                logger.warning(
                    f"User lacks permission to close tickets: "
                    f"user_id={user_id}, org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message=(
                        "You don't have permission to close tickets. "
                        "Please contact your organization administrator."
                    )
                )

            if ticket.project_id != project_id:
                logger.warning(
                    f"Ticket project mismatch: ticket_id={ticket_id}, "
                    f"ticket_project_id={ticket.project_id}, expected_project_id={project_id}"
                )
                raise PermissionDeniedError(
                    message="This ticket doesn't belong to the specified project."
                )

            if ticket.organization_id != organization_id:
                logger.warning(
                    f"Ticket organization mismatch: ticket_id={ticket_id}, "
                    f"ticket_org_id={ticket.organization_id}, expected_org_id={organization_id}"
                )
                raise PermissionDeniedError(
                    message="This ticket doesn't belong to your organization."
                )

            if ticket.status == TicketStatus.CLOSED:
                logger.info(f"Attempted to close already closed ticket: ticket_id={ticket_id}")
                raise AlreadyExistsError(message="This ticket is already closed")

            logger.info(f"Closing ticket_id={ticket_id} by user_id={user_id}")

            ticket.status = TicketStatus.CLOSED
            ticket.closed_at = datetime.now(timezone.utc)
            ticket.updated_at = datetime.now(timezone.utc)

            if close_data.closing_notes:
                if not ticket.description:
                    ticket.description = f"Closing notes: {close_data.closing_notes}"
                else:
                    ticket.description += f"\n\nClosing notes: {close_data.closing_notes}"

            self.db.add(ticket)
            await self.db.commit()
            await self.db.refresh(ticket)

            logger.info(f"Ticket closed successfully: ticket_id={ticket_id}, user_id={user_id}")

            return ticket

        except (
            NotFoundError,
            PermissionDeniedError,
            AlreadyExistsError,
            UserNotInOrganizationError,
        ) as e:
            await self.db.rollback()
            logger.error(f"Known error in close ticket: {type(e).__name__}: {str(e)}")
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error closing ticket: {str(e)}")
            raise ProcessingError(message="Failed to close ticket. Please try again.")
