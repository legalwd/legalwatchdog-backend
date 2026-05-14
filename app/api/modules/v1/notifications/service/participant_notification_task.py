import logging
from uuid import UUID

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.modules.v1.tickets.models.ticket_model import (
    ExternalParticipant,
    Ticket,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.celery_utils import syncify
from app.api.utils.db_utils import get_isolated_async_session

logger = logging.getLogger("app")


async def send_internal_user_notification(
    ticket_id: str,
    user_id: str,
    invited_by_user_id: str,
    ticket_link: str | None = None,
) -> None:
    """
    Send notification email to internal user (background task).

    IMPORTANT: This is NOT a magic link. Internal users log in normally
    and access the ticket through the regular authenticated dashboard.

    Args:
        ticket_id: UUID string of the ticket
        user_id: UUID string of the internal user being notified
        invited_by_user_id: UUID string of the user who sent the invitation
        ticket_link: Optional precomputed link to the ticket

    Raises:
        SQLAlchemyError: If there is a database error during processing
    """
    async with get_isolated_async_session() as session:
        try:
            ticket_uuid = UUID(ticket_id)
            user_uuid = UUID(user_id)
            invited_by_uuid = UUID(invited_by_user_id)
        except ValueError as e:
            logger.error(f"Invalid UUID format: {e}")
            return

        try:
            ticket_result = await session.execute(
                select(Ticket)
                .where(Ticket.id == ticket_uuid)
                .options(
                    joinedload(Ticket.organization),
                    joinedload(Ticket.project),
                )
            )
            ticket = ticket_result.unique().scalar_one_or_none()

            if not ticket:
                logger.warning(f"Ticket not found for notification: ticket_id={ticket_id}")
                return

            user_result = await session.execute(select(User).where(User.id == user_uuid))
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"User not found for notification: user_id={user_id}")
                return

            invited_by_result = await session.execute(
                select(User).where(User.id == invited_by_uuid)
            )
            invited_by_user = invited_by_result.scalar_one_or_none()

            if not invited_by_user:
                logger.warning(
                    f"Invited by user not found for notification: user_id={invited_by_user_id}"
                )
                return

            if not ticket_link:
                ticket_link = f"{settings.FRONTEND_URL}/tickets/{ticket.id}"

            context = {
                "recipient_name": user.name or user.email,
                "invited_by_name": (invited_by_user.name or invited_by_user.email),
                "organization_name": (
                    ticket.organization.name if ticket.organization else "the organization"
                ),
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority,
                "ticket_status": ticket.status.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "ticket_link": ticket_link,
                "is_internal": True,
            }

            await send_email(
                template_name="internal_user_ticket_notification.html",
                subject=f"You've been invited to collaborate: {ticket.title}",
                recipient=user.email,
                context=context,
            )

            logger.info(f"Internal user notification sent to {user.email} for ticket {ticket.id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error sending notification for ticket {ticket_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(
                f"Failed to send notification to {user.email} for ticket {ticket_id}: {str(e)}",
                exc_info=True,
            )
            raise


async def send_external_participant_notification(
    ticket_id: str,
    participant_id: str,
    invited_by_user_id: str,
    magic_link: str,
) -> None:
    """
    Send guest access email to external participant with magic link (background task).

    CRITICAL: The magic link must go to /guest/access?token=xyz
    NOT to /tickets/{id} (which requires login).

    Args:
        ticket_id: UUID string of the ticket
        participant_id: UUID string of the external participant
        invited_by_user_id: UUID string of the user who sent the invitation
        magic_link: The magic link with JWT token

    Raises:
        SQLAlchemyError: If there is a database error during processing
    """
    async with get_isolated_async_session() as session:
        try:
            ticket_uuid = UUID(ticket_id)
            participant_uuid = UUID(participant_id)
            invited_by_uuid = UUID(invited_by_user_id)
        except ValueError as e:
            logger.error(f"Invalid UUID format: {e}")
            return

        try:
            ticket_result = await session.execute(
                select(Ticket)
                .where(Ticket.id == ticket_uuid)
                .options(
                    joinedload(Ticket.organization),
                    joinedload(Ticket.project),
                )
            )
            ticket = ticket_result.unique().scalar_one_or_none()

            if not ticket:
                logger.warning(f"Ticket not found for notification: ticket_id={ticket_id}")
                return

            participant_result = await session.execute(
                select(ExternalParticipant).where(ExternalParticipant.id == participant_uuid)
            )
            participant = participant_result.scalar_one_or_none()

            if not participant:
                logger.warning(
                    f"External participant not found for notification: "
                    f"participant_id={participant_id}"
                )
                return

            invited_by_result = await session.execute(
                select(User).where(User.id == invited_by_uuid)
            )
            invited_by_user = invited_by_result.scalar_one_or_none()

            if not invited_by_user:
                logger.warning(
                    f"Invited by user not found for notification: user_id={invited_by_user_id}"
                )
                return

            recipient_name = participant.email.split("@")[0].title()

            context = {
                "recipient_name": recipient_name,
                "recipient_role": participant.role,
                "invited_by_name": (invited_by_user.name or invited_by_user.email),
                "organization_name": (
                    ticket.organization.name if ticket.organization else "the organization"
                ),
                "ticket_title": ticket.title,
                "ticket_description": ticket.description or "",
                "ticket_priority": ticket.priority,
                "ticket_status": ticket.status.replace("_", " "),
                "project_name": ticket.project.title if ticket.project else None,
                "magic_link": magic_link,  # CRITICAL: Guest access link
                "expires_at": (
                    participant.expires_at.strftime("%B %d, %Y") if participant.expires_at else ""
                ),
                "is_external": True,
            }

            await send_email(
                template_name="external_participant_invitation.html",
                subject=f"You've been invited to collaborate: {ticket.title}",
                recipient=participant.email,
                context=context,
            )

            logger.info(
                f"External participant email sent to {participant.email} for ticket {ticket.id}"
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error sending external participant notification "
                f"for ticket {ticket_id}: {str(e)}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to send email to {participant.email} for ticket {ticket_id}: {str(e)}",
                exc_info=True,
            )
            raise


@shared_task(bind=True, name="send_internal_user_notification", max_retries=3)
def send_internal_user_notification_task(
    self,
    ticket_id: str,
    user_id: str,
    invited_by_user_id: str,
    ticket_link: str | None = None,
):
    """
    Celery task wrapper for sending internal user ticket notifications.

    Args:
        ticket_id: UUID string of the ticket
        user_id: UUID string of the internal user being notified
        invited_by_user_id: UUID string of the user who sent the invitation
        ticket_link: Optional precomputed link to the ticket

    Returns:
        str: Result status message

    Raises:
        Retries the task up to 3 times with escalating countdown on failure.
    """
    logger.info(
        f"[CELERY TASK] Starting internal user notification task for "
        f"ticket {ticket_id}, user {user_id}"
    )
    try:
        syncify(send_internal_user_notification)(
            ticket_id, user_id, invited_by_user_id, ticket_link
        )
        logger.info(
            f"[CELERY TASK] Successfully sent internal user notification for ticket {ticket_id}"
        )
        return f"completed: {ticket_id}"
    except Exception as exc:
        logger.error(
            f"[CELERY TASK] Error sending internal user notification "
            f"for ticket {ticket_id}: {str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, name="send_external_participant_notification", max_retries=3)
def send_external_participant_notification_task(
    self,
    ticket_id: str,
    participant_id: str,
    invited_by_user_id: str,
    magic_link: str,
):
    """
    Celery task wrapper for sending external participant guest access notifications.

    Args:
        ticket_id: UUID string of the ticket
        participant_id: UUID string of the external participant
        invited_by_user_id: UUID string of the user who sent the invitation
        magic_link: The magic link with JWT token

    Returns:
        str: Result status message

    Raises:
        Retries the task up to 3 times with escalating countdown on failure.
    """
    logger.info(
        f"[CELERY TASK] Starting external participant notification task "
        f"for ticket {ticket_id}, participant {participant_id}"
    )
    try:
        syncify(send_external_participant_notification)(
            ticket_id, participant_id, invited_by_user_id, magic_link
        )
        logger.info(
            f"[CELERY TASK] Successfully sent external participant notification "
            f"for ticket {ticket_id}"
        )
        return f"completed: {ticket_id}"
    except Exception as exc:
        logger.error(
            f"[CELERY TASK] Error sending external participant notification "
            f"for ticket {ticket_id}: {str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
