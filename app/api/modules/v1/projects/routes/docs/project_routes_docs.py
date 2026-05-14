create_project_responses = {
    201: {
        "description": "Project Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Project created successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "org_id": "123e4567-e89b-12d3-a456-426614174001",
                                "title": "Legal Compliance Monitoring",
                                "description": "Monitor legal compliance across jurisdictions",
                                "master_prompt": "Analyze legal documents for compliance issues",
                                "is_deleted": False,
                                "created_at": "2023-10-01T12:00:00Z",
                                "updated_at": "2023-10-01T12:00:00Z",
                                "deleted_at": None,
                                "created_by": "123e4567-e89b-12d3-a456-426614174002",
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "permission_denied": {
                        "summary": "User Not in Organization",
                        "value": {
                            "error": "ERROR",
                            "message": "User is not a member of this organization",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "plan_limit": {
                        "summary": "Project Creation Limit Reached",
                        "value": {
                            "error": "PLAN_LIMIT_EXCEEDED",
                            "message": "Project creation limit reached for your plan",
                            "status_code": 403,
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
                                "title": [
                                    "Field required",
                                    "String should have at least 1 character",
                                ],
                                "description": ["String should have at most 1000 characters"],
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
                            "message": "Failed to create project. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_project_custom_errors = ["403", "422", "500"]
create_project_custom_success = {
    "status_code": 201,
    "description": "Project created successfully with creator automatically added as member.",
}


list_projects_in_organization_responses = {
    200: {
        "description": "Projects Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated Projects List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Projects retrieved successfully",
                            "data": {
                                "projects": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "org_id": "123e4567-e89b-12d3-a456-426614174001",
                                        "title": "Legal Compliance Monitoring",
                                        "description": "Monitor legal compliance",
                                        "master_prompt": "Analyze legal documents",
                                        "is_deleted": False,
                                        "created_at": "2023-10-01T12:00:00Z",
                                        "updated_at": "2023-10-01T12:00:00Z",
                                        "deleted_at": None,
                                        "created_by": "123e4567-e89b-12d3-a456-426614174002",
                                    }
                                ],
                                "total": 15,
                                "page": 1,
                                "limit": 20,
                                "total_pages": 1,
                            },
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
                                "limit": ["Must be between 1 and 100"],
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
                            "message": "Failed to retrieve projects. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_projects_in_organization_custom_errors = ["422", "500"]
list_projects_in_organization_custom_success = {
    "status_code": 200,
    "description": "Projects retrieved successfully with search and pagination.",
}


get_project_responses = {
    200: {
        "description": "Project Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Details",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project retrieved successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "org_id": "123e4567-e89b-12d3-a456-426614174001",
                                "title": "Legal Compliance Monitoring",
                                "description": "Monitor legal compliance across jurisdictions",
                                "master_prompt": "Analyze legal documents for compliance issues",
                                "is_deleted": False,
                                "created_at": "2023-10-01T12:00:00Z",
                                "updated_at": "2023-10-01T12:00:00Z",
                                "deleted_at": None,
                                "created_by": "123e4567-e89b-12d3-a456-426614174002",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                            "message": "Failed to retrieve project.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_project_custom_errors = ["404", "500"]
get_project_custom_success = {
    "status_code": 200,
    "description": "Project details retrieved successfully.",
}


update_project_responses = {
    200: {
        "description": "Project Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project updated successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "org_id": "123e4567-e89b-12d3-a456-426614174001",
                                "title": "Updated Project Title",
                                "description": "Updated project description",
                                "master_prompt": "Updated master prompt",
                                "is_deleted": False,
                                "created_at": "2023-10-01T12:00:00Z",
                                "updated_at": "2023-10-02T14:30:00Z",
                                "deleted_at": None,
                                "created_by": "123e4567-e89b-12d3-a456-426614174002",
                            },
                        },
                    },
                    "archived": {
                        "summary": "Project Archived",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project archived successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "is_deleted": True,
                                "deleted_at": "2023-10-02T14:30:00Z",
                            },
                        },
                    },
                    "restored": {
                        "summary": "Project Restored",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project restored successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "is_deleted": False,
                                "deleted_at": None,
                            },
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "permission_denied": {
                        "summary": "Edit Permission Required",
                        "value": {
                            "error": "ERROR",
                            "message": "You don't have permission to edit this project",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                                "title": ["String should have at least 1 character"],
                                "description": ["String should have at most 1000 characters"],
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
                            "message": "Failed to update project. Please try again.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_project_custom_errors = ["403", "404", "422", "500"]
update_project_custom_success = {
    "status_code": 200,
    "description": "Project updated successfully with partial updates and archive/restore support.",
}


delete_project_responses = {
    204: {
        "description": "Project Permanently Deleted",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Deleted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "Project permanently deleted",
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "permission_denied": {
                        "summary": "Delete Permission Required",
                        "value": {
                            "error": "ERROR",
                            "message": "You don't have permission to delete this project",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                            "message": "Failed to permanently delete project.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_project_custom_errors = ["403", "404", "500"]
delete_project_custom_success = {
    "status_code": 204,
    "description": "Project permanently deleted from database (irreversible).",
}


get_project_users_responses = {
    200: {
        "description": "Project Users Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Users List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Project users retrieved successfully",
                            "data": {
                                "user_ids": [
                                    "123e4567-e89b-12d3-a456-426614174002",
                                    "123e4567-e89b-12d3-a456-426614174003",
                                ],
                                "total": 2,
                                "page": 1,
                                "limit": 20,
                                "total_pages": 1,
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                                "limit": ["Must be between 1 and 100"],
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
                            "message": "Failed to retrieve project users.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_project_users_custom_errors = ["404", "422", "500"]
get_project_users_custom_success = {
    "status_code": 200,
    "description": "Project users retrieved successfully with pagination.",
}


add_user_to_project_responses = {
    201: {
        "description": "User Added to Project Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Added",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "User successfully added to project",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - User Already in Project or Not in Organization",
        "content": {
            "application/json": {
                "examples": {
                    "already_member": {
                        "summary": "User Already in Project",
                        "value": {
                            "error": "ERROR",
                            "message": "User is already a member of this project",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "not_in_org": {
                        "summary": "User Not in Organization",
                        "value": {
                            "error": "ERROR",
                            "message": "User is not a member of this organization",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "permission_denied": {
                        "summary": "Edit Projects Permission Required",
                        "value": {
                            "error": "ERROR",
                            "message": "You don't have permission to add users to projects",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                            "message": "Failed to add user to project.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

add_user_to_project_custom_errors = ["400", "403", "404", "500"]
add_user_to_project_custom_success = {
    "status_code": 201,
    "description": "User added to project successfully. Requires edit_projects permission.",
}


remove_user_from_project_responses = {
    200: {
        "description": "User Removed from Project Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "User Removed",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "User successfully removed from project",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - User Not in Project",
        "content": {
            "application/json": {
                "examples": {
                    "not_member": {
                        "summary": "User Not in Project",
                        "value": {
                            "error": "ERROR",
                            "message": "User is not a member of this project",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Permission Denied",
        "content": {
            "application/json": {
                "examples": {
                    "permission_denied": {
                        "summary": "Edit Projects Permission Required",
                        "value": {
                            "error": "ERROR",
                            "message": "You don't have permission to remove users from projects",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
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
                            "message": "Failed to remove user from project.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

remove_user_from_project_custom_errors = ["400", "403", "404", "500"]
remove_user_from_project_custom_success = {
    "status_code": 200,
    "description": "User removed from project successfully. Requires edit_projects permission.",
}


bulk_generate_project_blogs_responses = {
    202: {
        "description": "Bulk Blog Generation Triggered",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Job Queued",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": (
                                "Bulk blog generation triggered. Check back in a few moments."
                            ),
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                "status": "PENDING",
                                "totals": 50,
                                "processed": 0,
                                "failed": 0,
                                "skipped": 0,
                                "publish_requested": False,
                                "created_at": "2023-10-01T12:00:00Z",
                                "items": [],
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Empty Jurisdiction Set",
        "content": {
            "application/json": {
                "examples": {
                    "empty_set": {
                        "summary": "No Jurisdictions in Project",
                        "value": {
                            "error": "EMPTY_JURISDICTION_SET",
                            "message": "This project has no jurisdictions to process.",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    409: {
        "description": "Conflict - Bulk Job Already In Progress",
        "content": {
            "application/json": {
                "examples": {
                    "in_progress": {
                        "summary": "Job In Progress",
                        "value": {
                            "error": "BULK_BLOG_IN_PROGRESS",
                            "message": (
                                "A bulk blog generation is already in progress for this project."
                            ),
                            "status_code": 409,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

bulk_publish_project_blogs_responses = {
    200: {
        "description": "Batch publish/unpublish completed for project jurisdictions",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Batch publish",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Batch published: 3 succeeded, 1 skipped, 0 failed",
                            "data": {
                                "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                "is_published": True,
                                "not_in_project_jurisdiction_ids": [],
                                "succeeded": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174010",
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174020",
                                        "title": "Example",
                                        "slug": "example-slug",
                                        "is_published": True,
                                        "public_url": "https://legalwatch.dog/resources/...",
                                        "published_at": "2026-02-15T14:30:00Z",
                                    }
                                ],
                                "skipped": [
                                    {
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174021",
                                        "reason": "Blog post not found for this jurisdiction",
                                    }
                                ],
                                "failed": [],
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Project not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Project not found",
                        "value": {
                            "error": "ERROR",
                            "message": "Project not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_bulk_generation_job_responses = {
    200: {
        "description": "Bulk Blog Job Status Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Job Status",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Bulk blog generation status retrieved",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                "status": "COMPLETED",
                                "totals": 50,
                                "processed": 48,
                                "failed": 0,
                                "skipped": 2,
                                "publish_requested": True,
                                "created_at": "2023-10-01T12:00:00Z",
                                "completed_at": "2023-10-01T12:05:00Z",
                                "items": [
                                    {
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-42661417400X",
                                        "status": "COMPLETED",
                                        "message": "Processed",
                                        "public_url": "https://legalwatch.dog/resources/...",
                                    }
                                ],
                            },
                        },
                    }
                }
            }
        },
    },
}

list_bulk_generation_jobs_responses = {
    200: {
        "description": "Bulk Blog Jobs Paginated List",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jobs List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Bulk blog generation jobs retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "project_id": "123e4567-e89b-12d3-a456-426614174001",
                                        "status": "COMPLETED",
                                        "totals": 50,
                                        "processed": 48,
                                        "failed": 0,
                                        "skipped": 2,
                                        "publish_requested": True,
                                        "created_at": "2023-10-01T12:00:00Z",
                                        "completed_at": "2023-10-01T12:05:00Z",
                                    }
                                ],
                                "pagination": {
                                    "total": 1,
                                    "page": 1,
                                    "limit": 20,
                                    "total_pages": 1,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
}
