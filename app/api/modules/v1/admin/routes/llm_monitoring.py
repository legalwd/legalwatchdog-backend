"""Admin endpoints for LLM usage monitoring and analytics."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_200_OK

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.services.llm_monitoring_service import LLMMonitoringService
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.llm_monitoring_docs import (
    get_detailed_logs_custom_errors,
    get_detailed_logs_custom_success,
    get_detailed_logs_responses,
    get_llm_cost_breakdown_custom_errors,
    get_llm_cost_breakdown_custom_success,
    get_llm_cost_breakdown_responses,
    get_llm_provider_health_custom_errors,
    get_llm_provider_health_custom_success,
    get_llm_provider_health_responses,
    get_llm_usage_by_endpoint_custom_errors,
    get_llm_usage_by_endpoint_custom_success,
    get_llm_usage_by_endpoint_responses,
    get_llm_usage_by_model_custom_errors,
    get_llm_usage_by_model_custom_success,
    get_llm_usage_by_model_responses,
    get_llm_usage_by_provider_custom_errors,
    get_llm_usage_by_provider_custom_success,
    get_llm_usage_by_provider_responses,
    get_llm_usage_stats_custom_errors,
    get_llm_usage_stats_custom_success,
    get_llm_usage_stats_responses,
    get_llm_usage_trends_custom_errors,
    get_llm_usage_trends_custom_success,
    get_llm_usage_trends_responses,
    get_usage_by_organization_custom_errors,
    get_usage_by_organization_custom_success,
    get_usage_by_organization_responses,
    get_usage_by_project_custom_errors,
    get_usage_by_project_custom_success,
    get_usage_by_project_responses,
    get_usage_by_user_custom_errors,
    get_usage_by_user_custom_success,
    get_usage_by_user_responses,
    test_llm_connection_custom_errors,
    test_llm_connection_custom_success,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["Admin - LLM Monitoring"])


@router.get("/usage/stats", responses=get_llm_usage_stats_responses)
async def get_llm_usage_stats(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization ID"),
    provider: Optional[str] = Query(None, description="Filter by provider (openrouter, gemini)"),
    model: Optional[str] = Query(None, description="Filter by model"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get comprehensive LLM usage statistics.

    Returns aggregated metrics including:
    - Total requests and tokens consumed
    - Cost breakdown by provider/model
    - Success rates and error rates
    - Average latency metrics
    - Usage trends over time

    Examples:
        >>> GET /api/v1/admin/llm/usage/stats?start_date=2025-12-01&end_date=2025-12-15
    """
    service = LLMMonitoringService(db)
    stats = await service.get_usage_stats(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        organization_id=organization_id,
        provider=provider,
        model=model,
    )

    return success_response(
        data=stats,
        message="LLM usage statistics loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_llm_usage_stats._custom_errors = get_llm_usage_stats_custom_errors
get_llm_usage_stats._custom_success = get_llm_usage_stats_custom_success


@router.get("/usage/by-provider", responses=get_llm_usage_by_provider_responses)
async def get_usage_by_provider(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get usage breakdown by provider.

    Returns metrics grouped by provider (OpenRouter, Gemini) including:
    - Request counts and success rates
    - Token consumption per provider
    - Cost comparison
    - Performance metrics (latency, error rates)

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-provider?days=7
    """
    service = LLMMonitoringService(db)
    stats = await service.get_usage_by_provider(days=days, organization_id=organization_id)

    return success_response(
        data=stats,
        message=f"LLM provider usage for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_provider._custom_errors = get_llm_usage_by_provider_custom_errors
get_usage_by_provider._custom_success = get_llm_usage_by_provider_custom_success


@router.get("/usage/by-model", responses=get_llm_usage_by_model_responses)
async def get_usage_by_model(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get usage breakdown by model.

    Returns metrics grouped by model (Claude 3.5, Llama 3.1, Gemini 2.5, etc.) including:
    - Request counts per model
    - Token consumption and costs
    - Performance comparison
    - Usage patterns and trends

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-model?days=7&provider=openrouter
    """
    service = LLMMonitoringService(db)
    stats = await service.get_usage_by_model(
        days=days,
        provider=provider,
        organization_id=organization_id,
    )

    return success_response(
        data=stats,
        message=f"LLM model usage for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_model._custom_errors = get_llm_usage_by_model_custom_errors
get_usage_by_model._custom_success = get_llm_usage_by_model_custom_success


@router.get("/usage/by-endpoint", responses=get_llm_usage_by_endpoint_responses)
async def get_usage_by_endpoint(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get usage breakdown by API endpoint.

    Returns metrics grouped by endpoint showing:
    - Which endpoints use LLM most frequently
    - Cost per endpoint
    - Performance metrics per endpoint
    - Usage patterns

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-endpoint?days=7
    """
    service = LLMMonitoringService(db)
    stats = await service.get_usage_by_endpoint(days=days, organization_id=organization_id)

    return success_response(
        data=stats,
        message=f"LLM usage breakdown by endpoint for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_endpoint._custom_errors = get_llm_usage_by_endpoint_custom_errors
get_usage_by_endpoint._custom_success = get_llm_usage_by_endpoint_custom_success


@router.get("/usage/trends", responses=get_llm_usage_trends_responses)
async def get_usage_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    granularity: str = Query(
        "day", regex="^(hour|day|week|month)$", description="Aggregation granularity"
    ),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get usage trends over time.

    Returns time-series data for:
    - Request volume over time
    - Cost trends
    - Token consumption patterns
    - Success/error rates
    - Latency trends

    Examples:
        >>> GET /api/v1/admin/llm/usage/trends?days=30&granularity=day
    """
    service = LLMMonitoringService(db)
    trends = await service.get_usage_trends(
        days=days,
        granularity=granularity,
        organization_id=organization_id,
    )

    return success_response(
        data=trends,
        message=(
            f"LLM usage trends for the last {days} days (by {granularity}) loaded successfully."
        ),
        status_code=HTTP_200_OK,
    )


get_usage_trends._custom_errors = get_llm_usage_trends_custom_errors
get_usage_trends._custom_success = get_llm_usage_trends_custom_success


@router.get("/provider/health", responses=get_llm_provider_health_responses)
async def get_provider_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get health status of all LLM providers.

    Returns real-time health metrics including:
    - Provider availability status
    - Recent success/failure rates
    - Average latency per provider
    - Last successful request timestamp
    - Active alerts or issues

    Examples:
        >>> GET /api/v1/admin/llm/provider/health
    """
    service = LLMMonitoringService(db)
    health = await service.get_provider_health()

    return success_response(
        data={"providers": health},
        message="LLM provider health status loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_provider_health._custom_errors = get_llm_provider_health_custom_errors
get_provider_health._custom_success = get_llm_provider_health_custom_success


@router.get("/cost/breakdown", responses=get_llm_cost_breakdown_responses)
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    group_by: str = Query(
        "provider",
        regex="^(provider|model|endpoint|user|organization)$",
        description="Group costs by dimension",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get detailed cost breakdown.

    Returns cost analysis grouped by specified dimension:
    - Total costs and cost per request
    - Input/output token costs
    - Cost trends and projections
    - Top cost drivers

    Examples:
        >>> GET /api/v1/admin/llm/cost/breakdown?days=30&group_by=model
    """
    service = LLMMonitoringService(db)
    breakdown = await service.get_cost_breakdown(
        days=days,
        organization_id=organization_id,
        group_by=group_by,
    )

    return success_response(
        data=breakdown,
        message=f"LLM cost breakdown for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_cost_breakdown._custom_errors = get_llm_cost_breakdown_custom_errors
get_cost_breakdown._custom_success = get_llm_cost_breakdown_custom_success


@router.get("/usage/by-organization", responses=get_usage_by_organization_responses)
async def get_usage_by_organization(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get LLM usage breakdown by organization.

    Returns organization-level usage with:
    - Organization name and plan
    - Total cost and tokens
    - Number of unique users
    - Last request timestamp

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-organization?days=30
    """
    service = LLMMonitoringService(db)
    organizations = await service.get_usage_by_organization(days=days)

    return success_response(
        data={"organizations": organizations},
        message=f"Organization usage for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_organization._custom_errors = get_usage_by_organization_custom_errors
get_usage_by_organization._custom_success = get_usage_by_organization_custom_success


@router.get("/usage/by-user", responses=get_usage_by_user_responses)
async def get_usage_by_user(
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get LLM usage breakdown by user.

    Returns user-level usage with:
    - User name and email
    - Organization affiliation
    - Total cost and tokens
    - Request count
    - Last request timestamp

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-user?days=30
        >>> GET /api/v1/admin/llm/usage/by-user?organization_id=<uuid>&days=7
    """
    service = LLMMonitoringService(db)
    users = await service.get_usage_by_user(days=days, organization_id=organization_id)

    return success_response(
        data={"users": users},
        message=f"User usage for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_user._custom_errors = get_usage_by_user_custom_errors
get_usage_by_user._custom_success = get_usage_by_user_custom_success


@router.get("/usage/by-project", responses=get_usage_by_project_responses)
async def get_usage_by_project(
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get LLM usage breakdown by project.

    Returns project-level usage with:
    - Project name
    - Organization affiliation
    - Total cost and tokens
    - Request count

    Examples:
        >>> GET /api/v1/admin/llm/usage/by-project?days=30
    """
    service = LLMMonitoringService(db)
    projects = await service.get_usage_by_project(days=days, organization_id=organization_id)

    return success_response(
        data={"projects": projects},
        message=f"Project usage for the last {days} days loaded successfully.",
        status_code=HTTP_200_OK,
    )


get_usage_by_project._custom_errors = get_usage_by_project_custom_errors
get_usage_by_project._custom_success = get_usage_by_project_custom_success


@router.get("/usage/detailed-logs", responses=get_detailed_logs_responses)
async def get_detailed_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    project_id: Optional[UUID] = Query(None, description="Filter by project"),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    limit: int = Query(100, le=1000, description="Maximum logs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get detailed LLM request logs with full attribution.

    Returns paginated logs with:
    - Request details (model, tokens, cost, latency)
    - User details (name, email)
    - Organization details (name)
    - Project details (name)
    - Success/error status
    - Endpoint and IP address

    Examples:
        >>> GET /api/v1/admin/llm/usage/detailed-logs?days=7&limit=100
        >>> GET /api/v1/admin/llm/usage/detailed-logs?user_id=<uuid>&days=1
    """
    service = LLMMonitoringService(db)
    result = await service.get_detailed_logs(
        user_id=user_id,
        organization_id=organization_id,
        project_id=project_id,
        days=days,
        limit=limit,
        offset=offset,
    )

    return success_response(
        data=result,
        message=f"Retrieved {len(result['logs'])} detailed LLM request logs.",
        status_code=HTTP_200_OK,
    )


get_detailed_logs._custom_errors = get_detailed_logs_custom_errors
get_detailed_logs._custom_success = get_detailed_logs_custom_success


@router.post("/test-connection")
async def test_llm_connection(
    provider: str = Query("openrouter", regex="^(openrouter|gemini)$"),
    model: Optional[str] = Query(None, description="Specific model to test"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Test LLM provider connection.

    Sends a test request to verify connectivity and measure latency.

    Examples:
        >>> POST /api/v1/admin/llm/test-connection?provider=openrouter
    """
    service = LLMMonitoringService(db)
    result = await service.test_connection(
        provider=provider,
        model=model,
        user_id=current_user.id,
    )

    return success_response(
        data=result,
        message=f"Successfully connected to {provider}",
        status_code=HTTP_200_OK,
    )


test_llm_connection._custom_errors = test_llm_connection_custom_errors
test_llm_connection._custom_success = test_llm_connection_custom_success
