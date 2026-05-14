google_login_responses = {
    302: {
        "description": "Redirect to Google OAuth consent screen",
        "content": {
            "application/json": {
                "examples": {
                    "redirect": {
                        "summary": "Redirecting to Google",
                        "value": {
                            "message": "Redirecting to Google OAuth consent screen",
                            "redirect_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&state=...",
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid client parameter",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_client": {
                        "summary": "Invalid client parameter",
                        "value": {
                            "error_code": "INVALID_CLIENT",
                            "message": "There's an issue with the login request. Please try again.",
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
                    "processing_error": {
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Unable to complete sign-in with Google. "
                            "Please try again or use email login.",
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

google_login_custom_errors = ["400", "500"]
google_login_custom_success = {
    "status_code": 302,
    "description": "Redirect to Google OAuth consent screen initiated successfully.",
}


google_callback_responses = {
    302: {
        "description": "Authentication Successful - Redirecting to Frontend",
        "content": {
            "application/json": {
                "examples": {
                    "new_user_redirect": {
                        "summary": "New User Registered via Google",
                        "value": {
                            "message": "Redirecting to frontend with tokens",
                            "redirect_url": "https://app.example.com/auth/google/callback?is_new_user=true#access_token=...",
                            "cookies_set": ["lwd_access_token", "lwd_refresh_token"],
                        },
                    },
                    "existing_user_redirect": {
                        "summary": "Existing User Logged In",
                        "value": {
                            "message": "Redirecting to frontend with tokens",
                            "redirect_url": "https://app.example.com/auth/google/callback?is_new_user=false#access_token=...",
                            "cookies_set": ["lwd_access_token", "lwd_refresh_token"],
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - OAuth Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_state": {
                        "summary": "Invalid or Expired State Parameter",
                        "value": {
                            "error_code": "OAUTH_STATE_INVALID",
                            "message": "For your security, we need you to start the login process "
                            "again. Please try signing in once more.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "missing_code": {
                        "summary": "Missing Authorization Code",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Missing authorization code",
                            "status_code": 400,
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
                            "message": "Unable to complete sign-in with Google. "
                            "Please try again or use email login.",
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

google_callback_custom_errors = ["400", "500"]
google_callback_custom_success = {
    "status_code": 302,
    "description": "Google OAuth completed successfully. User redirected to frontend with tokens.",
}


google_profile_responses = {
    200: {
        "description": "Profile Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Profile Data",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Profile retrieved successfully",
                            "status_code": 200,
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "email": "user@example.com",
                                "name": "John Doe",
                                "profile_picture_url": "https://lh3.googleusercontent.com/...",
                                "auth_provider": "google",
                                "provider_user_id": "1234567890",
                                "provider_profile_data": {
                                    "given_name": "John",
                                    "family_name": "Doe",
                                    "picture": "https://lh3.googleusercontent.com/...",
                                },
                                "is_verified": True,
                                "created_at": "2023-10-01T12:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - User Not Authenticated",
        "content": {
            "application/json": {
                "examples": {
                    "unauthorized": {
                        "summary": "Authentication Required",
                        "value": {
                            "error_code": "INVALID_TOKEN",
                            "message": "Invalid token or expired token",
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
                    "processing_error": {
                        "summary": "Business Logic Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "We're unable to retrieve your profile information "
                            "at this time. Please try again later.",
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

google_profile_custom_errors = ["401", "500"]
google_profile_custom_success = {
    "status_code": 200,
    "description": "User profile retrieved successfully including OAuth provider metadata.",
}
