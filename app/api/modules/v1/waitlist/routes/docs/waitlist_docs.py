waitlist_signup_responses = {
    201: {
        "description": "Successfully Added to Waitlist",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Waitlist Signup Successful",
                        "value": {
                            "status": "SUCCESS",
                            "message": "Successfully added to waitlist. "
                            "Confirmation email will be sent shortly.",
                            "status_code": 201,
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "organization_name": "Acme Corporation",
                                "organization_email": "contact@acmecorp.com",
                                "position": "Legal Counsel",
                                "created_at": "2023-10-01T12:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    409: {
        "description": "Conflict - Email Already Exists",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_email": {
                        "summary": "Email Already on Waitlist",
                        "value": {
                            "error_code": "EMAIL_ALREADY_EXISTS",
                            "message": "Email is already registered on the waitlist.",
                            "status_code": 409,
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
                    "invalid_email": {
                        "summary": "Invalid Email Address",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "Only real organization email addresses are allowed. "
                                    "No test/dummy/disposable emails.",
                                ],
                            },
                        },
                    },
                    "invalid_organization_name": {
                        "summary": "Invalid Organization Name",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_name": [
                                    "Organization name should contain only letters, "
                                    "spaces, and common punctuation. No numbers allowed.",
                                    "String should have at least 2 characters",
                                    "String should have at most 100 characters",
                                ],
                            },
                        },
                    },
                    "missing_fields": {
                        "summary": "Missing Required Fields",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_email": ["Field required"],
                                "organization_name": ["Field required"],
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An error occurred during signup. Please try again.",
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

waitlist_signup_custom_errors = ["409", "422", "500"]
waitlist_signup_custom_success = {
    "status_code": 201,
    "description": "Successfully added to waitlist. Confirmation email will be sent.",
}
