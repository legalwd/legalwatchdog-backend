"""
Change Acceptance Routes

API routes for accepting jurisdiction changes.
Following SoC principles - routes only handle HTTP, no business logic.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.api.core.dependencies.auth import get_current_user
from app.api.db.database import get_db
from app.api.modules.v1.scraping.routes.docs.change_acceptance_docs import (
    ACCEPT_CHANGE_DOCS,
    BULK_ACCEPT_CHANGES_DOCS,
)
from app.api.modules.v1.scraping.schemas.change_acceptance_schemas import (
    BulkAcceptChangesRequest,
    JurisdictionChangeResponse,
)
from app.api.modules.v1.scraping.service.change_acceptance_service import (
    ChangeAcceptanceService,
)
from app.api.modules.v1.users.models.users_model import User
from app.api.utils.response_payloads import success_response

router = APIRouter(tags=["Jurisdiction Changes"])


@router.post(
    "/jurisdictions/{jurisdiction_id}/changes/{change_id}/accept",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    **ACCEPT_CHANGE_DOCS,
)
async def accept_jurisdiction_change(
    jurisdiction_id: UUID,
    change_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept a jurisdiction change.

    Marks a specific change as accepted/dismissed and records who accepted it.
    Requires create_tickets permission.

    **Note**: Permission checks are handled in the service layer.
    Exceptions raised by the service will be caught by global exception handlers.
    """
    service = ChangeAcceptanceService(db)

    change = await service.accept_change(change_id=change_id, user_id=current_user.id)

    return success_response(
        status_code=status.HTTP_200_OK,
        message="Change accepted successfully",
        data=JurisdictionChangeResponse.model_validate(change).model_dump(),
    )


@router.post(
    "/changes/bulk-accept",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    **BULK_ACCEPT_CHANGES_DOCS,
)
async def bulk_accept_jurisdiction_changes(
    request: BulkAcceptChangesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept multiple jurisdiction changes at once.

    Accepts multiple changes in a single request after team discussion.
    Requires create_tickets permission.

    **Note**: If permission is denied for any change, all changes will be rolled back.
    Otherwise, individual failures are tracked and returned.
    """
    service = ChangeAcceptanceService(db)

    result = await service.bulk_accept_changes(
        change_ids=request.change_ids, user_id=current_user.id
    )

    result["accepted_changes"] = [
        JurisdictionChangeResponse.model_validate(change).model_dump()
        for change in result["accepted_changes"]
    ]

    return success_response(
        status_code=status.HTTP_200_OK,
        message=f"{result['accepted_count']} changes accepted successfully",
        data=result,
    )
