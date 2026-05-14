create_manual_ticket_responses = {
    201: {
        "description": "Manual Ticket Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "source_level_ticket": {
                        "summary": "Source-Level Ticket Created",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Ticket created successfully",
                            "status_code": 201,
                            "data": {
                                "ticket": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "ticket_number": 1024,
                                    "title": (
                                        "[UK Financial Regulations] HMRC Updates - Change Detected"
                                    ),
                                    "description": "New compliance requirements detected",
                                    "status": "OPEN",
                                    "priority": "MEDIUM",
                                    "is_manual": True,
                                    "source_id": "223e4567-e89b-12d3-a456-426614174001",
                                    "data_revision_id": "323e4567-e89b-12d3-a456-426614174002",
                                    "organization_id": "423e4567-e89b-12d3-a456-426614174003",
                                    "project_id": "523e4567-e89b-12d3-a456-426614174004",
                                    "created_by_user_id": "723e4567-e89b-12d3-a456-426614174006",
                                    "created_at": "2023-10-01T10:00:00Z",
                                }
                            },
                        },
                    },
                    "jurisdiction_all_changes_ticket": {
                        "summary": "Jurisdiction Ticket - All Changes",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Ticket created successfully",
                            "status_code": 201,
                            "data": {
                                "ticket": {
                                    "id": "456e7890-e89b-12d3-a456-426614174010",
                                    "ticket_number": 1025,
                                    "title": (
                                        "[UK Financial Regulations] Jurisdiction Update - 5 Changes"
                                    ),
                                    "description": (
                                        "Multiple regulatory changes detected across sources"
                                    ),
                                    "status": "OPEN",
                                    "priority": "HIGH",
                                    "is_manual": True,
                                    "source_id": None,
                                    "data_revision_id": None,
                                    "jurisdiction_change_id": None,
                                    "organization_id": "423e4567-e89b-12d3-a456-426614174003",
                                    "project_id": "523e4567-e89b-12d3-a456-426614174004",
                                    "created_by_user_id": "723e4567-e89b-12d3-a456-426614174006",
                                    "created_at": "2023-10-01T10:00:00Z",
                                }
                            },
                        },
                    },
                    "jurisdiction_per_change_ticket": {
                        "summary": "Per-Change Ticket Created",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Ticket created successfully",
                            "status_code": 201,
                            "data": {
                                "ticket": {
                                    "id": "789e0123-e89b-12d3-a456-426614174011",
                                    "ticket_number": 1026,
                                    "title": (
                                        "[UK Financial Regulations] standard_license_fee Change"
                                    ),
                                    "description": (
                                        "standard_license_fee modified: $30,000.00 → $30,500.00"
                                    ),
                                    "status": "OPEN",
                                    "priority": "MEDIUM",
                                    "is_manual": True,
                                    "source_id": None,
                                    "data_revision_id": None,
                                    "jurisdiction_change_id": (
                                        "0a0f4736-1745-4472-9ff2-be6389566828"
                                    ),
                                    "organization_id": "423e4567-e89b-12d3-a456-426614174003",
                                    "project_id": "523e4567-e89b-12d3-a456-426614174004",
                                    "created_by_user_id": "723e4567-e89b-12d3-a456-426614174006",
                                    "created_at": "2026-01-17T10:00:00Z",
                                }
                            },
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
                    "no_organization_access": {
                        "summary": "No Organization Access",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have access to this organization. "
                            "Please contact your administrator for access.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "no_create_tickets_permission": {
                        "summary": "No CREATE_TICKETS Permission",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to create tickets. "
                            "Only administrators, managers, and owners can create tickets. "
                            "Please contact your organization administrator.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "revision_source_mismatch": {
                        "summary": "Revision Source Mismatch",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "The revision you selected doesn't belong to the specified "
                            "source. Please ensure you're selecting the correct revision.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Resource Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The data source you're trying to reference doesn't exist. "
                            "Please select a valid source.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction not found for the given source",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "project_not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The project you're trying to access doesn't exist or "
                            "doesn't belong to your organization.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "revision_not_found": {
                        "summary": "Data Revision Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The data revision you're trying to reference doesn't "
                            "exist. Please select a valid revision.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "jurisdiction_scrape_job_not_found": {
                        "summary": "Jurisdiction Scrape Job Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction scrape job not found",
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
                        "summary": "Request Validation Failed",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "source_id": ["Field required"],
                                "revision_id": ["Field required"],
                                "priority": [
                                    "Input should be 'low', 'medium', 'high' or 'critical'"
                                ],
                            },
                        },
                    },
                    "invalid_ticket_type": {
                        "summary": "Invalid Ticket Type",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": (
                                "Must provide either (source_id + revision_id) for "
                                "source-level tickets or (jurisdiction_id + "
                                "jurisdiction_scrape_job_id) for jurisdiction-level tickets."
                            ),
                            "status_code": 422,
                            "errors": {},
                        },
                    },
                    "mixed_ticket_type": {
                        "summary": "Mixed Ticket Type",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": (
                                "Cannot create ticket with both source-level and "
                                "jurisdiction-level data. Please provide only one type."
                            ),
                            "status_code": 422,
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
                            "message": "An error occurred while creating the ticket",
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

create_manual_ticket_custom_errors = ["403", "404", "422", "500"]

create_manual_ticket_custom_success = {
    "status_code": 201,
    "description": "Manual ticket created successfully for discussions or follow-ups.",
}

create_manual_ticket_request_body = {
    "content": {
        "application/json": {
            "examples": {
                "source_level_ticket": {
                    "summary": "Create Source-Level Ticket",
                    "description": "Create a ticket for a specific source revision",
                    "value": {
                        "source_id": "223e4567-e89b-12d3-a456-426614174001",
                        "revision_id": "323e4567-e89b-12d3-a456-426614174002",
                        "priority": "MEDIUM",
                    },
                },
                "jurisdiction_all_changes_ticket": {
                    "summary": "Create Jurisdiction Ticket - All Changes",
                    "description": (
                        "Create a ticket for all changes in a jurisdiction scrape (legacy)"
                    ),
                    "value": {
                        "jurisdiction_id": "e5e1e2b0-24fe-4819-8143-46e7b13f9612",
                        "jurisdiction_scrape_job_id": "4c3b13a8-11b9-4b4c-817e-7301ede6440a",
                        "priority": "HIGH",
                    },
                },
                "jurisdiction_per_change_ticket": {
                    "summary": "Create Ticket for Specific Change",
                    "description": "Create a ticket for a specific jurisdiction change to discuss",
                    "value": {
                        "jurisdiction_id": "e5e1e2b0-24fe-4819-8143-46e7b13f9612",
                        "jurisdiction_scrape_job_id": "fbc0fe77-3757-4baf-99de-cbcc54ba76ee",
                        "jurisdiction_change_id": "0a0f4736-1745-4472-9ff2-be6389566828",
                        "priority": "MEDIUM",
                    },
                },
            }
        }
    }
}

get_tickets_by_source_responses = {
    200: {
        "description": "Tickets Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Tickets List with Pagination",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Retrieved 15 ticket(s)",
                            "status_code": 200,
                            "data": {
                                "tickets": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "title": "Bug Report",
                                        "description": "Login issue on mobile",
                                        "status": "OPEN",
                                        "priority": "HIGH",
                                        "created_at": "2023-10-01T10:00:00Z",
                                        "created_by": {
                                            "id": "223e4567-e89b-12d3-a456-426614174001",
                                            "name": "John Doe",
                                            "email": "john@company.com",
                                        },
                                    },
                                    {
                                        "id": "323e4567-e89b-12d3-a456-426614174002",
                                        "title": "Feature Request",
                                        "description": "Add export functionality",
                                        "status": "IN_PROGRESS",
                                        "priority": "MEDIUM",
                                        "created_at": "2023-09-30T15:30:00Z",
                                        "created_by": {
                                            "id": "423e4567-e89b-12d3-a456-426614174003",
                                            "name": "Jane Smith",
                                            "email": "jane@company.com",
                                        },
                                    },
                                ],
                                "pagination": {
                                    "total": 45,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 3,
                                    "has_next": True,
                                    "has_previous": False,
                                },
                            },
                        },
                    },
                    "empty": {
                        "summary": "No Tickets Found",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Retrieved 0 ticket(s)",
                            "status_code": 200,
                            "data": {
                                "tickets": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 1,
                                    "has_next": False,
                                    "has_previous": False,
                                },
                            },
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
                    "no_project_access": {
                        "summary": "No Project Access",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to view tickets in this project. "
                            "Please contact your project administrator for access.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Resource Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The data source you're trying to access doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The jurisdiction for this data source doesn't exist. "
                            "Please contact support for assistance.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "project_not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The project associated with this jurisdiction doesn't "
                            "exist. Please contact support for assistance.",
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
                        "summary": "Query Parameter Validation",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "page": ["Input should be greater than or equal to 1"],
                                "limit": ["Input should be less than or equal to 100"],
                            },
                        },
                    },
                    "no_filters": {
                        "summary": "At Least One Filter Required",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "At least one filter (source_id, jurisdiction_id, "
                            "or organization_id) must be provided",
                            "status_code": 422,
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
                            "message": "An error occurred while fetching tickets",
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

get_tickets_by_source_custom_errors = ["403", "404", "422", "500"]

get_tickets_by_source_custom_success = {
    "status_code": 200,
    "description": "Paginated tickets retrieved successfully based on the specified filters "
    "(source, jurisdiction, or organization).",
}

get_ticket_by_id_responses = {
    200: {
        "description": "Ticket Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Ticket Details",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Ticket retrieved successfully",
                            "status_code": 200,
                            "data": {
                                "ticket": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "title": "Critical Bug Fix",
                                    "description": "Fix the authentication issue",
                                    "status": "OPEN",
                                    "priority": "CRITICAL",
                                    "source_id": "223e4567-e89b-12d3-a456-426614174001",
                                    "revision_id": "323e4567-e89b-12d3-a456-426614174002",
                                    "organization_id": "423e4567-e89b-12d3-a456-426614174003",
                                    "project_id": "523e4567-e89b-12d3-a456-426614174004",
                                    "jurisdiction_id": "623e4567-e89b-12d3-a456-426614174005",
                                    "created_at": "2023-10-01T10:00:00Z",
                                    "created_by": {
                                        "id": "723e4567-e89b-12d3-a456-426614174006",
                                        "name": "John Doe",
                                        "email": "john@company.com",
                                        "profile_picture_url": "https://example.com/profile.jpg",
                                    },
                                    "assigned_to": {
                                        "id": "823e4567-e89b-12d3-a456-426614174007",
                                        "name": "Jane Smith",
                                        "email": "jane@company.com",
                                        "profile_picture_url": "https://example.com/profile.jpg",
                                    },
                                    "assigned_by": {
                                        "id": "923e4567-e89b-12d3-a456-426614174008",
                                        "name": "Admin User",
                                        "email": "admin@company.com",
                                        "profile_picture_url": "https://example.com/profile.jpg",
                                    },
                                    "invited_users": [
                                        {
                                            "id": "a23e4567-e89b-12d3-a456-426614174009",
                                            "name": "External Counsel",
                                            "email": "counsel@lawfirm.com",
                                            "role": "REVIEWER",
                                            "status": "ACTIVE",
                                        }
                                    ],
                                    "comments": [
                                        {
                                            "comment_id": "c23e4567-e89b-12d3-a456-426614174000",
                                            "ticket_id": "123e4567-e89b-12d3-a456-426614174000",
                                            "content": "This change requires immediate attention",
                                            "attachments": None,
                                            "user_id": "723e4567-e89b-12d3-a456-426614174006",
                                            "participant_id": None,
                                            "mentioned_user_ids": None,
                                            "mentioned_participant_ids": None,
                                            "created_at": "2026-01-21T10:30:00Z",
                                            "updated_at": None,
                                            "deleted_at": None,
                                            "user": {
                                                "id": "723e4567-e89b-12d3-a456-426614174006",
                                                "name": "John Doe",
                                                "email": "john@company.com",
                                                "avatar_url": "https://example.com/profile.jpg",
                                            },
                                            "participant": None,
                                            "author_name": "John Doe",
                                            "author_email": "john@company.com",
                                            "author_avatar_url": "https://example.com/profile.jpg",
                                            "is_guest": False,
                                            "date": "21/01/2026",
                                            "time": "10:30:00",
                                        },
                                        {
                                            "comment_id": "c33e4567-e89b-12d3-a456-426614174010",
                                            "ticket_id": "123e4567-e89b-12d3-a456-426614174000",
                                            "content": "Guest review comment",
                                            "attachments": [
                                                {
                                                    "url": "https://minio.example.com/comment-images/abc123.jpg",
                                                    "name": "screenshot.png",
                                                    "type": "image/png",
                                                    "size": 524288,
                                                    "metadata": {
                                                        "uploaded_at": "2026-01-21T10:30:00Z"
                                                    },
                                                }
                                            ],
                                            "user_id": None,
                                            "participant_id": (
                                                "a23e4567-e89b-12d3-a456-426614174009"
                                            ),
                                            "mentioned_user_ids": None,
                                            "mentioned_participant_ids": None,
                                            "created_at": "2026-01-21T11:00:00Z",
                                            "updated_at": None,
                                            "deleted_at": None,
                                            "user": None,
                                            "participant": {
                                                "id": "a23e4567-e89b-12d3-a456-426614174009",
                                                "email": "counsel@lawfirm.com",
                                                "role": "Guest",
                                            },
                                            "author_name": "Guest",
                                            "author_email": "counsel@lawfirm.com",
                                            "author_avatar_url": None,
                                            "is_guest": True,
                                            "date": "21/01/2026",
                                            "time": "11:00:00",
                                        },
                                    ],
                                }
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
                        "summary": "No Ticket Access - Not in Project/Participant",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You don't have permission to view this ticket. "
                            "Only project members and ticket participants "
                            "can view this information",
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
                            "message": "Ticket not found",
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
                        "summary": "Invalid Ticket ID",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "ticket_id": [
                                    "Input should be a valid UUID, "
                                    "invalid length: expected length 32 for simple format, found 10"
                                ],
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
                            "message": "An error occurred while fetching the ticket",
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

get_ticket_by_id_custom_errors = ["401", "403", "404", "422", "500"]

get_ticket_by_id_custom_success = {
    "status_code": 200,
    "description": "Ticket details retrieved successfully. "
    "Accessible by project members, internal participants, and external participants (guests).",
}
