hire_specialist_responses = {
    201: {
        "description": "Specialist Hire Request Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Specialist Hire Request Submitted",
                        "value": {
                            "success": True,
                            "message": "Specialist hired successfully."
                            " A specialist will be sent to you shortly",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "company_name": "Example Corp",
                                "company_email": "contact@example.com",
                                "industry": "Technology",
                                "brief_description": "Looking for a legal specialist"
                                " with expertise in intellectual property law.",
                                "created_at": "2023-10-01T12:00:00Z",
                            },
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
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 400,
                            "errors": {
                                "company_name": ["Field required"],
                                "company_email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign."
                                ],
                                "industry": ["Field required"],
                                "brief_description": ["Field required"],
                            },
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access denied",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_in_organization": {
                        "summary": "User Not In Organization",
                        "value": {
                            "error": "USER_NOT_IN_ORGANIZATION",
                            "message": "User is not a member of the organization",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "project_org_mismatch": {
                        "summary": "Project Organization Mismatch",
                        "value": {
                            "error": "PERMISSION_DENIED",
                            "message": "This project doesn't belong to the specified organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User or project not found",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "User not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "project_not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "Project not found.",
                            "status_code": 404,
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
                                "company_name": ["Field required"],
                                "company_email": [
                                    "value is not a valid email address: "
                                    "An email address must have an @-sign.",
                                    "value is not a valid email address: "
                                    "An email address cannot have a period immediately after the"
                                    " @-sign.",
                                    "value is not a valid email address: "
                                    "The part after the @-sign is not valid."
                                    " It should have a period.",
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
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "We couldn't process your hire request at the moment."
                            " Please try again or contact support if the problem persists.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "We couldn't process your hire request at the moment."
                            " Please try again or contact support if the problem persists.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

hire_specialist_custom_errors = ["400", "403", "404", "422", "500"]
hire_specialist_custom_success = {
    "status_code": 201,
    "description": "Specialist hire request submitted successfully."
    " A specialist will contact you shortly.",
}


get_hire_status_responses = {
    200: {
        "description": "Hire Status Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "active_hire_found": {
                        "summary": "Active Specialist Hire Found",
                        "value": {
                            "success": True,
                            "message": "Active specialist hire found",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "company_name": "Example Corp",
                                "company_email": "contact@example.com",
                                "industry": "Technology",
                                "brief_description": "Looking for a legal specialist"
                                " with expertise in intellectual property law.",
                                "created_at": "2023-10-01T12:00:00Z",
                                "is_active": True,
                            },
                        },
                    },
                    "no_active_hire": {
                        "summary": "No Active Specialist Hire",
                        "value": {
                            "success": True,
                            "message": "No active specialist hire for this project",
                            "data": None,
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access denied",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_in_organization": {
                        "summary": "User Not In Organization",
                        "value": {
                            "error": "USER_NOT_IN_ORGANIZATION",
                            "message": "User is not a member of the organization",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "project_org_mismatch": {
                        "summary": "Project Organization Mismatch",
                        "value": {
                            "error": "PERMISSION_DENIED",
                            "message": "This project doesn't belong to the specified organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User or project not found",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "User not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "project_not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "Project not found.",
                            "status_code": 404,
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
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "We couldn't fetch the specialist hire status."
                            " Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "We couldn't fetch the specialist hire status."
                            " Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_hire_status_custom_errors = ["403", "404", "500"]
get_hire_status_custom_success = {
    "status_code": 200,
    "description": "Hire status retrieved successfully.",
}


deactivate_hire_responses = {
    200: {
        "description": "Specialist Hire Deactivated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Specialist Hire Deactivated",
                        "value": {
                            "success": True,
                            "message": "Specialist hire deactivated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "company_name": "Example Corp",
                                "is_active": False,
                                "deactivated_at": "2023-10-15T14:30:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access denied",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_in_organization": {
                        "summary": "User Not In Organization",
                        "value": {
                            "error": "USER_NOT_IN_ORGANIZATION",
                            "message": "User is not a member of the organization",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "project_org_mismatch": {
                        "summary": "Project Organization Mismatch",
                        "value": {
                            "error": "PERMISSION_DENIED",
                            "message": "This project doesn't belong to the specified organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - User, project, or active hire not found",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_found": {
                        "summary": "User Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "User not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "project_not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "Project not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "no_active_hire": {
                        "summary": "No Active Hire Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "No active specialist hire found for this project.",
                            "status_code": 404,
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
                    "internal_server_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "We couldn't deactivate the specialist hire."
                            " Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error": "PROCESSING_ERROR",
                            "message": "We couldn't deactivate the specialist hire."
                            " Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

deactivate_hire_custom_errors = ["403", "404", "500"]
deactivate_hire_custom_success = {
    "status_code": 200,
    "description": "Specialist hire deactivated successfully.",
}
