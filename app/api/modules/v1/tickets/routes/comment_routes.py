"""
Comment Routes
API endpoints for ticket comments with real-time updates.

Routes handle request validation and response formatting only.
Business logic is delegated to CommentService.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.comment_auth import CommentAuthor, get_comment_author
from app.api.db.database import get_db
from app.api.modules.v1.tickets.schemas.comment_schemas import CommentResponse
from app.api.modules.v1.tickets.service.comment_service import CommentService
from app.api.utils.response_payloads import success_response

from .docs.comment_routes_docs import (
    create_comment_custom_errors,
    create_comment_custom_success,
    create_comment_responses,
    delete_comment_custom_errors,
    delete_comment_custom_success,
    delete_comment_responses,
    update_comment_custom_errors,
    update_comment_custom_success,
    update_comment_responses,
)

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/tickets/{ticket_id}/comments",
    tags=["Comments"],
)


@router.post("", status_code=status.HTTP_201_CREATED, responses=create_comment_responses)
async def create_comment(
    ticket_id: UUID,
    content: Optional[str] = Form(
        None, max_length=3000, description="Comment text content (max 500 words / ~3000 characters)"
    ),
    images: Optional[List[UploadFile]] = File(
        None,
        description="Image files (max 5, 2MB each, JPEG/PNG/WebP only)",
    ),
    db: AsyncSession = Depends(get_db),
    author: CommentAuthor = Depends(get_comment_author),
):
    """
    Create a new comment on a ticket.

    **Content-Type:** multipart/form-data

    **Path Parameters:**
    - **ticket_id** (required): Ticket UUID

    **Form Fields:**
    - **content** (optional): Comment text content (max 500 words / ~3,000 characters)
    - **images** (optional): Image files to attach (max 5 images, 2MB each)

    *At least one of content or images must be provided.*

    **Supported Image Formats:**
    - JPEG (.jpg, .jpeg)
    - PNG (.png)
    - WebP (.webp)
    - GIF is NOT allowed

    **Image Validation:**
    - Backend validates actual file type using magic bytes (not just extension)
    - Backend calculates size and MIME type from actual file data
    - EXIF metadata is automatically stripped for privacy and security
    - All images uploaded to MinIO storage with secure URLs

    **Possible Errors:**

    **400 Bad Request:**
    - `INVALID_COMMENT_DATA`: At least one of content or images must be provided
    - `INVALID_IMAGE_FORMAT`: Unsupported image format (only JPEG, PNG, WebP allowed)
    - `IMAGE_TOO_LARGE`: Image exceeds 2MB size limit
    - `TOO_MANY_IMAGES`: More than 5 images provided
    - `GIF_NOT_ALLOWED`: GIF format detected and rejected
    - `IMAGE_VALIDATION_ERROR`: Image file is corrupted or invalid
    - `ATTACHMENT_UPLOAD_ERROR`: Failed to upload images to storage

    **401 Unauthorized:**
    - Authentication token is missing or invalid

    **403 Forbidden:**
    - User is not a project member (for internal users)
    - Guest is not invited to this specific ticket (for external participants)

    **404 Not Found:**
    - Ticket does not exist

    **422 Unprocessable Entity:**
    - Invalid UUID format for ticket_id

    **500 Internal Server Error:**
    - Unexpected server error during comment creation

    **Returns:**
    - Created comment with author details, attachment metadata, and timestamps

    **Access Control:**
    - Regular users: Must be a member of the project associated with the ticket
    - External participants (guests): Must have access to this specific ticket

    **Authentication:**
    - Accepts both regular user JWT and guest JWT tokens

    **Real-time:**
    - Broadcasts comment.created event to ticket participants via WebSocket
    """
    service = CommentService(db)
    comment = await service.create_comment(
        ticket_id=ticket_id,
        content=content,
        images=images,
        user_id=author.user_id,
        participant_id=author.participant_id,
    )

    logger.info(f"{author} created comment {comment.comment_id} on ticket {ticket_id}")

    return success_response(
        data=CommentResponse.from_comment(comment),
        message="Comment created successfully",
        status_code=status.HTTP_201_CREATED,
    )


create_comment._custom_errors = create_comment_custom_errors
create_comment._custom_success = create_comment_custom_success


@router.patch("/{comment_id}", status_code=status.HTTP_200_OK, responses=update_comment_responses)
async def update_comment(
    ticket_id: UUID,
    comment_id: UUID,
    content: Optional[str] = Form(
        None, max_length=3000, description="Updated comment text (max 500 words / ~3000 characters)"
    ),
    images: Optional[List[UploadFile]] = File(
        None,
        description="Updated image files (max 5, 2MB each, JPEG/PNG/WebP only)",
    ),
    db: AsyncSession = Depends(get_db),
    author: CommentAuthor = Depends(get_comment_author),
):
    """
    Update a comment.

    **Content-Type:** multipart/form-data

    **Path Parameters:**
    - **ticket_id** (required): Ticket UUID
    - **comment_id** (required): Comment UUID

    **Form Fields:**
    - **content** (optional): Updated comment text content
    - **images** (optional): Updated list of image files

    *At least one of content or images must be provided.*

    **Image Validation:**
    - Same as create: magic bytes verification, EXIF stripping, MinIO upload
    - Supports JPEG, PNG, WebP (max 5 images, 2MB each)

    **Possible Errors:**

    **400 Bad Request:**
    - `INVALID_COMMENT_DATA`: At least one of content or images must be provided
    - `INVALID_IMAGE_FORMAT`: Unsupported image format
    - `IMAGE_TOO_LARGE`: Image exceeds 2MB limit
    - `TOO_MANY_IMAGES`: More than 5 images provided
    - `GIF_NOT_ALLOWED`: GIF format not supported
    - `IMAGE_VALIDATION_ERROR`: Image file corrupted or invalid
    - `ATTACHMENT_UPLOAD_ERROR`: Failed to upload images

    **401 Unauthorized:**
    - Authentication token missing or invalid

    **403 Forbidden:**
    - `COMMENT_OWNERSHIP_ERROR`: Only the comment author can update their comments

    **404 Not Found:**
    - `COMMENT_NOT_FOUND`: Comment does not exist
    - `COMMENT_DELETED`: Comment has been deleted

    **422 Unprocessable Entity:**
    - Invalid UUID format for comment_id or ticket_id

    **500 Internal Server Error:**
    - Unexpected error during update

    **Note:** Updating images REPLACES all existing images with the new set.

    **Returns:**
    - Updated comment with refreshed metadata and timestamps

    **Access Control:**
    - Can only update your own comments (both users and guests)

    **Real-time:**
    - Broadcasts comment.updated event to ticket participants via WebSocket
    """
    service = CommentService(db)
    comment = await service.update_comment(
        comment_id=comment_id,
        content=content,
        images=images,
        user_id=author.user_id,
        participant_id=author.participant_id,
    )

    logger.info(f"{author} updated comment {comment_id}")

    return success_response(
        data=CommentResponse.from_comment(comment),
        message="Comment updated successfully",
        status_code=status.HTTP_200_OK,
    )


update_comment._custom_errors = update_comment_custom_errors
update_comment._custom_success = update_comment_custom_success


@router.delete("/{comment_id}", status_code=status.HTTP_200_OK, responses=delete_comment_responses)
async def delete_comment(
    ticket_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    author: CommentAuthor = Depends(get_comment_author),
):
    """
    Delete a comment (soft delete).

    **Path Parameters:**
    - **ticket_id** (required): Ticket UUID
    - **comment_id** (required): Comment UUID

    **Soft Delete Behavior:**
    - Comment is marked as deleted (sets deleted_at timestamp)
    - Comment data is retained in database for audit purposes
    - Deleted comments do not appear in comment lists

    **Possible Errors:**

    **401 Unauthorized:**
    - Authentication token missing or invalid

    **403 Forbidden:**
    - `COMMENT_OWNERSHIP_ERROR`: Only the comment author can delete their comments

    **404 Not Found:**
    - `COMMENT_NOT_FOUND`: Comment does not exist
    - `COMMENT_DELETED`: Comment already deleted

    **422 Unprocessable Entity:**
    - Invalid UUID format for comment_id or ticket_id

    **500 Internal Server Error:**
    - Unexpected error during deletion

    **Returns:**
    - Success message with HTTP 200

    **Access Control:**
    - Can only delete your own comments (both users and guests)

    **Real-time:**
    - Broadcasts comment.deleted event to ticket participants via WebSocket
    """
    service = CommentService(db)
    await service.delete_comment(
        comment_id=comment_id,
        user_id=author.user_id,
        participant_id=author.participant_id,
    )

    logger.info(f"{author} deleted comment {comment_id}")

    return success_response(
        data=None,
        message="Comment deleted successfully",
        status_code=status.HTTP_200_OK,
    )


delete_comment._custom_errors = delete_comment_custom_errors
delete_comment._custom_success = delete_comment_custom_success
