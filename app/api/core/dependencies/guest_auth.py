import logging
from typing import Union
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    ForbiddenError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
)
from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
    TicketStatus,
)
from app.api.modules.v1.tickets.utils.guest_token import decode_guest_token

logger = logging.getLogger("app")

security = HTTPBearer()


class GuestContext:
    """
    Context object for authenticated guest access.

    This replaces the User object for guest endpoints.
    """

    def __init__(
        self,
        participant: ExternalParticipant,
        ticket: Ticket,
        token_payload: dict,
    ):
        self.participant = participant
        self.ticket = ticket
        self.token_payload = token_payload

    @property
    def participant_id(self) -> UUID:
        return self.participant.id

    @property
    def ticket_id(self) -> UUID:
        return self.ticket.id

    @property
    def email(self) -> str:
        return self.participant.email

    @property
    def role(self) -> str:
        return self.participant.role


async def get_current_guest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> GuestContext:
    """
    Dependency to validate guest access tokens and return guest context.

    This is the guest equivalent of get_current_user().

    Validates:
        1. Token signature and expiration
        2. Token audience is "guest_access"
        3. ExternalParticipant exists and is active
        4. Ticket exists and is open
        5. Token matches the participant's ticket

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        GuestContext with participant and ticket information

    Raises:
        InvalidTokenError: Invalid or expired token (401)
        PermissionDeniedError: Access revoked (403)
        ForbiddenError: Ticket closed (403)
        NotFoundError: Participant or ticket not found (404)
    """
    token = credentials.credentials

    token_payload = decode_guest_token(token)

    if not token_payload:
        raise InvalidTokenError(message="Invalid token or expired token")

    participant_id = UUID(token_payload.sub)
    ticket_id = UUID(token_payload.ticket_id)

    participant_stmt = select(ExternalParticipant).where(ExternalParticipant.id == participant_id)
    participant_result = await db.execute(participant_stmt)
    participant = participant_result.scalar_one_or_none()

    if not participant:
        logger.warning(f"External participant {participant_id} not found")
        raise NotFoundError(message="Access record not found")

    if not participant.is_active:
        logger.warning(f"Guest access revoked for participant {participant_id}")
        raise PermissionDeniedError(message="Your access has been revoked")

    if participant.ticket_id != ticket_id:
        logger.warning(
            f"Token ticket mismatch: participant ticket {participant.ticket_id}, "
            f"token ticket {ticket_id}"
        )
        raise InvalidTokenError(message="Invalid token or expired token")

    from sqlalchemy.orm import selectinload

    ticket_stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.project),
            selectinload(Ticket.organization),
        )
    )
    ticket_result = await db.execute(ticket_stmt)
    ticket = ticket_result.scalar_one_or_none()

    if not ticket:
        logger.warning(f"Ticket {ticket_id} not found")
        raise NotFoundError(message="Ticket not found or has been deleted")

    if ticket.status == TicketStatus.CLOSED:
        logger.info(f"Guest attempt to access closed ticket {ticket_id}")
        raise ForbiddenError(message="This ticket is closed and no longer accessible")

    from datetime import datetime, timezone

    participant.last_accessed_at = datetime.now(timezone.utc)
    db.add(participant)
    await db.commit()

    logger.info(f"Guest {participant.email} accessed ticket {ticket_id}")

    return GuestContext(
        participant=participant,
        ticket=ticket,
        token_payload=token_payload.model_dump(),
    )


async def get_user_or_guest(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Union["User", GuestContext]:  # noqa: F821
    """
    Unified dependency that accepts either regular user auth or guest auth.

    This allows endpoints to be accessible by both:
    - Regular authenticated users (returns User object)
    - External participants with guest tokens (returns GuestContext)

    The endpoint can then check permissions based on the type returned.

    Args:
        credentials: Bearer token credentials (auto-extracted by HTTPBearer)
        db: Database session

    Returns:
        Union[User, GuestContext]: Either a User or GuestContext
    """
    token = credentials.credentials

    guest_payload = decode_guest_token(token)

    if guest_payload:
        return await get_current_guest(credentials=credentials, db=db)

    return await get_current_user(credentials=credentials, db=db)
