"""API documentation for change acceptance endpoints."""

ACCEPT_CHANGE_DOCS = {
    "summary": "Accept a jurisdiction change",
    "description": """
Accept or dismiss a specific change detected in a jurisdiction scrape.

Once accepted, the change is marked as reviewed and will no longer appear 
as pending in the data page.

**Permissions**: Requires `create_tickets` permission (admins/managers/owners).
    """,
    "responses": {
        200: {
            "description": "Change successfully accepted",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Change accepted successfully",
                        "data": {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "jurisdiction_scrape_job_id": "123e4567-e89b-12d3-a456-426614174001",
                            "field_name": "applicable_services",
                            "old_value": "accommodation only",
                            "new_value": "accommodation, dining, and events",
                            "change_description": (
                                "applicable_services changed: "
                                "accommodation only → accommodation, dining, and events"
                            ),
                            "change_index": 0,
                            "ticket_created": False,
                            "change_accepted": True,
                            "accepted_at": "2026-01-17T07:00:00Z",
                            "accepted_by_user_id": "123e4567-e89b-12d3-a456-426614174002",
                            "created_at": "2026-01-16T22:00:00Z",
                        },
                    }
                }
            },
        },
        404: {
            "description": "Change not found",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "The jurisdiction change was not found.",
                        "error_code": "JURISDICTION_CHANGE_NOT_FOUND",
                    }
                }
            },
        },
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": (
                            "You don't have permission to accept changes. "
                            "Only administrators, managers, and owners can accept changes."
                        ),
                        "error_code": "PERMISSION_DENIED",
                    }
                }
            },
        },
        409: {
            "description": "Change already accepted",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "This change has already been accepted.",
                        "error_code": "CHANGE_ALREADY_ACCEPTED",
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": "Validation error",
                        "error_code": "VALIDATION_ERROR",
                        "errors": {
                            "change_id": ["Input should be a valid UUID"],
                            "jurisdiction_id": ["Input should be a valid UUID"],
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
                                "status": "error",
                                "message": (
                                    "Failed to accept jurisdiction change. Please try again."
                                ),
                                "error_code": "PROCESSING_ERROR",
                                "status_code": 500,
                            },
                        },
                        "internal_server_error": {
                            "summary": "Internal Server Error - Unexpected Failure",
                            "value": {
                                "status": "error",
                                "message": "An unexpected error occurred. Please try again later.",
                                "error_code": "INTERNAL_SERVER_ERROR",
                                "status_code": 500,
                            },
                        },
                    }
                }
            },
        },
    },
}


BULK_ACCEPT_CHANGES_DOCS = {
    "summary": "Bulk accept jurisdiction changes",
    "description": """
Accept multiple jurisdiction changes at once after team discussion.

**Permissions**: Requires `create_tickets` permission.

**Behavior**:
- If permission denied for ANY change, ALL changes are rolled back
- Individual failures (not found, already accepted) are tracked
- Max 50 changes per request

**Workflow**: Scrape → Changes created → Create ticket → Discuss → Accept changes
    """,
    "responses": {
        200: {
            "description": "Bulk accept completed",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "3 changes accepted successfully",
                        "data": {
                            "accepted_count": 3,
                            "failed_changes": [
                                {
                                    "change_id": "123e4567-e89b-12d3-a456-426614174004",
                                    "error": "This change has already been accepted.",
                                }
                            ],
                            "accepted_changes": [
                                {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "field_name": "applicable_services",
                                    "change_accepted": True,
                                    "accepted_at": "2026-01-17T10:00:00Z",
                                }
                            ],
                        },
                    }
                }
            },
        },
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "status": "error",
                        "message": (
                            "You don't have permission to accept changes. "
                            "Only administrators, managers, and owners can accept changes."
                        ),
                        "error_code": "PERMISSION_DENIED",
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "examples": {
                        "empty_list": {
                            "summary": "Empty change_ids list",
                            "value": {
                                "status": "error",
                                "message": "Validation error",
                                "error_code": "VALIDATION_ERROR",
                                "errors": {
                                    "change_ids": [
                                        "List should have at least 1 item after validation"
                                    ]
                                },
                            },
                        },
                        "too_many_items": {
                            "summary": "More than 50 changes",
                            "value": {
                                "status": "error",
                                "message": "Validation error",
                                "error_code": "VALIDATION_ERROR",
                                "errors": {
                                    "change_ids": [
                                        "List should have at most 50 items after validation"
                                    ]
                                },
                            },
                        },
                        "invalid_uuid": {
                            "summary": "Invalid UUID format",
                            "value": {
                                "status": "error",
                                "message": "Validation error",
                                "error_code": "VALIDATION_ERROR",
                                "errors": {"change_ids": ["Input should be a valid UUID"]},
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
                                "status": "error",
                                "message": (
                                    "Failed to process bulk accept changes. Please try again."
                                ),
                                "error_code": "PROCESSING_ERROR",
                                "status_code": 500,
                            },
                        },
                        "internal_server_error": {
                            "summary": "Internal Server Error - Unexpected Failure",
                            "value": {
                                "status": "error",
                                "message": "An unexpected error occurred. Please try again later.",
                                "error_code": "INTERNAL_SERVER_ERROR",
                                "status_code": 500,
                            },
                        },
                    }
                }
            },
        },
    },
}
