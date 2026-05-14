"""
Comment Routes Documentation
Comprehensive OpenAPI documentation for ticket comment endpoints.

Includes error responses, success examples, and request/response schemas.
"""

create_comment_responses = {
    201: {
        "description": "Comment Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "text_comment": {
                        "summary": "Text Comment Created",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment created successfully",
                            "status_code": 201,
                            "data": {
                                "comment": {
                                    "comment_id": "c23e4567-e89b-12d3-a456-426614174000",
                                    "ticket_id": "t23e4567-e89b-12d3-a456-426614174001",
                                    "user_id": "u23e4567-e89b-12d3-a456-426614174002",
                                    "participant_id": None,
                                    "content": "This change looks significant and requires "
                                    "immediate review.",
                                    "attachments": None,
                                    "mentioned_user_ids": [],
                                    "is_guest": False,
                                    "author": {
                                        "id": "u23e4567-e89b-12d3-a456-426614174002",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "avatar_url": "https://example.com/avatar.jpg",
                                    },
                                    "created_at": "2026-01-21T10:30:00Z",
                                    "updated_at": None,
                                }
                            },
                        },
                    },
                    "image_comment": {
                        "summary": "Comment with Images",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment created successfully",
                            "status_code": 201,
                            "data": {
                                "comment": {
                                    "comment_id": "c33e4567-e89b-12d3-a456-426614174010",
                                    "ticket_id": "t23e4567-e89b-12d3-a456-426614174001",
                                    "user_id": "u23e4567-e89b-12d3-a456-426614174002",
                                    "participant_id": None,
                                    "content": "See the evidence in the attached screenshots.",
                                    "attachments": [
                                        {
                                            "url": "https://minio.example.com/comment-images/abc123.jpg",
                                            "name": "screenshot-1.png",
                                            "type": "image/png",
                                            "size": 524288,
                                            "metadata": {"uploaded_at": "2026-01-21T10:30:00Z"},
                                        },
                                        {
                                            "url": "https://minio.example.com/comment-images/def456.jpg",
                                            "name": "screenshot-2.jpeg",
                                            "type": "image/jpeg",
                                            "size": 768000,
                                            "metadata": {"uploaded_at": "2026-01-21T10:30:00Z"},
                                        },
                                    ],
                                    "mentioned_user_ids": [],
                                    "is_guest": False,
                                    "author": {
                                        "id": "u23e4567-e89b-12d3-a456-426614174002",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "avatar_url": "https://example.com/avatar.jpg",
                                    },
                                    "created_at": "2026-01-21T10:30:00Z",
                                    "updated_at": None,
                                }
                            },
                        },
                    },
                    "guest_comment": {
                        "summary": "Guest Comment Created",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment created successfully",
                            "status_code": 201,
                            "data": {
                                "comment": {
                                    "comment_id": "c43e4567-e89b-12d3-a456-426614174020",
                                    "ticket_id": "t23e4567-e89b-12d3-a456-426614174001",
                                    "user_id": None,
                                    "participant_id": "p23e4567-e89b-12d3-a456-426614174030",
                                    "content": "As an external party, "
                                    "I have concerns about this change.",
                                    "attachments": None,
                                    "mentioned_user_ids": [],
                                    "is_guest": True,
                                    "author": {
                                        "id": "p23e4567-e89b-12d3-a456-426614174030",
                                        "name": "Guest",
                                        "email": "external@partner.com",
                                        "avatar_url": None,
                                    },
                                    "created_at": "2026-01-21T10:30:00Z",
                                    "updated_at": None,
                                }
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Validation Errors",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_comment_data": {
                        "summary": "At Least One Field Required",
                        "value": {
                            "error_code": "INVALID_COMMENT_DATA",
                            "message": "At least one of 'content' or 'images' must be provided",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_image_format": {
                        "summary": "Invalid Image Format",
                        "value": {
                            "error_code": "INVALID_IMAGE_FORMAT",
                            "message": "Unsupported image format. Only JPEG, PNG, "
                            "and WebP are allowed. GIF is not supported.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "image_too_large": {
                        "summary": "Image Exceeds Size Limit",
                        "value": {
                            "error_code": "IMAGE_TOO_LARGE",
                            "message": "Image 'screenshot.jpg' exceeds 2MB limit (size: 3.5MB)",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "too_many_images": {
                        "summary": "Too Many Images",
                        "value": {
                            "error_code": "TOO_MANY_IMAGES",
                            "message": "Maximum 5 images per comment. You provided 7 images.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "gif_not_allowed": {
                        "summary": "GIF Format Not Allowed",
                        "value": {
                            "error_code": "GIF_NOT_ALLOWED",
                            "message": "GIF images are not supported. Please use JPEG, PNG, "
                            "or WebP instead.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "image_validation_error": {
                        "summary": "Image Validation Failed",
                        "value": {
                            "error_code": "IMAGE_VALIDATION_ERROR",
                            "message": "Image file is corrupted or not a valid image",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "attachment_upload_error": {
                        "summary": "Image Upload to Storage Failed",
                        "value": {
                            "error_code": "ATTACHMENT_UPLOAD_ERROR",
                            "message": "Failed to upload images to storage. Please try again.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "Authentication Required",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "no_ticket_access": {
                        "summary": "No Access to Ticket",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You must be a member of the project to access this ticket",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "guest_not_invited": {
                        "summary": "Guest Not Invited to Ticket",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You do not have access to this ticket",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "ticket_not_found": {
                        "summary": "Ticket Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The ticket doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid Request Parameters",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "ticket_id": ["Input should be a valid UUID"],
                            },
                        },
                    },
                },
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to create comment. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Unexpected Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
}

create_comment_custom_errors = ["400", "401", "403", "404", "422", "500"]

create_comment_custom_success = {
    "status_code": 201,
    "description": "Comment created successfully with validated images (magic byte verification, "
    "EXIF stripped). "
    "Broadcasts real-time event to ticket participants. "
    "Accessible by project members and external participants (guests) invited to the ticket.",
}


update_comment_responses = {
    200: {
        "description": "Comment Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "content_updated": {
                        "summary": "Content Updated",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment updated successfully",
                            "status_code": 200,
                            "data": {
                                "comment": {
                                    "comment_id": "c23e4567-e89b-12d3-a456-426614174000",
                                    "ticket_id": "t23e4567-e89b-12d3-a456-426614174001",
                                    "user_id": "u23e4567-e89b-12d3-a456-426614174002",
                                    "participant_id": None,
                                    "content": "Updated: This change requires immediate attention "
                                    "and escalation.",
                                    "attachments": None,
                                    "mentioned_user_ids": [],
                                    "is_guest": False,
                                    "author": {
                                        "id": "u23e4567-e89b-12d3-a456-426614174002",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "avatar_url": "https://example.com/avatar.jpg",
                                    },
                                    "created_at": "2026-01-21T10:30:00Z",
                                    "updated_at": "2026-01-21T11:00:00Z",
                                }
                            },
                        },
                    },
                    "images_replaced": {
                        "summary": "Images Replaced",
                        "description": "Note: Updating images replaces all existing images with "
                        "the new set",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment updated successfully",
                            "status_code": 200,
                            "data": {
                                "comment": {
                                    "comment_id": "c23e4567-e89b-12d3-a456-426614174000",
                                    "ticket_id": "t23e4567-e89b-12d3-a456-426614174001",
                                    "user_id": "u23e4567-e89b-12d3-a456-426614174002",
                                    "participant_id": None,
                                    "content": "Here are the updated screenshots.",
                                    "attachments": [
                                        {
                                            "url": "https://minio.example.com/comment-images/xyz789.jpg",
                                            "name": "new-screenshot.png",
                                            "type": "image/png",
                                            "size": 512000,
                                            "metadata": {"uploaded_at": "2026-01-21T11:00:00Z"},
                                        },
                                    ],
                                    "mentioned_user_ids": [],
                                    "is_guest": False,
                                    "author": {
                                        "id": "u23e4567-e89b-12d3-a456-426614174002",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "avatar_url": "https://example.com/avatar.jpg",
                                    },
                                    "created_at": "2026-01-21T10:30:00Z",
                                    "updated_at": "2026-01-21T11:00:00Z",
                                }
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Validation Errors",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_comment_data": {
                        "summary": "At Least One Field Required",
                        "value": {
                            "error_code": "INVALID_COMMENT_DATA",
                            "message": "At least one of 'content' or 'images' must be provided",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_image_format": {
                        "summary": "Invalid Image Format",
                        "value": {
                            "error_code": "INVALID_IMAGE_FORMAT",
                            "message": "Unsupported image format. Only JPEG, PNG, "
                            "and WebP are allowed.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "image_too_large": {
                        "summary": "Image Exceeds Size Limit",
                        "value": {
                            "error_code": "IMAGE_TOO_LARGE",
                            "message": "Image exceeds 2MB limit",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "too_many_images": {
                        "summary": "Too Many Images",
                        "value": {
                            "error_code": "TOO_MANY_IMAGES",
                            "message": "Maximum 5 images per comment",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "Authentication Required",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "not_comment_author": {
                        "summary": "Not Comment Author",
                        "value": {
                            "error_code": "COMMENT_OWNERSHIP_ERROR",
                            "message": "You can only update your own comments",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "comment_not_found": {
                        "summary": "Comment Not Found",
                        "value": {
                            "error_code": "COMMENT_NOT_FOUND",
                            "message": "Comment not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "comment_deleted": {
                        "summary": "Comment Already Deleted",
                        "value": {
                            "error_code": "COMMENT_DELETED",
                            "message": "This comment has been deleted",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid Request Parameters",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "comment_id": ["Input should be a valid UUID"],
                            },
                        },
                    },
                },
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to update comment. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
}

update_comment_custom_errors = ["400", "401", "403", "404", "422", "500"]

update_comment_custom_success = {
    "status_code": 200,
    "description": "Comment updated successfully. Only the comment author can update. "
    "Updating images replaces all existing images with the new set. "
    "Broadcasts real-time event to ticket participants.",
}


delete_comment_responses = {
    200: {
        "description": "Comment Deleted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Comment Deleted",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Comment deleted successfully",
                            "status_code": 200,
                            "data": None,
                        },
                    },
                },
            },
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "Authentication Required",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "not_comment_author": {
                        "summary": "Not Comment Author",
                        "value": {
                            "error_code": "COMMENT_OWNERSHIP_ERROR",
                            "message": "You can only delete your own comments",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "comment_not_found": {
                        "summary": "Comment Not Found",
                        "value": {
                            "error_code": "COMMENT_NOT_FOUND",
                            "message": "Comment not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "already_deleted": {
                        "summary": "Already Deleted",
                        "value": {
                            "error_code": "COMMENT_DELETED",
                            "message": "This comment is already deleted.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid Request Parameters",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "comment_id": ["Input should be a valid UUID"],
                            },
                        },
                    },
                },
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to delete comment. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
}

delete_comment_custom_errors = ["401", "403", "404", "422", "500"]

delete_comment_custom_success = {
    "status_code": 200,
    "description": "Comment deleted successfully (soft delete). "
    "Only the comment author can delete. "
    "Broadcasts real-time event to ticket participants.",
}
