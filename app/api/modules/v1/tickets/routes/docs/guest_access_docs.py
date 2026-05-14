guest_ticket_access_responses = {
    200: {
        "description": "Guest Access Validated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Guest Ticket Access Granted",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Guest access validated successfully",
                            "status_code": 200,
                            "data": {
                                "ticket_id": "123e4567-e89b-12d3-a456-426614174000",
                                "title": "Legal Review Required",
                                "description": "Review the contract terms",
                                "priority": "MEDIUM",
                                "status": "OPEN",
                                "created_at": "2023-10-01T10:00:00Z",
                                "project_name": "Legal Compliance Project",
                                "participant_email": "counsel@lawfirm.com",
                                "participant_role": "REVIEWER",
                                "access_expires_at": "2023-10-03T10:00:00Z",
                            },
                        },
                    },
                },
            },
        },
    },
    401: {
        "description": "Unauthorized - Invalid or Expired Token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Invalid Access Token",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Invalid token or expired token",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_expired": {
                        "summary": "Access Token Expired",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Token has expired",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "ticket_closed": {
                        "summary": "Ticket Is Closed",
                        "value": {
                            "error_code": "FORBIDDEN",
                            "message": "This ticket is closed and no longer accessible",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "participant_inactive": {
                        "summary": "Participant Is Inactive",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "Your access has been revoked",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Ticket Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "ticket_not_found": {
                        "summary": "Ticket Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Ticket not found or has been deleted",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "participant_not_found": {
                        "summary": "Participant Record Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Access record not found",
                            "status_code": 404,
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
                            "message": "Failed to load ticket. Please try again "
                            "or contact support.",
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

guest_ticket_access_custom_errors = ["401", "403", "404", "500"]

guest_ticket_access_custom_success = {
    "status_code": 200,
    "description": "Guest access token validated successfully. Ticket details returned.",
}
