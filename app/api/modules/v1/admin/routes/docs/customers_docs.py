list_customers_responses = {
    200: {
        "description": "Customers retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated customer list",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Customers retrieved successfully",
                            "data": {
                                "customers": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "John Doe",
                                        "email": "john@example.com",
                                        "payment_status": "paid",
                                        "plan": {
                                            "tier": "PROFESSIONAL",
                                            "label": "Professional Monthly",
                                            "interval": "month",
                                            "amount": 7900,
                                        },
                                        "registration_date": "2024-01-15T10:00:00Z",
                                        "last_active": "2024-02-10T15:30:00Z",
                                        "credits_used": 50000,
                                        "amount_spent": 150.00,
                                    }
                                ],
                                "meta": {"total": 1, "page": 1, "limit": 20, "total_pages": 1},
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
                    "invalid_payment_status": {
                        "summary": "Invalid payment status",
                        "value": {
                            "error": "PAYMENT_STATUS_ERROR",
                            "message": "Invalid payment status: invalid."
                            "Must be one of: trialing, paid, past_due",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_filter": {
                        "summary": "Invalid filter parameters",
                        "value": {
                            "error": "INVALID_CUSTOMER_FILTER",
                            "message": "Invalid sort field: invalid_field."
                            "Must be one of: created_at, last_active, credits_used",
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
                            "error": "INVALID_CUSTOMER_FILTER",
                            "message": "Limit must be between 1 and 100",
                            "status_code": 422,
                            "errors": {"limit": ["Must be between 1 and 100"]},
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
                    "data_retrieval_error": {
                        "summary": "Customer Data Retrieval Error",
                        "value": {
                            "error": "CUSTOMER_DATA_RETRIEVAL_ERROR",
                            "message": "Failed to retrieve customers list",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve customers",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_customer_detail_responses = {
    200: {
        "description": "Customer detail retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Customer detail",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Customer details retrieved successfully",
                            "data": {
                                "profile": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "name": "Jane Roe",
                                    "email": "jane@example.com",
                                    "payment_status": "paid",
                                    "plan": {
                                        "tier": "ESSENTIAL",
                                        "label": "Essential Monthly",
                                        "interval": "month",
                                        "amount": 2900,
                                    },
                                    "registration_date": "2024-01-15T10:00:00Z",
                                    "last_active": "2024-02-10T15:30:00Z",
                                    "credits_used": 30000,
                                    "amount_spent": 99.99,
                                },
                                "feature_usage": [
                                    {
                                        "feature": "AI Source Extraction",
                                        "credits_used": 30000,
                                        "usage_count": 100,
                                    }
                                ],
                                "llm_usage": {
                                    "total_requests": 50,
                                    "total_cost_usd": 5.00,
                                    "total_tokens": 25000,
                                },
                                "parallel_usage": {
                                    "total_requests": 30,
                                    "total_cost_usd": 3.00,
                                    "total_content_mb": 15.5,
                                },
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
    404: {
        "description": "Not Found - Customer not found",
        "content": {
            "application/json": {
                "examples": {
                    "customer_not_found": {
                        "summary": "Customer not found",
                        "value": {
                            "error": "CUSTOMER_NOT_FOUND",
                            "message": "Customer with ID"
                            "123e4567-e89b-12d3-a456-426614174000 not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid UUID or parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_uuid": {
                        "summary": "Invalid UUID format",
                        "value": {
                            "error": "BAD_REQUEST",
                            "message": "Invalid user_id format",
                            "status_code": 400,
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
                    "data_retrieval_error": {
                        "summary": "Customer Data Retrieval Error",
                        "value": {
                            "error": "CUSTOMER_DATA_RETRIEVAL_ERROR",
                            "message": "Failed to retrieve details for"
                            "customer 123e4567-e89b-12d3-a456-426614174000",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve customer details",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_customer_activity_responses = {
    200: {
        "description": "Customer activity retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Activity timeline",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Customer activity for the last 7"
                            "days retrieved successfully",
                            "data": {
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                "date_range": {
                                    "start_date": "2025-12-13T00:00:00Z",
                                    "end_date": "2025-12-20T00:00:00Z",
                                    "days": 7,
                                },
                                "feature_usage": [
                                    {"date": "2025-12-18", "credits_used": 5000, "requests": 50}
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
    404: {
        "description": "Not Found - Customer not found",
        "content": {
            "application/json": {
                "examples": {
                    "customer_not_found": {
                        "summary": "Customer not found",
                        "value": {
                            "error": "CUSTOMER_NOT_FOUND",
                            "message": "Customer with"
                            "ID 123e4567-e89b-12d3-a456-426614174000 not found",
                            "status_code": 404,
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
                            "error": "INVALID_CUSTOMER_FILTER",
                            "message": "Days must be between 1 and 90",
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
                            "error": "INVALID_CUSTOMER_FILTER",
                            "message": "Days must be between 1 and 90",
                            "status_code": 422,
                            "errors": {"days": ["Must be between 1 and 90"]},
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
                    "activity_error": {
                        "summary": "Customer Activity Error",
                        "value": {
                            "error": "CUSTOMER_ACTIVITY_ERROR",
                            "message": "Failed to retrieve activity for"
                            "customer 123e4567-e89b-12d3-a456-426614174000",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve customer activity",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_customers_custom_errors = ["400", "401", "422", "404", "500"]
get_customers_custom_success = {
    "status_code": 200,
    "description": "Customers retrieved successfully.",
}

# Activation/Deactivation endpoints documentation
activate_customer_responses = {
    200: {
        "description": "Customer Approved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Customer Account Approved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Customer approved successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "customer@example.com",
                                "name": "Jane Smith",
                                "is_approved": True,
                                "approved_at": "2024-01-26T12:00:00+00:00",
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
    403: {
        "description": "Forbidden - Superadmin access required",
        "content": {
            "application/json": {
                "examples": {
                    "not_superadmin": {
                        "summary": "Not a Superadmin",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": (
                                "You don't have permission to activate customers. "
                                "Please contact the system administrator."
                            ),
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Customer Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "customer_not_found": {
                        "summary": "Customer Does Not Exist",
                        "value": {
                            "error_code": "CUSTOMER_NOT_FOUND",
                            "message": "Customer with ID not found",
                            "status_code": 404,
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": ("Failed to activate customer. Please try again."),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": ("Internal Server Error - Unexpected Failure"),
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": ("An unexpected error occurred. Please try again later."),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

deactivate_customer_responses = {
    200: {
        "description": "Customer Approval Revoked Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Customer Approval Revoked",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Customer approval revoked successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "customer@example.com",
                                "name": "Jane Smith",
                                "is_approved": False,
                                "approved_at": "2024-01-26T12:00:00+00:00",
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
    403: {
        "description": "Forbidden - Superadmin access required",
        "content": {
            "application/json": {
                "examples": {
                    "not_superadmin": {
                        "summary": "Not a Superadmin",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": (
                                "You don't have permission to "
                                "deactivate customers. "
                                "Please contact the system administrator."
                            ),
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Customer Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "customer_not_found": {
                        "summary": "Customer Does Not Exist",
                        "value": {
                            "error_code": "CUSTOMER_NOT_FOUND",
                            "message": "Customer with ID not found",
                            "status_code": 404,
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": ("Failed to deactivate customer. Please try again."),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": ("Internal Server Error - Unexpected Failure"),
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": ("An unexpected error occurred. Please try again later."),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

activate_customer_custom_errors = ["401", "403", "404", "500"]
activate_customer_custom_success = {
    "status_code": 200,
    "description": (
        "Customer account approved successfully. User now has access to application features."
    ),
}

deactivate_customer_custom_errors = ["401", "403", "404", "500"]
deactivate_customer_custom_success = {
    "status_code": 200,
    "description": (
        "Customer approval revoked successfully. User can still login but cannot access features."
    ),
}
