import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.custom_exceptions.exceptions import (
    BadRequestError,
    NotFoundError,
    ProcessingError,
)
from app.api.modules.v1.notifications.models.revision_notification import (
    Notification,
    NotificationStatus,
)
from app.api.modules.v1.notifications.schemas.notification_schema import (
    NotificationFilter,
    NotificationUpdate,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for reading and managing notifications."""

    @staticmethod
    async def get_notification_by_id(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        """
        Get a notification by ID for a specific user.

        Args:
            db: Database session
            notification_id: The notification UUID
            user_id: The user UUID who must own the notification

        Returns:
            Notification object

        Raises:
            NotFoundError: If notification doesn't exist or doesn't belong to user
            ProcessingError: For unexpected errors
        """
        try:
            query = select(Notification).where(
                and_(
                    Notification.notification_id == notification_id,
                    Notification.user_id == user_id,
                )
            )

            result = await db.execute(query)
            notification = result.scalar_one_or_none()

            if not notification:
                logger.warning(
                    f"Notification not found: notification_id={notification_id}, user_id={user_id}"
                )
                raise NotFoundError(message="Notification not found for the user")

            return notification

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception(f"Error fetching notification: {str(e)}")
            raise ProcessingError(message="Failed to retrieve notification")

    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        filters: Optional[NotificationFilter] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict:
        """
        Retrieve notifications for a user with filtering and pagination.

        Args:
            db: Database session
            user_id: User UUID
            filters: Optional filters for notifications
            skip: Number of records to skip (pagination)
            limit: Maximum number of notifications to return

        Returns:
            Dict containing:
                - notifications: List of notification objects
                - total: Total count matching filters
                - page: Current page number
                - limit: Page size
                - unread_count: Total unread notifications

        Raises:
            ProcessingError: For unexpected errors
        """
        try:
            query = select(Notification).where(Notification.user_id == user_id)
            count_query = (
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id)
            )

            if filters:
                conditions = []

                if filters.status:
                    conditions.append(Notification.status == filters.status)

                if filters.notification_type:
                    conditions.append(Notification.notification_type == filters.notification_type)

                if filters.is_read is not None:
                    if filters.is_read:
                        conditions.append(Notification.read_at.is_not(None))
                    else:
                        conditions.append(Notification.read_at.is_(None))

                if filters.from_date:
                    conditions.append(Notification.created_at >= filters.from_date)

                if filters.to_date:
                    conditions.append(Notification.created_at <= filters.to_date)

                if filters.organization_id:
                    conditions.append(Notification.organization_id == filters.organization_id)

                if filters.source_id:
                    conditions.append(Notification.source_id == filters.source_id)

                if conditions:
                    query = query.where(and_(*conditions))
                    count_query = count_query.where(and_(*conditions))

            query = query.order_by(desc(Notification.created_at))

            query = query.offset(skip).limit(limit)

            result = await db.execute(query)
            notifications = result.scalars().all()

            count_result = await db.execute(count_query)
            total = count_result.scalar()

            unread_count = await NotificationService.get_unread_count(db, user_id)

            page = (skip // limit) + 1

            return {
                "notifications": list(notifications),
                "total": total,
                "page": page,
                "limit": limit,
                "unread_count": unread_count,
            }

        except Exception as e:
            logger.exception(f"Error fetching notifications: {str(e)}")
            raise ProcessingError(message="Failed to retrieve notifications")

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        notification_ids: List[uuid.UUID],
        user_id: uuid.UUID,
    ) -> int:
        """
        Mark notifications as read.

        Args:
            db: Database session
            notification_ids: List of notification UUIDs to mark as read
            user_id: User UUID who owns the notifications

        Returns:
            Count of updated notifications

        Raises:
            BadRequestError: If no notification IDs provided
            ProcessingError: For unexpected errors
        """
        try:
            if not notification_ids:
                raise BadRequestError(message="No notification IDs provided")

            query = select(Notification).where(
                and_(
                    Notification.notification_id.in_(notification_ids),
                    Notification.user_id == user_id,
                    Notification.read_at.is_(None),
                )
            )

            result = await db.execute(query)
            notifications = result.scalars().all()

            read_time = datetime.now(timezone.utc)
            for notification in notifications:
                notification.read_at = read_time
                notification.status = NotificationStatus.READ

            await db.commit()

            return len(notifications)

        except BadRequestError:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(f"Error marking notifications as read: {str(e)}")
            raise ProcessingError(message="Failed to mark notifications as read")

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Mark all unread notifications as read for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            Count of updated notifications

        Raises:
            ProcessingError: For unexpected errors
        """
        try:
            query = select(Notification).where(
                and_(Notification.user_id == user_id, Notification.read_at.is_(None))
            )

            result = await db.execute(query)
            notifications = result.scalars().all()

            read_time = datetime.now(timezone.utc)
            for notification in notifications:
                notification.read_at = read_time
                notification.status = NotificationStatus.READ

            await db.commit()

            return len(notifications)

        except Exception as e:
            await db.rollback()
            logger.exception(f"Error marking all notifications as read: {str(e)}")
            raise ProcessingError(message="Failed to mark all notifications as read")

    @staticmethod
    async def update_notification(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
        update_data: NotificationUpdate,
    ) -> Notification:
        """
        Update fields of a specific user-owned notification.

        Args:
            db: Database session
            notification_id: Notification UUID
            user_id: User UUID who owns the notification
            update_data: Data specifying which fields to update

        Returns:
            Updated notification object

        Raises:
            NotFoundError: If notification doesn't exist or doesn't belong to user
            ProcessingError: For unexpected errors
        """
        try:
            notification = await NotificationService.get_notification_by_id(
                db, notification_id, user_id
            )

            if update_data.status:
                notification.status = update_data.status

            if update_data.read_at:
                notification.read_at = update_data.read_at

            await db.commit()
            await db.refresh(notification)

            return notification

        except NotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(f"Error updating notification: {str(e)}")
            raise ProcessingError(message="Failed to update notification")

    @staticmethod
    async def delete_notification(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Delete a notification.

        Args:
            db: Database session
            notification_id: Notification UUID
            user_id: User UUID who owns the notification

        Raises:
            NotFoundError: If notification doesn't exist or doesn't belong to user
            ProcessingError: For unexpected errors
        """
        try:
            notification = await NotificationService.get_notification_by_id(
                db, notification_id, user_id
            )

            await db.delete(notification)
            await db.commit()

        except NotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            logger.exception(f"Error deleting notification: {str(e)}")
            raise ProcessingError(message="Failed to delete notification")

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
        """
        Get count of unread notifications for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            Count of unread notifications
        """
        query = (
            select(func.count())
            .select_from(Notification)
            .where(and_(Notification.user_id == user_id, Notification.read_at.is_(None)))
        )

        result = await db.execute(query)
        return result.scalar()

    @staticmethod
    async def get_notification_stats(db: AsyncSession, user_id: uuid.UUID) -> Dict:
        """
        Get statistics about user notifications.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            Dict containing notification statistics

        Raises:
            ProcessingError: For unexpected errors
        """
        try:
            total_query = (
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id)
            )
            total_result = await db.execute(total_query)
            total = total_result.scalar()

            unread_count = await NotificationService.get_unread_count(db, user_id)

            pending_query = (
                select(func.count())
                .select_from(Notification)
                .where(
                    and_(
                        Notification.user_id == user_id,
                        Notification.status == NotificationStatus.PENDING,
                    )
                )
            )
            pending_result = await db.execute(pending_query)
            pending = pending_result.scalar()

            type_query = (
                select(Notification.notification_type, func.count(Notification.notification_id))
                .where(Notification.user_id == user_id)
                .group_by(Notification.notification_type)
            )

            type_result = await db.execute(type_query)
            by_type = {row[0]: row[1] for row in type_result.all()}

            return {
                "total_notifications": total,
                "unread_count": unread_count,
                "pending_count": pending,
                "by_type": by_type,
            }

        except Exception as e:
            logger.exception(f"Error fetching notification stats: {str(e)}")
            raise ProcessingError(message="Failed to retrieve notification statistics")

    @staticmethod
    async def get_notification_with_context(
        db: AsyncSession,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Dict:
        """
        Retrieve a notification with related contextual entities.

        Args:
            db: Database session
            notification_id: Notification UUID
            user_id: User UUID who owns the notification

        Returns:
            Dict containing notification and related context

        Raises:
            NotFoundError: If notification doesn't exist or doesn't belong to user
            ProcessingError: For unexpected errors
        """
        try:
            notification = await NotificationService.get_notification_by_id(
                db, notification_id, user_id
            )

            context = {"notification": notification}

            if notification.revision_id:
                from app.api.modules.v1.scraping.models.data_revision import DataRevision

                rev_query = select(DataRevision).where(DataRevision.id == notification.revision_id)
                rev_result = await db.execute(rev_query)
                revision = rev_result.scalar_one_or_none()
                if revision:
                    context["revision"] = revision.model_dump()

            if notification.source_id:
                from app.api.modules.v1.scraping.models.source_model import Source

                source_query = select(Source).where(Source.id == notification.source_id)
                source_result = await db.execute(source_query)
                source = source_result.scalar_one_or_none()
                if source:
                    context["source"] = source.model_dump()

            if notification.organization_id:
                from app.api.modules.v1.organization.models.organization_model import Organization

                org_query = select(Organization).where(
                    Organization.id == notification.organization_id
                )
                org_result = await db.execute(org_query)
                org = org_result.scalar_one_or_none()
                if org:
                    context["organization"] = org.model_dump()

            if notification.change_diff_id:
                from app.api.modules.v1.scraping.models.change_diff import ChangeDiff

                diff_query = select(ChangeDiff).where(
                    ChangeDiff.diff_id == notification.change_diff_id
                )
                diff_result = await db.execute(diff_query)
                diff = diff_result.scalar_one_or_none()
                if diff:
                    context["change_diff"] = diff.model_dump()

            return context

        except NotFoundError:
            raise
        except Exception as e:
            logger.exception(f"Error fetching notification context: {str(e)}")
            raise ProcessingError(message="Failed to retrieve notification context")
