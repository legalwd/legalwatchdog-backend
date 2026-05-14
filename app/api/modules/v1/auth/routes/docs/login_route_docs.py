# LOGIN ENDPOINT DOCS
login_responses = {
    200: {
        "description": "Login Successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Authenticated",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Login successful",
                            "status_code": 200,
                            "data": {
                                "access_token": "<access_token>",
                                "refresh_token": "<refresh_token>",
                                "token_type": "bearer",
                                "expires_in": 3600,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid Credentials or Account Issues",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_credentials": {
                        "summary": "Wrong Email or Password",
                        "value": {
                            "message": (
                                "The email or password you entered is incorrect. Please try again."
                            ),
                            "error_code": "INVALID_CREDENTIALS",
                            "status_code": 401,
                        },
                    },
                    "invalid_token": {
                        "summary": "Invalid Session Token",
                        "value": {
                            "message": "Your session is invalid. Please log in again.",
                            "error_code": "INVALID_TOKEN",
                            "status_code": 401,
                        },
                    },
                    "token_expired": {
                        "summary": "Session Expired",
                        "value": {
                            "message": "Your session has expired. Please log in again to continue.",
                            "error_code": "TOKEN_EXPIRED",
                            "status_code": 401,
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Account Not Active or Verified",
        "content": {
            "application/json": {
                "examples": {
                    "account_inactive": {
                        "summary": "Account Deactivated",
                        "value": {
                            "message": (
                                "Your account has been deactivated. Please "
                                "contact our support team for assistance."
                            ),
                            "error_code": "ACCOUNT_INACTIVE",
                            "status_code": 403,
                        },
                    },
                    "account_unverified": {
                        "summary": "Email Not Verified",
                        "value": {
                            "message": (
                                "Please verify your email address before "
                                "logging in. Check your inbox for the "
                                "verification link."
                            ),
                            "error_code": "ACCOUNT_UNVERIFIED",
                            "status_code": 403,
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Too Many Requests - Rate Limit or Account Locked",
        "content": {
            "application/json": {
                "examples": {
                    "account_locked": {
                        "summary": "Account Temporarily Locked",
                        "value": {
                            "message": (
                                "Your account has been temporarily locked for "
                                "security reasons. Please try again later."
                            ),
                            "error_code": "ACCOUNT_LOCKED",
                            "status_code": 429,
                        },
                    },
                    "rate_limit_exceeded": {
                        "summary": "Too Many Login Attempts",
                        "value": {
                            "message": "Too many requests. Please try again later.",
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "status_code": 429,
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"email": ["Field required"], "code": ["Field required"]},
                        },
                    },
                    "invalid_code_format": {
                        "summary": "Invalid Email Format",
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
                                ],
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
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Login failed. Please try again later.",
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

login_custom_errors = ["401", "403", "422", "429", "500"]
login_custom_success = {"status_code": 200, "description": "Login successful and tokens issued."}

# REFRESH TOKEN ENDPOINT DOCS
refresh_token_responses = {
    200: {
        "description": "Refresh Token Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "New Tokens Issued",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Token refreshed successfully",
                            "data": {
                                "access_token": "<new_access_token>",
                                "refresh_token": "<new_refresh_token>",
                                "token_type": "bearer",
                                "expires_in": 3600,
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid or Expired Token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_token": {
                        "summary": "Invalid Refresh Token",
                        "value": {
                            "message": "Your session is invalid. Please log in again.",
                            "error_code": "INVALID_TOKEN",
                            "status_code": 401,
                        },
                    },
                    "token_expired": {
                        "summary": "Refresh Token Expired",
                        "value": {
                            "message": "Your session has expired. Please log in again to continue.",
                            "error_code": "TOKEN_EXPIRED",
                            "status_code": 401,
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Account Inactive",
        "content": {
            "application/json": {
                "examples": {
                    "account_inactive": {
                        "summary": "Account Deactivated",
                        "value": {
                            "message": (
                                "Your account has been deactivated. Please "
                                "contact support for assistance."
                            ),
                            "error_code": "ACCOUNT_INACTIVE",
                            "status_code": 403,
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User Account Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "summary": "User Account Not Found",
                        "value": {
                            "message": "Your account could not be found. Please log in again.",
                            "error_code": "NOT_FOUND",
                            "status_code": 404,
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
                        "summary": "Request Validation Failed - Missing Fields",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "refresh_token": ["Field required"],
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
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Token refresh failed. Please try again later.",
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

refresh_custom_errors = ["401", "403", "404", "422", "500"]
refresh_custom_success = {
    "status_code": 200,
    "description": "Refresh token validated and new tokens issued.",
}

# LOGOUT ENDPOINT DOCS
logout_responses = {
    200: {
        "description": "Logout Successful",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Tokens Blacklisted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Logged out successfully",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid User",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Invalid token or expired token",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "authentication_failed": {
                        "summary": "Authentication Failed",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Authentication failed",
                            "status_code": 401,
                            "errors": {},
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
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Logout failed. Please try again later.",
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

logout_custom_errors = ["401", "500"]
logout_custom_success = {
    "status_code": 200,
    "description": "User logged out and tokens blacklisted successfully.",
}
