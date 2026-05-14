# REQUEST PASSWORD RESET ENDPOINT DOCS
request_reset_responses = {
    200: {
        "description": "Password reset code sent",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Reset code sent",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Reset code sent to email.",
                            "data": {"email": "user@example.com"},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Account inactive",
        "content": {
            "application/json": {
                "examples": {
                    "inactive_user": {
                        "summary": "Account is inactive",
                        "value": {
                            "error_code": "ACCOUNT_INACTIVE",
                            "message": "Account is inactive. Please contact support.",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            },
        },
    },
    404: {
        "description": "Email does not exist",
        "content": {
            "application/json": {
                "examples": {
                    "email_not_found": {
                        "summary": "User not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Email does not exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid input",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "value is not a valid email address: "
                                    "An email address cannot have a period immediately after the"
                                    " @-sign.",
                                    "value is not a valid email address: "
                                    "The part after the @-sign is not valid. "
                                    "It should have a period.",
                                ]
                            },
                        },
                    },
                    "missing_field": {
                        "summary": "Missing required field",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required."]},
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "email_rate_limit": {
                        "summary": "Rate Limit Exceeded for Email",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests for this email. Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "ip_rate_limit": {
                        "summary": "Rate Limit Exceeded for IP",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests from this IP. Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                }
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Password reset request failed. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_error": {
                        "summary": "Infrastructure Failure",
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

request_reset_custom_errors = ["403", "404", "422", "429", "500"]
request_reset_custom_success = {
    "status_code": 200,
    "description": "Password reset code sent successfully to the registered email.",
}

# VERIFY RESET TOKEN ENDPOINT DOCS
verify_reset_responses = {
    200: {
        "description": "Reset token verified successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Token verified",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Token verified successfully.",
                            "data": {"reset_token": "<temporary_reset_token>"},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Invalid or expired token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Reset code invalid or expired",
                        "value": {
                            "error_code": "INVALID_RESET_CODE",
                            "message": (
                                "The reset code you entered is invalid or has expired. "
                                "Please request a new one."
                            ),
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Invalid input",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "value is not a valid email address: "
                                    "An email address cannot have a period immediately after "
                                    "the @-sign.",
                                    "value is not a valid email address: "
                                    "The part after the @-sign is not valid. "
                                    "It should have a period.",
                                ]
                            },
                        },
                    },
                    "missing_field": {
                        "summary": "Missing required field",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required."], "code": ["Field required."]},
                        },
                    },
                    "invalid_code_format": {
                        "summary": "Invalid OTP Format",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "validation failed",
                            "status_code": 422,
                            "errors": {"code": ["String should have at least 6 characters"]},
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "email_rate_limit": {
                        "summary": "Rate Limit Exceeded for Email",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many verification attempts from this email. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "ip_rate_limit": {
                        "summary": "Rate Limit Exceeded for IP",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many verification attempts from this IP. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                }
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Password verification failed. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_error": {
                        "summary": "Infrastructure Failure",
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

verify_reset_custom_errors = ["400", "422", "429", "500"]
verify_reset_custom_success = {
    "status_code": 200,
    "description": "Reset token verified successfully.",
}


# CONFIRM RESET PASSWORD ENDPOINT DOCS
confirm_reset_responses = {
    200: {
        "description": "Password reset successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Password updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Password reset successful.",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Invalid token or password reuse",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Token invalid or expired",
                        "value": {
                            "error_code": "RESET_TOKEN_EXPIRED",
                            "message": (
                                "Your reset link has expired for security reasons. "
                                "Please request a new password reset."
                            ),
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "password_reuse": {
                        "summary": "Old password reuse attempt",
                        "value": {
                            "error_code": "PASSWORD_REUSE_ERROR",
                            "message": "New password cannot be the same as your old password",
                            "status_code": 400,
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
                    "missing_fields": {
                        "summary": "Missing Required Fields",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "reset_token": ["Field required"],
                                "password": ["Field required"],
                                "confirm_password": ["Field required"],
                            },
                        },
                    },
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "password": [
                                    "String should have at least 8 characters",
                                    "Password must contain: one uppercase letter, "
                                    "one digit, one special character.",
                                ],
                            },
                        },
                    },
                    "password_mismatch": {
                        "summary": "Password Confirmation Mismatch",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"confirm_password": ["Passwords do not match"]},
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "email_rate_limit": {
                        "summary": "Rate Limit Exceeded for Email",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many confirmation attempts. Please try again in 1 hour",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "ip_rate_limit": {
                        "summary": "Rate Limit Exceeded for IP",
                        "value": {
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many confirmation attempts from this IP. "
                            "Please retry in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                }
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": (
                                "Password reset confirmation failed. Please try again later."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "internal_error": {
                        "summary": "Infrastructure Failure",
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

confirm_reset_custom_errors = ["400", "422", "429", "500"]
confirm_reset_custom_success = {
    "status_code": 200,
    "description": "Password reset completed successfully.",
}
