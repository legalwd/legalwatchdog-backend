create_jurisdiction_responses = {
    201: {
        "description": "Jurisdiction Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Jurisdiction created successfully",
                            "data": {
                                "jurisdiction": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                    "parent_id": None,
                                    "name": "Supreme Court of California",
                                    "description": "Highest court in California",
                                    "prompt": "Monitor all supreme court cases",
                                    "scrape_output": {"case_types": ["civil", "criminal"]},
                                    "created_at": "2023-10-01T12:00:00Z",
                                    "updated_at": "2023-10-01T12:00:00Z",
                                    "deleted_at": None,
                                    "is_deleted": False,
                                    "children": [],
                                }
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
                            "message": "Failed to create jurisdiction",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Plan Limit Exceeded",
        "content": {
            "application/json": {
                "examples": {
                    "plan_limit": {
                        "summary": "Jurisdiction Creation Limit Reached",
                        "value": {
                            "error": "PLAN_LIMIT_EXCEEDED",
                            "message": "Jurisdiction creation limit reached for your plan",
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
                                "project_id": ["Field required"],
                                "name": ["Field required"],
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
                            "message": "Failed to create jurisdiction",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_jurisdiction_custom_errors = ["400", "403", "422", "500"]
create_jurisdiction_custom_success = {
    "status_code": 201,
    "description": "Jurisdiction created successfully within the specified project.",
}


get_all_jurisdictions_responses = {
    200: {
        "description": "Jurisdictions Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated Jurisdictions List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdictions retrieved successfully",
                            "data": {
                                "jurisdictions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                        "parent_id": None,
                                        "name": "Supreme Court of California",
                                        "description": "Highest court in California",
                                        "prompt": "Monitor all supreme court cases",
                                        "scrape_output": {"case_types": ["civil", "criminal"]},
                                        "created_at": "2023-10-01T12:00:00Z",
                                        "updated_at": "2023-10-01T12:00:00Z",
                                        "deleted_at": None,
                                        "is_deleted": False,
                                        "children": [],
                                    }
                                ],
                                "pagination": {
                                    "total": 25,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 3,
                                    "has_next": True,
                                    "has_prev": False,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Pagination",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_pagination": {
                        "summary": "Invalid Pagination Parameters",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid pagination parameters",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Jurisdictions",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Jurisdictions Found",
                        "value": {
                            "error": "ERROR",
                            "message": "No jurisdictions found",
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
                                "page": ["Must be greater than or equal to 1"],
                                "page_size": ["Must be greater than or equal to 1"],
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
                            "message": "Failed to retrieve jurisdictions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_all_jurisdictions_custom_errors = ["400", "404", "422", "500"]
get_all_jurisdictions_custom_success = {
    "status_code": 200,
    "description": "Jurisdictions retrieved successfully with pagination.",
}


get_jurisdictions_by_project_responses = {
    200: {
        "description": "Jurisdictions Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Jurisdictions List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdictions retrieved successfully",
                            "data": {
                                "jurisdictions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                        "parent_id": None,
                                        "name": "Supreme Court of California",
                                        "description": "Highest court in California",
                                        "prompt": "Monitor all supreme court cases",
                                        "scrape_output": {"case_types": ["civil", "criminal"]},
                                        "created_at": "2023-10-01T12:00:00Z",
                                        "updated_at": "2023-10-01T12:00:00Z",
                                        "deleted_at": None,
                                        "is_deleted": False,
                                        "children": [],
                                    }
                                ],
                                "pagination": {
                                    "total": 15,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 2,
                                    "has_next": True,
                                    "has_prev": False,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Pagination",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_pagination": {
                        "summary": "Invalid Pagination Parameters",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid pagination parameters",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Jurisdictions",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Jurisdictions Found",
                        "value": {
                            "error": "ERROR",
                            "message": "No jurisdictions found",
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
                                "page": ["Must be greater than or equal to 1"],
                                "page_size": ["Must be greater than or equal to 1"],
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
                            "message": "Failed to retrieve jurisdictions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_jurisdictions_by_project_custom_errors = ["400", "404", "422", "500"]
get_jurisdictions_by_project_custom_success = {
    "status_code": 200,
    "description": "Jurisdictions for project retrieved successfully with pagination.",
}


soft_delete_jurisdictions_by_project_responses = {
    204: {
        "description": "Jurisdictions Soft Deleted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdictions Archived",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "Jurisdictions archived successfully",
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Jurisdictions",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Jurisdictions Found",
                        "value": {
                            "error": "ERROR",
                            "message": "No jurisdictions found to delete",
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
                            "message": "Failed to delete jurisdictions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

soft_delete_jurisdictions_by_project_custom_errors = ["404", "500"]
soft_delete_jurisdictions_by_project_custom_success = {
    "status_code": 204,
    "description": "All jurisdictions in project soft deleted (archived) successfully.",
}


get_jurisdiction_responses = {
    200: {
        "description": "Jurisdiction Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Details with Children",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction retrieved successfully",
                            "data": {
                                "jurisdiction": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                    "parent_id": None,
                                    "name": "Supreme Court of California",
                                    "description": "Highest court in California",
                                    "prompt": "Monitor all supreme court cases",
                                    "scrape_output": {"case_types": ["civil", "criminal"]},
                                    "created_at": "2023-10-01T12:00:00Z",
                                    "updated_at": "2023-10-01T12:00:00Z",
                                    "deleted_at": None,
                                    "is_deleted": False,
                                    "children": [
                                        {
                                            "id": "123e4567-e89b-12d3-a456-426614174002",
                                            "name": "Appellate Division",
                                            "description": "Handles appeals",
                                        }
                                    ],
                                },
                                "pagination": {
                                    "total": 5,
                                    "page": 1,
                                    "limit": 10,
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
    400: {
        "description": "Bad Request - Invalid Pagination",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_pagination": {
                        "summary": "Invalid Pagination Parameters",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid pagination parameters",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found",
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
                                "page": ["Must be greater than or equal to 1"],
                                "page_size": ["Must be greater than or equal to 1"],
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
                            "message": "Failed to retrieve jurisdiction",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_jurisdiction_custom_errors = ["400", "404", "422", "500"]
get_jurisdiction_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction retrieved successfully with child jurisdictions pagination.",
}


update_jurisdiction_responses = {
    200: {
        "description": "Jurisdiction Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction updated successfully",
                            "data": {
                                "jurisdiction": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                    "parent_id": None,
                                    "name": "Updated Court Name",
                                    "description": "Updated description",
                                    "prompt": "Updated monitoring prompt",
                                    "scrape_output": {
                                        "case_types": ["civil", "criminal", "family"]
                                    },
                                    "created_at": "2023-10-01T12:00:00Z",
                                    "updated_at": "2023-10-02T14:30:00Z",
                                    "deleted_at": None,
                                    "is_deleted": False,
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    204: {
        "description": "Jurisdiction Archived Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "archived": {
                        "summary": "Jurisdiction Soft Deleted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "Jurisdiction archived successfully",
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
                    "parent_cycle": {
                        "summary": "Circular Reference Detected",
                        "value": {
                            "error": "ERROR",
                            "message": "Cannot set parent_id to a descendant jurisdiction"
                            " (cycle detected)",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "self_parent": {
                        "summary": "Cannot Set Self as Parent",
                        "value": {
                            "error": "ERROR",
                            "message": "Cannot set parent_id to self",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found",
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
                                "name": ["String should have at least 1 character"],
                                "parent_id": ["Invalid UUID format"],
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
                            "message": "Failed to update jurisdiction",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_jurisdiction_custom_errors = ["400", "404", "422", "500"]
update_jurisdiction_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction updated successfully with partial updates allowed.",
}


soft_delete_jurisdiction_responses = {
    204: {
        "description": "Jurisdiction Soft Deleted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Archived",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "Jurisdiction archived successfully",
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found",
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
                            "message": "Failed to delete jurisdiction",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

soft_delete_jurisdiction_custom_errors = ["404", "500"]
soft_delete_jurisdiction_custom_success = {
    "status_code": 204,
    "description": "Jurisdiction soft deleted successfully including nested jurisdictions.",
}


restore_jurisdiction_responses = {
    200: {
        "description": "Jurisdiction Restored Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Restored",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction restored successfully",
                            "data": {
                                "jurisdiction": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                    "parent_id": None,
                                    "name": "Supreme Court of California",
                                    "description": "Highest court in California",
                                    "is_deleted": False,
                                    "deleted_at": None,
                                    "children": [],
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found or not deleted",
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
                            "message": "Failed to restore jurisdiction",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

restore_jurisdiction_custom_errors = ["404", "500"]
restore_jurisdiction_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction restored successfully including nested jurisdictions.",
}


restore_jurisdictions_by_project_id_responses = {
    200: {
        "description": "Jurisdictions Restored Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Jurisdictions Restored",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Restored 5 jurisdiction(s)",
                            "data": {
                                "jurisdictions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                        "parent_id": None,
                                        "name": "Supreme Court of California",
                                        "description": "Highest court in California",
                                        "is_deleted": False,
                                        "deleted_at": None,
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Archived Jurisdictions",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Archived Jurisdictions",
                        "value": {
                            "error": "ERROR",
                            "message": "No archived jurisdictions found for this project",
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
                            "message": "Failed to restore jurisdictions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

restore_jurisdictions_by_project_id_custom_errors = ["404", "500"]
restore_jurisdictions_by_project_id_custom_success = {
    "status_code": 200,
    "description": "All archived jurisdictions for project restored successfully.",
}


get_sources_for_jurisdiction_responses = {
    200: {
        "description": "Sources Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Sources List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Sources retrieved successfully",
                            "data": {
                                "sources": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174010",
                                        "name": "California Court Records",
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "url": "https://courts.ca.gov",
                                        "is_active": True,
                                        "scraping_frequency": "daily",
                                        "last_scraped_at": "2023-10-01T12:00:00Z",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Parameters",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_pagination": {
                        "summary": "Invalid Pagination Parameters",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid pagination parameters",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 500"],
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
                            "message": "Failed to retrieve sources",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_sources_for_jurisdiction_custom_errors = ["400", "404", "422", "500"]
get_sources_for_jurisdiction_custom_success = {
    "status_code": 200,
    "description": "Sources for jurisdiction retrieved successfully with filtering and pagination.",
}


# This is for getting Jurisdictions' states or states' history
get_jurisdiction_state_responses = {
    200: {
        "description": "Jurisdiction State Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction State Retrieved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction state retrieved successfully",
                            "data": {
                                "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174000",
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174002",
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "field_key": "minimum_wage",
                                        "value": "$15/hr",
                                        "source_evidence": [],
                                        "confirmed_at": "2026-02-20T11:56:00Z",
                                        "confirmed_by_user_id": "123e4567-e89b-12d3-a45266141703",
                                        "originating_job_id": "123e4567-e89b-12d3-a44266141704",
                                    }
                                ],
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction State Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction State Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction state not found",
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
                            "message": "Failed to retrieve jurisdiction state",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_jurisdiction_state_custom_errors = ["404", "500"]
get_jurisdiction_state_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction state retrieved successfully; all state rows returned",
}

# Get jurisdiction state history (audit log)
get_jurisdiction_state_history_responses = {
    200: {
        "description": "Jurisdiction State History Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction State History (Audit Log) Retrieved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction state history retrieved successfully",
                            "data": {
                                "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174000",
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174001",
                                        "state_id": "123e4567-e89b-12d3-a456-426614174002",
                                        "field_key": "minimum_wage",
                                        "previous_value": "$14/hr",
                                        "new_value": "$15/hr",
                                        "changed_at": "2026-02-20T11:56:00Z",
                                        "changed_by_user_id": "123e4567-e89b-12d3-a456-42661474003",
                                        "change_reason": "Accepted from scrape job",
                                    }
                                ],
                                "pagination": {
                                    "total": 42,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 5,
                                    "has_next": True,
                                    "has_prev": False,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Jurisdiction not found",
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
                            "message": "Failed to retrieve jurisdiction state history",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}
get_jurisdiction_state_history_custom_errors = ["404", "500"]
get_jurisdiction_state_history_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction state history (audit log) retrieved successfully with pagination.",
}

# Jurisdiction Scrape Endpoints Documentation

trigger_jurisdiction_scrape_responses = {
    202: {
        "description": "Scrape Initiated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Scrape Started",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Jurisdiction scrape initiated",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "PENDING",
                                "total_sources": 5,
                                "started_at": "2023-10-01T12:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    409: {
        "description": "Conflict - Scrape Already In Progress",
        "content": {
            "application/json": {
                "examples": {
                    "already_in_progress": {
                        "summary": "Scrape Already Running",
                        "value": {
                            "error_code": "SCRAPE_ALREADY_IN_PROGRESS",
                            "message": "A scrape is already in progress for this jurisdiction.",
                            "status_code": 409,
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
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to initiate jurisdiction scrape. Please try again.",
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

trigger_jurisdiction_scrape_custom_errors = ["404", "409", "500"]
trigger_jurisdiction_scrape_custom_success = {
    "status_code": 202,
    "description": "Jurisdiction scrape job created and initiated successfully.",
}


get_jurisdiction_scrape_status_responses = {
    200: {
        "description": "Scrape Status Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "in_progress": {
                        "summary": "Scrape In Progress",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape status retrieved",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "IN_PROGRESS",
                                "started_at": "2023-10-01T12:00:00Z",
                                "completed_at": None,
                                "total_sources": 10,
                                "successful_sources": 7,
                                "failed_sources": 1,
                                "progress_percentage": 70,
                            },
                        },
                    },
                    "completed": {
                        "summary": "Scrape Completed",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape status retrieved",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "COMPLETED",
                                "started_at": "2023-10-01T12:00:00Z",
                                "completed_at": "2023-10-01T12:15:00Z",
                                "total_sources": 10,
                                "successful_sources": 9,
                                "failed_sources": 1,
                                "progress_percentage": 100,
                            },
                        },
                    },
                    "no_jobs": {
                        "summary": "No Jobs Run Yet",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape status retrieved",
                            "data": {"status": "no_jobs_run"},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The jurisdiction doesn't exist",
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve scrape status. Please try again.",
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

get_jurisdiction_scrape_status_custom_errors = ["404", "500"]
get_jurisdiction_scrape_status_custom_success = {
    "status_code": 200,
    "description": "Lightweight scrape status for polling progress.",
}


get_jurisdiction_data_page_responses = {
    200: {
        "description": "Data Page Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Full Data Page with Multi-Source Changes",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Data page retrieved",
                            "data": {
                                "status": "available",
                                "last_updated": "2026-01-13T21:20:50.803608+00:00",
                                "job_id": "f6a84464-31c1-4412-ae4a-89b41e2969a4",
                                "summary": "Fee changes detected across sources",
                                "markdown_content": "## Summary\nAnalyzed updates...",
                                "extracted_data": {
                                    "fee_schedule_standard_license": {
                                        "canonical_value": "$13,500.00",
                                        "has_discrepancy": True,
                                        "source_count": 2,
                                        "agreement_count": 1,
                                        "discrepancies": [
                                            {
                                                "source_id": "source_2",
                                                "source_url": "https://example.com/fees",
                                                "value": "$9,500.00",
                                            }
                                        ],
                                    },
                                    "compliance_annual_audit_deadline": {
                                        "canonical_value": "December 31st",
                                        "has_discrepancy": False,
                                        "source_count": 2,
                                        "agreement_count": 2,
                                        "discrepancies": [],
                                    },
                                },
                                "data_items": [
                                    {
                                        "field": "fee_schedule_standard_license",
                                        "value": "$13,500.00",
                                        "has_change": True,
                                        "has_discrepancy": True,
                                        "source_count": 2,
                                        "agreement_count": 1,
                                        "discrepancies": [
                                            {
                                                "source_id": "source_2",
                                                "source_url": "https://example.com/fees",
                                                "value": "$9,500.00",
                                            }
                                        ],
                                        "change": {
                                            "field": "fee_schedule_standard_license",
                                            "old_value": "$13,500.00",
                                            "new_value": "$13,500.00",
                                            "change_description": "Modified",
                                            "detected_at": "2026-01-14T12:00:00Z",
                                        },
                                        "change_index": 0,
                                    },
                                    {
                                        "field": "compliance_annual_audit_deadline",
                                        "value": "December 31st",
                                        "has_change": False,
                                        "has_discrepancy": False,
                                        "source_count": 2,
                                        "agreement_count": 2,
                                    },
                                ],
                                "confidence_score": 0.95,
                                "changes": [
                                    {
                                        "field": "fee_schedule_standard_license",
                                        "old_value": "$13,500.00",
                                        "new_value": "$13,500.00",
                                        "change_description": "Modified",
                                    }
                                ],
                                "has_unaccepted_changes": True,
                                "change_detection": {
                                    "has_changed": True,
                                    "change_summary": "Fee changes detected",
                                    "risk_level": "MEDIUM",
                                    "field_changes": [
                                        {
                                            "field_name": "fee_schedule_standard_license",
                                            "old_value": "$13,500.00",
                                            "new_value": "$13,500.00",
                                            "change_type": "modified",
                                        }
                                    ],
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction not found.",
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Failed to retrieve data page. Please try again.",
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

get_jurisdiction_data_page_custom_errors = ["404", "500"]
get_jurisdiction_data_page_custom_success = {
    "status_code": 200,
    "description": "Full consolidated data page with extracted content and change tracking.",
}

get_jurisdiction_scrape_history_responses = {
    200: {
        "description": "Scrape History Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "paginated_history": {
                        "summary": "Paginated Scrape History",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape history retrieved successfully",
                            "data": {
                                "jobs": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "status": "COMPLETED",
                                        "total_sources": 10,
                                        "successful_sources": 9,
                                        "filtered_sources": 5,
                                        "created_at": "2026-01-15T10:00:00Z",
                                        "started_at": "2026-01-15T10:00:01Z",
                                        "completed_at": "2026-01-15T10:15:00Z",
                                        "error_message": None,
                                        "changes_count": 3,
                                    },
                                    {
                                        "id": "223e4567-e89b-12d3-a456-426614174001",
                                        "status": "FAILED",
                                        "total_sources": 10,
                                        "successful_sources": 2,
                                        "filtered_sources": 0,
                                        "created_at": "2026-01-14T10:00:00Z",
                                        "started_at": "2026-01-14T10:00:01Z",
                                        "completed_at": "2026-01-14T10:05:00Z",
                                        "error_message": "Connection timeout",
                                        "changes_count": 0,
                                    },
                                ],
                                "pagination": {
                                    "total": 15,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 2,
                                },
                            },
                        },
                    },
                    "empty_history": {
                        "summary": "No Scrape Jobs Yet",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape history retrieved successfully",
                            "data": {
                                "jobs": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 0,
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The jurisdiction doesn't exist.",
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An error occurred while retrieving scrape history. \
                                Please try again.",
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

get_jurisdiction_scrape_history_custom_errors = ["404", "500"]
get_jurisdiction_scrape_history_custom_success = {
    "status_code": 200,
    "description": "Paginated list of scrape jobs for the jurisdiction.",
}


# Scrape Job Summary Endpoint Documentation
get_jurisdiction_scrape_job_summary_responses = {
    200: {
        "description": "Scrape Job Summary Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "completed_job": {
                        "summary": "Completed Job with Changes",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job summary retrieved",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174001",
                                "status": "COMPLETED",
                                "markdown_summary": "## Jurisdiction Summary\n\n"
                                "This jurisdiction covers...",
                                "change_summary": "Filing fees increased from $50 to $75",
                                "changes": [
                                    {
                                        "field": "filing_fees",
                                        "old_value": "$50",
                                        "new_value": "$75",
                                        "change_description": "Filing fees increased by $25",
                                        "change_index": 0,
                                        "change_id": "abc12345-e89b-12d3-a456-426614174000",
                                        "ticket_created": False,
                                        "change_accepted": False,
                                    }
                                ],
                                "error_message": None,
                                "created_at": "2024-01-15T10:00:00Z",
                                "completed_at": "2024-01-15T10:05:00Z",
                            },
                        },
                    },
                    "failed_job": {
                        "summary": "Failed Job with Error Message",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job summary retrieved",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174001",
                                "status": "FAILED",
                                "markdown_summary": None,
                                "change_summary": None,
                                "changes": [],
                                "error_message": "LLM extraction failed after retries",
                                "created_at": "2024-01-15T10:00:00Z",
                                "completed_at": None,
                            },
                        },
                    },
                    "no_changes_job": {
                        "summary": "Completed Job with No Changes",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job summary retrieved",
                            "data": {
                                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174001",
                                "status": "COMPLETED",
                                "markdown_summary": "## Jurisdiction Summary\n\n"
                                "No significant changes detected.",
                                "change_summary": "No changes detected",
                                "changes": [],
                                "error_message": None,
                                "created_at": "2024-01-15T10:00:00Z",
                                "completed_at": "2024-01-15T10:05:00Z",
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Job Does Not Belong to Jurisdiction",
        "content": {
            "application/json": {
                "examples": {
                    "wrong_jurisdiction": {
                        "summary": "Job Belongs to Different Jurisdiction",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "The scrape job does not belong to this jurisdiction.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction or Job Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "jurisdiction_not_found": {
                        "summary": "Jurisdiction Does Not Exist",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "The jurisdiction doesn't exist.",
                            "status_code": 404,
                            "errors": {},
                        },
                    },
                    "job_not_found": {
                        "summary": "Scrape Job Does Not Exist",
                        "value": {
                            "error_code": "JURISDICTION_SCRAPE_JOB_NOT_FOUND",
                            "message": "The jurisdiction scrape job was not found.",
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
                    "processing_error": {
                        "summary": "Processing Error - Controlled Failure",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An error occurred while retrieving scrape job summary. "
                            "Please try again.",
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

get_jurisdiction_scrape_job_summary_custom_errors = ["400", "404", "500"]
get_jurisdiction_scrape_job_summary_custom_success = {
    "status_code": 200,
    "description": "Scrape job summary with markdown content and changes.",
}
