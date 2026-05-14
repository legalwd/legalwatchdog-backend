get_notifications_responses = {
    200: {
        "description": "Notifications Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notifications List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Notifications retrieved successfully",
                            "data": {
                                "notifications": [
                                    {
                                        "notification_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "user_id": "987e6543-e21b-12d3-a456-426614174000",
                                        "title": "New project assigned",
                                        "content": "You have been assigned to Project Alpha",
                                        "notification_type": "CHANGE_DETECTED",
                                        "status": "PENDING",
                                        "organization_id": "456e7890-e12b-34d5-a678-426614174000",
                                        "revision_id": "456e7890-e12b-34d5-a678-426614174000",
                                        "change_diff_id": "456e7890-e12b-34d5-a678-426614174000",
                                        "action_url": "https://app.example.com/notifications/123e4567-e89b-12d3-a456-426614174000",
                                        "source_id": "789e0123-e45b-67d8-a901-426614174000",
                                        "jurisdiction_id": "789e0123-e45b-67d8-a901-426614174000",
                                        "created_at": "2024-01-15T10:30:00Z",
                                        "updated_at": "2024-01-15T10:30:00Z",
                                    }
                                ],
                                "total": 45,
                                "page": 1,
                                "page_size": 50,
                                "unread_count": 12,
                            },
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
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
                    "invalid_page": {
                        "summary": "Invalid Page Number",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "page": ["Input should be greater than or equal to 1"],
                            },
                        },
                    },
                    "invalid_page_size": {
                        "summary": "Invalid Page Size",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "page_size": ["Input should be less than or equal to 100"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve notifications",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

get_notifications_custom_errors = ["401", "422", "500"]
get_notifications_custom_success = {
    "status_code": 200,
    "description": "Notifications retrieved successfully.",
}

get_notification_responses = {
    200: {
        "description": "Notification Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notification Details",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Notification retrieved successfully",
                            "data": {
                                "notification_id": "123e4567-e89b-12d3-a456-426614174000",
                                "user_id": "987e6543-e21b-12d3-a456-426614174000",
                                "title": "New project assigned",
                                "content": "You have been assigned to Project Alpha",
                                "notification_type": "CHANGE_DETECTED",
                                "status": "PENDING",
                                "organization_id": "456e7890-e12b-34d5-a678-426614174000",
                                "revision_id": "456e7890-e12b-34d5-a678-426614174000",
                                "change_diff_id": "456e7890-e12b-34d5-a678-426614174000",
                                "action_url": "https://app.example.com/notifications/123e4567-e89b-12d3-a456-426614174000",
                                "source_id": "789e0123-e45b-67d8-a901-426614174000",
                                "jurisdiction_id": "789e0123-e45b-67d8-a901-426614174000",
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:30:00Z",
                            },
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Notification Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "notification_not_found": {
                        "summary": "Notification Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Notification not found for the user",
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
                    "invalid_uuid": {
                        "summary": "Invalid Notification ID Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "notification_id": ["Invalid UUID format"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve notification",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

get_notification_custom_errors = ["401", "404", "422", "500"]
get_notification_custom_success = {
    "status_code": 200,
    "description": "Notification retrieved successfully.",
}

get_notification_context_responses = {
    200: {
        "description": "Notification Context Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notification with Full Context",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Notification context retrieved successfully",
                            "data": {
                                "notification": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "title": "New project assigned",
                                    "content": "You have been assigned to Project Alpha",
                                    "notification_type": "PROJECT_ASSIGNMENT",
                                    "is_read": False,
                                    "created_at": "2024-01-15T10:30:00Z",
                                },
                                "context": {
                                    "project": {
                                        "id": "789e0123-e45b-67d8-a901-426614174000",
                                        "name": "Project Alpha",
                                        "status": "ACTIVE",
                                    },
                                    "organization": {
                                        "id": "456e7890-e12b-34d5-a678-426614174000",
                                        "name": "Acme Corporation",
                                    },
                                    "source": {
                                        "id": "321e4567-e89b-12d3-a456-426614174000",
                                        "type": "PROJECT",
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {
                        "summary": "Invalid Request",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid request parameters",
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Notification Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "notification_not_found": {
                        "summary": "Notification Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Notification not found",
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
                    "invalid_uuid": {
                        "summary": "Invalid Notification ID Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "notification_id": ["Invalid UUID format"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve notification context. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

get_notification_context_custom_errors = ["400", "401", "404", "422", "500"]
get_notification_context_custom_success = {
    "status_code": 200,
    "description": "Notification context retrieved successfully.",
}

update_notification_responses = {
    200: {
        "description": "Notification Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notification Updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Notification updated successfully",
                            "data": {
                                "notification_id": "123e4567-e89b-12d3-a456-426614174000",
                                "user_id": "987e6543-e21b-12d3-a456-426614174000",
                                "title": "New project assigned",
                                "content": "You have been assigned to Project Alpha",
                                "notification_type": "CHANGE_DETECTED",
                                "status": "PENDING",
                                "organization_id": "456e7890-e12b-34d5-a678-426614174000",
                                "revision_id": "456e7890-e12b-34d5-a678-426614174000",
                                "change_diff_id": "456e7890-e12b-34d5-a678-426614174000",
                                "action_url": "https://app.example.com/notifications/123e4567-e89b-12d3-a456-426614174000",
                                "source_id": "789e0123-e45b-67d8-a901-426614174000",
                                "jurisdiction_id": "789e0123-e45b-67d8-a901-426614174000",
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:30:00Z",
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Update Error",
        "content": {
            "application/json": {
                "examples": {
                    "no_updates_provided": {
                        "summary": "No Update Fields Provided",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "No update fields provided",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_status": {
                        "summary": "Invalid Status Value",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid notification status",
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Notification Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "notification_not_found": {
                        "summary": "Notification Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Notification not found",
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
                    "invalid_uuid": {
                        "summary": "Invalid Notification ID Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "notification_id": ["Invalid UUID format"],
                            },
                        },
                    },
                    "invalid_field_type": {
                        "summary": "Invalid Field Type",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "is_read": ["Input should be a valid boolean"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to update notification. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

update_notification_custom_errors = ["400", "401", "404", "422", "500"]
update_notification_custom_success = {
    "status_code": 200,
    "description": "Notification updated successfully.",
}

mark_notifications_read_responses = {
    200: {
        "description": "Notifications Marked as Read Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notifications Marked as Read",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Marked 5 notification(s) as read",
                            "data": {
                                "count": 5,
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "no_ids_provided": {
                        "summary": "No Notification IDs Provided",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "No notification IDs provided",
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
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
                    "invalid_payload": {
                        "summary": "Invalid Request Payload",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "notification_ids": ["Field required"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to mark notifications as read",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

mark_notifications_read_custom_errors = ["400", "401", "422", "500"]
mark_notifications_read_custom_success = {
    "status_code": 200,
    "description": "Notifications marked as read successfully.",
}

mark_all_read_responses = {
    200: {
        "description": "All Notifications Marked as Read Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "All Notifications Marked as Read",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Marked 12 notification(s) as read",
                            "data": {
                                "count": 12,
                            },
                        },
                    },
                    "no_unread": {
                        "summary": "No Unread Notifications",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Marked 0 notification(s) as read",
                            "data": {
                                "count": 0,
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {
                        "summary": "Invalid Request",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid request",
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to mark all notifications as read. Please try.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

mark_all_read_custom_errors = ["400", "401", "500"]
mark_all_read_custom_success = {
    "status_code": 200,
    "description": "All notifications marked as read successfully.",
}

delete_notification_responses = {
    204: {
        "description": "Notification Deleted Successfully",
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {
                        "summary": "Invalid Request",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid request parameters",
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
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Notification Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "notification_not_found": {
                        "summary": "Notification Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Notification not found",
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
                    "invalid_uuid": {
                        "summary": "Invalid Notification ID Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "notification_id": ["Invalid UUID format"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to delete notification. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
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

delete_notification_custom_errors = ["400", "401", "404", "422", "500"]
delete_notification_custom_success = {
    "status_code": 204,
}

get_notification_stats_responses = {
    200: {
        "description": "Notification Statistics Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Notification Statistics",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Notification statistics retrieved successfully",
                            "data": {
                                "total_notifications": 45,
                                "unread_count": 12,
                                "read_count": 33,
                                "by_type": {
                                    "PROJECT_ASSIGNMENT": 15,
                                    "TASK_UPDATE": 20,
                                    "COMMENT": 8,
                                    "MENTION": 2,
                                },
                                "by_status": {
                                    "PENDING": 12,
                                    "READ": 30,
                                    "ARCHIVED": 3,
                                },
                                "recent_activity": {
                                    "last_24_hours": 5,
                                    "last_7_days": 18,
                                    "last_30_days": 45,
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {
                        "summary": "Invalid Request",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid request parameters",
                            "status_code": 400,
                            "errors": {},
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
                        "not_authenticated": {
                            "summary": "User Not Authenticated",
                            "value": {
                                "error_code": "UNAUTHORIZED",
                                "message": "Authentication required",
                                "status_code": 401,
                                "errors": {},
                            },
                        },
                    },
                }
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve notification statistics. "
                            "Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}


get_notification_stats_custom_errors = ["400", "401", "500"]
get_notification_stats_custom_success = {
    "status_code": 200,
    "description": "Notification statistics retrieved successfully.",
}
