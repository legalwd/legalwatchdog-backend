webhook_onboard_responses = {
    201: {
        "description": "API Key Created via Webhook",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "API Key Generated",
                        "value": {
                            "api_key": "lwd_sk_live_1234567890abcdef",
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "ERROR",
                            "message": "Validation failed",
                            "status_code": 400,
                            "errors": {
                                "organization_id": ["Field required"],
                                "key_name": ["Field required"],
                                "scopes": ["Field required"],
                            },
                        },
                    },
                    "invalid_scopes": {
                        "summary": "Invalid Scopes Provided",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid scope provided",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Invalid Webhook Secret",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_secret": {
                        "summary": "Invalid Webhook Secret",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid webhook secret",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "missing_secret": {
                        "summary": "Missing Webhook Secret Header",
                        "value": {
                            "error": "ERROR",
                            "message": "X-WEBHOOK-SECRET header is required",
                            "status_code": 403,
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
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["Invalid UUID format"],
                                "scopes": ["Must be a list of strings"],
                                "generated_by": ["Field required"],
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to generate API key via webhook",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

webhook_onboard_custom_errors = ["400", "403", "422", "500"]
webhook_onboard_custom_success = {
    "status_code": 201,
    "description": "API key created successfully via webhook"
    " for integrations that can't receive emails.",
}
