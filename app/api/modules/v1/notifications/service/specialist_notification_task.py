"""
Specialist hire notification background tasks for FastAPI.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.api.core.config import settings
from app.api.core.custom_exceptions.exceptions import ProcessingError
from app.api.core.dependencies.send_mail import send_email
from app.api.events.builders import build_notification_events
from app.api.events.factory import get_event_publisher
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)

logger = logging.getLogger("app")


async def send_admin_notification(specialist_hire: dict) -> None:
    """
    Send email notification to admin about new specialist request.

    Args:
        specialist_hire: Dictionary containing specialist hire details
    """
    admin_email = settings.ADMIN_EMAIL
    if not admin_email:
        logger.warning("ADMIN_EMAIL not configured. Skipping admin notification.")
        return

    admin_context = {
        "company_name": specialist_hire["company_name"],
        "company_email": specialist_hire["company_email"],
        "industry": specialist_hire["industry"],
        "brief_description": specialist_hire["brief_description"],
        "submitted_at": specialist_hire["submitted_at"],
        "hire_id": specialist_hire["hire_id"],
    }

    try:
        success = await send_email(
            template_name="specialist_hire_admin.html",
            subject=f"New Specialist Request: {specialist_hire['company_name']}",
            recipient=admin_email,
            context=admin_context,
        )

        if success:
            logger.info(
                f"✓ Admin notification sent for specialist hire {specialist_hire['hire_id']}"
            )
        else:
            logger.error(
                f"✗ Failed to send admin notification for hire {specialist_hire['hire_id']}"
            )
    except Exception as e:
        logger.exception(f"✗ Exception sending admin notification: {str(e)}")


async def send_user_confirmation(specialist_hire: dict) -> None:
    """
    Send confirmation email to user who requested specialist.

    Args:
        specialist_hire: Dictionary containing specialist hire details
    """
    user_context = {
        "company_name": specialist_hire["company_name"],
        "industry": specialist_hire["industry"],
        "submitted_at": specialist_hire["submitted_at"],
    }

    try:
        success = await send_email(
            template_name="specialist_hire_confirmation.html",
            subject="Your Specialist Request Has Been Received",
            recipient=specialist_hire["company_email"],
            context=user_context,
        )

        if success:
            logger.info(f"✓ User confirmation sent to {specialist_hire['company_email']}")
        else:
            logger.error(
                f"✗ Failed to send user confirmation to {specialist_hire['company_email']}"
            )
    except Exception as e:
        logger.exception(f"✗ Exception sending user confirmation: {str(e)}")


async def create_specialist_hire_notification(
    db_session,
    hire_id: UUID,
    company_name: str,
    user_id: UUID,
    project_id: UUID,
    org_id: UUID,
) -> None:
    """
    Create in-app notification for specialist hire request.

    This function is called synchronously during the request lifecycle,
    so it raises ProcessingError on failure to allow proper error handling.

    Args:
        db_session: Database session
        hire_id: UUID of the specialist hire
        company_name: Name of the company
        user_id: UUID of the user
        project_id: UUID of the project
        org_id: UUID of the organization

    Raises:
        ProcessingError: If notification creation fails
    """
    try:
        existing = await db_session.scalar(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.notification_type == NotificationType.SPECIALIST_REQUEST,
                Notification.specialist_hire_id == hire_id,
            )
        )

        if existing:
            logger.info(f"In-app notification already exists for user {user_id}")
            return

        base_url = settings.FRONTEND_URL or "https://legalwatch.dog"
        action_url = f"{base_url}/dashboard/organizations/{org_id}/projects/{project_id}"

        notification = Notification(
            user_id=user_id,
            notification_type=NotificationType.SPECIALIST_REQUEST,
            title="Specialist Request Received",
            message=(
                f"Your specialist request for {company_name} has been received. "
                f"Our team will review your request and get back to you within 1-2 business days."
            ),
            specialist_hire_id=hire_id,
            organization_id=org_id,
            status=NotificationStatus.SENT,
            action_url=action_url,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)

        logger.info(
            f"✓ In-app notification {notification.notification_id} created for user {user_id}"
        )

        # Publish real-time event if enabled
        if settings.ENABLE_REALTIME_WEBSOCKETS:
            try:
                publisher = await get_event_publisher()
                events = build_notification_events([notification])
                for event in events:
                    await publisher.publish(event)
                logger.info(
                    f"Real-time event published for notification {notification.notification_id}"
                )
            except Exception as e:
                logger.error(f"Failed to publish real-time event: {str(e)}")

    except ProcessingError:
        raise
    except Exception as e:
        logger.exception(f"Failed to create in-app notification: {str(e)}")
        raise ProcessingError(
            message="Failed to create notification. "
            "Your request was saved but you may not see the notification."
        )


async def send_specialist_request_notifications_background(
    hire_id: str,
    company_name: str,
    company_email: str,
    industry: str,
    brief_description: str,
    user_email: str,
    created_at: datetime,
) -> None:
    """
    Background task to send notifications for a specialist hire request.

    Args:
        hire_id: UUID string of the specialist hire request
        company_name: Name of the company requesting specialist
        company_email: Contact email for the company
        industry: Industry sector
        brief_description: Brief description of specialist requirements
        user_email: Email of the user who made the request
        created_at: Timestamp when hire was created

    Note:
        This is designed to run as a FastAPI background task.
        All data is passed as parameters to avoid database session issues.
        Exceptions are caught and logged but not raised since this runs in background.
    """
    try:
        logger.info(f"Processing notifications for specialist hire {hire_id} by user {user_email}")

        submitted_at = created_at.strftime("%B %d, %Y at %I:%M %p")

        specialist_hire = {
            "hire_id": hire_id,
            "company_name": company_name,
            "company_email": company_email,
            "industry": industry,
            "brief_description": brief_description,
            "submitted_at": submitted_at,
        }

        await send_admin_notification(specialist_hire)

        await send_user_confirmation(specialist_hire)

        logger.info(f"Specialist hire notification process completed for hire {hire_id}")

    except Exception as e:
        logger.exception(f"Error in background notification task for hire {hire_id}: {str(e)}")
