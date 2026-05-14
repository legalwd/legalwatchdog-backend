"""OpenAPI response documentation for Campaign CRUD endpoints."""

_SAMPLE_CAMPAIGN = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "organization_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "project_id": None,
    "name": "GDPR Compliance Monitor",
    "industry": "Technology",
    "domain_description": "Monitor GDPR regulatory changes across EU member states.",
    "target_depth": "COUNTRY",
    "monitor_backend": "CELERY_BEAT",
    "monitor_cadence": "0 9 * * 1",
    "sources_per_jurisdiction": 5,
    "max_jurisdictions": 15000,
    "status": "DRAFT",
    "taxonomy_json": None,
    "stats": None,
    "created_by": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "taxonomy_approved_by": None,
    "taxonomy_approved_at": None,
    "launched_by": None,
    "generation_model": None,
    "created_at": "2026-01-01T12:00:00Z",
    "updated_at": "2026-01-01T12:00:00Z",
    "execution_logs": [],
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns
# ---------------------------------------------------------------------------

create_campaign_responses = {
    201: {
        "description": "Campaign created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "DRAFT campaign created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Campaign created successfully.",
                            "data": _SAMPLE_CAMPAIGN,
                        },
                    }
                }
            }
        },
    },
    403: {
        "description": "Forbidden — superadmin required",
        "content": {
            "application/json": {
                "examples": {
                    "forbidden": {
                        "summary": "Non-superadmin",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You do not have permission to access this resource.",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error",
        "content": {
            "application/json": {
                "examples": {
                    "validation": {
                        "summary": "Missing required fields",
                        "value": {
                            "status": "failure",
                            "status_code": 422,
                            "message": "Validation failed",
                            "error_code": "VALIDATION_ERROR",
                            "errors": {"name": ["field required"]},
                        },
                    }
                }
            }
        },
    },
}

create_campaign_custom_errors = ["403", "422", "500"]
create_campaign_custom_success = {
    "status_code": 201,
    "description": "Campaign created in DRAFT status.",
}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns
# ---------------------------------------------------------------------------

list_campaigns_responses = {
    200: {
        "description": "Paginated list of campaigns",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "List retrieved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaigns retrieved successfully.",
                            "data": {
                                "campaigns": [_SAMPLE_CAMPAIGN],
                                "total": 1,
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
    403: {
        "description": "Forbidden",
        "content": {
            "application/json": {
                "examples": {
                    "forbidden": {
                        "summary": "Non-superadmin",
                        "value": {
                            "error_code": "PERMISSION_DENIED",
                            "message": "You do not have permission to access this resource.",
                            "status_code": 403,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

list_campaigns_custom_errors = ["403", "500"]
list_campaigns_custom_success = {
    "status_code": 200,
    "description": "Paginated campaigns list.",
}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}
# ---------------------------------------------------------------------------

get_campaign_responses = {
    200: {
        "description": "Campaign retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Campaign found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign retrieved successfully.",
                            "data": _SAMPLE_CAMPAIGN,
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_campaign_custom_errors = ["404", "403", "500"]
get_campaign_custom_success = {
    "status_code": 200,
    "description": "Campaign detail.",
}

# ---------------------------------------------------------------------------
# PATCH /api/v1/campaigns/{campaign_id}
# ---------------------------------------------------------------------------

update_campaign_responses = {
    200: {
        "description": "Campaign updated",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Campaign updated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign updated successfully.",
                            "data": _SAMPLE_CAMPAIGN,
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    423: {
        "description": "Campaign is locked (not in DRAFT)",
        "content": {
            "application/json": {
                "examples": {
                    "locked": {
                        "summary": "Campaign locked",
                        "value": {
                            "error_code": "RESOURCE_LOCKED",
                            "message": ("Campaign can only be updated while in DRAFT status."),
                            "status_code": 423,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

update_campaign_custom_errors = ["404", "423", "403", "422", "500"]
update_campaign_custom_success = {
    "status_code": 200,
    "description": "Campaign updated (DRAFT only).",
}

# ---------------------------------------------------------------------------
# DELETE /api/v1/campaigns/{campaign_id}
# ---------------------------------------------------------------------------

delete_campaign_responses = {
    200: {
        "description": "Campaign deleted",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Campaign deleted",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign deleted successfully.",
                            "data": {},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    423: {
        "description": "Campaign is locked (not in DRAFT)",
        "content": {
            "application/json": {
                "examples": {
                    "locked": {
                        "summary": "Campaign locked",
                        "value": {
                            "error_code": "RESOURCE_LOCKED",
                            "message": ("Campaign can only be deleted while in DRAFT status."),
                            "status_code": 423,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

delete_campaign_custom_errors = ["404", "423", "403", "500"]
delete_campaign_custom_success = {
    "status_code": 200,
    "description": "Campaign deleted (DRAFT only).",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/generate-taxonomy
# ---------------------------------------------------------------------------

generate_taxonomy_responses = {
    200: {
        "description": "Taxonomy generation completed",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Taxonomy generated",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Taxonomy generation completed.",
                            "data": {
                                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "status": "TAXONOMY_READY",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    423: {
        "description": "Campaign is locked (not in DRAFT)",
        "content": {
            "application/json": {
                "examples": {
                    "locked": {
                        "summary": "Campaign not in DRAFT status",
                        "value": {
                            "error_code": "RESOURCE_LOCKED",
                            "message": (
                                "Taxonomy can only be generated for campaigns in DRAFT status."
                            ),
                            "status_code": 423,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

generate_taxonomy_custom_errors = ["404", "423", "403", "500"]
generate_taxonomy_custom_success = {
    "status_code": 200,
    "description": "Taxonomy generated and geo-validated.",
}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}/taxonomy
# ---------------------------------------------------------------------------

get_taxonomy_responses = {
    200: {
        "description": "Taxonomy tree with warnings and preview stats",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Taxonomy retrieved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Taxonomy retrieved successfully.",
                            "data": {
                                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "status": "TAXONOMY_READY",
                                "taxonomy": [],
                                "warnings": [],
                                "preview_stats": {
                                    "total_nodes": 0,
                                    "countries": 0,
                                    "states": 0,
                                    "cities": 0,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_taxonomy_custom_errors = ["404", "403", "500"]
get_taxonomy_custom_success = {
    "status_code": 200,
    "description": "Taxonomy detail with preview stats.",
}

# ---------------------------------------------------------------------------
# PATCH /api/v1/campaigns/{campaign_id}/taxonomy
# ---------------------------------------------------------------------------

edit_taxonomy_responses = {
    200: {
        "description": "Taxonomy updated and re-validated",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Taxonomy edited",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Taxonomy updated and re-validated.",
                            "data": {
                                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "status": "TAXONOMY_READY",
                                "taxonomy": [],
                                "warnings": [],
                                "preview_stats": {
                                    "total_nodes": 0,
                                    "countries": 0,
                                    "states": 0,
                                    "cities": 0,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    423: {
        "description": "Campaign is locked (not in TAXONOMY_READY)",
        "content": {
            "application/json": {
                "examples": {
                    "locked": {
                        "summary": "Campaign not in TAXONOMY_READY status",
                        "value": {
                            "error_code": "RESOURCE_LOCKED",
                            "message": (
                                "Taxonomy can only be edited while in TAXONOMY_READY status."
                            ),
                            "status_code": 423,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

edit_taxonomy_custom_errors = ["404", "423", "403", "422", "500"]
edit_taxonomy_custom_success = {
    "status_code": 200,
    "description": "Taxonomy updated and re-validated (TAXONOMY_READY only).",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/approve-taxonomy
# ---------------------------------------------------------------------------

approve_taxonomy_responses = {
    200: {
        "description": "Taxonomy approved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Taxonomy approved",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Taxonomy approved successfully.",
                            "data": {
                                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "taxonomy_approved_by": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                                "taxonomy_approved_at": "2026-03-05T12:00:00Z",
                                "status": "TAXONOMY_READY",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    423: {
        "description": "Campaign is locked (not in TAXONOMY_READY)",
        "content": {
            "application/json": {
                "examples": {
                    "locked": {
                        "summary": "Campaign not in TAXONOMY_READY status",
                        "value": {
                            "error_code": "RESOURCE_LOCKED",
                            "message": (
                                "Taxonomy can only be approved while in TAXONOMY_READY status."
                            ),
                            "status_code": 423,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

approve_taxonomy_custom_errors = ["404", "423", "403", "500"]
approve_taxonomy_custom_success = {
    "status_code": 200,
    "description": "Taxonomy approved with audit fields recorded.",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/launch
# ---------------------------------------------------------------------------

launch_campaign_responses = {
    202: {
        "description": "Pipeline launched",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Pipeline launched",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Campaign pipeline launched.",
                            "data": {
                                "backend": "celery",
                                "task_id": "89b5d27b-e982-45e3-9990-2e3bfb6b3e77",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        }
                    }
                }
            }
        },
    },
    422: {
        "description": "Pipeline already running",
        "content": {
            "application/json": {
                "examples": {
                    "already_running": {
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Campaign pipeline is already running.",
                            "status_code": 422,
                            "errors": {},
                        }
                    }
                }
            }
        },
    },
}

launch_campaign_custom_errors = ["404", "500"]
launch_campaign_custom_success = {"status_code": 202, "description": "Campaign pipeline launched."}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}/status
# ---------------------------------------------------------------------------

campaign_status_responses = {
    200: {
        "description": "Campaign status retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Status returned",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign status retrieved.",
                            "data": {
                                "status": "HYDRATING",
                                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "taxonomy_task_id": "8f9f648f-77dc-4f18-8d80-2b8636b1f6ef",
                                "run_id": "9f53d9ab-e5f2-4bc8-a5a0-cd6ef57c4bc2",
                                "health": "DEGRADED",
                                "scrape_summary": {
                                    "total_jobs": 88,
                                    "completed_jobs": 68,
                                    "failed_jobs": 20,
                                    "active_jobs": 0,
                                },
                                "content_pipeline_status": "NOT_STARTED",
                                "content_summary": {
                                    "total_jurisdictions": 215,
                                    "jurisdictions_with_state": 46,
                                    "blog_count": 0,
                                    "missing_blog_count": 46,
                                    "last_run_mode": "",
                                    "last_run_generated": 0,
                                    "last_run_skipped": 0,
                                    "last_run_failed": 0,
                                    "last_run_missing_state": 0,
                                    "eligible_jurisdictions": 46,
                                    "content_pipeline_status": "NOT_STARTED",
                                    "last_run_id": "",
                                    "last_error_summary": "",
                                },
                                "failure": None,
                            },
                        },
                    }
                }
            }
        },
    },
}

campaign_status_custom_errors = ["404", "500"]
campaign_status_custom_success = {"status_code": 200, "description": "Campaign status."}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/content/run
# ---------------------------------------------------------------------------

run_campaign_content_responses = {
    202: {
        "description": "Campaign content pipeline queued",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Campaign content queued",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Campaign content pipeline queued.",
                            "data": {
                                "status": "queued",
                                "task_id": "fd4d4be7-5351-4ec7-8d5e-b3280bba7f94",
                                "run_id": "f1fef7ac-e960-4452-8b84-8d056b61db74",
                                "mode": "run",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {"description": "Campaign not found"},
}

run_campaign_content_custom_errors = ["404", "500"]
run_campaign_content_custom_success = {
    "status_code": 202,
    "description": "Campaign content pipeline queued.",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/content/retry-failed
# ---------------------------------------------------------------------------

retry_failed_campaign_content_responses = {
    202: {
        "description": "Failed campaign content queued for retry",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Retry failed content",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Failed campaign content jobs queued for retry.",
                            "data": {
                                "status": "queued",
                                "task_id": "31dcb4fb-8594-4ef3-b81f-4a4f3f023755",
                                "run_id": "ce0f76ee-86b8-4c27-a299-401aa8bffac8",
                                "mode": "retry_failed",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {"description": "Campaign not found"},
}

retry_failed_campaign_content_custom_errors = ["404", "500"]
retry_failed_campaign_content_custom_success = {
    "status_code": 202,
    "description": "Retry failed campaign content generation.",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/content/backfill-missing
# ---------------------------------------------------------------------------

backfill_campaign_content_responses = {
    202: {
        "description": "Missing campaign blogs queued for generation",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Backfill missing blogs",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Missing campaign blog generation queued.",
                            "data": {
                                "status": "queued",
                                "task_id": "c69d1127-788d-4e07-a7bd-c6badbef65dc",
                                "run_id": "219ad6d2-c405-4aa1-a20b-e476f58452b6",
                                "mode": "backfill_missing",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {"description": "Campaign not found"},
}

backfill_campaign_content_custom_errors = ["404", "500"]
backfill_campaign_content_custom_success = {
    "status_code": 202,
    "description": "Backfill missing campaign blogs.",
}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/pause
# ---------------------------------------------------------------------------

pause_campaign_responses = {
    200: {
        "description": "Campaign paused",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign paused.",
                            "data": {},
                        }
                    }
                }
            }
        },
    },
}

pause_campaign_custom_errors = ["404", "500"]
pause_campaign_custom_success = {"status_code": 200, "description": "Campaign paused."}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/resume
# ---------------------------------------------------------------------------

resume_campaign_responses = {
    200: {
        "description": "Campaign resumed",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign resumed.",
                            "data": {},
                        }
                    }
                }
            }
        },
    },
}

resume_campaign_custom_errors = ["404", "500"]
resume_campaign_custom_success = {"status_code": 200, "description": "Campaign pipeline resumed."}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/cancel
# ---------------------------------------------------------------------------

cancel_campaign_responses = {
    200: {
        "description": "Campaign cancelled",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign cancelled.",
                            "data": {},
                        }
                    }
                }
            }
        },
    },
}

cancel_campaign_custom_errors = ["404", "500"]
cancel_campaign_custom_success = {"status_code": 200, "description": "Campaign pipeline cancelled."}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}/progress-stream
# ---------------------------------------------------------------------------

progress_stream_responses = {
    200: {
        "description": "Server-Sent Events (SSE) stream of campaign progress",
        "content": {
            "text/event-stream": {
                "example": (
                    'data: {"phase": "HYDRATING", "completed": 5, "total": 10, '
                    '"pct": 50.0, "ts": "2026-03-09T22:00:00Z"}\n\n'
                )
            }
        },
    },
    404: {
        "description": "Campaign not found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Campaign not found.",
                            "status_code": 404,
                            "errors": {},
                        }
                    }
                }
            }
        },
    },
}

progress_stream_custom_errors = ["404"]
progress_stream_custom_success = {
    "status_code": 200,
    "description": "Campaign progress SSE stream.",
}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}/blogs
# ---------------------------------------------------------------------------

list_campaign_blogs_responses = {
    200: {
        "description": "Campaign blog posts retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Blogs returned",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign blog posts retrieved successfully.",
                            "data": [],
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Campaign not found",
    },
}

list_campaign_blogs_custom_errors = ["404", "500"]
list_campaign_blogs_custom_success = {"status_code": 200, "description": "Campaign blog posts."}

# ---------------------------------------------------------------------------
# POST /api/v1/campaigns/{campaign_id}/blogs/publish
# ---------------------------------------------------------------------------

publish_campaign_blogs_responses = {
    200: {
        "description": "Campaign blog batch publish completed",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Blogs batch published",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Campaign blog batch publish completed.",
                            "data": {
                                "campaign_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "action": "published",
                                "requested_count": 2,
                                "matched_count": 2,
                                "processed_count": 2,
                                "failed_count": 0,
                                "items": [
                                    {
                                        "id": "19585272-019e-46fd-9cf8-f9807d57d95c",
                                        "jurisdiction_id": "63c73e99-a0db-4340-bf06-b7b9917627be",
                                        "title": "UAE Labor Law Compliance Guide",
                                        "slug": "technology-guide-united-arab-emirates",
                                        "is_published": True,
                                        "public_url": "https://legalwatch.dog/resources/project/uae/technology-guide-united-arab-emirates/",
                                        "published_at": "2026-04-25T22:15:00Z",
                                        "status": "success",
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
        "description": "Campaign not found",
    },
    422: {
        "description": "Validation error",
    },
}

publish_campaign_blogs_custom_errors = ["404", "422", "500"]
publish_campaign_blogs_custom_success = {
    "status_code": 200,
    "description": "Campaign blogs batch publish/unpublish completed.",
}

# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{campaign_id}/blogs/{blog_id}/preview
# ---------------------------------------------------------------------------

preview_campaign_blog_responses = {
    200: {
        "description": "Campaign blog preview HTML",
        "content": {
            "text/html": {
                "example": (
                    "<!DOCTYPE html><html><head><title>Preview</title></head>"
                    "<body>...</body></html>"
                )
            }
        },
    },
    404: {
        "description": "Campaign or blog post not found",
    },
}

preview_campaign_blog_custom_errors = ["404", "500"]
preview_campaign_blog_custom_success = {
    "status_code": 200,
    "description": "Internal HTML preview for a campaign blog.",
}
