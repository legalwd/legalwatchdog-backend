import logging
from datetime import datetime, timezone

from app.api.db.database import CeleryAsyncSessionLocal
from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
from app.api.modules.v1.api_access.service.api_key_service import APIKeyService
from app.api.utils.celery_utils import syncify
from app.celery_app import celery_app

logger = logging.getLogger("app")

AsyncSessionLocal = CeleryAsyncSessionLocal


@celery_app.task(
    bind=True,
    name="app.api.modules.v1.api_access.service.rotation_tasks.rotate_due_keys",
    max_retries=3,
)
def rotate_due_keys(self):
    """Celery task entry — runs the async rotation helper via the shared syncifier."""
    try:
        syncify(_rotate_due_keys)()
    except Exception as exc:
        logger.exception("rotate_due_keys failed")
        raise self.retry(exc=exc, countdown=60)


async def _rotate_due_keys():
    """Find due API keys and rotate them using APIKeyService.api_key_rotation."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        crud = APIKeyCRUD()
        service = APIKeyService(crud)

        candidates = await service.find_keys_for_rotation(db)
        logger.info(f"Found {len(candidates)} API keys due for rotation at {now.isoformat()}")

        for key in candidates:
            try:
                new_raw = await service.api_key_rotation(db, key.id)
                if new_raw:
                    masked = f"{new_raw[:6]}...{new_raw[-4:]}" if len(new_raw) > 10 else new_raw
                    logger.info(
                        f"Rotated API key {key.id} (name={key.key_name}) "
                        f"— new key generated (raw mask={masked})"
                    )
                else:
                    logger.info(
                        f"Rotation skipped for API key {key.id}"
                        f"(name={key.key_name}) — no new key created"
                    )
            except Exception as exc:
                logger.exception(f"Failed to rotate API key {key.id}: {exc}")
