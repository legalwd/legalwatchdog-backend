"""Superadmin organization management routes."""

import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse
from starlette.status import HTTP_200_OK

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.admin.routes.docs.organization_docs import (
    export_csv_custom_errors,
    export_csv_custom_success,
    export_csv_responses,
    export_json_custom_errors,
    export_json_custom_success,
    export_json_responses,
    list_organizations_custom_errors,
    list_organizations_custom_success,
    list_organizations_responses,
)
from app.api.modules.v1.admin.services.organization_management_service import (
    OrganizationManagementService,
    generate_csv_stream,
    generate_json_stream,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/superadmin/organizations", tags=["Superadmin Organizations"])


@router.get(
    "",
    responses=list_organizations_responses,
)
async def list_organizations(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    is_approved: Optional[bool] = Query(
        None,
        description="Filter by owner approval status (true/false)",
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Filter by organization active status (true/false)",
    ),
    company_size: Optional[str] = Query(
        None,
        description="Filter by company size: 1-50, 51-200, 201-500, 501-1000, 1000+",
    ),
    industry: Optional[str] = Query(
        None,
        description="Filter by industry (partial match)",
    ),
    search: Optional[str] = Query(
        None,
        description="Search in organization name, email, or owner name/email",
    ),
    created_from: Optional[datetime] = Query(
        None,
        description="Filter organizations created after this date (ISO format)",
    ),
    created_to: Optional[datetime] = Query(
        None,
        description="Filter organizations created before this date (ISO format)",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, updated_at, name, owner_email, owner_created_at",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    List all organizations with owner details.

    Returns paginated list of organizations with their owner information,
    including owner's approval status. Supports filtering by owner approval
    status, organization active status, company size, industry, and date range.
    Search across organization and owner name/email is also supported.
    """
    service = OrganizationManagementService(db)
    result = await service.list_organizations(
        page=page,
        limit=limit,
        is_approved=is_approved,
        is_active=is_active,
        company_size=company_size,
        industry=industry,
        search=search,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"Superadmin {current_user.email} listed organizations "
        f"(page={page}, limit={limit}, total={result['total']})"
    )

    response_data = result["data"]
    response_data["meta"] = result["meta"]

    return success_response(
        status_code=HTTP_200_OK,
        message="Organizations retrieved successfully",
        data=response_data,
    )


list_organizations._custom_success = list_organizations_custom_success
list_organizations._custom_errors = list_organizations_custom_errors


@router.get(
    "/export/json",
    responses=export_json_responses,
)
async def export_organizations_json(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_approved: Optional[bool] = Query(
        None,
        description="Filter by owner approval status (true/false)",
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Filter by organization active status (true/false)",
    ),
    company_size: Optional[str] = Query(
        None,
        description="Filter by company size: 1-50, 51-200, 201-500, 501-1000, 1000+",
    ),
    industry: Optional[str] = Query(
        None,
        description="Filter by industry (partial match)",
    ),
    search: Optional[str] = Query(
        None,
        description="Search in organization name, email, or owner name/email",
    ),
    created_from: Optional[datetime] = Query(
        None,
        description="Filter organizations created after this date (ISO format)",
    ),
    created_to: Optional[datetime] = Query(
        None,
        description="Filter organizations created before this date (ISO format)",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, updated_at, name, owner_email, owner_created_at",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    Export all organizations as JSON file.

    Returns a downloadable JSON file containing all organizations matching
    the filter criteria with their owner details. No pagination applied.
    """
    service = OrganizationManagementService(db)
    data = await service.get_export_data(
        is_approved=is_approved,
        is_active=is_active,
        company_size=company_size,
        industry=industry,
        search=search,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"Superadmin {current_user.email} exported organizations as JSON (count={len(data)})"
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"organizations_export_{timestamp}.json"

    headers = {"Content-Disposition": f"attachment; filename={filename}"}

    return StreamingResponse(
        generate_json_stream(data),
        media_type="application/json",
        headers=headers,
    )


export_organizations_json._custom_success = export_json_custom_success
export_organizations_json._custom_errors = export_json_custom_errors


@router.get(
    "/export/csv",
    responses=export_csv_responses,
)
async def export_organizations_csv(
    current_user: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_approved: Optional[bool] = Query(
        None,
        description="Filter by owner approval status (true/false)",
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Filter by organization active status (true/false)",
    ),
    company_size: Optional[str] = Query(
        None,
        description="Filter by company size: 1-50, 51-200, 201-500, 501-1000, 1000+",
    ),
    industry: Optional[str] = Query(
        None,
        description="Filter by industry (partial match)",
    ),
    search: Optional[str] = Query(
        None,
        description="Search in organization name, email, or owner name/email",
    ),
    created_from: Optional[datetime] = Query(
        None,
        description="Filter organizations created after this date (ISO format)",
    ),
    created_to: Optional[datetime] = Query(
        None,
        description="Filter organizations created before this date (ISO format)",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field: created_at, updated_at, name, owner_email, owner_created_at",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
):
    """
    Export all organizations as CSV file.

    Returns a downloadable CSV file containing all organizations matching
    the filter criteria with their owner details. Includes curated fields
    for easy analysis in spreadsheet applications. No pagination applied.
    """
    service = OrganizationManagementService(db)
    data = await service.get_export_data(
        is_approved=is_approved,
        is_active=is_active,
        company_size=company_size,
        industry=industry,
        search=search,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    logger.info(
        f"Superadmin {current_user.email} exported organizations as CSV (count={len(data)})"
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"organizations_export_{timestamp}.csv"

    headers = {"Content-Disposition": f"attachment; filename={filename}"}

    return StreamingResponse(
        generate_csv_stream(data),
        media_type="text/csv",
        headers=headers,
    )


export_organizations_csv._custom_success = export_csv_custom_success
export_organizations_csv._custom_errors = export_csv_custom_errors
