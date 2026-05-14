"""Admin endpoints for Parallel.ai usage monitoring and analytics."""

from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.services.parallel_monitoring_service import (
    ParallelMonitoringService,
)
from app.api.utils.response_payloads import success_response

from .docs.parallel_monitoring_docs import (
    get_parallel_cost_breakdown_custom_errors,
    get_parallel_cost_breakdown_custom_success,
    get_parallel_cost_breakdown_responses,
    get_parallel_detailed_logs_custom_errors,
    get_parallel_detailed_logs_custom_success,
    get_parallel_detailed_logs_responses,
    get_parallel_usage_by_endpoint_custom_errors,
    get_parallel_usage_by_endpoint_custom_success,
    get_parallel_usage_by_endpoint_responses,
    get_parallel_usage_by_organization_custom_errors,
    get_parallel_usage_by_organization_custom_success,
    get_parallel_usage_by_organization_responses,
    get_parallel_usage_by_project_custom_errors,
    get_parallel_usage_by_project_custom_success,
    get_parallel_usage_by_project_responses,
    get_parallel_usage_by_user_custom_errors,
    get_parallel_usage_by_user_custom_success,
    get_parallel_usage_by_user_responses,
    get_parallel_usage_stats_custom_errors,
    get_parallel_usage_stats_custom_success,
    get_parallel_usage_stats_responses,
    get_recent_parallel_errors_custom_errors,
    get_recent_parallel_errors_custom_success,
    get_recent_parallel_errors_responses,
)

router = APIRouter(prefix="/parallel", tags=["Admin - Parallel.ai Monitoring"])


@router.get(
    "/usage/stats",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_usage_stats_responses,
)
async def get_parallel_usage_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get comprehensive Parallel.ai usage statistics.

    Aggregates extraction requests, success rates, costs, and performance metrics
    over the specified time period for admin dashboard visibility.

    Args:
        days: Number of days to analyze (1-365).
        db: Database session.

    Returns:
        Dict containing:
            - total_requests: Total extraction requests
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - success_rate: Percentage of successful extractions
            - total_cost: Total API costs in USD
            - avg_latency_ms: Average request latency
            - total_content_mb: Total extracted content size in MB
            - avg_content_kb: Average content size per request in KB

    """
    service = ParallelMonitoringService(db)
    stats = await service.get_usage_stats(days=days)

    return success_response(
        status_code=HTTP_200_OK,
        message="Parallel.ai usage statistics loaded successfully.",
        data=stats,
    )


get_parallel_usage_stats._custom_errors = get_parallel_usage_stats_custom_errors
get_parallel_usage_stats._custom_success = get_parallel_usage_stats_custom_success


@router.get(
    "/usage/by-endpoint",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_usage_by_endpoint_responses,
)
async def get_parallel_usage_by_endpoint(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get Parallel.ai usage breakdown by API endpoint.

    Shows which features are consuming the most Parallel.ai extractions,
    helping identify high-usage areas and optimize costs.

    Args:
        days: Number of days to analyze (1-365).
        db: Database session.

    Returns:
        Dict with endpoint_usage array containing:
            - endpoint_name: API endpoint name
            - request_count: Number of requests from this endpoint
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - total_cost: Total cost for this endpoint
            - avg_latency_ms: Average latency for this endpoint
    """
    service = ParallelMonitoringService(db)
    endpoint_usage = await service.get_usage_by_endpoint(days=days)

    return success_response(
        status_code=HTTP_200_OK,
        message="Endpoint breakdown for Parallel.ai usage loaded successfully.",
        data={"endpoint_usage": endpoint_usage},
    )


get_parallel_usage_by_endpoint._custom_errors = get_parallel_usage_by_endpoint_custom_errors
get_parallel_usage_by_endpoint._custom_success = get_parallel_usage_by_endpoint_custom_success


@router.get(
    "/usage/by-user",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_usage_by_user_responses,
)
async def get_parallel_usage_by_user(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of top users to return"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get Parallel.ai usage breakdown by user.

    Identifies power users and usage patterns for capacity planning
    and cost allocation across customers.

    Args:
        days: Number of days to analyze (1-365).
        limit: Number of top users to return (1-100).
        db: Database session.

    Returns:
        Dict with user_usage array containing:
            - user_id: User UUID
            - email: User email
            - request_count: Number of requests by this user
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - total_cost: Total cost for this user
            - avg_latency_ms: Average latency for this user
    """
    service = ParallelMonitoringService(db)
    user_usage = await service.get_usage_by_user(days=days, limit=limit)

    return success_response(
        status_code=HTTP_200_OK,
        message="Parallel.ai usage by user retrieved",
        data={"user_usage": user_usage},
    )


get_parallel_usage_by_user._custom_errors = get_parallel_usage_by_user_custom_errors
get_parallel_usage_by_user._custom_success = get_parallel_usage_by_user_custom_success


@router.get(
    "/cost/breakdown",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_cost_breakdown_responses,
)
async def get_parallel_cost_breakdown(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get daily Parallel.ai cost breakdown for trend analysis.

    Shows cost trends over time to identify usage spikes and
    support budgeting and capacity planning decisions.

    Args:
        days: Number of days to analyze (1-365).
        db: Database session.

    Returns:
        Dict with daily_costs array containing:
            - date: Date (YYYY-MM-DD)
            - request_count: Number of requests on this date
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - total_cost: Total cost for this date
    """
    service = ParallelMonitoringService(db)
    daily_costs = await service.get_cost_breakdown(days=days)

    return success_response(
        status_code=HTTP_200_OK,
        message="Parallel.ai cost breakdown retrieved",
        data={"daily_costs": daily_costs},
    )


get_parallel_cost_breakdown._custom_errors = get_parallel_cost_breakdown_custom_errors
get_parallel_cost_breakdown._custom_success = get_parallel_cost_breakdown_custom_success


@router.get(
    "/errors/recent",
    dependencies=[Depends(require_superadmin)],
    responses=get_recent_parallel_errors_responses,
)
async def get_recent_parallel_errors(
    limit: int = Query(default=50, ge=1, le=200, description="Number of errors to return"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get recent Parallel.ai extraction errors for troubleshooting.

    Shows failed extractions with error messages to help identify
    and resolve common extraction issues or API problems.

    Args:
        limit: Number of recent errors to return (1-200).
        db: Database session.

    Returns:
        Dict with recent_errors array containing:
            - id: Usage log ID
            - user_id: User who initiated the request
            - url_extracted: Target URL that failed
            - endpoint_name: Endpoint that triggered extraction
            - error_message: Error details
            - latency_ms: Time to failure
            - created_at: When the error occurred
    """
    service = ParallelMonitoringService(db)
    recent_errors = await service.get_recent_errors(limit=limit)

    return success_response(
        status_code=HTTP_200_OK,
        message="Recent Parallel.ai errors retrieved",
        data={"recent_errors": recent_errors},
    )


get_recent_parallel_errors._custom_errors = get_recent_parallel_errors_custom_errors
get_recent_parallel_errors._custom_success = get_recent_parallel_errors_custom_success


@router.get(
    "/usage/by-organization",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_usage_by_organization_responses,
)
async def get_parallel_usage_by_organization(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get detailed Parallel.ai usage breakdown by organization.

    Shows organization-level usage with unique user counts, total costs,
    and content extraction metrics for capacity planning and billing.

    Args:
        days: Number of days to analyze (1-365).
        db: Database session.

    Returns:
        Dict with organization_usage array containing:
            - organization_id: Organization UUID
            - organization_name: Organization name
            - plan: Subscription plan
            - unique_users: Number of unique users
            - request_count: Total requests
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - total_cost_usd: Total cost
            - total_content_mb: Total content extracted in MB
            - last_request_at: Last request timestamp
    """
    service = ParallelMonitoringService(db)
    organization_usage = await service.get_usage_by_organization(days=days)

    return success_response(
        status_code=HTTP_200_OK,
        message="Parallel.ai usage by organization retrieved successfully",
        data={"organization_usage": organization_usage},
    )


get_parallel_usage_by_organization._custom_errors = get_parallel_usage_by_organization_custom_errors
get_parallel_usage_by_organization._custom_success = (
    get_parallel_usage_by_organization_custom_success
)


@router.get(
    "/usage/by-project",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_usage_by_project_responses,
)
async def get_parallel_usage_by_project(
    organization_id: Optional[str] = Query(default=None, description="Filter by organization ID"),
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get Parallel.ai usage breakdown by project.

    Shows project-level usage for accurate cost attribution and
    helps identify which projects are consuming the most extraction resources.

    Args:
        organization_id: Optional organization filter.
        days: Number of days to analyze (1-365).
        db: Database session.

    Returns:
        Dict with project_usage array containing:
            - project_id: Project UUID
            - project_name: Project name
            - organization_id: Parent organization UUID
            - request_count: Total requests
            - successful_requests: Successful extractions
            - failed_requests: Failed extractions
            - total_cost_usd: Total cost
            - total_content_mb: Total content extracted in MB
    """

    org_id = UUID(organization_id) if organization_id else None

    service = ParallelMonitoringService(db)
    project_usage = await service.get_usage_by_project(
        organization_id=org_id,
        days=days,
    )

    return success_response(
        status_code=HTTP_200_OK,
        message="Parallel.ai usage by project retrieved successfully",
        data={"project_usage": project_usage},
    )


get_parallel_usage_by_project._custom_errors = get_parallel_usage_by_project_custom_errors
get_parallel_usage_by_project._custom_success = get_parallel_usage_by_project_custom_success


@router.get(
    "/usage/detailed-logs",
    dependencies=[Depends(require_superadmin)],
    responses=get_parallel_detailed_logs_responses,
)
async def get_parallel_detailed_logs(
    user_id: Optional[str] = Query(default=None, description="Filter by user ID"),
    organization_id: Optional[str] = Query(default=None, description="Filter by organization ID"),
    project_id: Optional[str] = Query(default=None, description="Filter by project ID"),
    days: int = Query(default=7, ge=1, le=90, description="Number of days to analyze"),
    limit: int = Query(default=100, ge=1, le=500, description="Number of logs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get detailed Parallel.ai request logs with full attribution.

    Provides paginated access to individual extraction requests with complete
    context including user, organization, project, costs, and performance metrics.

    Args:
        user_id: Optional user filter.
        organization_id: Optional organization filter.
        project_id: Optional project filter.
        days: Number of days to analyze (1-90).
        limit: Number of logs to return (1-500).
        offset: Pagination offset.
        db: Database session.

    Returns:
        Dict with:
            - total: Total matching logs
            - limit: Requested limit
            - offset: Current offset
            - logs: Array of detailed log entries with full attribution
    """

    uid = UUID(user_id) if user_id and user_id.strip() != "" else None
    org_id = UUID(organization_id) if organization_id and organization_id.strip() != "" else None
    proj_id = UUID(project_id) if project_id and project_id.strip() != "" else None

    service = ParallelMonitoringService(db)
    logs_data = await service.get_detailed_logs(
        user_id=uid,
        organization_id=org_id,
        project_id=proj_id,
        days=days,
        limit=limit,
        offset=offset,
    )

    return success_response(
        status_code=HTTP_200_OK,
        message="Detailed Parallel.ai logs retrieved successfully",
        data=logs_data,
    )


get_parallel_detailed_logs._custom_errors = get_parallel_detailed_logs_custom_errors
get_parallel_detailed_logs._custom_success = get_parallel_detailed_logs_custom_success
