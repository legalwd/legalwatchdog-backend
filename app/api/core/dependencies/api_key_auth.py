from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.db.database import get_db


async def get_api_key_from_header(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Dependency to validate an API key passed in the X-API-Key header.

    Returns the APIKey ORM object when valid. Raises 401/403 on failure.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    from app.api.core.dependencies.send_api_key import hash_api_key
    from app.api.modules.v1.api_access.models.api_key_model import APIKey
    from app.api.modules.v1.api_access.service.api_key_crud import APIKeyCRUD
    from app.api.modules.v1.api_access.service.api_key_service import APIKeyService

    hashed = hash_api_key(x_api_key)

    stmt = select(APIKey).where(APIKey.hashed_key == hashed)
    result = await db.execute(stmt)
    api_key = result.scalars().first()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not getattr(api_key, "is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key inactive")

    expires_at = getattr(api_key, "expires_at", None)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key expired")

    try:
        crud = APIKeyCRUD()
        service = APIKeyService(crud)
        await service.last_used_update(db, api_key.id)
    except Exception:
        pass

    return api_key


def api_key_has_scope(api_key, required_scope: str) -> bool:
    """Check whether an APIKey instance contains a required scope.

    APIKey.scope is stored as a comma-separated string. A value of '*' means all scopes.
    """
    scope_val = getattr(api_key, "scope", None) or ""
    if scope_val.strip() == "*":
        return True
    scopes = [s.strip() for s in scope_val.split(",") if s.strip()]
    return required_scope in scopes
