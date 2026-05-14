"""OpenAPI documentation schemas for Source Discovery API endpoints.

This module defines response examples and HTTP status code documentation
for the Parallel.ai-powered source suggestion and acceptance endpoints.
"""

suggest_sources_request_schema = {
    "type": "object",
    "properties": {
        "search_query": {
            "type": "string",
            "description": "Natural language search query describing what sources you need. "
            "Parallel.ai's semantic search understands intent and context.",
            "example": "Central Bank of Nigeria cryptocurrency licensing requirements 2024",
            "minLength": 10,
            "maxLength": 500,
        },
        "jurisdiction_name": {
            "type": "string",
            "nullable": True,
            "description": "Optional jurisdiction name to scope the search. "
            "If provided, will be added to the search context.",
            "example": "Central Bank of Nigeria",
            "maxLength": 200,
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of sources to return. Default is 10.",
            "example": 10,
            "minimum": 1,
            "maximum": 50,
            "default": 10,
        },
        "processor": {
            "type": "string",
            "description": "Search processor to use: 'base' for speed (<5s) or 'pro' for "
            "higher quality (15-60s). Use 'base' for most cases.",
            "example": "base",
            "enum": ["base", "pro"],
            "default": "base",
        },
    },
    "required": ["search_query"],
}

suggest_sources_responses = {
    200: {
        "description": "Sources Suggested Successfully via Parallel.ai",
        "content": {
            "application/json": {
                "examples": {
                    "success_with_official_sources": {
                        "summary": "Official Government Sources Found",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Found 8 high-quality sources",
                            "data": {
                                "session_id": "sess_01H2ABCDEF1234567890",
                                "sources": [
                                    {
                                        "title": "CBN Crypto Guidelines",
                                        "url": "https://www.cbn.gov.ng/out/2024/ccd/crypto-circular-01.pdf",
                                        "snippet": (
                                            "CBN issues crypto guidelines. "
                                            "Operators must get license. "
                                            "Minimum capital NGN 50M. "
                                            "Submit quarterly reports and maintain "
                                            "cybersecurity..."
                                        ),
                                        "confidence_reason": (
                                            "High-quality source by Parallel.ai ranking. "
                                            "Official source, specific page, recent dates, "
                                            "rich content (1247 chars), 3 excerpts."
                                        ),
                                        "is_official": True,
                                    },
                                    {
                                        "title": "CBN Crypto Licensing Framework",
                                        "url": "https://www.cbn.gov.ng/supervisionandregulation/crypto-licensing",
                                        "snippet": (
                                            "Licensing framework for crypto operators requires "
                                            "min capital NGN 50M, tech capability, KYC/AML, "
                                            "qualified management. Application 90-120 days. "
                                            "Annual fees..."
                                        ),
                                        "confidence_reason": (
                                            "High-quality source by Parallel.ai ranking. "
                                            "Official source, specific page, "
                                            "rich content (892 chars), 2 excerpts."
                                        ),
                                        "is_official": True,
                                    },
                                ],
                                "count": 2,
                                "processor_used": "base",
                                "guidance": {
                                    "powered_by": "Parallel.ai - AI-native web search",
                                    "next_steps": [
                                        "Review the sources and their extended excerpts",
                                        "Check confidence_reason for each source",
                                        "Accept relevant sources to start monitoring",
                                    ],
                                    "quality_indicators": [
                                        "is_official indicates government/regulatory sources",
                                        "Extended excerpts (500-2000 chars) for quality assessment",
                                        "All sources validated as reachable",
                                        "AI-native ranking prioritizes content relevance",
                                    ],
                                },
                            },
                        },
                    },
                    "success_with_news_sources": {
                        "summary": "Mixed Official and News Sources",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Found 10 high-quality sources",
                            "data": {
                                "session_id": "sess_01H2ABCDEF1234567890",
                                "sources": [
                                    {
                                        "title": "SEC Bitcoin ETF Approval",
                                        "url": "https://www.sec.gov/news/press-release/2024-10",
                                        "snippet": (
                                            "SEC approved spot Bitcoin ETFs. "
                                            "Decision follows review of submissions on "
                                            "investor protection, manipulation, custody. "
                                            "Funds must adhere to surveillance agreements..."
                                        ),
                                        "confidence_reason": (
                                            "High-quality source by Parallel.ai ranking. "
                                            "Official source, specific page, recent dates, "
                                            "rich content (1104 chars), 2 excerpts."
                                        ),
                                        "is_official": True,
                                    },
                                    {
                                        "title": "SEC Bitcoin ETF Impact Analysis",
                                        "url": "https://www.reuters.com/markets/us/sec-bitcoin-etf-approval-2024",
                                        "snippet": (
                                            "SEC Bitcoin ETF approval pivotal for crypto adoption. "
                                            "Experts suggest billions in institutional investment. "
                                            "Considerations: structure, fees, price impact..."
                                        ),
                                        "confidence_reason": (
                                            "High-quality source by Parallel.ai ranking. "
                                            "Specific page, recent dates, "
                                            "rich content (967 chars), 2 excerpts."
                                        ),
                                        "is_official": False,
                                    },
                                ],
                                "count": 2,
                                "processor_used": "base",
                                "guidance": {
                                    "powered_by": "Parallel.ai - AI-native web search",
                                    "next_steps": [
                                        "Review the sources and their extended excerpts",
                                        "Check confidence_reason for each source",
                                        "Accept relevant sources to start monitoring",
                                    ],
                                    "quality_indicators": [
                                        "is_official indicates government/regulatory sources",
                                        "Extended excerpts (500-2000 chars) for quality assessment",
                                        "All sources validated as reachable",
                                        "AI-native ranking prioritizes content relevance",
                                    ],
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "configuration_error": {
                        "summary": "Configuration Error - Missing API Key",
                        "value": {
                            "error_code": "CONFIGURATION_ERROR",
                            "message": "Configuration Error",
                            "status_code": 500,
                            "errors": {"details": "PARALLEL_API_KEY is not set in configuration."},
                        },
                    },
                    "search_api_failed": {
                        "summary": "Parallel.ai Search API Failed",
                        "value": {
                            "error_code": "SEARCH_API_FAILED",
                            "message": "Parallel.ai search failed",
                            "status_code": 500,
                            "errors": {
                                "details": (
                                    "Search API failed: Connection timeout to api.parallel.ai"
                                ),
                            },
                        },
                    },
                },
            },
        },
    },
}

suggest_sources_custom_errors = ["500"]
suggest_sources_custom_success = {
    "status_code": 200,
    "description": "High-quality sources discovered via Parallel.ai's AI-native search.",
}


accept_sources_responses = {
    201: {
        "description": "Sources accepted and created successfully",
        "content": {
            "application/json": {
                "examples": {
                    "created_sources_success": {
                        "summary": "Accepted suggestions created",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Sources activated for monitoring",
                            "data": {
                                "sources": [
                                    {
                                        "id": "src_01H2ABCDEF1234567890",
                                        "title": "CBN Crypto Guidelines",
                                        "url": "https://www.cbn.gov.ng/out/2024/ccd/crypto-circular-01.pdf",
                                        "monitoring": {"frequency": "daily"},
                                    }
                                ],
                                "count": 1,
                                "next_steps": [
                                    "Sources will be scraped according to the specified frequency",
                                    "Monitor scraping results in your dashboard",
                                ],
                                "powered_by": "Parallel.ai source discovery",
                            },
                        },
                    }
                }
            }
        },
    },
    400: {
        "description": "Bad Request - duplicate source or invalid suggestion data",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_source_error": {
                        "summary": "Duplicate source detected",
                        "value": {
                            "error_code": "DUPLICATE_SOURCE",
                            "message": "One or more suggested URLs already exist in your account",
                            "status_code": 400,
                            "errors": {
                                "details": "https://example.com/duplicate-url detected in payload"
                            },
                        },
                    },
                    "invalid_suggestion_data": {
                        "summary": "Invalid suggestion payload",
                        "value": {
                            "error_code": "INVALID_SUGGESTION_DATA",
                            "message": "Suggested source payload is invalid",
                            "status_code": 400,
                            "errors": {"details": "Missing required fields for suggested source"},
                        },
                    },
                }
            }
        },
    },
    422: {
        "description": "Request validation failed",
        "content": {
            "application/json": {
                "examples": {
                    "validation_error": {
                        "summary": "Payload validation error",
                        "value": {
                            "error_code": "REQUEST_VALIDATION_ERROR",
                            "message": "Validation failed for request",
                            "status_code": 422,
                            "errors": {"body": "'sources' must be a non-empty array"},
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
                    "processing_error": {
                        "summary": "Processing Error",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occurred while accepting suggestions",
                            "status_code": 500,
                            "errors": {
                                "details": "Unexpected database error or third-party failure"
                            },
                        },
                    }
                }
            }
        },
    },
}

accept_sources_custom_errors = ["400", "422", "500"]
accept_sources_custom_success = {
    "status_code": 201,
    "description": "Accepted suggestions created and scheduled for scraping.",
}


retrieve_cached_sources_responses = {
    200: {
        "description": "Cached suggested sources retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "cached_session_success": {
                        "summary": "Cached session returned",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Previously generated sources retrieved",
                            "data": {"sources": [], "expires_in": 3600},
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Session expired or not found",
        "content": {
            "application/json": {
                "examples": {
                    "results_expired": {
                        "summary": "Cached search session expired",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Results expired",
                            "status_code": 404,
                            "errors": {"details": "The requested session id is missing or expired"},
                        },
                    }
                }
            }
        },
    },
}

retrieve_cached_sources_custom_errors = ["404"]


accept_sources_responses = {
    201: {
        "description": "Suggested Sources Accepted Successfully",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "Sources Created from Parallel.ai Suggestions",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 201,
                            "message": "Sources activated for monitoring",
                            "data": {
                                "sources": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "name": ("CBN Crypto Guidelines"),
                                        "url": "https://www.cbn.gov.ng/out/2024/ccd/crypto-circular-01.pdf",
                                        "source_type": "web",
                                        "scrape_frequency": "DAILY",
                                        "is_active": True,
                                        "is_deleted": False,
                                        "has_auth": False,
                                        "created_at": "2025-12-12T10:30:00Z",
                                    },
                                    {
                                        "id": "223e4567-e89b-12d3-a456-426614174000",
                                        "jurisdiction_id": "550e8400-e29b-41d4-a716-446655440000",
                                        "name": ("CBN Crypto Licensing Framework"),
                                        "url": "https://www.cbn.gov.ng/supervisionandregulation/crypto-licensing",
                                        "source_type": "web",
                                        "scrape_frequency": "DAILY",
                                        "is_active": True,
                                        "is_deleted": False,
                                        "has_auth": False,
                                        "created_at": "2025-12-12T10:30:00Z",
                                    },
                                ],
                                "count": 2,
                                "next_steps": [
                                    "Sources will be scraped according to the specified frequency",
                                    "Monitor scraping results in your dashboard",
                                    "Adjust scraping_rules if needed based on actual content",
                                    "Review Parallel.ai excerpts for content structure hints",
                                ],
                                "powered_by": "Parallel.ai source discovery",
                            },
                        },
                    },
                },
            },
        },
    },
    400: {
        "description": "Bad Request - Duplicate URL or Invalid Data",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_url": {
                        "summary": "Duplicate Source URL",
                        "value": {
                            "error_code": "DUPLICATE_SOURCE",
                            "message": "Source URLs already exist",
                            "status_code": 400,
                            "errors": {
                                "duplicate_urls": [
                                    "https://www.cbn.gov.ng/out/2024/ccd/crypto-circular-01.pdf"
                                ]
                            },
                        },
                    },
                    "invalid_data": {
                        "summary": "Invalid Suggestion Data",
                        "value": {
                            "error_code": "INVALID_SUGGESTION_DATA",
                            "message": "Invalid suggestion data",
                            "status_code": 400,
                            "errors": {"details": "Invalid URL format or missing required fields"},
                        },
                    },
                },
            },
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
                            "error_code": "VALIDATION_ERROR",
                            "message": "Validation failed",
                            "status_code": 422,
                            "errors": {
                                "suggested_sources": ["ensure this value has at least 1 items"],
                                "jurisdiction_id": ["field required"],
                                "source_type": ["field required"],
                            },
                        },
                    },
                },
            },
        },
    },
    409: {
        "description": "Conflict - Duplicate Entry",
        "content": {
            "application/json": {
                "examples": {
                    "duplicate_entry": {
                        "summary": "Duplicate Entry - Conflict",
                        "value": {
                            "error_code": "DUPLICATE_ENTRY",
                            "message": "Source URLs already exist",
                            "status_code": 409,
                            "errors": {
                                "conflicting_sources": [
                                    "https://www.cbn.gov.ng/out/2024/ccd/crypto-circular-01.pdf"
                                ]
                            },
                            "resolution": [
                                "Remove or update conflicting sources before retrying",
                                "Use the provided URLs or IDs to identify duplicates",
                            ],
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
                    "internal_server_error": {
                        "summary": "Internal Server Error - Unexpected Failure",
                        "value": {
                            "error_code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred. Please try again later.",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                    "processing_error": {
                        "summary": "Processing Error - unexpected failure in service",
                        "value": {
                            "error_code": "PROCESSING_ERROR",
                            "message": "An unexpected error occured while accepting sources",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                },
            },
        },
    },
}

accept_sources_custom_errors = ["400", "422", "409", "500"]
accept_sources_custom_success = {
    "status_code": 201,
    "description": "Parallel.ai-suggested sources converted to active sources successfully.",
}
