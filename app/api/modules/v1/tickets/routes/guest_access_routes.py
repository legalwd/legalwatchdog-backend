import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.guest_auth import (
    GuestContext,
    get_current_guest,
)
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    GuestTicketAccessResponse,
)
from app.api.modules.v1.tickets.service.guest_access_service import GuestAccessService
from app.api.utils.response_payloads import success_response

from .docs.guest_access_docs import (
    guest_ticket_access_custom_errors,
    guest_ticket_access_custom_success,
    guest_ticket_access_responses,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets/external",
    tags=["Tickets"],
)


@router.get(
    "/access",
    response_model=GuestTicketAccessResponse,
    status_code=status.HTTP_200_OK,
    responses=guest_ticket_access_responses,
)
async def get_guest_ticket_access(
    guest: GuestContext = Depends(get_current_guest),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate guest access token and return ticket details.

    This endpoint is called when a guest clicks the magic link.
    It validates their token and returns the ticket they can access.

    CRITICAL SECURITY:
        - Token signature is validated
        - Token audience must be "guest_access"
        - ExternalParticipant must be active
        - Ticket must be open (not closed)
        - Token ticket_id must match the participant's ticket

    NO LOGIN REQUIRED - Uses Bearer token from magic link.

    Args:
        guest: Guest context from token validation (injected)
        db: Database session (injected)

    Returns:
        GuestTicketAccessResponse with limited ticket information
    """
    service = GuestAccessService(db)
    response_data = await service.get_guest_ticket_access(guest)

    logger.info(f"Guest {guest.participant.email} successfully accessed ticket {guest.ticket.id}!")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Guest access validated successfully",
        data=response_data.model_dump(),
    )


get_guest_ticket_access._custom_errors = guest_ticket_access_custom_errors
get_guest_ticket_access._custom_success = guest_ticket_access_custom_success
