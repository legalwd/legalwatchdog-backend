get_dashboard_overview_responses = {
    200: {
        "description": "Dashboard overview retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Dashboard overview with revenue, users, credits and breakdowns",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Dashboard overview loaded successfully.",
                            "data": {
                                "revenue": {
                                    "total": 150000.00,
                                    "vs_last_month": 8.5,
                                    "trend": [{"month": "2025-11", "revenue": 12000.00}],
                                },
                                "users": {"new_users": 45, "total_users": 320},
                                "ai_credits": {"total_tokens": 1500000},
                                "parallel_ai": {"total_requests": 1200, "total_cost": "1.25"},
                                "payment_breakdown": {"trialing": 100, "paid": 220},
                                "date_range": {
                                    "start_date": "2025-11-20T00:00:00Z",
                                    "end_date": "2025-12-20T00:00:00Z",
                                    "days": 30,
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
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_params": {
                        "summary": "Invalid date range",
                        "value": {
                            "error": "INVALID_DATE_RANGE",
                            "message": "Days must be between 1 and 365",
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
                            "errors": {"days": ["Ensure this value is between 1 and 365"]},
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Dashboard Service Error",
        "content": {
            "application/json": {
                "examples": {
                    "dashboard_overview_error": {
                        "summary": "Dashboard Overview Error",
                        "value": {
                            "error": "DASHBOARD_OVERVIEW_ERROR",
                            "message": "Unable to load dashboard overview. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "dashboard_error": {
                        "summary": "Dashboard Error - General Failure",
                        "value": {
                            "error": "DASHBOARD_ERROR",
                            "message": "Dashboard service encountered an error",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "revenue_metrics_error": {
                        "summary": "Revenue Metrics Error",
                        "value": {
                            "error": "REVENUE_METRICS_ERROR",
                            "message": "Unable to calculate revenue metrics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "user_metrics_error": {
                        "summary": "User Metrics Error",
                        "value": {
                            "error": "USER_METRICS_ERROR",
                            "message": "Unable to calculate user metrics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "ai_credits_metrics_error": {
                        "summary": "AI Credits Metrics Error",
                        "value": {
                            "error": "AI_CREDITS_METRICS_ERROR",
                            "message": "Unable to calculate AI credits metrics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "parallel_metrics_error": {
                        "summary": "Parallel Metrics Error",
                        "value": {
                            "error": "PARALLEL_METRICS_ERROR",
                            "message": "Unable to calculate parallel metrics",
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

get_dashboard_overview_custom_success = {
    "status_code": 200,
    "description": "Dashboard overview retrieved successfully.",
}
get_dashboard_overview_custom_errors = ["400", "401", "422", "500"]

get_revenue_trend_responses = {
    200: {
        "description": "Revenue trend retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Monthly revenue trend",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Revenue trends for the last 6 months loaded successfully.",
                            "data": {"trend": [{"month": "2025-01", "revenue": 12000.0}]},
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
                        "summary": "Invalid date range",
                        "value": {
                            "error": "INVALID_DATE_RANGE",
                            "message": "Months must be between 1 and 24",
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
                            "errors": {"months": ["Must be between 1 and 24"]},
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
        "description": "Revenue Service Error",
        "content": {
            "application/json": {
                "examples": {
                    "revenue_trend_error": {
                        "summary": "Revenue Trend Error",
                        "value": {
                            "error": "REVENUE_TREND_ERROR",
                            "message": "Unable to load revenue trends. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "revenue_metrics_error": {
                        "summary": "Revenue Metrics Error",
                        "value": {
                            "error": "REVENUE_METRICS_ERROR",
                            "message": "Unable to calculate revenue metrics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "dashboard_error": {
                        "summary": "Dashboard Error - General Failure",
                        "value": {
                            "error": "DASHBOARD_ERROR",
                            "message": "Dashboard service encountered an error",
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

get_revenue_trend_custom_success = {
    "status_code": 200,
    "description": "Revenue trends retrieved successfully.",
}
get_revenue_trend_custom_errors = ["400", "401", "422", "500"]

get_ai_credits_trend_responses = {
    200: {
        "description": "AI credits trend retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Monthly token usage",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "AI credit usage trends for the last 6 months loaded successfully."
                            ),
                            "data": {"trend": [{"month": "2025-01", "tokens": 150000}]},
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
                        "summary": "Invalid date range",
                        "value": {
                            "error": "INVALID_DATE_RANGE",
                            "message": "Months must be between 1 and 24",
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
                            "errors": {"months": ["Must be between 1 and 24"]},
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
        "description": "AI Credits Service Error",
        "content": {
            "application/json": {
                "examples": {
                    "ai_credits_trend_error": {
                        "summary": "AI Credits Trend Error",
                        "value": {
                            "error": "AI_CREDITS_TREND_ERROR",
                            "message": "Unable to load AI credit trends. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "ai_credits_metrics_error": {
                        "summary": "AI Credits Metrics Error",
                        "value": {
                            "error": "AI_CREDITS_METRICS_ERROR",
                            "message": "Unable to calculate AI credits metrics",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "dashboard_error": {
                        "summary": "Dashboard Error - General Failure",
                        "value": {
                            "error": "DASHBOARD_ERROR",
                            "message": "Dashboard service encountered an error",
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

get_ai_credits_trend_custom_success = {
    "status_code": 200,
    "description": "AI credit trends retrieved successfully.",
}
get_ai_credits_trend_custom_errors = ["400", "401", "422", "500"]

get_payment_breakdown_responses = {
    200: {
        "description": "Payment breakdown retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Monthly payment breakdown",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "Payment breakdown for the last 12 months loaded successfully."
                            ),
                            "data": {
                                "breakdown": [{"month": "2025-01", "trialing": 100, "paid": 50}]
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
                        "summary": "Invalid date range",
                        "value": {
                            "error": "INVALID_DATE_RANGE",
                            "message": "Months must be between 1 and 24",
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
                            "errors": {"months": ["Must be between 1 and 24"]},
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
        "description": "Payment Breakdown Service Error",
        "content": {
            "application/json": {
                "examples": {
                    "payment_breakdown_error": {
                        "summary": "Payment Breakdown Error",
                        "value": {
                            "error": "PAYMENT_BREAKDOWN_ERROR",
                            "message": "Unable to load payment breakdown. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "dashboard_error": {
                        "summary": "Dashboard Error - General Failure",
                        "value": {
                            "error": "DASHBOARD_ERROR",
                            "message": "Dashboard service encountered an error",
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

get_payment_breakdown_custom_success = {
    "status_code": 200,
    "description": "Payment breakdown retrieved successfully.",
}
get_payment_breakdown_custom_errors = ["400", "401", "422", "500"]
