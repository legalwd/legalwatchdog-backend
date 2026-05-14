get_llm_usage_stats_responses = {
    200: {
        "description": "LLM usage statistics loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Aggregated LLM usage statistics",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "LLM usage statistics loaded successfully.",
                            "data": {
                                "total_requests": 1250,
                                "total_tokens": 1500000,
                                "total_cost": "120.50",
                                "avg_latency_ms": 340,
                                "success_rate": 98.7,
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_date_format": {
                        "summary": "Invalid date format",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Invalid date format for start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_date_range": {
                        "summary": "Invalid date range",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Start date must be before end date",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"start_date": ["Invalid date format"]},
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
                    "llm_usage_error": {
                        "summary": "LLM Usage Error - Controlled Failure",
                        "value": {
                            "error_code": "LLM_USAGE_ERROR",
                            "message": "Failed to retrieve LLM usage statistics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request this time. Try again later.",
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

get_llm_usage_stats_custom_errors = ["400", "401", "422", "500"]
get_llm_usage_stats_custom_success = {
    "status_code": 200,
    "description": "LLM usage statistics loaded successfully.",
}

get_llm_cost_breakdown_responses = {
    200: {
        "description": "LLM cost breakdown retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Cost grouped by model/provider",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "LLM cost breakdown for the last 30 days loaded successfully."
                            ),
                            "data": {
                                "breakdown": [
                                    {"model": "openai/gpt-4o", "cost": "100.25"},
                                    {"model": "anthropic/claude-3.5-sonnet", "cost": "80.10"},
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_group_by": {
                        "summary": "Invalid group_by parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Group by must be: provider, model, endpoint, user, org",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_date_range": {
                        "summary": "Invalid date range",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is less than or equal to 365"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to generate LLM cost breakdown",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request at this time. Try again.",
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

get_llm_cost_breakdown_custom_errors = ["400", "401", "422", "500"]
get_llm_cost_breakdown_custom_success = {
    "status_code": 200,
    "description": "LLM cost breakdown retrieved successfully.",
}

get_llm_usage_by_provider_responses = {
    200: {
        "description": "LLM usage by provider loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Provider usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "LLM provider usage for the last 7 days loaded successfully."
                            ),
                            "data": [
                                {
                                    "provider": "openrouter",
                                    "request_count": 450,
                                    "total_tokens": 125000,
                                    "total_input_tokens": 75000,
                                    "total_output_tokens": 50000,
                                    "total_cost_usd": 85.50,
                                    "avg_latency_ms": 320.5,
                                    "failed_requests": 5,
                                    "success_rate": 0.9889,
                                },
                                {
                                    "provider": "gemini",
                                    "request_count": 280,
                                    "total_tokens": 89000,
                                    "total_input_tokens": 52000,
                                    "total_output_tokens": 37000,
                                    "total_cost_usd": 42.30,
                                    "avg_latency_ms": 280.2,
                                    "failed_requests": 2,
                                    "success_rate": 0.9929,
                                },
                            ],
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_days": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Invalid value for days parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is greater than or equal to 1"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve LLM provider usage",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
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

get_llm_usage_by_provider_custom_errors = ["400", "401", "422", "500"]
get_llm_usage_by_provider_custom_success = {
    "status_code": 200,
    "description": "LLM provider usage loaded successfully.",
}

get_llm_usage_by_model_responses = {
    200: {
        "description": "LLM usage by model loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Model usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "LLM model usage for the last 7 days loaded successfully.",
                            "data": [
                                {
                                    "model": "openai/gpt-4o",
                                    "provider": "openrouter",
                                    "request_count": 250,
                                    "total_tokens": 75000,
                                    "total_cost_usd": 75.50,
                                    "avg_latency_ms": 285.3,
                                },
                                {
                                    "model": "anthropic/claude-3.5-sonnet",
                                    "provider": "openrouter",
                                    "request_count": 180,
                                    "total_tokens": 52000,
                                    "total_cost_usd": 52.80,
                                    "avg_latency_ms": 320.1,
                                },
                            ],
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_days": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Invalid 'days' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is greater than or equal to 1"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve LLM model usage",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request at this time. Try again.",
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

get_llm_usage_by_model_custom_errors = ["400", "401", "422", "500"]
get_llm_usage_by_model_custom_success = {
    "status_code": 200,
    "description": "LLM model usage loaded successfully.",
}

get_llm_usage_by_endpoint_responses = {
    200: {
        "description": "LLM usage by endpoint loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Endpoint usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "LLM usage breakdown by endpoint for the last 7 days "
                                "loaded successfully."
                            ),
                            "data": [
                                {
                                    "endpoint": "extract_source_content",
                                    "request_count": 320,
                                    "total_tokens": 95000,
                                    "total_cost_usd": 95.25,
                                    "avg_latency_ms": 450.2,
                                    "failed_requests": 8,
                                    "success_rate": 0.975,
                                },
                                {
                                    "endpoint": "generate_summary",
                                    "request_count": 180,
                                    "total_tokens": 42000,
                                    "total_cost_usd": 42.10,
                                    "avg_latency_ms": 380.5,
                                    "failed_requests": 3,
                                    "success_rate": 0.9833,
                                },
                            ],
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_days": {
                        "summary": "Invalid days parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Invalid 'days' parameter",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is greater than or equal to 1"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve LLM endpoint usage",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request this time. Try again later.",
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

get_llm_usage_by_endpoint_custom_errors = ["400", "401", "422", "500"]
get_llm_usage_by_endpoint_custom_success = {
    "status_code": 200,
    "description": "LLM endpoint usage loaded successfully.",
}

get_llm_usage_trends_responses = {
    200: {
        "description": "LLM usage trends loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Time-series usage trends",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "LLM usage trends for the last 30 days (by day) "
                                "loaded successfully."
                            ),
                            "data": [
                                {
                                    "time": "2025-12-01T00:00:00",
                                    "request_count": 45,
                                    "total_tokens": 12500,
                                    "total_cost_usd": 12.50,
                                    "avg_latency_ms": 320.5,
                                    "failed_requests": 2,
                                    "success_rate": 0.9556,
                                },
                                {
                                    "time": "2025-12-02T00:00:00",
                                    "request_count": 52,
                                    "total_tokens": 15800,
                                    "total_cost_usd": 15.80,
                                    "avg_latency_ms": 305.2,
                                    "failed_requests": 1,
                                    "success_rate": 0.9808,
                                },
                            ],
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_granularity": {
                        "summary": "Invalid granularity parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Granularity must be: hour, day, week, or month",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"granularity": ["string does not match regex"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve LLM usage trends",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request at this time. Try again.",
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

get_llm_usage_trends_custom_errors = ["400", "401", "422", "500"]
get_llm_usage_trends_custom_success = {
    "status_code": 200,
    "description": "LLM usage trends loaded successfully.",
}

get_llm_provider_health_responses = {
    200: {
        "description": "LLM provider health status loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Provider health status",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "LLM provider health status loaded successfully.",
                            "data": {
                                "providers": [
                                    {
                                        "provider": "openrouter",
                                        "model": "gpt-4o",
                                        "is_available": True,
                                        "error_rate": 0.02,
                                        "avg_latency_ms": 285.5,
                                        "requests_last_hour": 150,
                                        "last_success_at": "2025-12-21T14:30:00Z",
                                        "last_error_at": None,
                                        "last_error": None,
                                    },
                                    {
                                        "provider": "gemini",
                                        "model": "gemini-1.5-pro",
                                        "is_available": True,
                                        "error_rate": 0.01,
                                        "avg_latency_ms": 245.2,
                                        "requests_last_hour": 95,
                                        "last_success_at": "2025-12-21T14:25:00Z",
                                        "last_error_at": "2025-12-21T12:15:00Z",
                                        "last_error": "Rate limit exceeded",
                                    },
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
                            "error_code": "UNAUTHORIZED",
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
                    "llm_provider_error": {
                        "summary": "LLM Provider Error - Provider Specific Failure",
                        "value": {
                            "error_code": "LLM_PROVIDER_ERROR",
                            "message": "Failed to retrieve LLM provider health status",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
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

get_llm_provider_health_custom_errors = ["401", "500"]
get_llm_provider_health_custom_success = {
    "status_code": 200,
    "description": "LLM provider health status loaded successfully.",
}

test_llm_connection_responses = {
    200: {
        "description": "LLM connection test completed",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Connection successful",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Successfully connected to openrouter",
                            "data": {
                                "provider": "openrouter",
                                "model": "gpt-4o",
                                "latency_ms": 245,
                                "status": "connected",
                                "response_preview": "OK",
                            },
                        },
                    },
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
                            "error_code": "UNAUTHORIZED",
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
                    "invalid_provider": {
                        "summary": "Invalid provider parameter",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Provider must be 'openrouter' or 'gemini'",
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "provider": ["string does not match regex '^(openrouter|gemini)$'"]
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error - Connection test failed",
        "content": {
            "application/json": {
                "examples": {
                    "llm_provider_error": {
                        "summary": "LLM Provider Error - Connection Failure",
                        "value": {
                            "error_code": "LLM_PROVIDER_ERROR",
                            "message": "Connection failed for openrouter: Authentication failed",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

test_llm_connection_custom_errors = ["400", "401", "422", "500"]
test_llm_connection_custom_success = {
    "status_code": 200,
    "description": "LLM connection test completed.",
}

get_usage_by_organization_responses = {
    200: {
        "description": "Organization LLM usage loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Organization usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "Organization usage for the last 30 days loaded successfully."
                            ),
                            "data": {
                                "organizations": [
                                    {
                                        "organization_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "organization_name": "Acme Corporation",
                                        "plan": "premium",
                                        "unique_users": 15,
                                        "request_count": 1250,
                                        "total_tokens": 500000,
                                        "total_cost_usd": 125.50,
                                        "last_request_at": "2025-12-30T00:00:00Z",
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
                            "error_code": "UNAUTHORIZED",
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
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is less than or equal to 365"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve organization usage data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request at this time. Try again.",
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

get_usage_by_organization_custom_errors = ["400", "401", "422", "500"]
get_usage_by_organization_custom_success = {
    "status_code": 200,
    "description": "Organization usage loaded successfully.",
}

get_usage_by_user_responses = {
    200: {
        "description": "User LLM usage loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User usage for the last 30 days loaded successfully.",
                            "data": {
                                "users": [
                                    {
                                        "user_id": "550e8400-e29b-41d4-a716-446655440001",
                                        "user_name": "John Doe",
                                        "user_email": "john@example.com",
                                        "organization_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "organization_name": "Acme Corporation",
                                        "request_count": 150,
                                        "total_tokens": 75000,
                                        "input_tokens": 60000,
                                        "output_tokens": 15000,
                                        "total_cost_usd": 18.75,
                                        "last_request_at": "2025-12-30T00:00:00Z",
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
                            "error_code": "UNAUTHORIZED",
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
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is less than or equal to 365"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve user usage data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request at this time. Try again.",
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

get_usage_by_user_custom_errors = ["400", "401", "422", "500"]
get_usage_by_user_custom_success = {
    "status_code": 200,
    "description": "User usage loaded successfully.",
}

get_usage_by_project_responses = {
    200: {
        "description": "Project LLM usage loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project usage breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project usage for the last 30 days loaded successfully.",
                            "data": {
                                "projects": [
                                    {
                                        "project_id": "550e8400-e29b-41d4-a716-446655440002",
                                        "project_name": "Legal Research Bot",
                                        "organization_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "request_count": 500,
                                        "total_tokens": 250000,
                                        "total_cost_usd": 62.50,
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
                            "error_code": "UNAUTHORIZED",
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
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 365 days",
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is less than or equal to 365"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve project usage data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to process your request this time. Try again later.",
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

get_usage_by_project_custom_errors = ["400", "401", "422", "500"]
get_usage_by_project_custom_success = {
    "status_code": 200,
    "description": "Project usage loaded successfully.",
}

get_detailed_logs_responses = {
    200: {
        "description": "Detailed LLM request logs loaded successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Detailed request logs with full attribution",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Retrieved 100 detailed LLM request logs.",
                            "data": {
                                "total": 1250,
                                "limit": 100,
                                "offset": 0,
                                "logs": [
                                    {
                                        "id": "550e8400-e29b-41d4-a716-446655440003",
                                        "request_id": "req_abc123",
                                        "model": "anthropic/claude-3.5-sonnet",
                                        "provider": "openrouter",
                                        "user": {
                                            "id": "550e8400-e29b-41d4-a716-446655440001",
                                            "name": "John Doe",
                                            "email": "john@example.com",
                                        },
                                        "organization": {
                                            "id": "550e8400-e29b-41d4-a716-446655440000",
                                            "name": "Acme Corporation",
                                        },
                                        "project": {
                                            "id": "550e8400-e29b-41d4-a716-446655440002",
                                            "name": "Legal Research Bot",
                                        },
                                        "tokens": {
                                            "input": 1500,
                                            "output": 300,
                                            "total": 1800,
                                        },
                                        "cost_usd": 0.0088,
                                        "latency_ms": 1234.5,
                                        "success": True,
                                        "error_message": None,
                                        "endpoint": "/api/v1/sources/extract",
                                        "ip_address": "192.168.1.1",
                                        "created_at": "2025-12-30T00:00:00Z",
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
                            "error_code": "UNAUTHORIZED",
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
                    "date_range_exceeded": {
                        "summary": "Date range exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Date range cannot exceed 90 days for detailed logs",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "limit_exceeded": {
                        "summary": "Limit exceeded",
                        "value": {
                            "error_code": "INVALID_INPUT",
                            "message": "Limit cannot exceed 1000 records",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"days": ["ensure this value is less than or equal to 90"]},
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
                    "llm_query_error": {
                        "summary": "LLM Query Error - Data Retrieval Failure",
                        "value": {
                            "error_code": "LLM_QUERY_ERROR",
                            "message": "Failed to retrieve detailed logs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - Database/System Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Cannot process your request at this time. Try again later.",
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

get_detailed_logs_custom_errors = ["400", "401", "422", "500"]
get_detailed_logs_custom_success = {
    "status_code": 200,
    "description": "Detailed logs loaded successfully.",
}
