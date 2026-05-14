"""OpenAPI docs for campaign remediation routes."""

failed_discovery_nodes_responses = {
    200: {
        "description": "Failed discovery jurisdictions retrieved successfully",
    },
    404: {
        "description": "Campaign not found",
    },
}
failed_discovery_nodes_custom_errors = ["404", "500"]
failed_discovery_nodes_custom_success = {
    "status_code": 200,
    "description": "Failed discovery jurisdictions retrieved successfully.",
}

manual_sources_responses = {
    200: {
        "description": "Manual sources created and jurisdiction dispatched successfully",
    },
    400: {
        "description": "Manual sources payload was invalid",
    },
    404: {
        "description": "Jurisdiction not found",
    },
}
manual_sources_custom_errors = ["400", "404", "500"]
manual_sources_custom_success = {
    "status_code": 200,
    "description": "Manual sources created and jurisdiction dispatched successfully.",
}

retry_discovery_responses = {
    200: {
        "description": "Jurisdiction discovery retry processed successfully",
    },
    400: {
        "description": "Jurisdiction cannot be retried",
    },
    404: {
        "description": "Jurisdiction not found",
    },
}
retry_discovery_custom_errors = ["400", "404", "500"]
retry_discovery_custom_success = {
    "status_code": 200,
    "description": "Jurisdiction discovery retry processed successfully.",
}
