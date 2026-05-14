import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.close_ticket_schemas import (
    TicketCloseRequest,
    TicketResponse,
)
from app.api.modules.v1.tickets.service.close_ticket_service import TicketService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.close_ticket_docs import (
    close_ticket_custom_errors,
    close_ticket_custom_success,
    close_ticket_responses,
)

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)
logger = logging.getLogger("app")


@router.patch(
    "/{ticket_id}/close", status_code=status.HTTP_200_OK, responses=close_ticket_responses
)
async def close_ticket(
    ticket_id: UUID,
    payload: TicketCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Close a ticket with optional closing notes.

    This endpoint closes a ticket, marking it as resolved or handled.
    Only users with 'close_tickets' permission can close tickets.
    Organization and project IDs are automatically derived from the ticket.

    Args:
        ticket_id (UUID): Unique identifier of the ticket to close.
        payload (TicketCloseRequest): Optional closing notes:
            - closing_notes (Optional[str]): Notes explaining
            why the ticket was closed (max 1000 chars)
        current_user (User): The authenticated user performing the request.
        db (AsyncSession): Database session for query execution.

    Returns:
        JSONResponse: Success response containing:
            - status (str): "success"
            - message (str): "Ticket closed successfully"
            - data (TicketResponse): Complete ticket details with updated status.

    Raises:
        HTTPException:
            - 400 Bad Request if ticket is already closed
            - 401 Unauthorized if authentication fails
            - 403 Forbidden if user lacks close_tickets permission or user
              is not a member of the ticket's organization
            - 404 Not Found if ticket doesn't exist
            - 500 Internal Server Error if operation fails
    """
    logger.info(f"Closing ticket_id={ticket_id} by user_id={current_user.id}")

    ticket_service = TicketService(db)
    ticket = await ticket_service.close_ticket(
        ticket_id=ticket_id,
        user_id=current_user.id,
        close_data=payload,
    )

    logger.info(f"Ticket closed successfully: ticket_id={ticket_id}, user_id={current_user.id}")

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Ticket closed successfully",
        data=TicketResponse.model_validate(ticket),
    )


close_ticket._custom_errors = close_ticket_custom_errors
close_ticket._custom_success = close_ticket_custom_success
