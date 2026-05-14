import logging
from datetime import datetime, timezone
from uuid import UUID

from celery import shared_task
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.api.core.config import settings
from app.api.core.dependencies.send_mail import send_email
from app.api.events.builders import build_notification_events
from app.api.events.factory import get_event_publisher
from app.api.modules.v1.jurisdictions.models.jurisdiction_model import Jurisdiction
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
    NotificationType,
)
from app.api.modules.v1.projects.models.project_user_model import ProjectUser
from app.api.modules.v1.scraping.models.change_diff import ChangeDiff
from app.api.modules.v1.scraping.models.data_revision import DataRevision
from app.api.modules.v1.scraping.models.source_model import Source
from app.api.utils.celery_utils import syncify
from app.api.utils.db_utils import get_isolated_async_session

logger = logging.getLogger("app")


async def send_revision_notifications(revision_id: str):
    """
    Send notifications to ALL users in the project for a data revision.

    All users with access to the project will receive notifications when
    a source in their jurisdiction has a data revision.

    Args:
        revision_id: UUID string of the data revision

    Raises:
        SQLAlchemyError: If there is a database error during processing
    """
    async with get_isolated_async_session() as session:
        try:
            revision_uuid = UUID(revision_id)
        except ValueError as e:
            logger.error(f"Invalid revision_id format: {revision_id} - {e}")
            return

        try:
            revision_result = await session.execute(
                select(DataRevision)
                .where(DataRevision.id == revision_uuid)
                .options(
                    joinedload(DataRevision.source)
                    .joinedload(Source.jurisdiction)
                    .joinedload(Jurisdiction.project)
                )
            )
            revision = revision_result.unique().scalar_one_or_none()
            if not revision:
                logger.warning(f"No data revision found with id {revision_id}")
                return

            source = revision.source
            if not source:
                logger.warning(f"No source found for revision {revision_id}")
                return

            jurisdiction = source.jurisdiction
            if not jurisdiction:
                logger.warning(f"No jurisdiction found for revision {revision_id}")
                return

            project = jurisdiction.project
            if not project:
                logger.warning(f"No project found for revision {revision_id}")
                return

            project_users_result = await session.execute(
                select(ProjectUser)
                .where(ProjectUser.project_id == project.id)
                .options(joinedload(ProjectUser.user))
            )
            project_users = project_users_result.unique().scalars().all()
            if not project_users:
                logger.info(f"No users associated with project {project.id}")
                return

            logger.info(
                f"Found {len(project_users)} user(s) in project {project.id} "
                f"(organization: {getattr(project, 'organization_id', 'N/A')})"
            )

            change_diff_result = await session.execute(
                select(ChangeDiff).where(ChangeDiff.new_revision_id == revision.id).limit(1)
            )
            change_diff = change_diff_result.scalars().first()

            if change_diff and change_diff.diff_patch:
                change_summary = change_diff.diff_patch.get(
                    "change_summary",
                    revision.ai_summary or "A new revision was detected for this source.",
                )
                risk_level = change_diff.diff_patch.get("risk_level", "UNKNOWN")
            else:
                change_summary = (
                    revision.ai_summary or "A new revision was detected for this source."
                )
                risk_level = "UNKNOWN"

            notification_title = f"New Change Detected: {source.name}"
            notification_message = change_summary

            base_url = settings.FRONTEND_URL or "https://legalwatch.dog"

            action_url = (
                f"{base_url}/app/jurisdictions/{jurisdiction.id}"
                f"?organizationId={project.org_id}&tab=data-page"
            )
            logger.info(f"Linking to jurisdiction {jurisdiction.id} for project {project.id}")

            notifications_sent = 0
            notifications_skipped = 0
            notifications_failed = 0
            has_changes = False
            notifications_to_publish: dict[UUID, Notification] = {}

            existing_result = await session.execute(
                select(Notification).where(
                    Notification.revision_id == revision_uuid,
                    Notification.user_id.in_([pu.user_id for pu in project_users]),
                )
            )
            existing_notifications = {
                (n.revision_id, n.user_id): n for n in existing_result.scalars().all()
            }

            # Batch insert new notifications
            new_notifications = []
            for project_user in project_users:
                user = project_user.user
                if not user:
                    logger.warning(f"User {project_user.user_id} not found, skipping")
                    continue

                key = (revision_uuid, user.id)
                if key in existing_notifications:
                    existing = existing_notifications[key]
                    if existing.status == NotificationStatus.SENT:
                        logger.info(
                            f"Notification already sent for user {user.email} "
                            f"(notification_id: {existing.notification_id})"
                        )
                        notifications_skipped += 1
                        continue

                else:
                    notification = Notification(
                        revision_id=revision_uuid,
                        user_id=user.id,
                        notification_type=NotificationType.CHANGE_DETECTED,
                        title=notification_title,
                        message=notification_message,
                        source_id=source.id,
                        jurisdiction_id=jurisdiction.id,
                        organization_id=getattr(project, "organization_id", None),
                        status=NotificationStatus.PENDING,
                        action_url=action_url,
                        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    new_notifications.append(notification)
                    notifications_to_publish[notification.notification_id] = notification

            # Batch insert all new notifications
            if new_notifications:
                session.add_all(new_notifications)
                await session.flush()
                has_changes = True

            for project_user in project_users:
                user = project_user.user
                if not user:
                    continue

                key = (revision_uuid, user.id)
                notification = existing_notifications.get(key)
                if not notification and any(n.user_id == user.id for n in new_notifications):
                    notification = next(n for n in new_notifications if n.user_id == user.id)

                if not notification:
                    continue

                email_context = {
                    "user_name": user.name or getattr(user, "username", "User"),
                    "ai_summary": change_summary,
                    "risk_level": risk_level,
                    "source_name": source.name,
                    "action_url": action_url,
                    "subject": notification_title,
                }

                try:
                    success = await send_email(
                        template_name="revision_notification.html",
                        subject=notification_title,
                        recipient=user.email,
                        context=email_context,
                    )

                    if success:
                        notification.status = NotificationStatus.SENT
                        notifications_sent += 1
                        logger.info(
                            f"✓ Notification {notification.notification_id} sent to {user.email}"
                        )
                    else:
                        notification.status = NotificationStatus.FAILED
                        notifications_failed += 1
                        logger.error(
                            f"✗ Failed to send notification {notification.notification_id} "
                            f"to {user.email}"
                        )
                except Exception as e:
                    notification.status = NotificationStatus.FAILED
                    notifications_failed += 1
                    logger.error(
                        f"✗ Exception sending notification {notification.notification_id} "
                        f"to {user.email}: {str(e)}"
                    )

                notification.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.add(notification)
                notifications_to_publish[notification.notification_id] = notification
                has_changes = True

            if has_changes:
                await session.commit()

            if settings.ENABLE_REALTIME_WEBSOCKETS and notifications_to_publish:
                publisher = await get_event_publisher()
                events = build_notification_events(notifications_to_publish.values())
                for event in events:
                    await publisher.publish(event)

            logger.info(
                f"Notification summary for revision {revision_id}: "
                f"Sent: {notifications_sent}, "
                f"Skipped: {notifications_skipped}, Failed: {notifications_failed}"
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error sending notifications for revision {revision_id}: {str(e)}"
            )
            raise


@shared_task(bind=True, name="send_revision_notifications", max_retries=3)
def send_revision_notifications_task(self, revision_id: str):
    """
    Celery task wrapper for sending revision notifications to ALL project users.

    Args:
        revision_id: UUID string of the data revision

    Returns:
        str: Result status message

    Raises:
        Retries the task up to 3 times with escalating countdown on failure.
    """
    logger.info(f"[CELERY TASK] Starting notification task for revision {revision_id}")
    try:
        syncify(send_revision_notifications)(revision_id)
        logger.info(
            f"[CELERY TASK] Successfully processed notifications for revision {revision_id}"
        )
        return f"completed: {revision_id}"
    except Exception as exc:
        logger.error(
            f"[CELERY TASK] Error processing notifications for revision {revision_id}: {str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
