from typing import Any

search_data_revisions_responses: dict[int, dict[str, Any]] = {
    200: {
        "description": "Search Completed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Data Revisions Found",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Data revision search successful",
                            "status_code": 200,
                            "data": {
                                "results": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "title": "financial-report-2024.pdf",
                                        "summary": "AI-generated summary of the document content",
                                        "content": None,
                                        "key_fields": {
                                            "year": "2024",
                                            "category": "finance",
                                            "department": "accounting",
                                        },
                                        "revision_date": "2024-01-08T10:30:00Z",
                                        "relevance_score": 0.85,
                                    },
                                    {
                                        "id": "234e5678-e89b-12d3-a456-426614174001",
                                        "title": "quarterly-report-q4.pdf",
                                        "summary": "Q4 quarterly financial report",
                                        "content": None,
                                        "key_fields": {
                                            "year": "2024",
                                            "quarter": "Q4",
                                            "category": "finance",
                                        },
                                        "revision_date": "2024-01-07T15:45:00Z",
                                        "relevance_score": 0.72,
                                    },
                                ],
                                "total": 42,
                                "page": 1,
                                "limit": 20,
                                "total_pages": 3,
                                "query": "financial report",
                                "operator": "AND",
                            },
                        },
                    },
                    "no_results": {
                        "summary": "No Results Found",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Data revision search successful",
                            "status_code": 200,
                            "data": {
                                "results": [],
                                "total": 0,
                                "page": 1,
                                "limit": 20,
                                "total_pages": 0,
                                "query": "nonexistent term",
                                "operator": "AND",
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Search Parameters",
        "content": {
            "application/json": {
                "examples": {
                    "empty_query": {
                        "summary": "Empty Search Query",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Search query cannot be empty",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_filter_key": {
                        "summary": "Invalid Filter Key",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": (
                                "Invalid filter key: 'key$name'. "
                                "Only alphanumeric characters and underscores are allowed."
                            ),
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "no_valid_terms": {
                        "summary": "No Valid Search Terms",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Search query resulted in no valid search terms",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Failed",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Invalid or Expired Token",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Invalid or expired token.",
                            "status_code": 401,
                            "errors": {},
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
                        "summary": "Insufficient Permissions",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You do not have permission to search data revisions",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
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
                                "query": ["String should have at least 1 character"],
                                "limit": ["Input should be less than or equal to 100"],
                            },
                        },
                    }
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
                            "message": "Failed to search data revisions. Please try again.",
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

search_data_revisions_custom_errors: list[str] = ["400", "401", "403", "422", "500"]
search_data_revisions_custom_success: dict[str, Any] = {
    "status_code": 200,
    "description": "Search completed successfully with paginated results.",
}
