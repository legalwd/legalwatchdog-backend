# ACCEPT INVITATION ENDPOINT DOCS
accept_invitation_responses = {
    200: {
        "description": "Invitation Accepted - User Already Member",
        "content": {
            "application/json": {
                "examples": {
                    "already_member": {
                        "summary": "User Already Member of Organization",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": (
                                "You are already a member of this organization. "
                                "Invitation accepted."
                            ),
                            "data": {"organization_id": "123e4567-e89b-12d3-a456-426614174000"},
                        },
                    }
                }
            }
        },
    },
    302: {
        "description": "Redirect - Invitation Accepted or Registration Required",
        "content": {
            "application/json": {
                "examples": {
                    "authenticated_success": {
                        "summary": "Authenticated User - Added to Organization",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 302,
                            "message": (
                                "Invitation accepted. You have been added to the organization."
                            ),
                            "data": {
                                "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                "organization_name": "Example Organization",
                                "role_name": "Member",
                            },
                        },
                    },
                    "unauthenticated_redirect": {
                        "summary": "Unauthenticated User - Redirect to Registration",
                        "value": {
                            "message": "Redirecting to registration page",
                            "redirect_url": "https://app.example.com/signup?token=abc123...",
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid or Processed Invitation",
        "content": {
            "application/json": {
                "examples": {
                    "already_processed": {
                        "summary": "Invitation Already Processed",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "This invitation has already been accepted.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Email Mismatch",
        "content": {
            "application/json": {
                "examples": {
                    "email_mismatch": {
                        "summary": "Email Address Mismatch",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": (
                                "This invitation was sent to a different email address. "
                                "You can only accept invitations sent to your email."
                            ),
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Invalid Invitation",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Invitation Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The invitation link is invalid or has been removed.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    409: {
        "description": "Conflict - User Already Member",
        "content": {
            "application/json": {
                "examples": {
                    "already_exists": {
                        "summary": "Already Organization Member",
                        "value": {
                            "error_code": "RESOURCE_EXISTS",
                            "message": "You are already a member of this organization.",
                            "status_code": 409,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    410: {
        "description": "Gone - Invitation Expired",
        "content": {
            "application/json": {
                "examples": {
                    "expired": {
                        "summary": "Invitation Expired",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": (
                                "This invitation has expired. Please request a new invitation."
                            ),
                            "status_code": 410,
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
                    "server_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": (
                                "We're unable to process your invitation right now. "
                                "Please try again later."
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "unexpected_error": {
                        "summary": "Unexpected Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to accept invitation. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

accept_invitation_custom_errors = ["400", "403", "404", "409", "410", "500"]
accept_invitation_custom_success = {
    "status_code": 302,
    "description": (
        "Invitation accepted successfully. User added to organization "
        "or redirected to registration."
    ),
}
