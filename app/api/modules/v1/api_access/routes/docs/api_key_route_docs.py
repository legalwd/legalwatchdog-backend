create_api_key_responses = {
    201: {
        "description": "API Key Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "API Key Generated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "APIKey created Successfully",
                            "data": {
                                "key_name": "Production API Key",
                                "organization_name": "Example Corp",
                                "user_name": "John Doe",
                                "receiver_email": "integration@example.com",
                                "api_key": "lwd_sk_live_1234567890abcdef",
                                "scope": "read:project,write:project",
                                "generated_by": "Admin User",
                                "is_active": True,
                                "created_at": "2023-10-01T12:00:00Z",
                                "expires_at": "2024-10-01T12:00:00Z",
                                "last_used_at": None,
                                "rotation_enabled": False,
                                "rotation_interval_days": None,
                                "last_rotated_at": None,
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
                    "organization_mismatch": {
                        "summary": "Organization ID Mismatch",
                        "value": {
                            "error": "ERROR",
                            "message": "Organization mismatch",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_scope": {
                        "summary": "Invalid API Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid scope provided",
                            "status_code": 400,
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
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
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
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "key_name": ["Field required"],
                                "scope": ["Field required"],
                                "expires_at": ["Invalid date format"],
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
                            "message": "Failed to generate API key",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_api_key_custom_errors = ["400", "403", "422", "500"]
create_api_key_custom_success = {
    "status_code": 201,
    "description": "API key created successfully. Store the key securely"
    " as it won't be shown again.",
}


list_api_keys_responses = {
    200: {
        "description": "API Keys Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated API Keys List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "API Keys Retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "key_name": "Production API Key",
                                        "organization_name": "Example Corp",
                                        "user_name": "John Doe",
                                        "receiver_email": "integration@example.com",
                                        "api_key": "hashed_key_here",
                                        "scope": "read:project,write:project",
                                        "generated_by": "Admin User",
                                        "is_active": True,
                                        "created_at": "2023-10-01T12:00:00Z",
                                        "expires_at": "2024-10-01T12:00:00Z",
                                        "last_used_at": None,
                                        "rotation_enabled": False,
                                        "rotation_interval_days": None,
                                        "last_rotated_at": None,
                                    }
                                ],
                                "pagination": {
                                    "total": 15,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 1,
                                    "has_next": False,
                                    "has_prev": False,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
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
                    "invalid_pagination": {
                        "summary": "Invalid Pagination Parameters",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "page": ["Page must be greater than or equal to 1"],
                                "limit": ["Limit must be between 1 and 100"],
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
                            "message": "Failed to retrieve API keys",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_api_keys_custom_errors = ["403", "422", "500"]
list_api_keys_custom_success = {
    "status_code": 200,
    "description": "API keys retrieved successfully with pagination.",
}


get_api_key_responses = {
    200: {
        "description": "API Key Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "API Key Details",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "APIKey retrieved successfully",
                            "data": {
                                "key_name": "Production API Key",
                                "organization_name": "Example Corp",
                                "user_name": "John Doe",
                                "receiver_email": "integration@example.com",
                                "api_key": "hashed_key_here",
                                "scope": "read:project,write:project",
                                "generated_by": "Admin User",
                                "is_active": True,
                                "created_at": "2023-10-01T12:00:00Z",
                                "expires_at": "2024-10-01T12:00:00Z",
                                "last_used_at": None,
                                "rotation_enabled": False,
                                "rotation_interval_days": None,
                                "last_rotated_at": None,
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - API Key Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "API Key Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "API key not found",
                            "status_code": 404,
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve API key",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_api_key_custom_errors = ["403", "404", "500"]
get_api_key_custom_success = {
    "status_code": 200,
    "description": "API key details retrieved successfully.",
}


delete_api_key_responses = {
    204: {
        "description": "API Key Deleted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "API Key Revoked",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "API Key revoked",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - API Key Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "API Key Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "API Key not found",
                            "status_code": 404,
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to delete API key",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_api_key_custom_errors = ["403", "404", "500"]
delete_api_key_custom_success = {
    "status_code": 204,
    "description": "API key revoked successfully. This action cannot be undone.",
}


rotate_api_key_responses = {
    201: {
        "description": "API Key Rotated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "New API Key Generated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "API key rotated",
                            "data": {"api_key": "lwd_sk_live_new_abcdef123456"},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - API Key Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "API Key Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "API Key not found",
                            "status_code": 404,
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to rotate API key",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

rotate_api_key_custom_errors = ["403", "404", "500"]
rotate_api_key_custom_success = {
    "status_code": 201,
    "description": "API key rotated successfully. Old key is now invalid.",
}


set_rotation_responses = {
    200: {
        "description": "Rotation Settings Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Rotation Settings Updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Rotation set successfully",
                            "data": {
                                "key_name": "Production API Key",
                                "organization_name": "Example Corp",
                                "user_name": "John Doe",
                                "receiver_email": "integration@example.com",
                                "api_key": "hashed_key_here",
                                "scope": "read:project,write:project",
                                "generated_by": "Admin User",
                                "is_active": True,
                                "created_at": "2023-10-01T12:00:00Z",
                                "expires_at": "2024-10-01T12:00:00Z",
                                "last_used_at": None,
                                "rotation_enabled": True,
                                "rotation_interval_days": 30,
                                "last_rotated_at": None,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Rotation Settings",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_interval": {
                        "summary": "Invalid Rotation Interval",
                        "value": {
                            "error": "ERROR",
                            "message": "Rotation interval must be between 1 and 365 days",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - API Key Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "API Key Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "API Key not found",
                            "status_code": 404,
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
                    "validation_error": {
                        "summary": "Request Validation Failed",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "rotation_enabled": ["Field required"],
                                "rotation_interval_days": ["Must be positive integer"],
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
                            "message": "Failed to update rotation settings",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

set_rotation_custom_errors = ["400", "403", "404", "422", "500"]
set_rotation_custom_success = {
    "status_code": 200,
    "description": "API key rotation settings updated successfully.",
}


get_scopes_responses = {
    200: {
        "description": "Scopes Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Available API Key Scopes",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scope retrieved successfully",
                            "data": {
                                "scopes": [
                                    {"value": "*", "label": "All"},
                                    {"value": "read:project", "label": "Read Project"},
                                    {"value": "write:project", "label": "Write Project"},
                                    {"value": "read:source", "label": "Read Source"},
                                    {
                                        "value": "download:data_revision",
                                        "label": "Download Data Revision",
                                    },
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Permissions",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_permissions": {
                        "summary": "Permission Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient permissions",
                            "status_code": 403,
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
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to retrieve scopes",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_scopes_custom_errors = ["403", "500"]
get_scopes_custom_success = {
    "status_code": 200,
    "description": "Available API key scopes retrieved successfully for UI dropdown.",
}
