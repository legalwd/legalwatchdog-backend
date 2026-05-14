"""
Comment Service
Business logic for comment operations with real-time updates and attachment handling.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select

from app.api.core.custom_exceptions.exceptions import (
    AttachmentUploadError,
    CommentDeletedError,
    CommentNotFoundError,
    CommentOwnershipError,
    InvalidCommentDataError,
    NotFoundError,
    PermissionDeniedError,
    ProcessingError,
)
from app.api.events.factory import get_event_publisher
from app.api.events.models import TicketCommentEvent
from app.api.modules.v1.projects.utils.project_utils import check_project_user_exists
from app.api.modules.v1.scraping.storage.minio_storage import upload_raw_content
from app.api.modules.v1.tickets.models.comment_model import Comment
from app.api.modules.v1.tickets.models.ticket_model import ExternalParticipant, Ticket
from app.api.utils.image_validator import validate_images

logger = logging.getLogger("app")


class CommentService:
    """Service for comment operations with attachment handling and real-time updates."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db

    async def create_comment(
        self,
        ticket_id: UUID,
        content: Optional[str] = None,
        images: Optional[List[UploadFile]] = None,
        user_id: Optional[UUID] = None,
        participant_id: Optional[UUID] = None,
    ) -> Comment:
        """
        Create a new comment on a ticket with optional attachments.

        Args:
            ticket_id: Ticket UUID
            content: Comment text content (optional if images provided)
            images: List of uploaded image files (optional if content provided)
            user_id: User creating the comment (internal)
            participant_id: External participant creating the comment (guest)

        Returns:
            Created Comment object with author relationships

        Raises:
            InvalidCommentDataError: If neither content nor images provided
            NotFoundError: If ticket not found
            PermissionDeniedError: If user lacks access
            AttachmentUploadError: If attachment upload fails
            ProcessingError: For unexpected errors
        """
        try:
            if not user_id and not participant_id:
                raise InvalidCommentDataError("Either user_id or participant_id must be provided")

            if not content and not images:
                raise InvalidCommentDataError(
                    message="At least one of 'content' or 'images' must be provided"
                )

            ticket = await self._get_ticket_with_access_check(
                ticket_id=ticket_id,
                user_id=user_id,
                participant_id=participant_id,
            )

            mentioned_user_ids = None

            processed_attachments = None
            if images:
                image_data = []
                for img_file in images:
                    data = await img_file.read()
                    image_data.append(
                        {
                            "filename": img_file.filename,
                            "data": data,
                        }
                    )

                is_valid, errors, processed = validate_images(image_data)
                if not is_valid:
                    raise AttachmentUploadError(message="; ".join(errors))
                processed_attachments = await self._upload_images_to_minio(processed)

            comment = Comment(
                ticket_id=ticket_id,
                user_id=user_id,
                participant_id=participant_id,
                content=content,
                attachments=processed_attachments,
                mentioned_user_ids=mentioned_user_ids,
            )

            self.db.add(comment)
            await self.db.flush()
            await self.db.refresh(
                comment,
                ["user", "participant"],
            )
            await self.db.commit()

            author_type = "user" if user_id else "participant"
            author_id = user_id or participant_id
            logger.info(
                f"Created comment {comment.comment_id} on ticket {ticket_id} "
                f"by {author_type} {author_id}",
                extra={"ticket_id": str(ticket_id), "comment_id": str(comment.comment_id)},
            )

            await self._publish_comment_event(
                event="comment.created",
                comment=comment,
                ticket=ticket,
            )

            return comment

        except (
            InvalidCommentDataError,
            NotFoundError,
            PermissionDeniedError,
            AttachmentUploadError,
        ):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error creating comment on ticket {ticket_id}: {str(e)}")
            raise ProcessingError(message="Failed to create comment. Please try again.")

    async def update_comment(
        self,
        comment_id: UUID,
        content: Optional[str] = None,
        images: Optional[List[UploadFile]] = None,
        user_id: Optional[UUID] = None,
        participant_id: Optional[UUID] = None,
    ) -> Comment:
        """
        Update a comment's content and/or attachments.

        Args:
            comment_id: Comment UUID
            content: Updated comment text (optional)
            images: Updated list of image files (optional)
            user_id: User updating (internal)
            participant_id: Guest updating (external)

        Returns:
            Updated Comment object

        Raises:
            CommentNotFoundError: If comment doesn't exist
            CommentDeletedError: If comment was deleted
            CommentOwnershipError: If not the author
            InvalidCommentDataError: If no content/images in update
            AttachmentUploadError: If attachment upload fails
            ProcessingError: For unexpected errors
        """
        try:
            query = (
                select(Comment)
                .where(Comment.comment_id == comment_id)
                .options(
                    selectinload(Comment.user),
                    selectinload(Comment.participant),
                    selectinload(Comment.ticket),
                )
            )
            result = await self.db.execute(query)
            comment = result.scalar_one_or_none()

            if not comment:
                raise CommentNotFoundError()

            if comment.deleted_at:
                raise CommentDeletedError()

            is_owner = (user_id and comment.user_id == user_id) or (
                participant_id and comment.participant_id == participant_id
            )
            if not is_owner:
                raise CommentOwnershipError()

            if not content and not images:
                raise InvalidCommentDataError(
                    message="At least one of 'content' or 'images' must be provided"
                )

            if images:
                image_data = []
                for img_file in images:
                    data = await img_file.read()
                    image_data.append(
                        {
                            "filename": img_file.filename,
                            "data": data,
                        }
                    )

                is_valid, errors, processed = validate_images(image_data)
                if not is_valid:
                    raise AttachmentUploadError(message="; ".join(errors))
                comment.attachments = await self._upload_images_to_minio(processed)

            if content is not None:
                comment.content = content
                # Extract mentions from updated content
                # Note: For now, we don't update mentioned_user_ids as it requires DB lookups
                # TODO: Implement mention resolution to convert @mentions to user UUIDs

            comment.updated_at = datetime.now(timezone.utc)

            await self.db.commit()
            await self.db.refresh(comment)

            logger.info(
                f"Updated comment {comment_id}",
                extra={"comment_id": str(comment_id), "ticket_id": str(comment.ticket_id)},
            )

            await self._publish_comment_event(
                event="comment.updated",
                comment=comment,
                ticket=comment.ticket,
            )

            return comment

        except (
            CommentNotFoundError,
            CommentDeletedError,
            CommentOwnershipError,
            InvalidCommentDataError,
            AttachmentUploadError,
        ):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error updating comment {comment_id}: {str(e)}")
            raise ProcessingError(message="Failed to update comment. Please try again.")

    async def delete_comment(
        self,
        comment_id: UUID,
        user_id: Optional[UUID] = None,
        participant_id: Optional[UUID] = None,
    ) -> None:
        """
        Soft delete a comment.

        Args:
            comment_id: Comment UUID
            user_id: User deleting (internal)
            participant_id: Guest deleting (external)

        Raises:
            CommentNotFoundError: If comment doesn't exist
            CommentDeletedError: If already deleted
            CommentOwnershipError: If not the author
            ProcessingError: For unexpected errors
        """
        try:
            query = (
                select(Comment)
                .where(Comment.comment_id == comment_id)
                .options(selectinload(Comment.ticket))
            )
            result = await self.db.execute(query)
            comment = result.scalar_one_or_none()

            if not comment:
                raise CommentNotFoundError()

            if comment.deleted_at:
                raise CommentDeletedError("This comment is already deleted.")

            is_owner = (user_id and comment.user_id == user_id) or (
                participant_id and comment.participant_id == participant_id
            )
            if not is_owner:
                raise CommentOwnershipError()

            comment.deleted_at = datetime.now(timezone.utc)
            await self.db.commit()

            logger.info(
                f"Deleted comment {comment_id}",
                extra={"comment_id": str(comment_id), "ticket_id": str(comment.ticket_id)},
            )

            await self._publish_comment_event(
                event="comment.deleted",
                comment=comment,
                ticket=comment.ticket,
            )

        except (CommentNotFoundError, CommentDeletedError, CommentOwnershipError):
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error deleting comment {comment_id}: {str(e)}")
            raise ProcessingError(message="Failed to delete comment. Please try again.")

    def _extract_mentions(self, content: str) -> list[str]:
        """
        Extract @mentions from content text.

        Args:
            content: Comment text content

        Returns:
            List of mentioned usernames/identifiers (empty if none found)
        """
        if not content:
            return []

        # Find all @mention patterns (usernames: letters, numbers, dots, hyphens, underscores)
        mention_pattern = r"@([\w.-]+)"
        matches = re.findall(mention_pattern, content)

        if not matches:
            return []

        unique_mentions = list(dict.fromkeys(matches))
        return unique_mentions

    async def _upload_images_to_minio(self, images: list) -> list:
        """
        Upload validated and cleaned images to MinIO storage.

        Args:
            images: List of processed image dicts with validated data and cleaned metadata

        Returns:
            List of attachment metadata with MinIO URLs

        Raises:
            AttachmentUploadError: If upload fails
        """
        try:
            uploaded = []
            for image in images:
                image_id = uuid.uuid4()
                filename = f"comment-images/{image_id}.{
                    'jpg'
                    if image['mime_type'] == 'image/jpeg'
                    else image['mime_type'].split('/')[-1]
                }"

                image_bytes = image.get("data", b"")
                url = await upload_raw_content(
                    content=image_bytes,
                    filename=filename,
                    content_type=image["mime_type"],
                )

                uploaded.append(
                    {
                        "url": url,
                        "name": image["filename"],
                        "type": image["mime_type"],
                        "size": image["size"],
                        "metadata": {"uploaded_at": datetime.now(timezone.utc).isoformat()},
                    }
                )

            return uploaded

        except AttachmentUploadError:
            raise
        except Exception as e:
            logger.exception(f"Error uploading images to MinIO: {str(e)}")
            raise AttachmentUploadError(message="Failed to upload images. Please try again.")

    async def _process_attachments(self, attachments: list) -> list:
        """
        Process and upload attachments to MinIO.

        Args:
            attachments: List of AttachmentInfo objects with urls

        Returns:
            List of processed attachment metadata with MinIO urls

        Raises:
            AttachmentUploadError: If upload fails
        """
        try:
            processed = []
            for attachment in attachments:
                # Attachments should already have URLs from frontend
                # For now, we just validate and store the metadata
                if not attachment.url:
                    raise AttachmentUploadError(message="Attachment must have a URL")

                processed.append(
                    {
                        "url": attachment.url,
                        "name": attachment.name,
                        "type": attachment.type,
                        "size": attachment.size,
                        "metadata": attachment.metadata,
                    }
                )

            return processed

        except AttachmentUploadError:
            raise
        except Exception as e:
            logger.exception(f"Error processing attachments: {str(e)}")
            raise AttachmentUploadError()

    async def _get_ticket_with_access_check(
        self,
        ticket_id: UUID,
        user_id: Optional[UUID] = None,
        participant_id: Optional[UUID] = None,
    ) -> Ticket:
        """
        Get ticket and verify access permissions.

        For users: Check project membership
        For guests: Check participant is registered for this ticket

        Args:
            ticket_id: Ticket UUID
            user_id: User ID (if internal)
            participant_id: Participant ID (if guest)

        Returns:
            Ticket object if access granted

        Raises:
            NotFoundError: If ticket doesn't exist
            PermissionDeniedError: If access denied
        """
        try:
            query = select(Ticket).where(Ticket.id == ticket_id)
            result = await self.db.execute(query)
            ticket = result.scalar_one_or_none()

            if not ticket:
                raise NotFoundError(message="The ticket doesn't exist.")

            if user_id:
                is_member = await check_project_user_exists(self.db, ticket.project_id, user_id)
                if not is_member:
                    raise PermissionDeniedError(
                        message="You must be a member of the project to access this ticket"
                    )
            elif participant_id:
                participant_query = select(ExternalParticipant).where(
                    and_(
                        ExternalParticipant.id == participant_id,
                        ExternalParticipant.ticket_id == ticket_id,
                        ExternalParticipant.is_active,
                    )
                )
                participant_result = await self.db.execute(participant_query)
                participant = participant_result.scalar_one_or_none()

                if not participant:
                    raise PermissionDeniedError(message="You do not have access to this ticket")
            else:
                raise InvalidCommentDataError(
                    message="Either user_id or participant_id must be provided"
                )

            return ticket

        except (NotFoundError, PermissionDeniedError, InvalidCommentDataError):
            raise
        except Exception as e:
            logger.exception(f"Error checking ticket access for {ticket_id}: {str(e)}")
            raise ProcessingError(message="Failed to verify access. Please try again.")

    async def _publish_comment_event(
        self,
        event: str,
        comment: Comment,
        ticket: Ticket,
    ) -> None:
        """
        Publish real-time comment event via WebSocket.

        Args:
            event: Event type (comment.created, comment.updated, comment.deleted)
            comment: Comment object
            ticket: Ticket object
        """
        try:
            publisher = await get_event_publisher()

            recipient_ids = set()

            if ticket.created_by_user_id:
                recipient_ids.add(ticket.created_by_user_id)
            if ticket.assigned_to_user_id:
                recipient_ids.add(ticket.assigned_to_user_id)

            if comment.mentioned_user_ids:
                recipient_ids.update(comment.mentioned_user_ids)

            if comment.user_id and comment.user_id in recipient_ids:
                recipient_ids.discard(comment.user_id)

            if comment.user:
                author_name = comment.user.name
                author_avatar_url = comment.user.avatar_url
                is_guest = False
            elif comment.participant:
                author_name = "Guest"
                author_avatar_url = None
                is_guest = True
            else:
                author_name = "Unknown"
                author_avatar_url = None
                is_guest = False

            comment_event = TicketCommentEvent(
                event=event,
                payload={
                    "comment_id": str(comment.comment_id),
                    "ticket_id": str(comment.ticket_id),
                    "content": comment.content,
                    "attachments": comment.attachments,
                    "user_id": str(comment.user_id) if comment.user_id else None,
                    "participant_id": str(comment.participant_id)
                    if comment.participant_id
                    else None,
                    "author_name": author_name,
                    "author_avatar_url": author_avatar_url,
                    "is_guest": is_guest,
                    "mentioned_user_ids": [str(uid) for uid in (comment.mentioned_user_ids or [])],
                    "mentioned_participant_ids": [
                        str(uid) for uid in (comment.mentioned_participant_ids or [])
                    ],
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                },
                recipient_ids=list(recipient_ids),
            )

            await publisher.publish(comment_event)
            logger.debug(
                f"Published {event} event for comment {comment.comment_id}",
                extra={"event": event, "comment_id": str(comment.comment_id)},
            )

        except Exception as e:
            logger.error(
                f"Failed to publish comment event: {e}",
                extra={"event": event, "comment_id": str(comment.comment_id)},
                exc_info=True,
            )
