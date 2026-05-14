apple_login_responses = {
    200: {
        "description": "Apple login successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User authenticated via Apple",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Apple login successful",
                            "status_code": 200,
                            "data": {
                                "access_token": "<access_token>",
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "is_new_user": True,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Failed",
        "content": {
            "application/json": {
                "examples": {
                    "token_exchange_failed": {
                        "summary": "Failed to exchange authorization code",
                        "value": {
                            "error_code": "OAUTH_TOKEN_EXCHANGE_FAILED",
                            "message": "The login information from Apple is invalid.  "
                            "Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_verification_failed": {
                        "summary": "Failed to verify ID token",
                        "value": {
                            "error_code": "OAUTH_TOKEN_VERIFICATION_FAILED",
                            "message": "The login information from Apple is invalid. "
                            "Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_expired": {
                        "summary": "Token has expired",
                        "value": {
                            "error_code": "OAUTH_TOKEN_VERIFICATION_FAILED",
                            "message": "Your Apple login session has expired. "
                            "Please try signing in again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "missing_id_token": {
                        "summary": "ID token missing from response",
                        "value": {
                            "error_code": "MISSING_ID_TOKEN",
                            "message": "We didn't receive complete authentication information "
                            "from Apple. Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Apple login data",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_data": {
                        "summary": "Invalid Apple login information",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "The login information from Apple is invalid. "
                            "Please try again.",
                            "status_code": 400,
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
                                "code": ["Field required"],
                                "redirect_uri": ["Field required"],
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
                        "summary": "Failed to process Apple sign-in",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "We're unable to complete Apple sign-in at this time. "
                            "Please try again later or use email login.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_server_error": {
                        "summary": "Internal Server Error",
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

apple_login_custom_errors = ["400", "401", "422", "500"]
apple_login_custom_success = {
    "status_code": 200,
    "description": "Apple login successful. User authenticated and access token issued.",
}


apple_callback_responses = {
    200: {
        "description": "Apple OAuth callback successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Login successful via Apple callback",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Login successful",
                            "status_code": 200,
                            "data": {
                                "access_token": "<access_token>",
                                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "is_new_user": False,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Failed",
        "content": {
            "application/json": {
                "examples": {
                    "token_exchange_failed": {
                        "summary": "Failed to exchange authorization code",
                        "value": {
                            "error_code": "OAUTH_TOKEN_EXCHANGE_FAILED",
                            "message": "The login information from Apple is invalid. "
                            "Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_verification_failed": {
                        "summary": "Failed to verify ID token",
                        "value": {
                            "error_code": "OAUTH_TOKEN_VERIFICATION_FAILED",
                            "message": "The login information from Apple is invalid. "
                            "Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_expired": {
                        "summary": "Token has expired",
                        "value": {
                            "error_code": "OAUTH_TOKEN_VERIFICATION_FAILED",
                            "message": "Your Apple login session has expired. "
                            "Please try signing in again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "missing_id_token": {
                        "summary": "ID token missing from response",
                        "value": {
                            "error_code": "MISSING_ID_TOKEN",
                            "message": "We didn't receive complete authentication information "
                            "from Apple. Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid callback data",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_data": {
                        "summary": "Invalid Apple callback information",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "The login information from Apple is invalid. "
                            "Please try again.",
                            "status_code": 400,
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
                        "summary": "Request Validation Failed - Missing Code",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"code": ["Field required"]},
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
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Failed to process Apple sign-in",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to complete sign-in with Apple. "
                            "Please try again or use email login.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

apple_callback_custom_errors = ["400", "401", "422", "500"]
apple_callback_custom_success = {
    "status_code": 200,
    "description": "Apple OAuth callback processed successfully. User authenticated.",
}
