"""OpenAPI documentation for jurisdiction blog post endpoints.

Defines response examples and custom markers for the OpenAPI specification.
Follows the project's standard documentation pattern for route responses.
"""

# GET /{jurisdiction_id}/blog
get_blog_responses = {
    200: {
        "description": "Blog Post Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Published Blog Post",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog post retrieved successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "title": "California EOR Compliance Guide 2026",
                                "slug": "eor-guide-california",
                                "content": (
                                    "# California EOR Compliance Guide\\n\\n## Overview\\n..."
                                ),
                                "meta_description": (
                                    "Comprehensive guide to employment regulations in California "
                                    "for EOR providers, updated 2026."
                                ),
                                "keywords": [
                                    "California",
                                    "EOR",
                                    "employment law",
                                    "compliance",
                                    "minimum wage",
                                ],
                                "is_published": True,
                                "version": 3,
                                "content_hash": "abc123def456...",
                                "created_at": "2026-01-01T12:00:00Z",
                                "updated_at": "2026-02-15T10:30:00Z",
                                "published_at": "2026-02-15T11:00:00Z",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Blog Post Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Blog Post Exists",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Blog post not found for this jurisdiction",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_blog_custom_errors = ["404", "500"]
get_blog_custom_success = {
    "status_code": 200,
    "description": "Blog post retrieved successfully.",
}

# GET /blog/posts
get_all_blog_posts_responses = {
    200: {
        "description": "Blog Posts Retrieved Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Search Results",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog posts retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "title": "California EOR Compliance Guide 2026",
                                    }
                                ],
                                "pagination": {
                                    "total": 1,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 1,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Invalid Query Parameters",
        "content": {
            "application/json": {
                "examples": {
                    "bad_request": {
                        "summary": "Invalid Query Terms or Pagination",
                        "value": {
                            "error_code": "BAD_REQUEST",
                            "message": "Invalid query terms or pagination parameters provided",
                            "status_code": 400,
                            "errors": {
                                "query_terms": "must be a string or list of strings",
                                "page": "must be an integer >= 1",
                            },
                        },
                    }
                }
            }
        },
    },
    500: {
        "description": "Processing Error",
        "content": {
            "application/json": {
                "examples": {
                    "processing_error": {
                        "summary": "Internal Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "Error fetching blog posts",
                            "status_code": 500,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_all_blog_posts_custom_errors = ["400", "500"]
get_all_blog_posts_custom_success = {
    "status_code": 200,
    "description": "Blog posts retrieved successfully.",
}


# POST /{jurisdiction_id}/blog/generate
generate_blog_responses = {
    202: {
        "description": "Blog Generation Triggered",
        "content": {
            "application/json": {
                "examples": {
                    "accepted": {
                        "summary": "Generation Started",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 202,
                            "message": "Blog generation triggered. Check back in a few moments.",
                            "data": {
                                "job_id": "abc12345-e89b-12d3-a456-426614174002",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "status": "PENDING",
                                "message": "Blog generation job queued successfully",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Invalid Jurisdiction",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
    409: {
        "description": "Generation Already In Progress",
        "content": {
            "application/json": {
                "examples": {
                    "conflict": {
                        "summary": "Duplicate Generation Request",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": (
                                "A blog generation is already in progress for this jurisdiction. "
                                "Please wait for it to complete."
                            ),
                            "status_code": 409,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

generate_blog_custom_errors = ["404", "409", "500"]
generate_blog_custom_success = {
    "status_code": 202,
    "description": "Blog generation triggered successfully.",
}


# GET /{jurisdiction_id}/blog/generations/{job_id}
get_generation_status_responses = {
    200: {
        "description": "Generation Job Status Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "completed": {
                        "summary": "Completed Job",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog generation job status retrieved successfully",
                            "data": {
                                "id": "abc12345-e89b-12d3-a456-426614174002",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "status": "COMPLETED",
                                "error_message": None,
                                "created_at": "2026-02-17T10:00:00Z",
                                "started_at": "2026-02-17T10:00:01Z",
                                "completed_at": "2026-02-17T10:00:15Z",
                                "triggered_by": None,
                            },
                        },
                    },
                    "in_progress": {
                        "summary": "In Progress Job",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog generation job status retrieved successfully",
                            "data": {
                                "id": "abc12345-e89b-12d3-a456-426614174002",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "status": "IN_PROGRESS",
                                "error_message": None,
                                "created_at": "2026-02-17T10:00:00Z",
                                "started_at": "2026-02-17T10:00:01Z",
                                "completed_at": None,
                                "triggered_by": None,
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Generation Job Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Job Not Found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Blog generation job not found",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_generation_status_custom_errors = ["404", "500"]
get_generation_status_custom_success = {
    "status_code": 200,
    "description": "Blog generation job status retrieved successfully.",
}


# GET /{jurisdiction_id}/blog/generations
list_generations_responses = {
    200: {
        "description": "Generation Jobs Listed Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Jobs List",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog generation jobs retrieved successfully",
                            "data": {
                                "items": [
                                    {
                                        "id": "abc12345-e89b-12d3-a456-426614174002",
                                        "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                        "status": "COMPLETED",
                                        "error_message": None,
                                        "created_at": "2026-02-17T10:00:00Z",
                                        "started_at": "2026-02-17T10:00:01Z",
                                        "completed_at": "2026-02-17T10:00:15Z",
                                        "triggered_by": None,
                                    }
                                ],
                                "pagination": {
                                    "total": 1,
                                    "page": 1,
                                    "limit": 10,
                                    "total_pages": 1,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Jurisdiction Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Invalid Jurisdiction",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Jurisdiction not found in this organization",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

list_generations_custom_errors = ["404", "500"]
list_generations_custom_success = {
    "status_code": 200,
    "description": "Blog generation jobs retrieved successfully.",
}


# PATCH /{jurisdiction_id}/blog/publish
publish_blog_responses = {
    200: {
        "description": "Blog Post Published Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "published": {
                        "summary": "Post Published",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog post published successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "title": "California EOR Compliance Guide 2026",
                                "slug": "eor-guide-california",
                                "is_published": True,
                                "public_url": "https://staging.legalwatch.dog/resources/eor-guide-california/",
                                "published_at": "2026-02-15T14:30:00Z",
                            },
                        },
                    },
                    "unpublished": {
                        "summary": "Post Unpublished",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Blog post unpublished successfully",
                            "data": {
                                "id": "123e4567-e89b-12d3-a456-426614174000",
                                "jurisdiction_id": "789e4567-e89b-12d3-a456-426614174001",
                                "title": "California EOR Compliance Guide 2026",
                                "slug": "eor-guide-california",
                                "is_published": False,
                                "public_url": None,
                                "published_at": None,
                            },
                        },
                    },
                }
            }
        },
    },
    404: {
        "description": "Blog Post Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No Blog Post to Publish",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Blog post not found for this jurisdiction",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

publish_blog_custom_errors = ["404", "500"]
publish_blog_custom_success = {
    "status_code": 200,
    "description": "Blog post publish status updated successfully.",
}
