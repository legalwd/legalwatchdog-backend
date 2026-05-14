import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.core.dependencies.guest_auth import GuestContext
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    GuestTicketAccessResponse,
)

logger = logging.getLogger("app")


class GuestAccessService:
    """Service for handling guest ticket access operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_guest_ticket_access(
        self,
        guest: GuestContext,
    ) -> GuestTicketAccessResponse:
        """
        Process guest access request and return ticket details.

        The guest context has already been validated by the get_current_guest dependency,
        which ensures:
        - Token signature is valid
        - Token audience is "guest_access"
        - ExternalParticipant exists and is active
        - Ticket exists and is open (not closed)
        - Token ticket_id matches participant's ticket

        Args:
            guest: Validated guest context with ticket and participant info

        Returns:
            GuestTicketAccessResponse with limited ticket information

        Raises:
            ProcessingError: For any unexpected errors
        """
        try:
            ticket = guest.ticket
            participant = guest.participant

            response_data = GuestTicketAccessResponse(
                ticket_id=str(ticket.id),
                title=ticket.title,
                description=ticket.description,
                priority=ticket.priority,
                status=ticket.status,
                created_at=ticket.created_at,
                project_name=ticket.project.title if ticket.project else None,
                participant_email=participant.email,
                participant_role=participant.role,
                access_expires_at=participant.expires_at,
            )

            logger.info(
                f"Guest access validated for {participant.email} on ticket {ticket.id}",
                extra={
                    "participant_id": str(participant.id),
                    "ticket_id": str(ticket.id),
                    "participant_email": participant.email,
                },
            )

            return response_data

        except Exception as e:
            logger.exception(
                f"Error processing guest ticket access: {str(e)}",
                extra={
                    "participant_id": str(guest.participant_id),
                    "ticket_id": str(guest.ticket_id),
                },
            )
            raise ProcessingError(
                message="Failed to load ticket. Please try again or contact support."
            )
