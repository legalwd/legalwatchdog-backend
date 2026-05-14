"""OpenAPI documentation for superadmin organization management endpoints."""

list_organizations_responses = {
    200: {
        "description": "Organizations retrieved successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated organization list with owner details",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": {
                                "organizations": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "Acme Corporation",
                                        "industry": "Legal",
                                        "location": "United Kingdom",
                                        "country": "UK",
                                        "email": "contact@acme.com",
                                        "company_size": "51-200",
                                        "org_type": "Law Firm",
                                        "plan": "Professional",
                                        "logo_url": "https://example.com/logo.png",
                                        "is_active": True,
                                        "created_at": "2024-01-15T10:00:00Z",
                                        "updated_at": "2024-02-10T15:30:00Z",
                                        "owner": {
                                            "id": "456e7890-e89b-12d3-a456-426614174001",
                                            "name": "John Doe",
                                            "email": "john@acme.com",
                                            "is_approved": True,
                                            "is_active": True,
                                            "is_verified": True,
                                            "approved_at": "2024-01-16T09:00:00Z",
                                            "created_at": "2024-01-15T10:00:00Z",
                                            "last_login": "2024-02-10T15:30:00Z",
                                            "last_active": "2024-02-10T15:35:00Z",
                                        },
                                    },
                                    {
                                        "id": "789e0123-e89b-12d3-a456-426614174002",
                                        "name": "Beta Inc",
                                        "industry": "Technology",
                                        "location": None,
                                        "country": "US",
                                        "email": None,
                                        "company_size": "1-50",
                                        "org_type": None,
                                        "plan": "Essential",
                                        "logo_url": None,
                                        "is_active": True,
                                        "created_at": "2024-02-01T08:00:00Z",
                                        "updated_at": "2024-02-01T08:00:00Z",
                                        "owner": None,
                                    },
                                ],
                                "meta": {
                                    "total": 2,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 1,
                                },
                            },
                        },
                    },
                    "filtered_by_approval": {
                        "summary": "Filtered by owner approval status",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Organizations retrieved successfully",
                            "data": {
                                "organizations": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "Pending Corp",
                                        "industry": "Finance",
                                        "is_active": True,
                                        "created_at": "2024-01-15T10:00:00Z",
                                        "updated_at": "2024-02-10T15:30:00Z",
                                        "owner": {
                                            "id": "456e7890-e89b-12d3-a456-426614174001",
                                            "name": "Jane Smith",
                                            "email": "jane@pending.com",
                                            "is_approved": False,
                                            "is_active": True,
                                            "is_verified": True,
                                        },
                                    }
                                ],
                                "meta": {
                                    "total": 1,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 1,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "status": "error",
                            "status_code": 401,
                            "message": "Authentication required",
                            "error_code": "UNAUTHORIZED",
                            "errors": {},
                        },
                    },
                    "not_superadmin": {
                        "summary": "Not a superadmin",
                        "value": {
                            "status": "error",
                            "status_code": 403,
                            "message": "Superadmin access required",
                            "error_code": "FORBIDDEN",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid query parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_sort_field": {
                        "summary": "Invalid sort field",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": (
                                "Invalid sort field: invalid_field. "
                                "Must be one of: created_at, updated_at, name, "
                                "owner_email, owner_created_at"
                            ),
                            "error_code": "INVALID_ORGANIZATION_FILTER",
                            "errors": {},
                        },
                    },
                    "invalid_company_size": {
                        "summary": "Invalid company size filter",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": (
                                "Invalid company size: invalid. "
                                "Must be one of: 1-50, 51-200, 201-500, 501-1000, 1000+"
                            ),
                            "error_code": "INVALID_ORGANIZATION_FILTER",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Unprocessable Entity - Validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Validation failed",
                        "value": {
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation error",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {"limit": ["Must be between 1 and 100"]},
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
                    "data_retrieval_error": {
                        "summary": "Data Retrieval Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Failed to retrieve organizations list",
                            "error_code": "ORGANIZATION_DATA_RETRIEVAL_ERROR",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

export_json_responses = {
    200: {
        "description": "Organizations exported as JSON file",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "JSON file download",
                        "value": [
                            {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "name": "Acme Corporation",
                                "industry": "Legal",
                                "is_active": True,
                                "created_at": "2024-01-15T10:00:00Z",
                                "owner": {
                                    "id": "456e7890-e89b-12d3-a456-426614174001",
                                    "name": "John Doe",
                                    "email": "john@acme.com",
                                    "is_approved": True,
                                },
                            }
                        ],
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "status": "error",
                            "status_code": 401,
                            "message": "Authentication required",
                            "error_code": "UNAUTHORIZED",
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
                    "export_error": {
                        "summary": "Export Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Failed to export organizations",
                            "error_code": "ORGANIZATION_EXPORT_ERROR",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

export_csv_responses = {
    200: {
        "description": "Organizations exported as CSV file",
        "content": {
            "text/csv": {
                "examples": {
                    "success": {
                        "summary": "CSV file download",
                        "value": (
                            "org_id,org_name,industry,location,country,org_email,"
                            "company_size,org_type,plan,is_active,org_created_at,"
                            "org_updated_at,owner_id,owner_name,owner_email,"
                            "owner_is_approved,owner_is_active,owner_is_verified,"
                            "owner_approved_at,owner_created_at,owner_last_login,"
                            "owner_last_active\n"
                            "123e4567-e89b-12d3-a456-426614174000,Acme Corporation,Legal,"
                            "United Kingdom,UK,contact@acme.com,51-200,Law Firm,Professional,"
                            "True,2024-01-15T10:00:00Z,2024-02-10T15:30:00Z,"
                            "456e7890-e89b-12d3-a456-426614174001,John Doe,john@acme.com,"
                            "True,True,True,2024-01-16T09:00:00Z,2024-01-15T10:00:00Z,"
                            "2024-02-10T15:30:00Z,2024-02-10T15:35:00Z"
                        ),
                    }
                }
            }
        },
    },
    401: {
        "description": "Unauthorized - Superadmin credentials required",
        "content": {
            "application/json": {
                "examples": {
                    "not_authenticated": {
                        "summary": "Unauthorized",
                        "value": {
                            "status": "error",
                            "status_code": 401,
                            "message": "Authentication required",
                            "error_code": "UNAUTHORIZED",
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
                    "export_error": {
                        "summary": "Export Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "Failed to export organizations",
                            "error_code": "ORGANIZATION_EXPORT_ERROR",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

list_organizations_custom_success = {
    "status_code": 200,
    "description": "Organizations list retrieved successfully with owner details and pagination.",
}

list_organizations_custom_errors = ["400", "401", "403", "422", "500"]

export_json_custom_success = {
    "status_code": 200,
    "description": "Organizations exported as JSON file successfully.",
}

export_json_custom_errors = ["401", "403", "500"]

export_csv_custom_success = {
    "status_code": 200,
    "description": "Organizations exported as CSV file successfully.",
}

export_csv_custom_errors = ["401", "403", "500"]
