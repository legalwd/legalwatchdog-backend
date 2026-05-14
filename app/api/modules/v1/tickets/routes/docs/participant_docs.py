invite_participants_responses = {
    201: {
        "description": "Participants Invited Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Participants Invited",
                        "value": {
                            "status": "SUCCESS",
                            "message": "2 internal user(s) notified. "
                            "3 external participant(s) invited. "
                            "1 email(s) already invited.",
                            "status_code": 201,
                            "data": {
                                "internal_users": [
                                    {
                                        "email": "john@company.com",
                                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "notified": True,
                                    },
                                    {
                                        "email": "jane@company.com",
                                        "user_id": "223e4567-e89b-12d3-a456-426614174001",
                                        "notified": True,
                                    },
                                ],
                                "external_participants": [
                                    {
                                        "email": "counsel@lawfirm.com",
                                        "participant_id": "323e4567-e89b-12d3-a456-426614174002",
                                        "invitation_sent": True,
                                        "magic_link": "https://app.example.com/guest/access?token=eyJhbGciOi...&client=local",
                                    },
                                    {
                                        "email": "expert@consulting.com",
                                        "participant_id": "423e4567-e89b-12d3-a456-426614174003",
                                        "invitation_sent": True,
                                        "magic_link": "https://app.example.com/guest/access?token=eyJhbGciOi...&client=local",
                                    },
                                    {
                                        "email": "reviewer@agency.gov",
                                        "participant_id": "523e4567-e89b-12d3-a456-426614174004",
                                        "invitation_sent": True,
                                        "magic_link": "https://app.example.com/guest/access?token=eyJhbGciOi...&client=local",
                                    },
                                ],
                                "already_invited": [
                                    {
                                        "email": "existing@partner.com",
                                        "reason": "Already invited to this ticket",
                                    }
                                ],
                                "not_in_project": [],
                            },
                        },
                    },
                    "only_internal": {
                        "summary": "Only Internal Users Invited",
                        "value": {
                            "status": "SUCCESS",
                            "message": "3 internal user(s) notified",
                            "status_code": 201,
                            "data": {
                                "internal_users": [
                                    {
                                        "email": "user1@company.com",
                                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "notified": True,
                                    },
                                    {
                                        "email": "user2@company.com",
                                        "user_id": "223e4567-e89b-12d3-a456-426614174001",
                                        "notified": True,
                                    },
                                    {
                                        "email": "user3@company.com",
                                        "user_id": "323e4567-e89b-12d3-a456-426614174002",
                                        "notified": True,
                                    },
                                ],
                                "external_participants": [],
                                "already_invited": [],
                                "not_in_project": [],
                            },
                        },
                    },
                    "only_external": {
                        "summary": "Only External Participants Invited",
                        "value": {
                            "status": "SUCCESS",
                            "message": "2 external participant(s) invited",
                            "status_code": 201,
                            "data": {
                                "internal_users": [],
                                "external_participants": [
                                    {
                                        "email": "external1@partner.com",
                                        "participant_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "invitation_sent": True,
                                        "magic_link": "https://app.example.com/guest/access?token=eyJhbGciOi...&client=local",
                                    },
                                    {
                                        "email": "external2@vendor.com",
                                        "participant_id": "223e4567-e89b-12d3-a456-426614174001",
                                        "invitation_sent": True,
                                        "magic_link": "https://app.example.com/guest/access?token=eyJhbGciOi...&client=local",
                                    },
                                ],
                                "already_invited": [],
                                "not_in_project": [],
                            },
                        },
                    },
                    "internal_user_not_in_project": {
                        "summary": "Internal User Not in Project",
                        "value": {
                            "status": "SUCCESS",
                            "message": "1 internal user(s) notified. 1 email(s) not invited "
                            "(not in project - add to project first)",
                            "status_code": 201,
                            "data": {
                                "internal_users": [
                                    {
                                        "email": "member@company.com",
                                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "notified": True,
                                    },
                                ],
                                "external_participants": [],
                                "already_invited": [],
                                "not_in_project": ["nonmember@company.com"],
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Ticket Closed",
        "content": {
            "application/json": {
                "examples": {
                    "ticket_closed": {
                        "summary": "Ticket is Closed",
                        "value": {
                            "error_code": "CLOSED_TICKET",
                            "message": "Cannot invite participants to a closed ticket",
                            "status_code": 400,
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
                    "no_permission": {
                        "summary": "No Permission to Invite",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to invite participants. "
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
                    "billing_access_denied": {
                        "summary": "Billing Access Denied",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "Billing access denied for this organization",
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
                            "message": "The ticket you're trying to add participants to doesn't "
                            "exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "User not found",
                            "status_code": 404,
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
                                "emails": [
                                    "value is not a valid list",
                                    "List should have at least 1 item after validation, not 0",
                                ],
                            },
                        },
                    },
                    "email_validation": {
                        "summary": "Email Validation Failed",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "emails": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                ],
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
                            "message": "Failed to invite participants. Please try again.",
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

invite_participants_custom_errors = ["400", "403", "404", "422", "500"]
invite_participants_custom_success = {
    "status_code": 201,
    "description": "Participants invited successfully. Internal users "
    "notified, external participants sent magic links.",
}

get_ticket_participants_responses = {
    200: {
        "description": "Participants Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Participants List Retrieved",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Retrieved 5 participant(s)",
                            "status_code": 200,
                            "data": {
                                "internal_participants": [
                                    {
                                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "profile_picture_url": "https://example.com/profile.jpg",
                                        "avatar_url": "https://example.com/avatar.jpg",
                                        "status": "online",
                                        "invited_at": "2025-12-05T10:30:00Z",
                                    },
                                    {
                                        "user_id": "223e4567-e89b-12d3-a456-426614174001",
                                        "name": "Jane Smith",
                                        "email": "jane@company.com",
                                        "profile_picture_url": "https://example.com/profile2.jpg",
                                        "avatar_url": "https://example.com/avatar2.jpg",
                                        "status": "offline",
                                        "invited_at": "2025-12-05T11:00:00Z",
                                    },
                                ],
                                "external_participants": [
                                    {
                                        "participant_id": "323e4567-e89b-12d3-a456-426614174002",
                                        "name": "Guest",
                                        "email": "counsel@lawfirm.com",
                                        "role": "Guest",
                                        "status": "offline",
                                        "invited_at": "2025-12-05T12:00:00Z",
                                        "expires_at": "2025-12-07T12:00:00Z",
                                    },
                                ],
                            },
                        },
                    },
                }
            }
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
                    "not_in_project": {
                        "summary": "Not in Project or Participant",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to view these participants. "
                            "Only project members and ticket participants "
                            "can view this information.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "not_in_organization": {
                        "summary": "Not in Organization",
                        "value": {
                            "error_code": "FORBIDDEN",
                            "message": "You don't have access to this organization.",
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
                            "message": "The ticket you're trying to view doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "User not found",
                            "status_code": 404,
                            "errors": {},
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
                            "message": "Failed to retrieve ticket participants. Please try again.",
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

get_ticket_participants_custom_errors = ["401", "403", "404", "500"]
get_ticket_participants_custom_success = {
    "status_code": 200,
    "description": "Participants retrieved successfully with online/offline status. "
    "Accessible by project members, internal participants, and external participants (guests).",
}
