"""Route exports for scraping module."""

from fastapi import APIRouter

from app.api.modules.v1.scraping.routes import (
    change_acceptance_routes,
    output_routes,
    scrape_routes,
    source_discovery_route,
    source_routes,
)

router = APIRouter()

router.include_router(source_routes.router)
router.include_router(source_discovery_route.router)
router.include_router(scrape_routes.router)
router.include_router(output_routes.router)
router.include_router(change_acceptance_routes.router)

__all__ = ["router"]
