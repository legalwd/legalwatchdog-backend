"""OpenAPI documentation for public Guides listing endpoints."""

# GET /guides/{industry}/
list_industry_responses = {
    200: {
        "description": "Industry Listing Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "EOR Industry Listing",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Industry listing retrieved successfully",
                            "data": {
                                "industry": "eor",
                                "industry_display_name": "EOR",
                                "total_jurisdictions": 150,
                                "last_updated": "2026-04-25T10:30:00Z",
                                "regions": [
                                    {
                                        "id": "123e4567-e89b-12d3-a456-426614174000",
                                        "name": "United States",
                                        "slug": "united-states",
                                        "jurisdiction_count": 52,
                                        "latest_update": "2026-04-25T10:30:00Z",
                                        "url": "https://legalwatch.dog/guides/eor/united-states/",
                                    }
                                ],
                                "pagination": {
                                    "page": 1,
                                    "per_page": 20,
                                    "total_pages": 3,
                                    "total_items": 45,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Industry Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "No published guides for this industry",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "No published guides found for industry: fintech",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

list_industry_custom_errors = ["404", "500"]
list_industry_custom_success = {
    "status_code": 200,
    "description": "Industry listing retrieved successfully.",
}

# GET /guides/{industry}/{region}/
list_region_responses = {
    200: {
        "description": "Region Listing Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "US Region Listing",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Region listing retrieved successfully",
                            "data": {
                                "industry": "eor",
                                "region_id": "123e4567-e89b-12d3-a456-426614174000",
                                "region_name": "United States",
                                "region_slug": "united-states",
                                "jurisdictions": [
                                    {
                                        "id": "789e4567-e89b-12d3-a456-426614174001",
                                        "name": "California",
                                        "slug": "california",
                                        "post_url": (
                                            "https://legalwatch.dog/guides/eor"
                                            "/united-states/california/"
                                        ),
                                        "summary": (
                                            "Comprehensive EOR compliance guide for "
                                            "California covering minimum wage, PTO, "
                                            "and termination rules."
                                        ),
                                        "updated_at": "2026-04-25T10:30:00Z",
                                        "key_topics": [
                                            "minimum wage",
                                            "PTO",
                                            "termination",
                                            "payroll",
                                        ],
                                    }
                                ],
                                "pagination": {
                                    "page": 1,
                                    "per_page": 20,
                                    "total_pages": 3,
                                    "total_items": 52,
                                },
                            },
                        },
                    }
                }
            }
        },
    },
    404: {
        "description": "Region Not Found",
        "content": {
            "application/json": {
                "examples": {
                    "not_found": {
                        "summary": "Region not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "Region 'invalid-region' not found for industry: eor",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

list_region_custom_errors = ["404", "500"]
list_region_custom_success = {
    "status_code": 200,
    "description": "Region listing retrieved successfully.",
}

# GET /guides/{industry}/{region}/{jurisdiction}
get_jurisdiction_detail_responses = {
    200: {
        "description": "Jurisdiction Detail Retrieved",
        "content": {
            "application/json": {
                "examples": {
                    "success": {
                        "summary": "California EOR Detail",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Jurisdiction detail retrieved successfully",
                            "data": {
                                "id": "789e4567-e89b-12d3-a456-426614174001",
                                "name": "California",
                                "slug": "california",
                                "industry": "eor",
                                "post_url": (
                                    "https://legalwatch.dog/guides/eor/united-states/california/"
                                ),
                                "breadcrumbs": [
                                    {
                                        "name": "United States",
                                        "url": ("https://legalwatch.dog/guides/eor/united-states/"),
                                    },
                                    {
                                        "name": "California",
                                        "url": (
                                            "https://legalwatch.dog/guides/eor"
                                            "/united-states/california/"
                                        ),
                                    },
                                ],
                                "title": "California EOR Compliance Guide 2026",
                                "meta_description": (
                                    "Comprehensive EOR compliance guide for California "
                                    "covering minimum wage, PTO, and termination rules."
                                ),
                                "keywords": [
                                    "California",
                                    "EOR",
                                    "employment law",
                                    "compliance",
                                ],
                                "published_at": "2026-04-01T12:00:00Z",
                                "updated_at": "2026-04-25T10:30:00Z",
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
                        "summary": "Jurisdiction not found",
                        "value": {
                            "error_code": "NOT_FOUND",
                            "message": "No published blog post for jurisdiction 'invalid'.",
                            "status_code": 404,
                            "errors": {},
                        },
                    }
                }
            }
        },
    },
}

get_jurisdiction_detail_custom_errors = ["404", "500"]
get_jurisdiction_detail_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction detail retrieved successfully.",
}
