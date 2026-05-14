def create_api_router():
    """Assemble the full API router tree.

    This is a factory function called at app startup (in main.py), NOT at
    import time.  Keeping the router assembly lazy prevents circular imports
    when celery_app.py imports settings from app.api.core.config.

    Returns:
        APIRouter: The fully assembled /api router with all v1 sub-routers.
    """
    from fastapi import APIRouter

    from app.api.modules.v1.router import router as v1_router

    router = APIRouter(prefix="/api")
    router.include_router(v1_router)
    return router
