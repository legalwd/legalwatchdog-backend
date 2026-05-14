# GET SOURCE REVISIONS DOCS
get_source_revisions_responses = {
    200: {
        "description": "Revisions Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Successful Retrieval",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Revisions retrieved successfully",
                            "data": {
                                "revisions": [
                                    {
                                        "id": "987e6543-e21c-34d5-b678-556655440000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "minio_object_key": "scrapes/2025/11/25/source-13e457.html",
                                        "content_hash": "abc123def456",
                                        "extracted_data": {
                                            "title": "New Regulation 2025-001",
                                            "content": "Full text of the regulation...",
                                            "effective_date": "2025-12-01",
                                        },
                                        "ai_summary": "New data privacy law effective March 2026",
                                        "ai_markdown_summary": "##New Regulation\n\nKey changes...",
                                        "ai_confidence_score": 0.95,
                                        "scraped_at": "2025-11-25T10:30:00Z",
                                        "was_change_detected": True,
                                    },
                                    {
                                        "id": "876e5432-d10b-23c4-a567-445544330000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "minio_object_key": "scrapes/2025/11/20/source-13e47.html",
                                        "content_hash": "def456ghi789",
                                        "extracted_data": {
                                            "title": "Previous Regulation Update",
                                            "content": "Updated text...",
                                            "effective_date": "2025-11-01",
                                        },
                                        "ai_summary": "Minor update to existing regulation",
                                        "ai_markdown_summary": "## Update\\n\\nMinor changes...",
                                        "ai_confidence_score": 0.88,
                                        "scraped_at": "2025-11-20T08:15:00Z",
                                        "was_change_detected": False,
                                    },
                                ],
                                "pagination": {
                                    "total": 150,
                                    "page": 1,
                                    "limit": 50,
                                    "total_pages": 3,
                                },
                            },
                        },
                    },
                    "empty_results": {
                        "summary": "No Revisions Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Revisions retrieved successfully",
                            "data": {
                                "revisions": [],
                                "pagination": {
                                    "total": 0,
                                    "page": 1,
                                    "limit": 50,
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
        "description": "Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Does Not Exist",
                        "value": {
                            "error": "ERROR",
                            "status_code": 404,
                            "message": "Source not found",
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_skip": {
                        "summary": "Invalid Skip Parameter",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "status_code": 422,
                            "message": "Validation failed",
                            "errors": {"skip": ["Input should be greater than or equal to 0"]},
                        },
                    },
                    "invalid_limit": {
                        "summary": "Invalid Limit Parameter",
                        "value": {
                            "error": "VALIDATION_ERROR",
                            "status_code": 422,
                            "message": "Validation failed",
                            "errors": {"limit": ["Input should be less than or equal to 200"]},
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Revisions retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while retrieving revisions. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_source_revisions_custom_errors = ["404", "422", "500"]
get_source_revisions_custom_success = {
    "status_code": 200,
    "description": "Revisions retrieved successfully with pagination metadata",
}
create_source_responses = {
    201: {
        "description": "Source Created Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Source Created",
                        "value": {
                            "status": "success",
                            "status_code": 201,
                            "message": "Source created successfully",
                            "data": {
                                "source": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Supreme Court Opinions",
                                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                                    "source_type": "web",
                                    "scrape_frequency": "DAILY",
                                    "is_active": True,
                                    "is_deleted": False,
                                    "auto_create_tickets": False,
                                    "has_auth": False,
                                    "created_at": "2025-11-21T10:30:00Z",
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Duplicate URL in Jurisdiction",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_url": {
                        "summary": "Duplicate URL in Jurisdiction",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": "Source with this URL already exists in the jurisdiction",
                            "error_code": "DUPLICATE_URL",
                            "errors": {},
                        },
                    },
                    "missing_prompt": {
                        "summary": "Missing Jurisdiction Prompt",
                        "value": {
                            "status": "error",
                            "status_code": 400,
                            "message": "Add jurisdiction prompt before adding sources. \
                                These instructions guide the AI scraping pipeline.",
                            "error_code": "BAD_REQUEST",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Jurisdiction or Project Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Jurisdiction or Project Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Jurisdiction not found",
                            "error_code": "NOT_FOUND",
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
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {
                                "jurisdiction_id": ["Field required"],
                                "name": ["Field required"],
                                "url": ["Field required", "Invalid URL format"],
                                "source_type": ["Field required"],
                                "scrape_frequency": ["Field required"],
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Source creation failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while creating the source. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

create_source_custom_errors = ["400", "422", "500", "404"]
create_source_custom_success = {
    "status_code": 201,
    "description": "Source created successfully with provided configuration.",
}

get_sources_responses = {
    200: {
        "description": "Sources Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Sources Retrieved",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Sources retrieved successfully",
                            "data": {
                                "sources": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "name": "Supreme Court Opinions",
                                        "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                                        "source_type": "web",
                                        "scrape_frequency": "DAILY",
                                        "is_active": True,
                                        "is_deleted": False,
                                        "auto_create_tickets": False,
                                        "has_auth": False,
                                        "created_at": "2025-11-21T10:30:00Z",
                                    }
                                ],
                                "count": 1,
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
                        "summary": "Query Parameter Validation Failed",
                        "value": {
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {
                                "limit": ["ensure this value is less than or equal to 500"],
                                "skip": ["ensure this value is greater than or equal to 0"],
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Sources retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while retrieving sources. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_sources_custom_errors = ["422", "500"]
get_sources_custom_success = {
    "status_code": 200,
    "description": "Sources retrieved successfully with applied filters and pagination.",
}


get_source_responses = {
    200: {
        "description": "Source Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Source Retrieved",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Source retrieved successfully",
                            "data": {
                                "source": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Supreme Court Opinions",
                                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                                    "source_type": "web",
                                    "scrape_frequency": "DAILY",
                                    "is_active": True,
                                    "is_deleted": False,
                                    "auto_create_tickets": False,
                                    "has_auth": False,
                                    "created_at": "2025-11-21T10:30:00Z",
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Source not found",
                            "error_code": "SOURCE_NOT_FOUND",
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Source retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while retrieving the source. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_source_custom_errors = ["404", "500"]
get_source_custom_success = {
    "status_code": 200,
    "description": "Source retrieved successfully by ID.",
}


update_source_responses = {
    200: {
        "description": "Source Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Source Updated",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Source updated successfully",
                            "data": {
                                "source": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Supreme Court Opinions",
                                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                                    "source_type": "web",
                                    "scrape_frequency": "HOURLY",
                                    "is_active": False,
                                    "is_deleted": False,
                                    "auto_create_tickets": True,
                                    "has_auth": False,
                                    "created_at": "2025-11-21T10:30:00Z",
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Source not found",
                            "error_code": "SOURCE_NOT_FOUND",
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
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {
                                "url": ["Invalid URL format"],
                                "scrape_frequency": ["Invalid frequency value"],
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Source update failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while updating the source. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_source_custom_errors = ["404", "422", "500"]
update_source_custom_success = {
    "status_code": 200,
    "description": "Source updated successfully with provided changes.",
}


delete_source_responses = {
    204: {
        "description": "Source Deleted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success_soft_delete": {"summary": "Source Soft Deleted", "value": None},
                    "success_hard_delete": {"summary": "Source Permanently Deleted", "value": None},
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Source not found",
                            "error_code": "SOURCE_NOT_FOUND",
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Source deletion failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while deleting the source. \
                                Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

delete_source_custom_errors = ["404", "500"]
delete_source_custom_success = {
    "status_code": 204,
    "description": "Source deleted successfully (soft or permanent based on request).",
}


update_source_patch_responses = {
    200: {
        "description": "Source Updated Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Source Updated",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Source updated successfully",
                            "data": {
                                "source": {
                                    "id": "123e4567-e89b-12d3-a456-426614174000",
                                    "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Supreme Court Opinions",
                                    "url": "https://www.supremecourt.gov/opinions/slipopinion.aspx",
                                    "source_type": "web",
                                    "scrape_frequency": "DAILY",
                                    "is_active": True,
                                    "is_deleted": False,
                                    "auto_create_tickets": False,
                                    "has_auth": False,
                                    "created_at": "2025-11-21T10:30:00Z",
                                }
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Source not found",
                            "error_code": "NOT_FOUND",
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
                            "status": "error",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {
                                "url": ["Invalid URL format"],
                                "scrape_frequency": ["Invalid frequency"],
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
                            "status": "error",
                            "status_code": 500,
                            "message": "Source update failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while updating the source \
                                via patch. Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

update_source_patch_custom_errors = ["404", "422", "500"]
update_source_patch_custom_success = {
    "status_code": 200,
    "description": "Source updated successfully via partial update.",
}
