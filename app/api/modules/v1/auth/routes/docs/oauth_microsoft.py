microsoft_login_responses = {
    200: {
        "description": "Authorization URL Generated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Microsoft authorization URL generated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Authorization URL generated successfully",
                            "data": {
                                "authorization_url": "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?client_id=...&state=...",
                                "state": "randomStateString123",
                            },
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_redirect_uri": {
                        "summary": "Invalid redirect URI",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Invalid Redirect URI Format",
                            "status_code": 422,
                            "errors": {"redirect_uri": ["Must be a valid URL format"]},
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
                        "summary": "Failed to initiate Microsoft login",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to initiate Microsoft login",
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


microsoft_login_custom_errors = ["422", "500"]
microsoft_login_custom_success = {
    "status_code": 200,
    "description": "Authorization URL generated successfully. Redirect user to this URL.",
}


microsoft_callback_responses = {
    302: {
        "description": "Authentication Successful - Redirecting to Frontend",
        "content": {
            "application/json": {
                "examples": {
                    "new_user_redirect": {
                        "summary": "New user registered via Microsoft",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 302,
                            "message": "Redirecting to new user onboarding page",
                            "data": {
                                "redirect_url": "https://app.example.com/onboarding",
                                "cookies_set": [
                                    "lwd_access_token",
                                    "lwd_refresh_token",
                                ],
                            },
                        },
                    },
                    "existing_user_redirect": {
                        "summary": "Existing user logged in via Microsoft",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 302,
                            "message": "Redirecting to dashboard",
                            "redirect_url": "https://app.example.com/app",
                            "cookies_set": ["lwd_access_token", "lwd_refresh_token"],
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - OAuth Error from Microsoft",
        "content": {
            "application/json": {
                "examples": {
                    "oauth_error": {
                        "summary": "Microsoft OAuth authorization error",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "User denied the authorization request",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Invalid State or Token",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_state": {
                        "summary": "Invalid or expired OAuth state",
                        "value": {
                            "error_code": "OAUTH_STATE_INVALID",
                            "message": "For your security, we need you to start the login process "
                            "again. Please try signing in once more.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "token_exchange_failed": {
                        "summary": "Authorization code exchange failed",
                        "value": {
                            "error_code": "OAUTH_TOKEN_EXCHANGE_FAILED",
                            "message": "Failed to exchange code for access token",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                    "missing_access_token": {
                        "summary": "Access token missing from Microsoft response",
                        "value": {
                            "error_code": "MISSING_ID_TOKEN",
                            "message": "We didn't receive complete authentication information "
                            "from Microsoft. Please try again.",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "missing_code": {
                        "summary": "Authorization code missing",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Authorization code is required",
                            "status_code": 422,
                            "errors": {"code": ["This field is required"]},
                        },
                    },
                    "missing_state": {
                        "summary": "OAuth state parameter missing",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "State parameter is required",
                            "status_code": 422,
                            "errors": {"state": ["This field is required"]},
                        },
                    },
                    "invalid_parameters": {
                        "summary": "Invalid OAuth callback parameters",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Invalid OAuth callback parameters",
                            "status_code": 422,
                            "errors": {
                                "code": ["Authorization code format is invalid"],
                                "state": ["State parameter format is invalid"],
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
                        "summary": "Failed to complete Microsoft OAuth flow",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": (
                                "Unable to complete sign-in with Microsoft. "
                                "Please try again or use email login."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "graph_api_error": {
                        "summary": "Microsoft Graph API communication failed",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to complete sign-in with Microsoft. "
                            "Please try again or use email login.",
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


microsoft_callback_custom_errors = ["400", "401", "422", "500"]
microsoft_callback_custom_success = {
    "status_code": 302,
    "description": "Logged in successfully. Tokens set as httpOnly cookies and user redirected.",
}
