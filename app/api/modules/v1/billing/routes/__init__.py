from fastapi import APIRouter

from app.api.modules.v1.billing.routes.billing_routes import router as billing
from app.api.modules.v1.billing.routes.public_routes import router as public
from app.api.modules.v1.billing.routes.webhook_route import router as webhook

billing_router = APIRouter()

billing_router.include_router(billing)
billing_router.include_router(public)
billing_router.include_router(webhook)


__all__ = [
    "billing",
    "public",
    "webhook",
]
