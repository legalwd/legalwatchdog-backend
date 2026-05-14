from fastapi import APIRouter

from app.api.modules.v1.organization.routes.organization_route import org_router
from app.api.modules.v1.organization.routes.organization_route import router as base_router

router = APIRouter()

router.include_router(base_router)
router.include_router(org_router)


__all__ = ["base_router", "org_router"]
