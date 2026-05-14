from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.core.config import settings
from app.api.db.database import get_db
from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
from app.api.modules.v1.api_access.service.api_key_service import APIKeyService

from .docs.webhook_route_docs import (
    webhook_onboard_custom_errors,
    webhook_onboard_custom_success,
    webhook_onboard_responses,
)


class WebhookOnboardPayload(BaseModel):
    organization_id: str
    key_name: str
    scopes: List[str]
    generated_by: str


router = APIRouter(prefix="/webhooks", tags=["API Key Webhooks"])


@router.post(
    "/onboard",
    status_code=status.HTTP_201_CREATED,
    responses=webhook_onboard_responses,
)
async def webhook_onboard(
    payload: WebhookOnboardPayload,
    x_webhook_secret: str | None = Header(None, alias="X-WEBHOOK-SECRET"),
    db: AsyncSession = Depends(get_db),
):
    """Webhook endpoint to create API keys for integrations that can't receive emails.

    Security: requires X-WEBHOOK-SECRET header matching settings.SECRET_KEY.
    Returns the raw API key in response (only once) so the integrator can store it.
    """
    if x_webhook_secret is None or x_webhook_secret != settings.WEB_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    crud = APIKeyCRUD()
    service = APIKeyService(crud)

    try:
        api_key_obj, raw_key = await service.generate_and_hash_api_key(
            db=db,
            key_name=payload.key_name,
            organization_id=payload.organization_id,
            generated_by=payload.generated_by,
            scopes=payload.scopes,
            user_id=None,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return {"api_key": raw_key, "id": str(api_key_obj.id)}


webhook_onboard._custom_errors = webhook_onboard_custom_errors
webhook_onboard._custom_success = webhook_onboard_custom_success
