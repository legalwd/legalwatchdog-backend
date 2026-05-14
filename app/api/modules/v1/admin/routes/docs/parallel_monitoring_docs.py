get_parallel_usage_stats_responses = {
    200: {
        "description": "Parallel.ai usage statistics loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Aggregated Parallel.ai usage stats",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Parallel.ai usage statistics loaded successfully.",
                            "data": {
                                "total_requests": 1250,
                                "successful_requests": 1180,
                                "failed_requests": 70,
                                "success_rate": 94.4,
                                "total_cost": "1.25",
                                "avg_latency_ms": 1340,
                                "total_content_mb": 45.2,
                                "avg_content_kb": 37.5,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid 'days' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["Must be between 1 and 365"]},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_usage_error": {
                        "summary": "Parallel Usage Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_USAGE_ERROR",
                            "message": "Failed to retrieve Parallel.ai usage statistics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Database Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to query Parallel.ai usage data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_usage_stats_custom_errors = ["400", "401", "422", "500"]
get_parallel_usage_stats_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai usage statistics loaded successfully.",
}

get_parallel_cost_breakdown_responses = {
    200: {
        "description": "Parallel.ai daily cost breakdown retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Daily cost breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Parallel.ai cost breakdown retrieved",
                            "data": {
                                "daily_costs": [
                                    {
                                        "date": "2025-12-18",
                                        "request_count": 45,
                                        "successful_requests": 43,
                                        "failed_requests": 2,
                                        "total_cost": "0.045",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid 'days' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["Must be between 1 and 365"]},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve Parallel.ai cost breakdown",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_cost_breakdown_custom_errors = ["400", "401", "422", "500"]
get_parallel_cost_breakdown_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai daily cost breakdown retrieved successfully.",
}

get_parallel_usage_by_user_responses = {
    200: {
        "description": "Parallel.ai usage by user retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Top users by requests",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Parallel.ai usage by user retrieved",
                            "data": {
                                "user_usage": [
                                    {
                                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "email": "user@example.com",
                                        "request_count": 120,
                                        "successful_requests": 115,
                                        "failed_requests": 5,
                                        "total_cost": "0.120",
                                        "avg_latency_ms": 1300,
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid limit parameter",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid 'limit' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"limit": ["Must be <= 100"]},
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve Parallel.ai usage by user",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_usage_by_user_custom_errors = ["400", "401", "422", "500"]
get_parallel_usage_by_user_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai usage by user retrieved successfully.",
}

get_parallel_usage_by_endpoint_responses = {
    200: {
        "description": "Parallel.ai usage by endpoint retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Usage breakdown by API endpoint",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "Endpoint breakdown for Parallel.ai usage loaded successfully."
                            ),
                            "data": {
                                "endpoint_usage": [
                                    {
                                        "endpoint_name": "scrape_source",
                                        "request_count": 450,
                                        "successful_requests": 430,
                                        "failed_requests": 20,
                                        "total_cost": "0.450",
                                        "avg_latency_ms": 1250,
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid 'days' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["Must be <= 365"]},
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve Parallel.ai usage by endpoint",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_usage_by_endpoint_custom_errors = ["400", "401", "422", "500"]
get_parallel_usage_by_endpoint_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai usage by endpoint retrieved successfully.",
}

get_recent_parallel_errors_responses = {
    200: {
        "description": "Recent Parallel.ai errors retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Recent extraction errors",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Recent Parallel.ai errors retrieved",
                            "data": {
                                "recent_errors": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "user_id": "789e0123-e89b-12d3-a456-426614174001",
                                        "url_extracted": "https://example.com/page",
                                        "endpoint_name": "scrape_source",
                                        "error_message": "Request timeout",
                                        "latency_ms": 30000,
                                        "created_at": "2025-12-18T10:30:00Z",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid limit parameter",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid 'limit' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"limit": ["Must be <= 200"]},
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve recent Parallel.ai errors",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_recent_parallel_errors_custom_errors = ["400", "401", "422", "500"]
get_recent_parallel_errors_custom_success = {
    "status_code": 200,
    "description": "Recent Parallel.ai errors retrieved successfully.",
}

get_parallel_usage_by_organization_responses = {
    200: {
        "description": "Parallel.ai usage by organization retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Organization-level usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Parallel.ai usage by organization retrieved successfully",
                            "data": {
                                "organization_usage": [
                                    {
                                        "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "organization_name": "Acme Corp",
                                        "plan": "premium",
                                        "unique_users": 15,
                                        "request_count": 450,
                                        "successful_requests": 430,
                                        "failed_requests": 20,
                                        "total_cost_usd": 0.45,
                                        "total_content_mb": 12.5,
                                        "last_request_at": "2025-12-29T15:30:00Z",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve Parallel.ai usage by organization",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_usage_by_organization_custom_errors = ["401", "500"]
get_parallel_usage_by_organization_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai usage by organization retrieved successfully.",
}

get_parallel_usage_by_project_responses = {
    200: {
        "description": "Parallel.ai usage by project retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project-level usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Parallel.ai usage by project retrieved successfully",
                            "data": {
                                "project_usage": [
                                    {
                                        "project_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "project_name": "Legal Monitoring",
                                        "organization_id": "789e0123-e89b-12d3-a456-426614174001",
                                        "request_count": 120,
                                        "successful_requests": 115,
                                        "failed_requests": 5,
                                        "total_cost_usd": 0.12,
                                        "total_content_mb": 3.5,
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve Parallel.ai usage by project",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_usage_by_project_custom_errors = ["401", "500"]
get_parallel_usage_by_project_custom_success = {
    "status_code": 200,
    "description": "Parallel.ai usage by project retrieved successfully.",
}

get_parallel_detailed_logs_responses = {
    200: {
        "description": "Detailed Parallel.ai logs retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated request logs with full attribution",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Detailed Parallel.ai logs retrieved successfully",
                            "data": {
                                "total": 250,
                                "limit": 100,
                                "offset": 0,
                                "logs": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "url_extracted": "https://example.com/page",
                                        "endpoint_name": "scrape_source",
                                        "user": {
                                            "id": "789e0123-e89b-12d3-a456-426614174001",
                                            "name": "John Doe",
                                            "email": "john@example.com",
                                        },
                                        "organization": {
                                            "id": "456e7890-e89b-12d3-a456-426614174002",
                                            "name": "Acme Corp",
                                        },
                                        "project": {
                                            "id": "012e3456-e89b-12d3-a456-426614174003",
                                            "name": "Legal Monitoring",
                                        },
                                        "success": True,
                                        "cost_usd": 0.001,
                                        "latency_ms": 1250,
                                        "content_size_bytes": 15000,
                                        "error_message": None,
                                        "created_at": "2025-12-29T15:30:00Z",
                                    }
                                ],
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
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
                    "parallel_provider_connection_error": {
                        "summary": "Parallel Provider Connection Error - Service Unavailable",
                        "value": {
                            "error": "PARALLEL_PROVIDER_CONNECTION_ERROR",
                            "message": "Parallel.ai service is currently unavailable",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_query_error": {
                        "summary": "Parallel Query Error - Data Retrieval Failure",
                        "value": {
                            "error": "PARALLEL_QUERY_ERROR",
                            "message": "Failed to retrieve detailed Parallel.ai logs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
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

get_parallel_detailed_logs_custom_errors = ["401", "500"]
get_parallel_detailed_logs_custom_success = {
    "status_code": 200,
    "description": "Detailed Parallel.ai logs retrieved successfully.",
}
