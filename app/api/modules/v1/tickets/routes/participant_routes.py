import logging
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.core.dependencies.auth import get_current_user
from app.api.core.dependencies.guest_auth import GuestContext, get_user_or_guest
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.external_participant_schema import (
    InviteParticipantsRequest,
    InviteParticipantsResponse,
    TicketParticipantsResponse,
)
from app.api.modules.v1.tickets.service.participant_service import ParticipantService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.participant_docs import (
    get_ticket_participants_custom_errors,
    get_ticket_participants_custom_success,
    get_ticket_participants_responses,
    invite_participants_custom_errors,
    invite_participants_custom_success,
    invite_participants_responses,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
)


@router.post(
    "/{ticket_id}/invitations",
    response_model=InviteParticipantsResponse,
    status_code=status.HTTP_201_CREATED,
    responses=invite_participants_responses,
)
async def invite_participants(
    ticket_id: UUID,
    payload: InviteParticipantsRequest,
    client: str = Query(
        default=settings.OAUTH_DEFAULT_CLIENT,
        description="Which frontend should receive the invitation link.",
        pattern="^(local|staging|production)$",
        examples=["local"],
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite participants to a ticket (BOTH internal users AND external participants).

    This UNIFIED endpoint handles both types of invitations automatically:

    **For Internal Users (existing in system):**
    - Sends notification email with regular ticket link
    - They log in normally to view the ticket
    - No expiration, full dashboard access
    - Email example: "john@yourcompany.com"

    **For External Participants (not in system):**
    - Creates guest access record with role "Guest"
    - Generates secure JWT magic link (expires in 2 days)
    - Sends email with magic link (/guest/access?token=xyz)
    - No login required
    - Email example: "counsel@lawfirm.com"

    Args:
        ticket_id: UUID of the ticket
        payload: Request body with emails to invite
        current_user: Authenticated user (injected)
        db: Database session (injected)

    Returns:
        InviteParticipantsResponse with:
            - internal_users: List of notified internal users
            - external_participants: List of external participants with magic links
            - already_invited: List of emails already invited
            - not_in_project: List of internal user emails that cannot be invited
              (they're in the org but not in the ticket's project - must be added to project first)

        Message will include counts for each category, e.g.:
        "2 internal user(s) notified. 1 external participant(s) invited.
         1 email(s) already invited. 1 email(s) not invited (not in project - add to project first)"
    """
    service = ParticipantService(db)
    result = await service.invite_participants(
        ticket_id=ticket_id,
        emails=payload.emails,
        current_user_id=current_user.id,
        client=client,
    )

    logger.info(
        f"User {current_user.id} invited {len(result.internal_users)} internal users "
        f"and {len(result.external_participants)} external participants to ticket {ticket_id}"
    )

    message_parts = []
    if result.internal_users:
        message_parts.append(f"{len(result.internal_users)} internal user(s) notified")
    if result.external_participants:
        message_parts.append(f"{len(result.external_participants)} external participant(s) invited")
    if result.already_invited:
        message_parts.append(f"{len(result.already_invited)} email(s) already invited")
    if result.not_in_project:
        message_parts.append(
            f"{len(result.not_in_project)} email(s) not invited (not in project - add to "
            f"project first)"
        )

    message = ". ".join(message_parts) if message_parts else "No changes made"

    return success_response(
        status_code=status.HTTP_201_CREATED,
        message=message,
        data=result.model_dump(),
    )


invite_participants._custom_errors = invite_participants_custom_errors
invite_participants._custom_success = invite_participants_custom_success


@router.get(
    "/{ticket_id}/participants",
    response_model=TicketParticipantsResponse,
    status_code=status.HTTP_200_OK,
    responses=get_ticket_participants_responses,
)
async def get_ticket_participants(
    ticket_id: UUID,
    user_or_guest: Union[User, GuestContext] = Depends(get_user_or_guest),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all participants (internal users + external guests) for a ticket.

    This endpoint returns complete information about everyone invited to the ticket:

    **Internal Participants (registered users):**
    - Full name, email, profile picture
    - Online/offline status (online if active in last 5 minutes)
    - Invitation timestamp

    **External Participants (guest access):**
    - Display name always shown as "Guest"
    - Email and role only (no profile picture)
    - Online/offline status (online if active in last 5 minutes)
    - Invitation and expiration timestamps

    **Access Control:**
    - Users with VIEW_TICKETS permission (admins/managers/owners) can view all participants
    - Users in the project can view
    - Internal participants can view
    - External participants (guests) can view
    - Users in org but not in project/participants/permission → Permission Denied

    Args:
        ticket_id: UUID of the ticket
        user_or_guest: Authenticated user or guest (injected)
        db: Database session (injected)

    Returns:
        TicketParticipantsResponse with internal_participants and external_participants lists
    """
    service = ParticipantService(db)
    result = await service.get_ticket_participants(
        ticket_id=ticket_id,
        user_or_guest=user_or_guest,
    )

    logger.info(
        f"Retrieved {len(result.internal_participants)} internal and "
        f"{len(result.external_participants)} external participants for ticket {ticket_id}"
    )

    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"Retrieved {
            len(result.internal_participants) + len(result.external_participants)
        } participant(s)",
        data=result.model_dump(),
    )


get_ticket_participants._custom_errors = get_ticket_participants_custom_errors
get_ticket_participants._custom_success = get_ticket_participants_custom_success
