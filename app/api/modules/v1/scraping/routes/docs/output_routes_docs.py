# Output Source Revision Docs
download_revision_markdown_responses = {
    200: {
        "description": "Revision Markdown Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Revision markdown payload",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Revision markdown retrieved",
                            "data": {
                                "content": "# Title\n\nContent...",
                                "filename": "jurisdiction_source_20250101_120000.md",
                                "content_type": "text/markdown; charset=utf-8",
                                "metadata": {
                                    "revision_id": "987e6543-e21c-34d5-b678-556655440000",
                                    "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                    "source_name": "Supreme Court Opinions",
                                    "jurisdiction": "US",
                                    "url": "https://example.gov/doc.html",
                                    "scraped_at": "2025-11-25T10:30:00Z",
                                    "content_hash": "abc123def456",
                                    "was_change_detected": True,
                                    "confidence_score": 0.95,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Revision or Content Missing",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Revision not found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Data revision not found",
                            "error_code": "NOT_FOUND",
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
                            "message": "Revision retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while \
                                fetching the revision. Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

download_revision_markdown_custom_errors = ["404", "500"]
download_revision_markdown_custom_success = {
    "status_code": 200,
    "description": "Revision markdown retrieved successfully",
}


# Download latest markdown for a source
download_latest_markdown_responses = {
    200: {
        "description": "Latest Revision Markdown Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Latest revision markdown payload",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Latest revision markdown retrieved",
                            "data": {
                                "content": "# Title\n\nContent...",
                                "filename": "jurisdiction_source_20250101_120000.md",
                                "content_type": "text/markdown; charset=utf-8",
                                "metadata": {
                                    "revision_id": "987e6543-e21c-34d5-b678-556655440000",
                                    "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                    "source_name": "Supreme Court Opinions",
                                    "jurisdiction": "US",
                                    "url": "https://example.gov/doc.html",
                                    "scraped_at": "2025-11-25T10:30:00Z",
                                    "content_hash": "abc123def456",
                                    "was_change_detected": True,
                                    "confidence_score": 0.95,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Revisions for Source",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No revisions",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "No revisions found for source",
                            "error_code": "NOT_FOUND",
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
                            "message": "Latest revision retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while fetching \
                                the latest revision. Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

download_latest_markdown_custom_errors = ["404", "500"]
download_latest_markdown_custom_success = {
    "status_code": 200,
    "description": "Latest revision markdown retrieved successfully",
}


# View revision for display (structured JSON)
view_revision_responses = {
    200: {
        "description": "Revision Retrieved for Display",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Revision for UI display",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Revision retrieved for display",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "content": "# Title\n\nContent...",
                                "sections": [
                                    {
                                        "title": "Introduction",
                                        "content": "...",
                                        "level": 1,
                                        "id": "introduction",
                                    }
                                ],
                                "metadata": {
                                    "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                    "source_name": "Supreme Court Opinions",
                                },
                                "filename": "jurisdiction_source_20250101_120000.md",
                                "preview": "First sentences...",
                                "word_count": 123,
                                "character_count": 789,
                                "format": "markdown",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - Revision Missing",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Revision not found",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "Data revision not found",
                            "error_code": "NOT_FOUND",
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
                            "message": "Revision display retrieval failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while preparing \
                                the revision for display. Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

view_revision_custom_errors = ["404", "500"]
view_revision_custom_success = {
    "status_code": 200,
    "description": "Revision returned for display",
}


# View latest revision for display
view_latest_revision_responses = {
    200: {
        "description": "Latest Revision Retrieved for Display",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Latest revision for UI display",
                        "value": {
                            "status": "success",
                            "status_code": 200,
                            "message": "Latest revision retrieved for display",
                            "data": {
                                "id": "987e6543-e21c-34d5-b678-556655440000",
                                "content": "# Title\n\nContent...",
                                "sections": [
                                    {
                                        "title": "Introduction",
                                        "content": "...",
                                        "level": 1,
                                        "id": "introduction",
                                    }
                                ],
                                "metadata": {
                                    "source_id": "123e4567-e89b-12d3-a456-426614174000",
                                    "source_name": "Supreme Court Opinions",
                                },
                                "filename": "jurisdiction_source_20250101_120000.md",
                                "preview": "First sentences...",
                                "word_count": 123,
                                "character_count": 789,
                                "format": "markdown",
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Not Found - No Revisions for Source",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No revisions",
                        "value": {
                            "status": "error",
                            "status_code": 404,
                            "message": "No revisions found for source",
                            "error_code": "NOT_FOUND",
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
                            "message": "Latest revision display retrieval \
                                failed. Please try again later.",
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "status": "error",
                            "status_code": 500,
                            "message": "A processing error occurred while preparing the latest \
                                revision for display. Please try again later.",
                            "error_code": "PROCESSING_ERROR",
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

view_latest_revision_custom_errors = ["404", "500"]
view_latest_revision_custom_success = {
    "status_code": 200,
    "description": "Latest revision returned for display",
}
