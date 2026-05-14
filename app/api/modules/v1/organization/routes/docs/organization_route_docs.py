create_organization_responses = {
    201: {
        "description": "Organization Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Organization Created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Organization created successfully",
                            "data": {
                                "organization_id": "06a68053-4b99-4ef3-8438-15b21e1f18e3",
                                "organization_name": "Acme Corporation",
                                "country": "United States",
                                "email": "contact@acme.com",
                                "company_size": "51-200",
                                "org_type": "Private",
                                "user_id": "90ea20e6-351d-4e8d-9d21-0ceb92244f94",
                                "role": "Owner",
                                "billing_account_id": "5cb2d79a-d849-45cd-bd53-ac0018eabc15",
                                "billing_status": "TRIALING",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Organization Creation Error",
        "content": {
            "application/json": {
                "examples": {
                    "user_not_verified": {
                        "summary": "User Email Not Verified",
                        "value": {
                            "error": "ERROR",
                            "message": "User must be verified before creating an organization",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "organization_name_exists": {
                        "summary": "Organization Name Already Exists",
                        "value": {
                            "error": "ERROR",
                            "message": "An organization with this name already exists.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
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
                    "missing_required_fields": {
                        "summary": "Missing Required Fields",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "name": ["Field required"],
                            },
                        },
                    },
                    "invalid_name_length": {
                        "summary": "Invalid Name Length",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "name": ["String should have at least 2 characters"],
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
                            "message": "Organization creation failed. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_organization_custom_errors = ["400", "401", "422", "500"]
create_organization_custom_success = {
    "status_code": 201,
    "description": "Organization created successfully.",
}

get_organization_responses = {
    200: {
        "description": "Organization Details Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Organization Details",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organization details retrieved successfully",
                            "data": {
                                "organization_id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Acme Corporation",
                                "industry": "Technology",
                                "location": "New York, USA",
                                "country": "United States",
                                "email": "contact@acme.com",
                                "company_size": "51-200",
                                "org_type": "Private",
                                "is_active": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:30:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Request",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_request": {
                        "summary": "Invalid Request",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid request parameters.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Access Denied",
        "content": {
            "application/json": {
                "examples": {
                    "no_access": {
                        "summary": "No Access to Organization",
                        "value": {
                            "error": "FORBIDDEN",
                            "message": "You do not have access to this organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Organization Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "organization_not_found": {
                        "summary": "Organization Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "Organization not found.",
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
                    "invalid_uuid": {
                        "summary": "Invalid Organization ID Format",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["Invalid UUID format"],
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
                            "message": "Failed to retrieve organization details. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_organization_custom_errors = ["400", "401", "403", "404", "422", "500"]
get_organization_custom_success = {
    "status_code": 200,
    "description": "Organization details retrieved successfully.",
}

update_organization_responses = {
    200: {
        "description": "Organization Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Organization Updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organization updated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Acme Corporation Inc.",
                                "industry": "Technology & Innovation",
                                "country": "United States",
                                "email": "contact@acme.com",
                                "company_size": "51-200",
                                "org_type": "Private",
                                "is_active": True,
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-20T14:45:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Update Error",
        "content": {
            "application/json": {
                "examples": {
                    "no_updates_provided": {
                        "summary": "No Update Fields Provided",
                        "value": {
                            "error": "ERROR",
                            "message": "No update fields provided.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "organization_name_exists": {
                        "summary": "Organization Name Already Exists",
                        "value": {
                            "error": "ERROR",
                            "message": "An organization with this name already exists.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Authentication Required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "User Not Authenticated",
                        "value": {
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "no_access": {
                        "summary": "No Access to Organization",
                        "value": {
                            "error": "FORBIDDEN",
                            "message": "You do not have access to this organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "no_permission": {
                        "summary": "No Permission to Update",
                        "value": {
                            "error": "FORBIDDEN",
                            "message": "You do not have permission to update this organization.",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Organization Does Not Exist",
        "content": {
            "application/json": {
                "examples": {
                    "organization_not_found": {
                        "summary": "Organization Not Found",
                        "value": {
                            "error": "NOT_FOUND",
                            "message": "Organization not found.",
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
                    "invalid_uuid": {
                        "summary": "Invalid Organization ID Format",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "organization_id": ["Invalid UUID format"],
                            },
                        },
                    },
                    "invalid_name_length": {
                        "summary": "Invalid Name Length",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "name": ["String should have at least 2 characters"],
                            },
                        },
                    },
                    "invalid_field_type": {
                        "summary": "Invalid Field Type",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "is_active": ["Input should be a valid boolean"],
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
                            "message": "Failed to update organization. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_organization_custom_errors = ["400", "401", "403", "404", "422", "500"]
update_organization_custom_success = {
    "status_code": 200,
    "description": "Organization updated successfully.",
}

delete_organization_responses = {
    204: {
        "description": "Organization Deleted Successfully",
    },
    400: {
        "description": "Bad Request - Cannot Delete Organization",
        "content": {
            "application/json": {
                "examples": {
                    "active_members": {
                        "summary": "Organization Has Active Members",
                        "value": {
                            "status": "ERROR",
                            "message": "Cannot delete org with active members. Deactivate first",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "already_deleted": {
                        "summary": "Organization Already Deleted",
                        "value": {
                            "status": "ERROR",
                            "message": "Organization is already deleted",
                            "status_code": 400,
                            "errors": {},
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
                    "not_admin": {
                        "summary": "User Not Organization Admin",
                        "value": {
                            "status": "ERROR",
                            "message": "Only organization admins can delete organizations",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Organization Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "organization_not_found": {
                        "summary": "Organization Not Found",
                        "value": {
                            "status": "ERROR",
                            "message": "Organization not found",
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "status": "ERROR",
                            "message": "Failed to delete organization",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_organization_custom_errors = ["400", "403", "404", "500"]
delete_organization_custom_success = {
    "status_code": 204,
    "description": "Organization deleted successfully.",
}
