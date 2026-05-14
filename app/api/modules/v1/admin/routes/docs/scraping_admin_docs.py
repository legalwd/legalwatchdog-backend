manual_scrape_source_responses = {
    202: {
        "description": "Manual scrape task initiated successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Task initiated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Manual scrape task initiated",
                            "data": {
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                "task_id": "abc123-def456-ghi789",
                                "status": "initiated",
                            },
                        },
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
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source not found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source not found",
                        "value": {
                            "error": "SOURCE_NOT_FOUND",
                            "message": (
                                "Source with ID 123e4567-e89b-12d3-a456-426614174000 not found"
                            ),
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
                    "manual_scrape_error": {
                        "summary": "Manual Scrape Error",
                        "value": {
                            "error": "MANUAL_SCRAPE_ERROR",
                            "message": (
                                "Failed to initiate manual scrape for source "
                                "123e4567-e89b-12d3-a456-426614174000"
                            ),
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "task_initiation_error": {
                        "summary": "Task Initiation Error",
                        "value": {
                            "error": "TASK_INITIATION_ERROR",
                            "message": "Failed to initiate manual scrape task",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to initiate manual scrape",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

manual_scrape_source_custom_errors = ["401", "404", "500"]
manual_scrape_source_custom_success = {
    "status_code": 202,
    "description": "Manual scrape task initiated successfully.",
}

retry_stuck_jobs_responses = {
    202: {
        "description": "Retry stuck jobs task initiated successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Task initiated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Retry stuck jobs task initiated",
                            "data": {
                                "task_id": "abc123-def456-ghi789",
                                "status": "initiated",
                            },
                        },
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
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
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
                    "stuck_job_retry_error": {
                        "summary": "Stuck Job Retry Error",
                        "value": {
                            "error": "STUCK_JOB_RETRY_ERROR",
                            "message": "Failed to initiate retry of stuck jobs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "task_initiation_error": {
                        "summary": "Task Initiation Error",
                        "value": {
                            "error": "TASK_INITIATION_ERROR",
                            "message": "Failed to initiate retry stuck jobs task",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to initiate retry stuck jobs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

retry_stuck_jobs_custom_errors = ["401", "500"]
retry_stuck_jobs_custom_success = {
    "status_code": 202,
    "description": "Retry stuck jobs task initiated successfully.",
}

clear_stuck_jobs_responses = {
    200: {
        "description": "Stuck jobs cleared successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jobs cleared",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Successfully cleared 5 stuck jobs",
                            "data": {
                                "cleared_count": 5,
                                "source_id": "123e4567-e89b-12d3-a456-426614174000",
                            },
                        },
                    },
                    "no_jobs": {
                        "summary": "No stuck jobs found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "No stuck jobs found",
                            "data": {"cleared_count": 0},
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
                            "error": "UNAUTHORIZED",
                            "message": "Authentication required",
                            "status_code": 401,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Source not found",
        "content": {
            "application/json": {
                "examples": {
                    "source_not_found": {
                        "summary": "Source not found",
                        "value": {
                            "error": "SOURCE_NOT_FOUND",
                            "message": (
                                "Source with ID 123e4567-e89b-12d3-a456-426614174000 not found"
                            ),
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
                    "clear_stuck_jobs_error": {
                        "summary": "Clear Stuck Jobs Error",
                        "value": {
                            "error": "CLEAR_STUCK_JOBS_ERROR",
                            "message": "Failed to clear stuck jobs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "server_error": {
                        "summary": "Server Error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Failed to clear stuck jobs",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

clear_stuck_jobs_custom_errors = ["401", "404", "500"]
clear_stuck_jobs_custom_success = {
    "status_code": 200,
    "description": "Stuck jobs cleared successfully.",
}
