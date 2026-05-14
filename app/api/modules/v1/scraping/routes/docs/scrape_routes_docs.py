"""
OpenAPI documentation for scrape job routes.

Provides response schemas and examples for:
- POST /scrapes/{source_id} - Trigger manual scrape
- GET /scrapes/{source_id}/{job_id} - Get scrape job status
- GET /scrapes/{source_id}/active - Get active scrape job
- GET /scrapes/{source_id} - List scrape jobs for source
"""

manual_scrape_trigger_responses = {
    202: {
        "description": "Scrape Job Queued Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Scrape Job Queued",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Scrape job queued successfully",
                            "data": {
                                "job_id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "PENDING",
                                "is_baseline": False,
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Source Inactive",
        "content": {
            "application/json": {
                "examples": {
                    "inactive_source": {
                        "summary": "Source Inactive",
                        "value": {
                            "error_code": "SOURCE_INACTIVE",
                            "message": "Cannot scrape inactive source. Please enable it first.",
                            "status_code": 400,
                            "errors": {},
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
                            "error_code": "SOURCE_NOT_FOUND",
                            "message": "Source not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    409: {
        "description": "Conflict - Scrape Already In Progress",
        "content": {
            "application/json": {
                "examples": {
                    "scrape_in_progress": {
                        "summary": "Scrape Already Running",
                        "value": {
                            "error_code": "SCRAPE_IN_PROGRESS",
                            "message": "A scrape is already in progress for this source. "
                            "Please wait for it to complete.",
                            "status_code": 409,
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
                    "internal_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occured while accepting sources",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

manual_scrape_trigger_custom_errors = ["400", "404", "409", "500"]
manual_scrape_trigger_custom_success = {
    "status_code": 202,
    "description": "Scrape job queued successfully. Use job_id to poll for status.",
}


get_scrape_job_status_responses = {
    200: {
        "description": "Scrape Job Status Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "pending": {
                        "summary": "Job Pending",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "PENDING",
                                "result": None,
                                "error_message": None,
                                "data_revision_id": None,
                                "is_baseline": False,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": None,
                                "completed_at": None,
                            },
                        },
                    },
                    "in_progress": {
                        "summary": "Job In Progress",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "IN_PROGRESS",
                                "result": None,
                                "error_message": None,
                                "data_revision_id": None,
                                "is_baseline": False,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": None,
                            },
                        },
                    },
                    "completed": {
                        "summary": "Job Completed",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "COMPLETED",
                                "result": {
                                    "status": "success",
                                    "change_detected": True,
                                    "change_summary": "New regulation added for data privacy",
                                },
                                "error_message": None,
                                "data_revision_id": "abc12345-d678-90ef-ghij-klmnopqrstuv",
                                "is_baseline": False,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": "2025-12-04T10:31:15Z",
                            },
                        },
                    },
                    "failed": {
                        "summary": "Job Failed",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape job status retrieved successfully",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "FAILED",
                                "result": None,
                                "error_message": (
                                    "Scrape execution failed. Please try again or "
                                    "contact support if the issue persists."
                                ),
                                "data_revision_id": None,
                                "is_baseline": False,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": "2025-12-04T10:30:45Z",
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Not Found - Scrape Job Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "job_not_found": {
                        "summary": "Job Not Found",
                        "value": {
                            "error_code": "JOB_NOT_FOUND",
                            "message": "Scrape job not found",
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
                    "internal_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occurred while retrieving status",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_scrape_job_status_custom_errors = ["404", "500"]
get_scrape_job_status_custom_success = {
    "status_code": 200,
    "description": "Scrape job status retrieved successfully with current state and results.",
}


get_active_scrape_job_responses = {
    200: {
        "description": "Active Scrape Job Found",
        "content": {
            "application/json": {
                "examples": {
                    "active_job": {
                        "summary": "Active Job Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Active scrape job found for this source",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "status": "IN_PROGRESS",
                                "result": None,
                                "error_message": None,
                                "data_revision_id": None,
                                "is_baseline": False,
                                "created_at": "2025-12-04T10:30:00Z",
                                "started_at": "2025-12-04T10:30:05Z",
                                "completed_at": None,
                            },
                        },
                    }
                }
            }
        },
    },
    204: {
        "description": "No Active Scrape Job",
        "content": {
            "application/json": {
                "examples": {
                    "no_active_job": {
                        "summary": "No Active Job",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 204,
                            "message": "No active scrape job found for this source",
                            "data": {},
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
                            "error_code": "SOURCE_NOT_FOUND",
                            "message": "Source not found",
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
                    "internal_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occurred while retrieving scrape job",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

get_active_scrape_job_custom_errors = ["404", "500"]
get_active_scrape_job_custom_success = {
    "status_code": 200,
    "description": "Active scrape job retrieved successfully. Returns 204 if no active job.",
}


list_scrape_jobs_responses = {
    200: {
        "description": "Scrape Jobs Listed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "jobs_list": {
                        "summary": "Jobs List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Scrape jobs retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "987e6543-e21c-34d5-b678-556655440000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "status": "COMPLETED",
                                        "result": {
                                            "status": "success",
                                            "change_detected": True,
                                            "change_summary": "New regulation added",
                                        },
                                        "error_message": None,
                                        "data_revision_id": "abc12345-d678-90ef-ghij-klmnopqrstuv",
                                        "is_baseline": False,
                                        "created_at": "2025-12-04T10:30:00Z",
                                        "started_at": "2025-12-04T10:30:05Z",
                                        "completed_at": "2025-12-04T10:31:15Z",
                                    },
                                    {
                                        "id": "876e5432-d21c-43d5-c678-665544330000",
                                        "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                        "status": "FAILED",
                                        "result": None,
                                        "error_message": (
                                            "Scrape execution failed. Please try again"
                                        ),
                                        "data_revision_id": None,
                                        "is_baseline": False,
                                        "created_at": "2025-12-04T09:15:00Z",
                                        "started_at": "2025-12-04T09:15:02Z",
                                        "completed_at": "2025-12-04T09:15:30Z",
                                    },
                                ],
                                "total": 2,
                                "page": 1,
                                "per_page": 20,
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
                            "error_code": "SOURCE_NOT_FOUND",
                            "message": "Source not found",
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
                    "internal_error": {
                        "summary": "Internal Server Error",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occurred while retrieving scrape jobs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

list_scrape_jobs_custom_errors = ["404", "500"]
list_scrape_jobs_custom_success = {
    "status_code": 200,
    "description": "Scrape jobs listed successfully with pagination metadata.",
}
