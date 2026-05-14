list_sources_responses = {
    200: {
        "description": "Sources Listed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated Sources List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Sources listed",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "Supreme Court of California",
                                        "slug": "supreme-court-ca",
                                        "jurisdiction_id": "123e4567-e89b-12d3-a456-426614174001",
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
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                            "message": "Failed to list sources",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_sources_custom_errors = ["400", "403", "422", "500"]
list_sources_custom_success = {
    "status_code": 200,
    "description": "Sources retrieved successfully with organization-based filtering.",
}


list_jurisdictions_responses = {
    200: {
        "description": "Jurisdictions Listed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated Jurisdictions List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdictions listed",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174001",
                                        "name": "California",
                                        "project_id": "123e4567-e89b-12d3-a456-426614174002",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                            "message": "Failed to list jurisdictions",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_jurisdictions_custom_errors = ["403", "422", "500"]
list_jurisdictions_custom_success = {
    "status_code": 200,
    "description": "Jurisdictions retrieved successfully with organization-based filtering.",
}


list_projects_responses = {
    200: {
        "description": "Projects Listed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Paginated Projects List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Projects listed",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174002",
                                        "title": "California Courts Monitoring",
                                        "org_id": "123e4567-e89b-12d3-a456-426614174003",
                                    }
                                ]
                            },
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                            "message": "Failed to list projects",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_projects_custom_errors = ["403", "422", "500"]
list_projects_custom_success = {
    "status_code": 200,
    "description": "Projects retrieved successfully with organization-based filtering.",
}


get_source_extracted_data_responses = {
    200: {
        "description": "Extracted Data Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Source Extracted Data",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Extracted data retrieved",
                            "data": {
                                "revisions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174004",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "scraped_at": "2023-10-01T12:00:00Z",
                                        "extracted_data": {
                                            "case_number": "SC123456",
                                            "title": "Smith v. Jones",
                                            "filing_date": "2023-09-15",
                                            "status": "Pending",
                                        },
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
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope or Organization Mismatch",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "organization_mismatch": {
                        "summary": "Organization Access Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Organization mismatch",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Source Not Found",
                        "value": {
                            "error": "ERROR",
                            "message": "Source not found",
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
                                "limit": ["Must be between 1 and 1000"],
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
                            "message": "Failed to retrieve extracted data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_source_extracted_data_custom_errors = ["400", "403", "404", "422", "500"]
get_source_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Extracted data for source retrieved successfully with optional filtering.",
}


download_source_extracted_data_responses = {
    200: {
        "description": "File Download Ready",
        "content": {
            "application/octet-stream": {
                "examples": {
                    "success": {
                        "summary": "JSON File Download",
                        "value": "Binary file stream with extracted data",
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 5000"],
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
                            "message": "Failed to generate download file",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

download_source_extracted_data_custom_errors = ["400", "403", "422", "500"]
download_source_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Extracted data file ready for download in JSON format.",
}


download_jurisdiction_extracted_data_responses = {
    200: {
        "description": "File Download Ready",
        "content": {
            "application/octet-stream": {
                "examples": {
                    "success": {
                        "summary": "JSON File Download",
                        "value": "Binary file stream with jurisdiction extracted data",
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 5000"],
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
                            "message": "Failed to generate download file",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

download_jurisdiction_extracted_data_custom_errors = ["400", "403", "422", "500"]
download_jurisdiction_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction extracted data file ready for download in JSON format.",
}


download_project_extracted_data_responses = {
    200: {
        "description": "File Download Ready",
        "content": {
            "application/octet-stream": {
                "examples": {
                    "success": {
                        "summary": "JSON File Download",
                        "value": "Binary file stream with project extracted data",
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 5000"],
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
                            "message": "Failed to generate download file",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

download_project_extracted_data_custom_errors = ["400", "403", "422", "500"]
download_project_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Project extracted data file ready for download in JSON format.",
}


get_jurisdiction_extracted_data_responses = {
    200: {
        "description": "Extracted Data Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jurisdiction Extracted Data",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Extracted data retrieved",
                            "data": {
                                "revisions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174005",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "scraped_at": "2023-10-01T12:00:00Z",
                                        "extracted_data": {
                                            "case_number": "SC123456",
                                            "title": "Smith v. Jones",
                                            "filing_date": "2023-09-15",
                                            "status": "Pending",
                                        },
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
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope or Organization Mismatch",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "organization_mismatch": {
                        "summary": "Organization Access Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Organization mismatch",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 1000"],
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
                            "message": "Failed to retrieve extracted data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_jurisdiction_extracted_data_custom_errors = ["400", "403", "422", "500"]
get_jurisdiction_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Extracted data for jurisdiction retrieved successfully"
    " with optional filtering.",
}


get_project_extracted_data_responses = {
    200: {
        "description": "Extracted Data Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Project Extracted Data",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Extracted data retrieved",
                            "data": {
                                "revisions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174006",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "scraped_at": "2023-10-01T12:00:00Z",
                                        "extracted_data": {
                                            "case_number": "SC123456",
                                            "title": "Smith v. Jones",
                                            "filing_date": "2023-09-15",
                                            "status": "Pending",
                                        },
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
        "description": "Bad Request - Invalid Date Format",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_date": {
                        "summary": "Invalid Date Format",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid start_date",
                            "status_code": 400,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden - Insufficient Scope or Organization Mismatch",
        "content": {
            "application/json": {
                "examples": {
                    "insufficient_scope": {
                        "summary": "Missing Required Scope",
                        "value": {
                            "error": "ERROR",
                            "message": "Insufficient scope",
                            "status_code": 403,
                            "errors": {},
                        },
                    },
                    "organization_mismatch": {
                        "summary": "Organization Access Denied",
                        "value": {
                            "error": "ERROR",
                            "message": "Organization mismatch",
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
                                "skip": ["Must be greater than or equal to 0"],
                                "limit": ["Must be between 1 and 1000"],
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
                            "message": "Failed to retrieve extracted data",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_project_extracted_data_custom_errors = ["400", "403", "422", "500"]
get_project_extracted_data_custom_success = {
    "status_code": 200,
    "description": "Extracted data for project retrieved successfully with optional filtering.",
}
