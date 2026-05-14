"""Administrative remediation routes for campaign discovery failures."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.dependencies.auth import require_superadmin
from app.api.db.database import get_db
from app.api.modules.v1.campaigns.schemas.campaign_schema import (
    CampaignResetRequest,
    JurisdictionManualSourcesRequest,
)
from app.api.modules.v1.campaigns.service.campaign_remediation_service import (
    CampaignRemediationService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

from .docs.campaign_remediation_docs import (
    failed_discovery_nodes_custom_errors,
    failed_discovery_nodes_custom_success,
    failed_discovery_nodes_responses,
    manual_sources_custom_errors,
    manual_sources_custom_success,
    manual_sources_responses,
    retry_discovery_custom_errors,
    retry_discovery_custom_success,
    retry_discovery_responses,
)

router = APIRouter(tags=["Campaign Remediation"])


@router.get(
    "/campaigns/{campaign_id}/failed-discovery-nodes",
    status_code=status.HTTP_200_OK,
    responses=failed_discovery_nodes_responses,
)
async def get_failed_discovery_nodes(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Return jurisdictions in a campaign that still require manual sources."""
    service = CampaignRemediationService(db)
    result = await service.get_failed_discovery_nodes(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Failed discovery jurisdictions retrieved successfully.",
        data=result.model_dump(),
    )


get_failed_discovery_nodes._custom_errors = failed_discovery_nodes_custom_errors
get_failed_discovery_nodes._custom_success = failed_discovery_nodes_custom_success


@router.post(
    "/jurisdictions/{jurisdiction_id}/manual-sources",
    status_code=status.HTTP_200_OK,
    responses=manual_sources_responses,
)
async def add_manual_sources(
    jurisdiction_id: UUID,
    payload: JurisdictionManualSourcesRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Create manual sources for a jurisdiction and dispatch a catch-up scrape."""
    service = CampaignRemediationService(db)
    result = await service.add_manual_sources(jurisdiction_id, payload)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Manual sources created and jurisdiction dispatched successfully.",
        data=result.model_dump(),
    )


add_manual_sources._custom_errors = manual_sources_custom_errors
add_manual_sources._custom_success = manual_sources_custom_success


@router.post(
    "/jurisdictions/{jurisdiction_id}/retry-discovery",
    status_code=status.HTTP_200_OK,
    responses=retry_discovery_responses,
)
async def retry_discovery(
    jurisdiction_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Reset discovery status and rerun source discovery for one jurisdiction."""
    service = CampaignRemediationService(db)
    result = await service.retry_discovery(jurisdiction_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message="Jurisdiction discovery retry processed successfully.",
        data=result.model_dump(),
    )


retry_discovery._custom_errors = retry_discovery_custom_errors
retry_discovery._custom_success = retry_discovery_custom_success


@router.post(
    "/campaigns/{campaign_id}/reset-to-discovery",
    status_code=status.HTTP_200_OK,
)
async def reset_campaign_to_discovery(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Reset a stuck/failed campaign back to source discovery phase for recovery."""
    from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
        CampaignOrchestrationService,
    )

    service = CampaignOrchestrationService(db)
    await service.reset_to_discovery(campaign_id)
    return success_response(
        status_code=status.HTTP_200_OK,
        message=("Campaign reset to discovery phase successfully. You can now relaunch it."),
        data={"campaign_id": str(campaign_id), "status": "DISCOVERING_SOURCES"},
    )


@router.post(
    "/campaigns/{campaign_id}/reset",
    status_code=status.HTTP_200_OK,
)
async def reset_campaign(
    campaign_id: UUID,
    payload: CampaignResetRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Reset a campaign to a specific phase."""
    from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
        CampaignOrchestrationService,
    )

    service = CampaignOrchestrationService(db)
    await service.reset_to_status(campaign_id, payload.target_status)
    return success_response(
        status_code=status.HTTP_200_OK,
        message=(
            f"Campaign reset to {payload.target_status.value} successfully. "
            "You can now relaunch it."
        ),
        data={"campaign_id": str(campaign_id), "status": payload.target_status.value},
    )


@router.post(
    "/campaigns/{campaign_id}/smart-reset",
    status_code=status.HTTP_200_OK,
)
async def smart_reset_campaign(
    campaign_id: UUID,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Auto-detect where a campaign failed and reset to the correct phase."""
    from app.api.modules.v1.campaigns.service.campaign_orchestration_service import (
        CampaignOrchestrationService,
    )

    service = CampaignOrchestrationService(db)
    result = await service.smart_reset(campaign_id)
    target_status = result["target_status"]

    return success_response(
        status_code=status.HTTP_200_OK,
        message=(
            f"Campaign smartly reset to {target_status} automatically. You can now relaunch it."
        ),
        data={"campaign_id": str(campaign_id), "status": target_status},
    )
