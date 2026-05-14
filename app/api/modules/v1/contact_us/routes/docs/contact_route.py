contact_us_responses = {
    200: {
        "description": "Contact Form Submitted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Message Sent Successfully",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Thank you for contacting us. We'll get back to you soon!",
                            "data": {
                                "email": "user@example.com",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Contact Form Error",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation Error",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid phone number format",
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
                    "validation_error_missing": {
                        "summary": "Request Validation Failed - Missing Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "full_name": ["Field required"],
                                "email": ["Field required"],
                                "phone_number": ["Field required"],
                                "message": ["Field required"],
                            },
                        },
                    },
                    "validation_error_invalid_email": {
                        "summary": "Request Validation Failed - Invalid Email",
                        "value": {
                            "error": "VALIDATION_ERROR",
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
                    "validation_error_short_message": {
                        "summary": "Message Too Short",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {"message": ["String should have at least 10 characters"]},
                        },
                    },
                    "validation_error_invalid_phone": {
                        "summary": "Invalid Phone Number",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "phone_number": [
                                    "Phone number must contain only digits and optional '+'"
                                ]
                            },
                        },
                    },
                    "validation_error_long_fields": {
                        "summary": "Field Length Exceeded",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "full_name": ["String should have at most 255 characters"],
                                "message": ["String should have at most 1000 characters"],
                            },
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Too Many Requests - Rate Limit Exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "rate_limit_email": {
                        "summary": "Rate Limit Exceeded - Email",
                        "value": {"detail": "Too many attempts. Please try again in 1 hour."},
                    },
                    "rate_limit_ip": {
                        "summary": "Rate Limit Exceeded - IP Address",
                        "value": {"detail": "Too many attempts from this IP. Try again in 1 hour."},
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
                            "message": "Failed to submit your message. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

contact_us_custom_errors = ["400", "422", "429", "500"]
contact_us_custom_success = {
    "status_code": 200,
    "description": "Contact form submitted successfully. Confirmation email sent.",
}


get_all_contacts_responses = {
    200: {
        "description": "Contact Submissions Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Successfully Retrieved Contact Submissions",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Contact submissions retrieved successfully",
                            "data": {
                                "contacts": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "full_name": "John Doe",
                                        "email": "john.doe@company.com",
                                        "phone_number": "+1234567890",
                                        "message": "I would like to inquire about your services.",
                                        "created_at": "2024-01-15T10:30:00Z",
                                    },
                                    {
                                        "id": "223e4567-e89b-12d3-a456-426614174001",
                                        "full_name": "Jane Smith",
                                        "email": "jane.smith@company.com",
                                        "phone_number": "+0987654321",
                                        "message": "Please reach me for partnership opportunities.",
                                        "created_at": "2024-01-14T15:45:00Z",
                                    },
                                ],
                                "total": 25,
                                "page": 1,
                                "limit": 10,
                                "total_pages": 3,
                            },
                        },
                    },
                    "success_filtered": {
                        "summary": "Retrieved Submissions Filtered by Email",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Contact submissions retrieved successfully",
                            "data": {
                                "contacts": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "full_name": "John Doe",
                                        "email": "john.doe@company.com",
                                        "phone_number": "+1234567890",
                                        "message": "I would like to inquire about your services.",
                                        "created_at": "2024-01-15T10:30:00Z",
                                    }
                                ],
                                "total": 1,
                                "page": 1,
                                "limit": 10,
                                "total_pages": 1,
                            },
                        },
                    },
                    "success_empty": {
                        "summary": "No Submissions Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Contact submissions retrieved successfully",
                            "data": {
                                "contacts": [],
                                "total": 0,
                                "page": 1,
                                "limit": 10,
                                "total_pages": 0,
                            },
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Admin Access Required",
        "content": {
            "application/json": {
                "examples": {
                    "forbidden": {
                        "summary": "Unauthorized Access - Admin Email Invalid",
                        "value": {
                            "status": "ERROR",
                            "status_code": 403,
                            "message": "You are not authorized to access this resource.",
                            "errors": {
                                "admin_email": "Provided admin email does not match system admin."
                            },
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve contact submissions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_all_contacts_custom_errors = ["500"]
get_all_contacts_custom_success = {
    "status_code": 200,
    "description": "Contact submissions retrieved successfully with pagination metadata.",
}


request_demo_responses = {
    201: {
        "description": "Demo Request Submitted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Demo Request Submitted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Demo request submitted. Our team will reach out shortly.",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "first_name": "Jane",
                                "last_name": "Doe",
                                "company_name": "Acme Corp",
                                "company_size": "51-200",
                                "industry": "Technology",
                                "company_website_url": "https://acme.example.com",
                                "country": "United States",
                                "work_email": "jane.doe@acme.example.com",
                                "job_title": "Head of Legal",
                                "additional_context": "We would like a walkthrough for our team.",
                                "created_at": "2025-11-27T18:09:53.101508Z",
                                "updated_at": "2025-11-27T18:09:53.101508Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Domain Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_company_size": {
                        "summary": "Invalid Company Size Band",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Invalid company size band. \
                                Please select one of:1-50, 51-200, 201-500, 501-1000, 1000+",
                            "status_code": 422,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Request Validation Failed",
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
                                "first_name": ["Field required"],
                                "last_name": ["Field required"],
                                "company_name": ["Field required"],
                                "company_size": ["Field required"],
                                "industry": ["Field required"],
                                "company_website_url": ["Field required"],
                                "country": ["Field required"],
                                "work_email": ["Field required"],
                            },
                        },
                    },
                    "invalid_email": {
                        "summary": "Invalid Work Email",
                        "value": {
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "work_email": [
                                    "This is not a valid email address. \
                                        An email address must have an @-sign.",
                                ],
                            },
                        },
                    },
                }
            }
        },
    },
    429: {
        "description": "Too Many Requests - Rate Limit Exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "rate_limit_email": {
                        "summary": "Rate Limit Exceeded - Email",
                        "value": {
                            "error_code": "HTTP_ERROR",
                            "message": "Too many demo requests. Please try again in 1 hour.",
                            "status_code": 429,
                            "errors": {},
                        },
                    },
                    "rate_limit_ip": {
                        "summary": "Rate Limit Exceeded - IP Address",
                        "value": {
                            "error_code": "HTTP_ERROR",
                            "message": "Too many attempts from this IP. Try again in 1 hour.",
                            "status_code": 429,
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
                        "summary": "Server Error",
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

request_demo_custom_errors = ["400", "401", "422", "429", "500"]
request_demo_custom_success = {
    "status_code": 201,
    "description": "Demo request submitted successfully. Confirmation email sent.",
}
