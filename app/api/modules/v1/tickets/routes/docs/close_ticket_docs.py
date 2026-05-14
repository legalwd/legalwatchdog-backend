close_ticket_responses = {
    200: {
        "description": "Ticket Closed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Ticket Closed",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Ticket closed successfully",
                            "status_code": 200,
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "title": "Bug Fix Required",
                                "description": "Fix the login issue",
                                "status": "CLOSED",
                                "priority": "HIGH",
                                "closing_notes": "Fixed the authentication issue",
                                "closed_by_id": "123e4567-e89b-12d3-a456-426614174000",
                                "closed_at": "2023-10-01T12:00:00Z",
                                "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                "project_id": "123e4567-e89b-12d3-a456-426614174000",
                                "created_by_id": "123e4567-e89b-12d3-a456-426614174000",
                                "created_at": "2023-10-01T10:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "no_permission": {
                        "summary": "No Permission to Close Tickets",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to close tickets. "
                            "Please contact your organization administrator.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "not_in_organization": {
                        "summary": "Not in Organization",
                        "value": {
                            "error_code": "USER_NOT_IN_ORGANIZATION",
                            "message": "The user is not part of the organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "ticket_project_mismatch": {
                        "summary": "Ticket Project Mismatch",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "This ticket doesn't belong to the specified project.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "ticket_org_mismatch": {
                        "summary": "Ticket Organization Mismatch",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "This ticket doesn't belong to your organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Resource Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "ticket_not_found": {
                        "summary": "Ticket Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The ticket you're trying to close doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "User not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    409: {
        "description": "Conflict - Ticket Already Closed",
        "content": {
            "application/json": {
                "examples": {
                    "already_closed": {
                        "summary": "Ticket Already Closed",
                        "value": {
                            "error_code": "RESOURCE_EXISTS",
                            "message": "This ticket is already closed",
                            "status_code": 409,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "closing_notes": ["String should have at most 1000 characters"],
                            },
                        },
                    },
                }
            }
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
                            "message": "Failed to close ticket. Please try again.",
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

close_ticket_custom_errors = ["403", "404", "409", "422", "500"]
close_ticket_custom_success = {
    "status_code": 200,
    "description": "Ticket closed successfully with optional closing notes.",
}
